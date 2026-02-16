"""Local filesystem storage for uploaded files — handles single and ZIP uploads."""

import logging
import mimetypes
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StoredFile:
    """Result of storing a single file on disk."""

    stored_path: str
    filename: str
    original_path: str
    file_size: int
    mime_type: str


class LocalFileStorage:
    """Infrastructure adapter for local file storage."""

    def __init__(self, upload_dir: str):
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    async def store_file(
        self, content: bytes, filename: str, original_path: str = ""
    ) -> StoredFile:
        """Store a single file and return its metadata."""
        # Generate a unique subdirectory so filenames don't collide
        file_id = str(uuid.uuid4())
        dest_dir = self._upload_dir / file_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / filename
        dest_path.write_bytes(content)

        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        return StoredFile(
            stored_path=str(dest_path),
            filename=filename,
            original_path=original_path or filename,
            file_size=len(content),
            mime_type=mime_type,
        )

    async def store_zip(self, content: bytes, zip_filename: str) -> list[StoredFile]:
        """Extract a ZIP archive and store each file individually."""
        import tempfile

        stored_files: list[StoredFile] = []

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for entry in zf.infolist():
                    # Skip directories and hidden files
                    if entry.is_dir() or entry.filename.startswith("__MACOSX"):
                        continue
                    if Path(entry.filename).name.startswith("."):
                        continue

                    file_content = zf.read(entry.filename)
                    just_filename = Path(entry.filename).name
                    original_path_in_zip = entry.filename

                    stored = await self.store_file(
                        content=file_content,
                        filename=just_filename,
                        original_path=f"{zip_filename}/{original_path_in_zip}",
                    )
                    stored_files.append(stored)
                    logger.info(
                        "Extracted from ZIP: %s (%d bytes)",
                        just_filename,
                        len(file_content),
                    )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return stored_files

    def get_file_path(self, stored_path: str) -> Path:
        """Return the absolute path to a stored file."""
        return Path(stored_path)

    def file_exists(self, stored_path: str) -> bool:
        """Check if a stored file exists."""
        return Path(stored_path).exists()

    async def delete_file(self, stored_path: str) -> bool:
        """Delete a stored file and its parent directory from disk.

        Each file is stored in its own UUID subdirectory, so removing
        the parent directory cleans up completely.
        Returns True if successfully deleted, False if not found.
        """
        file_path = Path(stored_path)
        if not file_path.exists():
            return False

        # Remove the parent UUID directory (contains only this file)
        parent = file_path.parent
        if parent != self._upload_dir:
            shutil.rmtree(parent, ignore_errors=True)
        else:
            file_path.unlink(missing_ok=True)

        logger.info("Deleted file from disk: %s", stored_path)
        return True
