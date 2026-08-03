# Phase 2 Correct Identity and Caching

## Canonical CV identity

CV identity is resolved in this order:

1. Candidate ID and CV ID: `cv_candidate_{candidate_id}_document_{cv_id}`.
2. CV ID only: `cv_document_{cv_id}`.
3. Candidate ID only: `cv_candidate_{candidate_id}`.
4. No supplied IDs: the legacy normalized filename key, `cv_{filename_stem}`.

Unsafe or truncated identifier components receive a SHA-256 suffix so different supplied IDs do not collapse during filename normalization.
Every result stores its canonical identity metadata and a `legacy_cv_keys` list.

`ResultRepository.resolve_result` continues resolving legacy filename keys when exactly one canonical result owns the alias.
If multiple ID-based records share a legacy filename alias, the alias is treated as ambiguous rather than selecting an unrelated candidate.

## Collision behavior

Before enqueue and again under the processing lock, the repository checks whether the canonical result key is already owned by another identity.

- The same supplied candidate/CV identity may upload changed content and is treated as a new version of that CV.
- A filename-only identity may reuse the existing result only when its content hash matches.
- Changed content under a filename-only identity returns HTTP 409 because the service cannot prove that it belongs to the same candidate.
- Explicit administrator reprocessing may refresh the existing filename-only record.
- A collision discovered by a racing background job does not write a failed marker over the existing candidate result.

Clients that need to replace content should supply stable candidate/CV IDs or use the existing reprocessing endpoint.

## Extracted Markdown cache

Extracted Markdown and its parser metadata are stored through `doc_cache_manager` using a SHA-256 cache key composed from:

- source document SHA-256;
- `EXTRACTION_PARSER_VERSION`;
- `EXTRACTION_SCHEMA_VERSION`.

The former `{cv_key}.md` lookup is no longer used.
Changed bytes, parser versions, or schema versions therefore cannot reuse stale Markdown.
Existing filename-based Markdown files are ignored and may be removed later through a separate operational cleanup.

## Match and LLM cache inputs

`MatchService` computes `SHA-256(cv_text UTF-8 bytes)` whenever a caller, including either raw-text API, does not provide `document_hash`.

Final match-result keys contain:

- document hash and candidate identity;
- complete vacancy-content version and vacancy IDs;
- optimized prompt version and Ollama model;
- parser/schema extraction version;
- `MATCHING_VERSION`.

Optimized LLM-generation keys contain the same version dimensions and the filtered vacancy IDs.
The generic Ollama extraction fallbacks use a prompt SHA-256 digest, prompt/model versions, and extraction version instead of sharing one key across unrelated prompts.

The complete matching vacancy version hashes the full canonical vacancy dictionaries, so requirement or scoring-input changes invalidate results even when vacancy IDs and titles stay unchanged.

## Compatibility

- Upload acknowledgement and polling response shapes are unchanged.
- Filename-only uploads retain their existing `cv_{stem}` keys.
- ID-bearing uploads now return their canonical ID-based key.
- Existing result files remain readable through direct keys and unambiguous legacy aliases.
- Cache-key method signatures remain backward compatible through optional added components.
