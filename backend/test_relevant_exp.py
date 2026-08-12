import pytest
from app.services.match_evaluators import _calculate_relevant_experience
from app.schemas.normalized_resume import NormalizedEmployment, NormalizedDateInterval, NormalizedResume, NormalizedStringField
from app.schemas.candidate_context import CandidateAnalysisContext
from app.services.job_taxonomy import DynamicTaxonomyService, TaxonomyClassification
from app.schemas.job_context import JobEvaluationContext
from app.services.scoring_engine import ScoringEngine
from unittest.mock import patch

def test_chef_and_python():
    resume = NormalizedResume(
        employment=[
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="Chef"),
                interval=NormalizedDateInterval(start_date="2009-01-01", end_date="2024-01-01"),
                responsibilities=["Cooking", "Menu"]
            ),
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="Python Developer"),
                interval=NormalizedDateInterval(start_date="2024-01-01", end_date="2024-03-01"),
                responsibilities=["Python", "Django"]
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Python Developer",
        "vac_family": "Software Engineering",
        "vac_tax_domain": "Information Technology",
        "required_skills": ["Python"]
    })
    
    def mock_resolve(title, **kwargs):
        if "Python" in title:
            return TaxonomyClassification(domain="Information Technology", job_family="Software Engineering")
        return TaxonomyClassification(domain="Hospitality", job_family="Restaurant")
        
    with patch.object(DynamicTaxonomyService, "resolve_vacancy_domain_and_family", side_effect=mock_resolve):
        rel_exp = _calculate_relevant_experience(context, job, ScoringEngine._extract_term_matches)
    
    # 2 months of Python is 0.16 years, approx 0.2
    assert rel_exp == 0.2

def test_restaurant_manager_to_it_manager():
    resume = NormalizedResume(
        employment=[
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="Restaurant Manager"),
                interval=NormalizedDateInterval(start_date="2010-01-01", end_date="2020-01-01"),
                responsibilities=["Food", "Menu", "Staff"]
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "IT Infrastructure Manager",
        "vac_family": "Information Technology",
        "vac_tax_domain": "Information Technology",
        "required_skills": ["Networking", "Linux"]
    })
    
    def mock_resolve(title, **kwargs):
        return TaxonomyClassification(domain="Hospitality", job_family="Restaurant")
        
    with patch.object(DynamicTaxonomyService, "resolve_vacancy_domain_and_family", side_effect=mock_resolve):
        rel_exp = _calculate_relevant_experience(context, job, ScoringEngine._extract_term_matches)
        
    assert rel_exp == 0.0

def test_generic_skill_overlap_only():
    resume = NormalizedResume(
        employment=[
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="Delivery Driver"),
                interval=NormalizedDateInterval(start_date="2018-01-01", end_date="2020-01-01"),
                responsibilities=["Communication", "Driving"]
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Software Engineer",
        "vac_family": "Software Engineering",
        "vac_tax_domain": "Information Technology",
        "required_skills": ["Python", "Communication"]
    })
    
    def mock_resolve(title, **kwargs):
        return TaxonomyClassification(domain="Logistics", job_family="Transportation")
        
    with patch.object(DynamicTaxonomyService, "resolve_vacancy_domain_and_family", side_effect=mock_resolve):
        rel_exp = _calculate_relevant_experience(context, job, ScoringEngine._extract_term_matches)
        
    assert rel_exp == 0.0

def test_overlapping_intervals():
    resume = NormalizedResume(
        employment=[
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="React Developer"),
                interval=NormalizedDateInterval(start_date="2018-01-01", end_date="2024-01-01"), # 6 years
                responsibilities=["React"]
            ),
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="Frontend Engineer"),
                interval=NormalizedDateInterval(start_date="2020-01-01", end_date="2024-01-01"), # 4 years overlapping
                responsibilities=["React"]
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "React Developer",
        "vac_family": "Frontend Engineering",
        "vac_tax_domain": "Information Technology",
        "required_skills": ["React"]
    })
    
    def mock_resolve(title, **kwargs):
        return TaxonomyClassification(domain="Information Technology", job_family="Frontend Engineering")
        
    with patch.object(DynamicTaxonomyService, "resolve_vacancy_domain_and_family", side_effect=mock_resolve):
        rel_exp = _calculate_relevant_experience(context, job, ScoringEngine._extract_term_matches)
        
    assert rel_exp == 6.0

def test_unparseable_dates():
    resume = NormalizedResume(
        employment=[
            NormalizedEmployment(
                job_title=NormalizedStringField(normalized_value="React Developer"),
                interval=NormalizedDateInterval(start_date=None, end_date=None), # Unparseable
                responsibilities=["React"]
            )
        ]
    )
    context = CandidateAnalysisContext.create(cv_text="", normalized_resume=resume)
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "React Developer",
        "vac_family": "Frontend Engineering",
        "vac_tax_domain": "Information Technology",
        "required_skills": ["React"]
    })
    
    def mock_resolve(title, **kwargs):
        return TaxonomyClassification(domain="Information Technology", job_family="Frontend Engineering")
        
    with patch.object(DynamicTaxonomyService, "resolve_vacancy_domain_and_family", side_effect=mock_resolve):
        rel_exp = _calculate_relevant_experience(context, job, ScoringEngine._extract_term_matches)
        
    assert rel_exp is None
