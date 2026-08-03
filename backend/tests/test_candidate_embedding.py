from unittest.mock import MagicMock, patch

import pytest

from app.core.cache import embedding_cache_manager
from app.core.config import settings
from app.services.cv_service import get_stable_cv_key, process_cv_file
from app.services.document_parser import MarkdownResult
from app.services.embedding_service import get_candidate_embedding


@pytest.mark.asyncio
async def test_candidate_side_embedding_end_to_end_with_external_systems_mocked(tmp_path):
    filename = "john_doe_flutter_dev.pdf"
    content = b"mock-pdf-content"
    markdown = (
        "John Doe\nSenior Flutter Developer\n"
        "Experience: 5 years in Flutter, Dart, iOS, Android, and REST APIs.\n"
        "Education: Bachelor of Science in Computer Science."
    )
    expected_cv_key = get_stable_cv_key(filename, candidate_id=9901, cv_id=4401)
    expected_embedding = [0.1] * 768
    match_analysis = MagicMock()
    match_analysis.model_dump.return_value = {"primary_department": "Engineering"}

    def cache_embedding(cv_key, embedding, _content_hash=None):
        embedding_cache_manager.set(f"{settings.EMBEDDING_MODEL}:{cv_key}", embedding)
        return True

    embedding_cache_manager.clear()
    with (
        patch.object(settings, "RESULTS_DIR", tmp_path),
        patch("app.core.database.pg_SessionLocal", None),
        patch(
            "app.services.cv_service.MarkdownGenerator.generate_with_timeout",
            return_value=MarkdownResult(markdown, page_count=1, is_scanned=False, ocr_applied=False),
        ),
        patch("app.services.cv_service.EmbeddingService.generate_embedding", return_value=expected_embedding),
        patch("app.services.embedding_service.save_candidate_embedding", side_effect=cache_embedding) as save_mock,
        patch("app.services.match_service.MatchService.analyze_single_cv", return_value=match_analysis),
        patch("app.services.similar_candidate_service.SimilarCandidateService.detect_similar_candidates", return_value=[]),
    ):
        result = await process_cv_file(
            filename=filename,
            content=content,
            candidate_id=9901,
            cv_id=4401,
            force_reprocess=True,
        )

        candidate_embedding = get_candidate_embedding(expected_cv_key)

    assert result["id"] == expected_cv_key
    assert candidate_embedding == expected_embedding
    assert len(candidate_embedding) == 768
    save_mock.assert_called_once()
