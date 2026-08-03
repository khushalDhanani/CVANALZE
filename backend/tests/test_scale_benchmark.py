import gc
import resource
import time
from typing import Any

import pytest

from app.core.profiler import PipelineProfiler
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.job_taxonomy import TaxonomyClassifier
from app.services.scoring_engine import ScoringEngine


def generate_synthetic_vacancies(count: int) -> list[dict[str, Any]]:
    """Generates realistic synthetic vacancy dataset across 8 departments."""
    departments = [
        (
            "CIS Team",
            "Software Engineer",
            ["Python", "FastAPI", "Docker", "PostgreSQL"],
        ),
        ("CIS Team", "DevOps Engineer", ["Kubernetes", "Docker", "Terraform", "CI/CD"]),
        ("Finance Team", "Accountant", ["Tally", "GST", "Excel", "Auditing"]),
        (
            "HR & IR Team",
            "HR Manager",
            ["Recruitment", "Payroll", "Employee Relations"],
        ),
        (
            "Maintenance Team - 1 (Ramesh Maurya)",
            "Mechanical Technician",
            ["HVAC", "Pumps", "Boilers", "Maintenance"],
        ),
        ("Sales Team", "Sales Executive", ["CRM", "B2B Sales", "Lead Generation"]),
        ("EHS Team", "Safety Officer", ["Safety Audit", "ISO 14001", "OSHA"]),
        (
            "Procurement Team",
            "Purchase Executive",
            ["Vendor Management", "SAP", "Negotiation"],
        ),
    ]

    vacancies: list[dict[str, Any]] = []
    for i in range(count):
        dept_name, title, skills = departments[i % len(departments)]
        vacancies.append(
            {
                "id": f"vac_{i + 1:05d}",
                "vacancy_id": i + 1,
                "title": f"{title} #{i + 1}",
                "department_name": dept_name,
                "required_skills": skills,
                "preferred_keywords": ["Teamwork", "Problem Solving"],
                "min_experience_years": float((i % 5) + 1),
                "max_experience_years": float((i % 5) + 6),
                "max_ctc": float(500000 + (i * 100)),
            }
        )
    return vacancies


def measure_memory_mb() -> float:
    """Returns max RSS memory footprint in Megabytes."""
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 2)


@pytest.mark.parametrize("vacancy_count", [100, 1000, 10000])
def test_scale_benchmark_throughput_and_memory(vacancy_count: int):
    gc.collect()
    mem_before = measure_memory_mb()

    # 1. Dataset Generation
    t0 = time.perf_counter()
    raw_vacancies = generate_synthetic_vacancies(vacancy_count)
    t_gen_ms = (time.perf_counter() - t0) * 1000.0

    # 2. Vacancy Pre-processing (JobEvaluationContext)
    t0 = time.perf_counter()
    job_contexts = JobEvaluationContext.from_jobs(raw_vacancies)
    t_vac_ctx_ms = (time.perf_counter() - t0) * 1000.0

    # Candidate CV
    cv_text = """
    ## Senior Python Developer
    Current Role: Senior Software Engineer
    Skills: Python, FastAPI, Docker, PostgreSQL, REST API, Microservices
    Experience: 6 years developing scalable enterprise cloud applications.
    Education: B.Tech in Computer Science
    """

    # 3. Candidate Context Creation
    t0 = time.perf_counter()
    cand_context = CandidateAnalysisContext.create(cv_text, candidate_experience=6.0)
    t_cand_ctx_ms = (time.perf_counter() - t0) * 1000.0

    # 4. Stage-0 Taxonomy Retrieval Filtering
    t0 = time.perf_counter()
    filtered_job_contexts = [j for j in job_contexts if TaxonomyClassifier.are_families_compatible(cand_context.cand_families, j.vac_family)]
    t_stage0_ms = (time.perf_counter() - t0) * 1000.0
    pruned_count = vacancy_count - len(filtered_job_contexts)
    prune_ratio_pct = round((pruned_count / vacancy_count) * 100.0, 1)

    # 5. Full Multi-Vacancy Scoring Pipeline
    profiler = PipelineProfiler()
    t0 = time.perf_counter()
    analysis = ScoringEngine.analyze_cv(
        cv_text,
        job_openings=filtered_job_contexts,
        profiler=profiler,
    )
    t_scoring_ms = (time.perf_counter() - t0) * 1000.0

    mem_after = measure_memory_mb()
    throughput_eval_per_sec = round(len(filtered_job_contexts) / (t_scoring_ms / 1000.0), 1) if t_scoring_ms > 0 else 0

    print("\n==================================================")
    print(f"SCALE BENCHMARK RESULTS (N = {vacancy_count} Vacancies)")
    print("==================================================")
    print(f"Dataset Gen Time       : {t_gen_ms:.2f} ms")
    print(f"Vacancy Context Time   : {t_vac_ctx_ms:.2f} ms ({t_vac_ctx_ms / vacancy_count:.3f} ms/vac)")
    print(f"Candidate Context Time : {t_cand_ctx_ms:.2f} ms")
    print(f"Stage-0 Prefilter Time : {t_stage0_ms:.2f} ms")
    print(f"Taxonomy Pruning Ratio : {pruned_count}/{vacancy_count} ({prune_ratio_pct}% pruned)")
    print(f"Post-Filter Vacancies  : {len(filtered_job_contexts)}")
    print(f"Scoring Engine Time    : {t_scoring_ms:.2f} ms ({t_scoring_ms / max(1, len(filtered_job_contexts)):.3f} ms/vac scored)")
    print(f"Scoring Throughput     : {throughput_eval_per_sec} evaluations/sec")
    print(f"Memory Footprint Delta : {mem_after - mem_before:.2f} MB (Peak RSS: {mem_after} MB)")
    print(f"Best Match Found       : {analysis.best_match.job_title} (Score: {analysis.best_match.score}%)")
    print("==================================================\n")

    assert analysis.best_match is not None
    assert analysis.best_match.score > 0.0
    assert len(analysis.suitable_openings) == len(filtered_job_contexts)
    # Ensure Stage-0 taxonomy pre-filter pruned non-IT vacancies (Finance, HR, Maintenance, etc.)
    assert prune_ratio_pct >= 60.0
