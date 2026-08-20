from __future__ import annotations

from unittest.mock import patch

from app.core.config import settings
from app.repositories.result import ResultRepository, cv_result_cache_manager
from app.services.upload_service import UploadService


def test_upload_lookup_reads_legacy_nested_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_DATA_ROOT", tmp_path)
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    legacy = tmp_path / "uploads" / "candidate_hash.pdf"
    legacy.parent.mkdir()
    legacy.write_bytes(b"legacy-source")

    found = UploadService.find_reprocessable_upload(
        storage_filename=legacy.name,
        original_filename="candidate.pdf",
        cv_key="candidate",
    )

    assert found == legacy


def test_result_lookup_reads_legacy_nested_results(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_DATA_ROOT", tmp_path)
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")
    legacy = tmp_path / "uploads" / "results" / "candidate.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"id":"candidate"}', encoding="utf-8")

    with (
        patch.object(cv_result_cache_manager, "get", return_value=None),
        patch("app.repositories.result.PostgresAppSession", side_effect=RuntimeError("offline")),
    ):
        result = ResultRepository.read_result_by_filename("candidate.json")

    assert result is not None
    assert result["id"] == "candidate"


def test_canonical_storage_candidates_precede_legacy_candidates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_DATA_ROOT", tmp_path)
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(settings, "RESULTS_DIR", tmp_path / "results")

    assert UploadService._read_storage_roots() == (tmp_path.resolve(), (tmp_path / "uploads").resolve())
    assert ResultRepository._disk_result_candidates("candidate") == (
        tmp_path / "results" / "candidate.json",
        tmp_path / "uploads" / "results" / "candidate.json",
    )
