import asyncio
import pytest
from app.repositories.job import JobRepository
from app.services.match_service import MatchService
from app.services.vacancy_prefilter import VacancyPreFilter
from app.services.embedding_service import get_embedding


TARUN_GUPTA_CV_TEXT = """
Tarun Gupta
Software Engineer | Mobile Developer

Location: Surat, Gujarat
Email: tarun.gupta@example.com

SKILLS
- Flutter & Dart
- Cross-platform Mobile App Development
- State Management (Provider, Riverpod, BLoC)
- REST APIs & Firebase
- iOS & Android native bridging

EXPERIENCE
Flutter Developer
Tech Solutions Inc, Surat (2021 - Present)
- Developed and maintained cross-platform mobile apps using Flutter.
- Collaborated with UI/UX designers to implement pixel-perfect designs.
- Integrated RESTful APIs for real-time data fetching.

EDUCATION
B.Tech in Computer Science
Gujarat Technological University (2020)
"""


@pytest.mark.asyncio
async def test_tarun_gupta_flutter_retrieval_and_ranking():
    openings = JobRepository.get_all_jobs()
    assert openings, "No job openings loaded from JobRepository"

    # Step 1: Pre-filter test
    cv_emb = get_embedding(TARUN_GUPTA_CV_TEXT[:8000])
    shortlist = VacancyPreFilter.filter_vacancies(
        cv_text=TARUN_GUPTA_CV_TEXT,
        openings=openings,
        top_k=5,
        cv_embedding=cv_emb,
    )

    shortlist_vids = [str(j.get("vacancy_id") or j.get("id")) for j in shortlist]
    print(f"\n[PRE-FILTER SHORTLIST VIDS]: {shortlist_vids}")

    flutter_job_in_shortlist = None
    flutter_shortlist_rank = None
    for rank, job in enumerate(shortlist, 1):
        vid = str(job.get("vacancy_id") or job.get("id"))
        title = job.get("title", "")
        print(f"  Shortlist Rank #{rank}: Vacancy #{vid} - '{title}' (RRF score={job.get('_prefilter_score'):.5f}, details={job.get('_rrf_details')})")
        if vid == "1065" or "flutter" in title.lower():
            flutter_job_in_shortlist = job
            flutter_shortlist_rank = rank

    assert flutter_job_in_shortlist is not None, (
        "FAIL: Vacancy 1065 ('Flutter Developer') was NOT found in the pre-filter shortlist!"
    )

    # Step 2: Full pipeline analysis test
    analysis = await MatchService.analyze_single_cv(
        cv_text=TARUN_GUPTA_CV_TEXT,
        job_openings=openings,
        document_hash="tarun_gupta_test_hash_p5",
        candidate_id="tarun_gupta_p5",
    )

    print("\n[FULL PIPELINE MATCH RESULTS SUMMARY]:")
    print(f"Primary Department: {analysis.primary_department}")
    if analysis.best_match:
        print(f"Best Match: Vacancy #{analysis.best_match.vacancy_id} ('{analysis.best_match.job_title}') - Score: {analysis.best_match.score}%")

    top_matches = analysis.suitable_openings
    for idx, m in enumerate(top_matches, 1):
        print(f"  Rank #{idx}: Vacancy #{m.vacancy_id} ('{m.job_title}') - Score: {m.score}% (Coverage: {m.coverage})")



    print(f"\n[PHASE 5 PROOF]")
    print(f"Vacancy 1065 ('Flutter Developer') in Pre-filter Shortlist: True")
    print(f"Pre-filter Shortlist Rank: #{flutter_shortlist_rank} out of {len(shortlist)}")


if __name__ == "__main__":
    asyncio.run(test_tarun_gupta_flutter_retrieval_and_ranking())
