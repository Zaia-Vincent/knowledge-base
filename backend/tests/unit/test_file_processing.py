"""Unit tests for Sprint 2: file upload, storage, text extraction, and file processing service."""

import zipfile
import tempfile
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest

from app.application.interfaces import FileRepository
from app.application.services.file_processing_service import FileProcessingService
from app.domain.entities import (
    ClassificationResult,
    ClassificationSignal,
    ProcessedFile,
    ProcessingStatus,
)
from app.infrastructure.extractors.multi_format_text_extractor import MultiFormatTextExtractor
from app.infrastructure.storage.local_file_storage import LocalFileStorage


# ── Fake Repository ──────────────────────────────────────────────────

class FakeFileRepository(FileRepository):
    """In-memory file repository for testing."""

    def __init__(self):
        self._files: dict[str, ProcessedFile] = {}

    async def get_by_id(self, file_id: str) -> ProcessedFile | None:
        return self._files.get(file_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ProcessedFile]:
        files = sorted(self._files.values(), key=lambda f: f.uploaded_at, reverse=True)
        return files[skip : skip + limit]

    async def create(self, pf: ProcessedFile) -> ProcessedFile:
        if not pf.id:
            pf.id = str(uuid.uuid4())
        self._files[pf.id] = pf
        return pf

    async def update(self, pf: ProcessedFile) -> ProcessedFile:
        self._files[pf.id] = pf
        return pf

    async def count(self) -> int:
        return len(self._files)

    async def delete(self, file_id: str) -> bool:
        if file_id in self._files:
            del self._files[file_id]
            return True
        return False


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_upload_dir(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    return str(upload_dir)


@pytest.fixture
def storage(tmp_upload_dir):
    return LocalFileStorage(upload_dir=tmp_upload_dir)


@pytest.fixture
def extractor():
    return MultiFormatTextExtractor()


@pytest.fixture
def repo():
    return FakeFileRepository()


@pytest.fixture
def service(repo, storage, extractor):
    return FileProcessingService(
        file_repository=repo,
        file_storage=storage,
        text_extractor=extractor,
    )


# ── LocalFileStorage Tests ──────────────────────────────────────────

class TestLocalFileStorage:
    async def test_store_file(self, storage):
        content = b"Hello, World!"
        result = await storage.store_file(content, "test.txt")

        assert result.filename == "test.txt"
        assert result.file_size == 13
        assert result.mime_type == "text/plain"
        assert Path(result.stored_path).exists()
        assert Path(result.stored_path).read_bytes() == content

    async def test_store_file_unique_paths(self, storage):
        """Two files with the same name should get unique storage paths."""
        r1 = await storage.store_file(b"file 1", "same.txt")
        r2 = await storage.store_file(b"file 2", "same.txt")

        assert r1.stored_path != r2.stored_path
        assert Path(r1.stored_path).read_bytes() == b"file 1"
        assert Path(r2.stored_path).read_bytes() == b"file 2"

    async def test_store_zip(self, storage):
        """ZIP extraction should return all non-hidden, non-directory entries."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("readme.txt", "This is a readme")
            zf.writestr("docs/manual.txt", "User manual content")
            zf.writestr("__MACOSX/.hidden", "Should be skipped")

        results = await storage.store_zip(zip_buffer.getvalue(), "archive.zip")

        filenames = {r.filename for r in results}
        assert filenames == {"readme.txt", "manual.txt"}
        assert len(results) == 2

        # Check stored content
        for r in results:
            assert Path(r.stored_path).exists()

    async def test_file_exists(self, storage):
        result = await storage.store_file(b"test", "exists.txt")
        assert storage.file_exists(result.stored_path)
        assert not storage.file_exists("/nonexistent/path.txt")


# ── MultiFormatTextExtractor Tests ───────────────────────────────────

class TestMultiFormatTextExtractor:
    async def test_extract_txt(self, extractor, tmp_path):
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Hello, this is a test document.")

        text = await extractor.extract_text(str(txt_file))
        assert "Hello, this is a test document." in text

    async def test_extract_csv(self, extractor, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25")

        text = await extractor.extract_text(str(csv_file))
        assert "Alice" in text
        assert "Bob" in text

    async def test_can_extract_supported_types(self, extractor):
        assert extractor.can_extract("text/plain")
        assert extractor.can_extract("application/pdf")
        assert extractor.can_extract("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert not extractor.can_extract("application/octet-stream")

    async def test_extract_unsupported_type_raises(self, extractor, tmp_path):
        file = tmp_path / "binary.bin"
        file.write_bytes(b"\x00\x01\x02\x03")

        with pytest.raises(ValueError, match="Unsupported"):
            await extractor.extract_text(str(file), "application/octet-stream")

    async def test_extract_file_not_found(self, extractor):
        with pytest.raises(FileNotFoundError):
            await extractor.extract_text("/nonexistent/file.txt")

    async def test_supported_types(self, extractor):
        types = extractor.supported_types()
        assert "text/plain" in types
        assert "application/pdf" in types
        assert len(types) >= 8  # At least 8 formats


# ── FileProcessingService Tests ──────────────────────────────────────

class TestFileProcessingService:
    async def test_upload_file(self, service, repo):
        content = b"Invoice number: INV-2025-001\nAmount: EUR 1.250,00"
        pf = await service.upload_file(content, "invoice.txt")

        assert pf.id is not None
        assert pf.filename == "invoice.txt"
        assert pf.file_size == len(content)
        assert pf.extracted_text is not None
        assert "Invoice number" in pf.extracted_text
        assert pf.status == ProcessingStatus.DONE

        # Verify it's in the repository
        stored = await repo.get_by_id(pf.id)
        assert stored is not None

    async def test_upload_zip(self, service, repo):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("doc1.txt", "First document")
            zf.writestr("doc2.txt", "Second document")

        results = await service.upload_zip(zip_buffer.getvalue(), "batch.zip")

        assert len(results) == 2
        count = await repo.count()
        assert count == 2

    async def test_list_files(self, service):
        await service.upload_file(b"file 1", "a.txt")
        await service.upload_file(b"file 2", "b.txt")

        files = await service.list_files()
        assert len(files) == 2

    async def test_get_file_by_id(self, service):
        pf = await service.upload_file(b"test content", "lookup.txt")
        found = await service.get_file(pf.id)

        assert found is not None
        assert found.filename == "lookup.txt"

    async def test_get_file_not_found(self, service):
        result = await service.get_file("nonexistent-id")
        assert result is None

    async def test_get_file_count(self, service):
        assert await service.get_file_count() == 0
        await service.upload_file(b"data", "count.txt")
        assert await service.get_file_count() == 1

    async def test_delete_file(self, service, repo, storage):
        """Deleting a file should remove it from both disk and database."""
        pf = await service.upload_file(b"delete me", "doomed.txt")
        assert Path(pf.stored_path).exists()
        assert await repo.count() == 1

        result = await service.delete_file(pf.id)
        assert result is True
        assert await repo.count() == 0
        assert await repo.get_by_id(pf.id) is None
        # File should be removed from disk
        assert not Path(pf.stored_path).exists()

    async def test_delete_file_not_found(self, service):
        """Deleting a nonexistent file returns False."""
        result = await service.delete_file("nonexistent-id")
        assert result is False
