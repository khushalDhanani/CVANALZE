import asyncio
import hashlib
import os
import re
import tempfile
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath

import filetype
from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import logger


class UploadValidationError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_upload", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class UploadTooLargeError(UploadValidationError):
    def __init__(self):
        max_mb = settings.MAX_FILE_SIZE_BYTES / (1024 * 1024)
        super().__init__(
            f"File size exceeds the configured limit of {max_mb:g} MB.",
            code="upload_too_large",
            status_code=413,
        )


@dataclass(frozen=True)
class NormalizedFilename:
    original_filename: str
    safe_filename: str
    extension: str


@dataclass(frozen=True)
class AcceptedUpload:
    original_filename: str
    safe_filename: str
    storage_filename: str
    extension: str
    declared_content_type: str | None
    detected_content_type: str
    content_hash: str
    content: bytes
    path: Path
    was_already_stored: bool


@dataclass(frozen=True)
class StoredUpload:
    safe_filename: str
    storage_filename: str
    detected_content_type: str
    content: bytes
    path: Path


class UploadService:
    _STORAGE_FILE_PATTERN = re.compile(r"^cv_[A-Za-z0-9_-]+_[0-9a-f]{64}\.(pdf|docx)$", re.IGNORECASE)
    _REQUIRED_DOCX_ENTRIES = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}

    @classmethod
    def normalize_filename(cls, filename: str | None) -> NormalizedFilename:
        if not filename or not filename.strip():
            raise UploadValidationError("Filename is required.", code="filename_required")

        basename = PurePosixPath(filename.replace("\\", "/")).name
        extension = Path(basename).suffix.lower().lstrip(".")
        if not extension:
            raise UploadValidationError("Filename must have a valid extension.", code="extension_required")
        if extension not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise UploadValidationError(
                f"Unsupported file extension '.{extension}'. Allowed formats: {allowed}.",
                code="unsupported_extension",
            )

        stem = Path(basename).stem
        ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_stem).strip("._-")
        stem_limit = max(1, settings.UPLOAD_FILENAME_MAX_CHARS - len(extension) - 1)
        safe_stem = safe_stem[:stem_limit].rstrip("._-") or "document"
        return NormalizedFilename(
            original_filename=filename,
            safe_filename=f"{safe_stem}.{extension}",
            extension=extension,
        )

    @classmethod
    async def accept_and_persist(cls, file: UploadFile, *, storage_key: str) -> AcceptedUpload:
        normalized = cls.normalize_filename(file.filename)
        content = await cls._read_bounded(file)
        detected_content_type = cls.validate_content(
            normalized.safe_filename,
            content,
            declared_content_type=file.content_type,
        )
        content_hash = hashlib.sha256(content).hexdigest()
        storage_filename = cls._storage_filename(storage_key, content_hash, normalized.extension)
        path, was_already_stored = await asyncio.to_thread(cls._persist_atomically, storage_filename, content)
        try:
            await asyncio.to_thread(cls.cleanup_expired)
        except OSError as exc:
            logger.warning(f"Could not apply raw-upload retention policy: {exc}")
        return AcceptedUpload(
            original_filename=normalized.original_filename,
            safe_filename=normalized.safe_filename,
            storage_filename=storage_filename,
            extension=normalized.extension,
            declared_content_type=file.content_type,
            detected_content_type=detected_content_type,
            content_hash=content_hash,
            content=content,
            path=path,
            was_already_stored=was_already_stored,
        )

    @classmethod
    async def _read_bounded(cls, file: UploadFile) -> bytes:
        chunks: list[bytes] = []
        total = 0
        chunk_size = max(1, settings.UPLOAD_READ_CHUNK_SIZE_BYTES)
        max_size = max(0, settings.MAX_FILE_SIZE_BYTES)

        while True:
            read_size = min(chunk_size, max_size - total + 1)
            chunk = await file.read(read_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                raise UploadTooLargeError()
            chunks.append(chunk)

        if total == 0:
            raise UploadValidationError("Uploaded file is empty (0 bytes).", code="empty_upload")
        return b"".join(chunks)

    @classmethod
    def validate_content(cls, filename: str, content: bytes, declared_content_type: str | None = None) -> str:
        normalized = cls.normalize_filename(filename)
        if not content:
            raise UploadValidationError("Uploaded file is empty (0 bytes).", code="empty_upload")
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            raise UploadTooLargeError()

        declared_mime = (declared_content_type or "").split(";", 1)[0].strip().lower()
        allowed_mimes = {mime.lower() for mime in settings.ALLOWED_MIME_TYPES.get(normalized.extension, [])}
        if declared_mime and declared_mime not in allowed_mimes:
            raise UploadValidationError(
                f"Declared MIME type '{declared_mime}' does not match a supported .{normalized.extension} upload.",
                code="mime_type_mismatch",
            )

        if normalized.extension == "pdf":
            cls._validate_pdf(content)
            return "application/pdf"

        cls._validate_docx(content)
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    @classmethod
    def _validate_pdf(cls, content: bytes) -> None:
        kind = filetype.guess(content)
        if not content[:1024].lstrip().startswith(b"%PDF-") or kind is None or kind.mime != "application/pdf":
            raise UploadValidationError(
                "Invalid PDF signature. The file content does not match its .pdf extension.",
                code="signature_mismatch",
            )

        import fitz

        document = None
        try:
            document = fitz.open(stream=content, filetype="pdf")
            if document.needs_pass:
                raise UploadValidationError("Password-protected PDFs are not supported.", code="encrypted_document")
            if document.page_count < 1:
                raise UploadValidationError("The PDF contains no pages.", code="invalid_document_structure")
            if document.page_count > settings.MAX_PDF_PAGES:
                raise UploadValidationError(
                    f"PDF page count exceeds the configured limit of {settings.MAX_PDF_PAGES}.",
                    code="pdf_page_limit_exceeded",
                )
            if document.xref_length() > settings.MAX_PDF_XREF_OBJECTS:
                raise UploadValidationError(
                    f"PDF resource count exceeds the configured limit of {settings.MAX_PDF_XREF_OBJECTS} objects.",
                    code="pdf_resource_limit_exceeded",
                )

            image_count = 0
            total_page_area = 0.0
            for page in document:
                total_page_area += max(0.0, page.rect.width) * max(0.0, page.rect.height)
                if total_page_area > settings.MAX_PDF_TOTAL_PAGE_AREA_POINTS:
                    raise UploadValidationError(
                        "PDF page dimensions exceed the configured aggregate resource limit.",
                        code="pdf_resource_limit_exceeded",
                    )
                image_count += len(page.get_images(full=True))
                if image_count > settings.MAX_PDF_IMAGES:
                    raise UploadValidationError(
                        f"PDF image count exceeds the configured limit of {settings.MAX_PDF_IMAGES}.",
                        code="pdf_resource_limit_exceeded",
                    )

            embedded_names = document.embfile_names() if hasattr(document, "embfile_names") else []
            if len(embedded_names) > settings.MAX_PDF_EMBEDDED_FILES:
                raise UploadValidationError(
                    f"PDF embedded-file count exceeds the configured limit of {settings.MAX_PDF_EMBEDDED_FILES}.",
                    code="pdf_embedded_file_limit_exceeded",
                )
        except UploadValidationError:
            raise
        except Exception as exc:
            raise UploadValidationError(
                "Invalid or corrupted PDF document structure.",
                code="invalid_document_structure",
            ) from exc
        finally:
            if document is not None:
                document.close()

    @classmethod
    def _validate_docx(cls, content: bytes) -> None:
        kind = filetype.guess(content)
        if kind is not None and kind.mime not in {
            "application/zip",
            "application/x-zip-compressed",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            raise UploadValidationError(
                "Invalid DOCX signature. The file content does not match its .docx extension.",
                code="signature_mismatch",
            )
        if not zipfile.is_zipfile(BytesIO(content)):
            raise UploadValidationError(
                "Invalid DOCX signature. A DOCX file must be a valid ZIP-based Office document.",
                code="signature_mismatch",
            )

        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > settings.MAX_DOCX_ENTRIES:
                    raise UploadValidationError(
                        f"DOCX entry count exceeds the configured limit of {settings.MAX_DOCX_ENTRIES}.",
                        code="docx_entry_limit_exceeded",
                    )

                names: set[str] = set()
                expanded_size = 0
                compressed_size = 0
                for entry in entries:
                    normalized_name = entry.filename.replace("\\", "/")
                    parts = PurePosixPath(normalized_name).parts
                    if normalized_name.startswith("/") or ".." in parts:
                        raise UploadValidationError(
                            "DOCX contains an unsafe archive entry path.",
                            code="unsafe_archive_entry",
                        )
                    if entry.flag_bits & 0x1:
                        raise UploadValidationError(
                            "Encrypted DOCX archive entries are not supported.",
                            code="encrypted_document",
                        )
                    unix_mode = (entry.external_attr >> 16) & 0o170000
                    if unix_mode == 0o120000:
                        raise UploadValidationError(
                            "DOCX symbolic-link archive entries are not supported.",
                            code="unsafe_archive_entry",
                        )
                    if normalized_name in names:
                        raise UploadValidationError(
                            "DOCX contains duplicate archive entries.",
                            code="invalid_document_structure",
                        )
                    names.add(normalized_name)
                    expanded_size += entry.file_size
                    compressed_size += entry.compress_size
                    if expanded_size > settings.MAX_DOCX_EXPANDED_SIZE_BYTES:
                        raise UploadValidationError(
                            "DOCX expanded size exceeds the configured limit.",
                            code="docx_expanded_size_exceeded",
                        )
                    if entry.file_size and entry.file_size / max(1, entry.compress_size) > settings.MAX_DOCX_COMPRESSION_RATIO:
                        raise UploadValidationError(
                            "DOCX compression ratio exceeds the configured limit.",
                            code="docx_compression_ratio_exceeded",
                        )

                total_ratio = expanded_size / max(1, compressed_size)
                if total_ratio > settings.MAX_DOCX_COMPRESSION_RATIO:
                    raise UploadValidationError(
                        "DOCX compression ratio exceeds the configured limit.",
                        code="docx_compression_ratio_exceeded",
                    )
                missing = cls._REQUIRED_DOCX_ENTRIES - names
                if missing:
                    raise UploadValidationError(
                        "Invalid DOCX document structure: required Office entries are missing.",
                        code="invalid_document_structure",
                    )
                if any(name.lower().endswith("vbaproject.bin") for name in names):
                    raise UploadValidationError(
                        "Macro-enabled Word documents are not supported.",
                        code="unsupported_active_content",
                    )

            import docx

            docx.Document(BytesIO(content))
        except UploadValidationError:
            raise
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            raise UploadValidationError(
                "Invalid or corrupted DOCX document structure.",
                code="invalid_document_structure",
            ) from exc
        except Exception as exc:
            raise UploadValidationError(
                "Invalid or corrupted DOCX document structure.",
                code="invalid_document_structure",
            ) from exc

    @classmethod
    def _storage_filename(cls, storage_key: str, content_hash: str, extension: str) -> str:
        safe_key = re.sub(r"[^A-Za-z0-9_-]+", "_", storage_key).strip("._-") or "cv"
        key_limit = max(1, min(settings.UPLOAD_FILENAME_MAX_CHARS, 253 - len(content_hash) - len(extension)))
        safe_key = safe_key[:key_limit].rstrip("._-") or "cv"
        return f"{safe_key}_{content_hash}.{extension}"

    @classmethod
    def _persist_atomically(cls, storage_filename: str, content: bytes) -> tuple[Path, bool]:
        uploads_dir = settings.UPLOADS_DIR.resolve()
        uploads_dir.mkdir(parents=True, exist_ok=True)
        target = cls._contained_path(storage_filename)
        was_already_stored = target.is_file()
        file_descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", suffix=".tmp", dir=uploads_dir)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        logger.info(f"Persisted validated raw upload as '{target.name}'.")
        return target, was_already_stored

    @classmethod
    def _contained_path(cls, filename: str) -> Path:
        basename = PurePosixPath(filename.replace("\\", "/")).name
        if basename != filename or not basename:
            raise UploadValidationError("Unsafe storage filename.", code="unsafe_filename")
        uploads_dir = settings.UPLOADS_DIR.resolve()
        candidate = (uploads_dir / basename).resolve()
        if candidate.parent != uploads_dir:
            raise UploadValidationError("Unsafe storage path.", code="unsafe_filename")
        return candidate

    @classmethod
    def remove_stored_upload(cls, storage_filename: str | None) -> None:
        if not storage_filename:
            return
        try:
            path = cls._contained_path(storage_filename)
            if path.is_file():
                path.unlink()
                logger.info(f"Removed raw upload '{path.name}'.")
        except (OSError, UploadValidationError) as exc:
            logger.warning(f"Could not remove raw upload '{storage_filename}': {exc}")

    @classmethod
    def cleanup_after_processing(cls, storage_filename: str | None, *, succeeded: bool) -> None:
        should_delete = settings.RAW_UPLOAD_DELETE_ON_SUCCESS if succeeded else settings.RAW_UPLOAD_DELETE_ON_FAILURE
        if should_delete:
            cls.remove_stored_upload(storage_filename)

    @classmethod
    def cleanup_expired(cls) -> int:
        retention_days = settings.RAW_UPLOAD_RETENTION_DAYS
        if retention_days < 0:
            return 0
        uploads_dir = settings.UPLOADS_DIR.resolve()
        if not uploads_dir.exists():
            return 0

        cutoff = time.time() - (retention_days * 86400)
        removed = 0
        for path in uploads_dir.iterdir():
            if not path.is_file() or not cls._STORAGE_FILE_PATTERN.fullmatch(path.name):
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError as exc:
                logger.warning(f"Could not apply raw-upload retention to '{path.name}': {exc}")
        if removed:
            logger.info(f"Removed {removed} expired raw upload(s).")
        return removed

    @classmethod
    def find_reprocessable_upload(
        cls,
        *,
        storage_filename: str | None,
        original_filename: str | None,
        cv_key: str,
    ) -> Path | None:
        candidates: list[str] = []
        if storage_filename:
            candidates.append(storage_filename)
        if original_filename:
            try:
                candidates.append(cls.normalize_filename(original_filename).safe_filename)
            except UploadValidationError:
                pass
        candidates.extend(f"{cv_key}.{extension}" for extension in sorted(settings.ALLOWED_EXTENSIONS))

        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                path = cls._contained_path(candidate)
            except UploadValidationError:
                continue
            if path.is_file() and path.suffix.lower().lstrip(".") in settings.ALLOWED_EXTENSIONS:
                return path
        return None

    @classmethod
    def load_reprocessable_upload(
        cls,
        *,
        storage_filename: str | None,
        original_filename: str | None,
        cv_key: str,
    ) -> StoredUpload | None:
        path = cls.find_reprocessable_upload(
            storage_filename=storage_filename,
            original_filename=original_filename,
            cv_key=cv_key,
        )
        if path is None:
            return None

        chunks: list[bytes] = []
        total = 0
        with path.open("rb") as raw_file:
            while True:
                read_size = min(
                    max(1, settings.UPLOAD_READ_CHUNK_SIZE_BYTES),
                    max(0, settings.MAX_FILE_SIZE_BYTES) - total + 1,
                )
                chunk = raw_file.read(read_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.MAX_FILE_SIZE_BYTES:
                    raise UploadTooLargeError()
                chunks.append(chunk)
        content = b"".join(chunks)

        try:
            normalized = cls.normalize_filename(original_filename)
            if normalized.extension != path.suffix.lower().lstrip("."):
                normalized = cls.normalize_filename(path.name)
        except UploadValidationError:
            normalized = cls.normalize_filename(path.name)
        detected_content_type = cls.validate_content(normalized.safe_filename, content)
        return StoredUpload(
            safe_filename=normalized.safe_filename,
            storage_filename=path.name,
            detected_content_type=detected_content_type,
            content=content,
            path=path,
        )
