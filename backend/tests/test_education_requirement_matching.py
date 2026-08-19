import pytest
from app.schemas.normalized_resume import NormalizedResume, NormalizedEducation, NormalizedStringField
from app.schemas.candidate_context import CandidateAnalysisContext
from app.services.match_evaluators import _education_requirement_matches
from app.services.scoring_engine import ScoringEngine

def test_btech_cs_vs_btech_mech():
    resume = NormalizedResume(
        education=[
            NormalizedEducation(
                degree=NormalizedStringField(normalized_value="B.Tech"),
                domain=NormalizedStringField(normalized_value="Mechanical Engineering")
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    status = _education_requirement_matches(context, "B.Tech Computer Science", ScoringEngine._extract_term_matches)
    assert status == "CONFLICT"

def test_bachelor_vs_diploma():
    resume = NormalizedResume(
        education=[
            NormalizedEducation(
                degree=NormalizedStringField(normalized_value="Diploma"),
                domain=NormalizedStringField(normalized_value="Computer Science")
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    status = _education_requirement_matches(context, "Bachelor Computer Science", ScoringEngine._extract_term_matches)
    assert status == "MISSING"

def test_word_computer_in_history():
    resume = NormalizedResume()
    context = CandidateAnalysisContext.create(cv_text="Used a computer everyday", normalized_resume=resume)
    status = _education_requirement_matches(context, "B.Tech Computer Science", ScoringEngine._extract_term_matches)
    assert status == "UNKNOWN"
