from app.schemas.cv import CVUploadResponse


def test_completed_cv_response_accepts_analysis_without_a_primary_department():
    response = CVUploadResponse(
        id="cv_no_department",
        scan_id="cv_no_department",
        filename="candidate.pdf",
        characters=0,
        page_count=1,
        is_scanned=False,
        ocr_applied=False,
        text="",
        markdown="",
        match_analysis={
            "primary_department": None,
            "suitable_openings": [],
        },
    )

    assert response.match_analysis.primary_department is None
