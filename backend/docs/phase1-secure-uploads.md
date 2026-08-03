# Phase 1 Secure Uploads

## Scope and compatibility

`POST /api/cv/upload` and `POST /api/match/upload` retain their existing HTTP 200 acknowledgement shape and deterministic `cv_key` behavior.
Both routes now delegate file acceptance to `UploadService` and accept PDF and DOCX only.

Legacy `.doc` is unsupported because the deployed image has no maintained conversion sandbox and binary Word parsing would add a separate attack surface.
Plain-text `.txt` is unsupported because it has no dependable file signature.
The Docker image therefore intentionally includes no `antiword` or `catdoc` packages.

## Acceptance sequence

No upload is written to disk or enqueued until all of these checks pass:

1. Extract the basename from both POSIX and Windows-style client paths.
2. Normalize the stem to ASCII and restrict it to letters, digits, `_`, and `-`.
3. Confirm that the extension is `pdf` or `docx`.
4. Read the request in configurable bounded chunks and stop with HTTP 413 as soon as `MAX_FILE_SIZE_BYTES` is exceeded.
5. Validate the declared MIME type against the extension.
6. Detect the file signature and validate its document structure.
7. Apply PDF or expanded-DOCX resource limits.
8. Atomically persist the accepted bytes under a server-generated content-addressed name.
9. Enqueue processing with the normalized display filename and generated storage filename.

Upload validation errors preserve the existing FastAPI `{"detail": "..."}` compatibility envelope. Oversized uploads return HTTP 413; other invalid uploads return HTTP 400.

## Document resource limits

All limits use `app.core.config.settings` and can be overridden with environment variables.

| Setting | Default | Purpose |
|---|---:|---|
| `MAX_FILE_SIZE_BYTES` | 15 MiB | Maximum compressed request-file size |
| `UPLOAD_READ_CHUNK_SIZE_BYTES` | 1 MiB | Maximum request read size per iteration |
| `MAX_DOCX_EXPANDED_SIZE_BYTES` | 75 MiB | Maximum combined uncompressed ZIP entry size |
| `MAX_DOCX_ENTRIES` | 2,000 | Maximum ZIP entry count |
| `MAX_DOCX_COMPRESSION_RATIO` | 200 | Maximum individual and aggregate expansion ratio |
| `MAX_PDF_PAGES` | 100 | Maximum pages |
| `MAX_PDF_XREF_OBJECTS` | 10,000 | Maximum PDF cross-reference objects |
| `MAX_PDF_IMAGES` | 1,000 | Maximum images across all pages |
| `MAX_PDF_TOTAL_PAGE_AREA_POINTS` | 500,000,000 | Maximum aggregate page area in PDF points squared |
| `MAX_PDF_EMBEDDED_FILES` | 0 | Maximum embedded attachments |

DOCX validation also rejects encrypted entries, unsafe archive paths, symbolic links, macro payloads, and archives missing required Office document entries.
PDF validation rejects encrypted, empty, corrupt, signature-mismatched, and over-limit documents.

## Persistence and filenames

Validated raw files are written to a temporary file inside `UPLOADS_DIR`, flushed, and atomically moved into place. Storage names use this form:

```text
{cv_key}_{sha256}.{extension}
```

Client filenames are retained only as normalized result metadata. Repeated identical uploads for the same CV key converge on the same raw-file path.

## Retention, cleanup, and reprocessing

- `RAW_UPLOAD_RETENTION_DAYS=30` removes generated raw files older than 30 days opportunistically after a new accepted upload. A negative value disables age cleanup.
- `RAW_UPLOAD_DELETE_ON_SUCCESS=false` retains successful source files by default so they can be reprocessed.
- `RAW_UPLOAD_DELETE_ON_FAILURE=false` retains failed source files by default for diagnosis and retry. Either flag can enable immediate cleanup for stricter data-minimization policies.
- Validation failures never create a raw file. A failure while registering the background task removes the newly persisted raw file.
- Candidate reprocessing first resolves and revalidates the retained source. Only after that succeeds are caches and the old result invalidated.
- If the retained source is missing or invalid, reprocessing returns HTTP 409 and preserves the existing result. Extracted text is never converted into a synthetic replacement document.

Age-based retention intentionally targets only generated content-addressed filenames.
Legacy manually placed PDF/DOCX files are left untouched and remain eligible for the compatibility lookup used by reprocessing.

## Remaining boundary

Structural validation is not malware scanning or content disarm and reconstruction.
Deployments handling untrusted public uploads should add an isolated malware-scanning stage before processing and enforce equivalent request-body limits at the reverse proxy.
