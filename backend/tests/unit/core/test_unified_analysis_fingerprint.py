from __future__ import annotations

from app.core.cache import CacheKey
from app.schemas.analysis_fingerprint import AnalysisFingerprint


def test_analysis_fingerprint_creation_and_digest() -> None:
    """Workstream 5.2: AnalysisFingerprint builds single identity from all 11 version/revision inputs."""
    fp = AnalysisFingerprint.create(
        source_document_hash="doc_hash_abc123",
        candidate_revision="rev_1",
        vacancy_revision="vac_rev_1",
        policy_snapshot_id="snap_1.1.0_1b5d9c5a",
    )

    assert fp.source_document_hash == "doc_hash_abc123"
    assert fp.candidate_revision == "rev_1"
    assert fp.vacancy_revision == "vac_rev_1"
    assert fp.parser_version == "v2.1-docling"
    assert fp.normalization_version == "v1.4-taxonomy"
    assert fp.taxonomy_version == "v3.0-enterprise"
    assert fp.policy_snapshot_id == "snap_1.1.0_1b5d9c5a"
    assert fp.embedding_model_id == "nomic-embed-text"
    assert fp.generation_model_id == "gemma2:9b-instruct-q4_K_M"
    assert fp.prompt_version == "4.0"
    assert fp.schema_version == "v1.0"

    digest = fp.compute_fingerprint_digest()
    assert isinstance(digest, str)
    assert len(digest) == 64


def test_cache_key_from_fingerprint() -> None:
    """Workstream 5.2: CacheKey.from_fingerprint generates unique, version-safe cache keys."""
    fp = AnalysisFingerprint.create(
        source_document_hash="doc_hash_xyz987",
        policy_snapshot_id="snap_1.1.0_1b5d9c5a",
    )

    key = CacheKey.from_fingerprint(fp, domain_prefix="match")
    key_str = key.to_key()

    assert key_str != ""
    assert fp.compute_fingerprint_digest() in key_str or key_str.startswith("doc_")


def test_natural_version_invalidation() -> None:
    """Workstream 5.2: Modifying ANY component naturally invalidates fingerprint without blanket purges."""
    base_fp = AnalysisFingerprint.create(
        source_document_hash="doc_hash_invalidation_test",
        policy_snapshot_id="snap_v1",
    )
    base_digest = base_fp.compute_fingerprint_digest()

    # 1. Document hash change -> different digest
    fp_doc = base_fp.model_copy(update={"source_document_hash": "doc_hash_changed"})
    assert fp_doc.compute_fingerprint_digest() != base_digest

    # 2. Policy snapshot ID change -> different digest
    fp_pol = base_fp.model_copy(update={"policy_snapshot_id": "snap_v2"})
    assert fp_pol.compute_fingerprint_digest() != base_digest

    # 3. Taxonomy version change -> different digest
    fp_tax = base_fp.model_copy(update={"taxonomy_version": "v4.0-enterprise"})
    assert fp_tax.compute_fingerprint_digest() != base_digest

    # 4. Prompt version change -> different digest
    fp_prm = base_fp.model_copy(update={"prompt_version": "5.0"})
    assert fp_prm.compute_fingerprint_digest() != base_digest

    # 5. Embedding model change -> different digest
    fp_emb = base_fp.model_copy(update={"embedding_model_id": "bge-large-en-v1.5"})
    assert fp_emb.compute_fingerprint_digest() != base_digest
