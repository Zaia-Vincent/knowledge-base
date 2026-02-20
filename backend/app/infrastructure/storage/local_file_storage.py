"""Local filesystem storage for uploaded files — handles single and ZIP uploads.

Storage layout:
    <upload_dir>/files/<stem>_<YYYYMMDD_HHmmss>.<ext>        — uploaded files
    <upload_dir>/websites/<domain>/<path_slug>_<YYYYMMDD_HHmmss>.png — website captures
"""

import logging
import mimetypes
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class StoredFile:
    """Result of storing a single file on disk."""

    stored_path: str
    filename: str
    original_path: str
    file_size: int
    mime_type: str


def _datetime_stamp() -> str:
    """Return a UTC datetime stamp suitable for filenames: YYYYMMDD_HHmmss."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sanitise(name: str, max_len: int = 80) -> str:
    """Replace non-word characters with underscores and truncate."""
    return re.sub(r"[^\w\-]", "_", name)[:max_len].strip("_") or "unnamed"


class LocalFileStorage:
    """Infrastructure adapter for local file storage."""

    def __init__(self, upload_dir: str):
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    # ── File Storage ────────────────────────────────────────────────

    async def store_file(
        self, content: bytes, filename: str, original_path: str = ""
    ) -> StoredFile:
        """Store an uploaded file in ``<upload_dir>/files/``.

        The filename is augmented with a UTC datetime stamp to avoid
        collisions: ``<stem>_<YYYYMMDD_HHmmss>.<ext>``.
        """
        files_dir = self._upload_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(filename).stem
        suffix = Path(filename).suffix  # includes the dot
        stamped_name = f"{_sanitise(stem)}_{_datetime_stamp()}{suffix}"

        dest_path = files_dir / stamped_name
        dest_path.write_bytes(content)

        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        logger.info("Stored file: %s (%d bytes)", dest_path, len(content))

        return StoredFile(
            stored_path=str(dest_path),
            filename=stamped_name,
            original_path=original_path or filename,
            file_size=len(content),
            mime_type=mime_type,
        )

    # ── Website Capture Storage ─────────────────────────────────────

    async def store_website_capture(
        self, content: bytes, url: str, title: str | None = None
    ) -> StoredFile:
        """Store a website screenshot in ``<upload_dir>/websites/<domain>/<slug>_<stamp>.png``.

        The domain is extracted from the URL; the path is slugified into a
        filesystem-friendly name.
        """
        parsed = urlparse(url)
        domain = _sanitise(parsed.netloc or "unknown_domain")

        # Build a slug from the URL path (e.g. /products/overview → products_overview)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if path_parts:
            path_slug = _sanitise("_".join(path_parts))
        else:
            path_slug = _sanitise(title or "index")

        domain_dir = self._upload_dir / "websites" / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        stamped_name = f"{path_slug}_{_datetime_stamp()}.png"
        dest_path = domain_dir / stamped_name

        dest_path.write_bytes(content)

        logger.info("Stored website capture: %s (%d bytes)", dest_path, len(content))

        return StoredFile(
            stored_path=str(dest_path),
            filename=stamped_name,
            original_path=url,
            file_size=len(content),
            mime_type="image/png",
        )

    # ── ZIP Handling ────────────────────────────────────────────────

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

    # ── Utilities ───────────────────────────────────────────────────

    def get_file_path(self, stored_path: str) -> Path:
        """Return the absolute path to a stored file."""
        return Path(stored_path)

    def file_exists(self, stored_path: str) -> bool:
        """Check if a stored file exists."""
        return Path(stored_path).exists()

    async def delete_file(self, stored_path: str) -> bool:
        """Delete a stored file from disk.

        Returns True if successfully deleted, False if not found.
        Removes the file directly; empty parent directories are
        *not* pruned to keep the domain-folder structure intact.
        """
        file_path = Path(stored_path)
        if not file_path.exists():
            return False

        file_path.unlink(missing_ok=True)
        logger.info("Deleted file from disk: %s", stored_path)
        return True
