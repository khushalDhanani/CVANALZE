import asyncio

import fitz  # PyMuPDF
import pytest
from sqlalchemy import text

from app.core.database import pg_engine
from app.services.cv_service import get_stable_cv_key, process_cv_file
from app.services.embedding_service import get_candidate_embedding


def create_sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    text_content = (
        "John Doe\n"
        "Senior Flutter & Mobile Developer\n"
        "Experience: 5 years in Flutter, Dart, iOS, Android, REST APIs, and State Management (Bloc, Provider).\n"
        "Education: Bachelor of Science in Computer Science."
    )
    page.insert_text((50, 50), text_content)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_candidate_side_embedding_end_to_end():
    filename = "john_doe_flutter_dev.pdf"
    content = create_sample_pdf_bytes()

    # Process CV end-to-end
    result = await process_cv_file(
        filename=filename,
        content=content,
        candidate_id=9901,
        cv_id=4401,
        force_reprocess=True,
    )

    expected_cv_key = get_stable_cv_key(filename, candidate_id=9901, cv_id=4401)
    assert result["id"] == expected_cv_key

    # Retrieve candidate embedding via get_candidate_embedding helper
    candidate_emb = get_candidate_embedding(expected_cv_key)
    assert candidate_emb is not None, f"Candidate embedding for '{expected_cv_key}' was not found"
    assert len(candidate_emb) == 768, f"Expected 768 dimensions, got {len(candidate_emb)}"

    # Direct PostgreSQL verification query
    with pg_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT cv_key, embedding_model_version, content_hash "
                "FROM candidate_embeddings WHERE cv_key = :cv_key"
            ),
            {"cv_key": expected_cv_key},
        ).fetchone()

    assert row is not None, f"No row found in candidate_embeddings table for '{expected_cv_key}'"
    print("\n[PHASE 4 PROOF]")
    print(f"Processed CV Key: {expected_cv_key}")
    print(f"Embedding Vector Retrievable: True (Dimensions: {len(candidate_emb)})")
    print(f"PostgreSQL Candidate Record: cv_key={row[0]}, model={row[1]}")


if __name__ == "__main__":
    asyncio.run(test_candidate_side_embedding_end_to_end())
