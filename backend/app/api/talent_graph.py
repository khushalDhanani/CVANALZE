from typing import Any

from fastapi import APIRouter

from app.services.talent_graph_service import TalentKnowledgeGraphService

router = APIRouter(prefix="/talent-graph", tags=["Talent Knowledge Graph"])


@router.get("/candidate/{candidate_id}", response_model=dict[str, Any])
def get_candidate_360_graph(candidate_id: str) -> dict[str, Any]:
    """
    Candidate 360 Graph API.
    Returns candidate node graph, skills network, work experience, matched vacancies,
    and semantically similar candidate profiles (discovered via embeddings).
    """
    return TalentKnowledgeGraphService.get_candidate_360_graph(candidate_id)


@router.get("/vacancy/{vacancy_id}", response_model=dict[str, Any])
def get_vacancy_360_graph(vacancy_id: str) -> dict[str, Any]:
    """
    Vacancy 360 Graph API.
    Returns vacancy node graph, department node, required skills, top candidate matches,
    and semantically similar vacancy openings.
    """
    return TalentKnowledgeGraphService.get_vacancy_360_graph(vacancy_id)


@router.get("/skill/{skill_name}", response_model=dict[str, Any])
def get_skill_intelligence_graph(skill_name: str) -> dict[str, Any]:
    """
    Skill Intelligence Graph API.
    Returns skill node network, semantically equivalent skills, candidate supply pool,
    and vacancy market demand.
    """
    return TalentKnowledgeGraphService.get_skill_intelligence_graph(skill_name)


@router.get("/analytics", response_model=dict[str, Any])
def get_recruitment_analytics_graph() -> dict[str, Any]:
    """
    Recruitment Analytics Graph API.
    Returns global Talent Knowledge Graph metrics: node/edge counts, skill frequencies,
    and department distributions.
    """
    return TalentKnowledgeGraphService.get_recruitment_analytics_graph()
