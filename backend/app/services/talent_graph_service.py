from __future__ import annotations
from typing import Any

from app.repositories.job import JobRepository
from app.repositories.result import ResultRepository
from app.services.domain_embedding_service import DomainEmbeddingService


class TalentKnowledgeGraphService:
    """
    Enterprise Talent Knowledge Graph Service.
    Links Candidates, Skills, Projects, Companies, Vacancies, Certifications, Departments,
    Technologies, and Industries.
    Embeddings are used strictly for relationship discovery (SEMANTICALLY_SIMILAR edges)
    while deterministic business logic remains the source of truth for match scores.
    """

    @classmethod
    def get_candidate_360_graph(cls, candidate_id: str) -> dict[str, Any]:
        cid = candidate_id.strip()
        result_filename = f"{cid}.json" if not cid.endswith(".json") else cid
        cv_key = result_filename.removesuffix(".json")

        r = ResultRepository.read_result_by_filename(result_filename)
        if not r:
            matches = ResultRepository.find_results_by_scan_id(cv_key)
            if matches:
                r = ResultRepository.read_result(matches[0])

        if not r or not isinstance(r, dict):
            return {"nodes": [], "edges": [], "candidate_summary": None}

        raw_match = r.get("match_analysis")
        match_analysis = raw_match if isinstance(raw_match, dict) else {}
        best_match = match_analysis.get("best_match") or {}

        resume_json = r.get("resume_json") or {}
        contact_info = resume_json.get("contact_info") or {}
        extracted_name = contact_info.get("name") or contact_info.get("full_name") or cv_key

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        cand_node_id = f"candidate:{cv_key}"
        nodes.append(
            {
                "id": cand_node_id,
                "type": "Candidate",
                "label": extracted_name,
                "properties": {
                    "email": contact_info.get("email"),
                    "phone": contact_info.get("phone"),
                    "primary_department": match_analysis.get("primary_department"),
                    "experience_years": r.get("quality_metrics", {}).get("experience_years"),
                },
            }
        )

        # 1. Skills Nodes & HAS_SKILL Edges
        skills = resume_json.get("skills") or best_match.get("matched_skills") or []
        for skill in skills[:15]:
            if not skill or not isinstance(skill, str):
                continue
            clean_skill = skill.strip()
            skill_node_id = f"skill:{clean_skill.lower()}"

            nodes.append(
                {
                    "id": skill_node_id,
                    "type": "Skill",
                    "label": clean_skill,
                    "properties": {"category": "technical"},
                }
            )

            edges.append(
                {
                    "source": cand_node_id,
                    "target": skill_node_id,
                    "relationship": "HAS_SKILL",
                    "properties": {"weight": 1.0},
                }
            )

        # 2. Company Nodes & WORKED_AT Edges
        work_history = resume_json.get("work_experience") or []
        if isinstance(work_history, list):
            for work in work_history[:5]:
                if isinstance(work, dict) and work.get("company"):
                    company_name = str(work["company"]).strip()
                    comp_node_id = f"company:{company_name.lower()}"

                    nodes.append(
                        {
                            "id": comp_node_id,
                            "type": "Company",
                            "label": company_name,
                            "properties": {"role": work.get("role") or work.get("job_title")},
                        }
                    )

                    edges.append(
                        {
                            "source": cand_node_id,
                            "target": comp_node_id,
                            "relationship": "WORKED_AT",
                            "properties": {"role": work.get("role")},
                        }
                    )

        # 3. Vacancy Matches & MATCHES Edges (Deterministic score authority preserved)
        suitable_openings = match_analysis.get("suitable_openings") or []
        for vac in suitable_openings[:5]:
            if isinstance(vac, dict):
                vac_id = str(vac.get("vacancy_id") or vac.get("id"))
                vac_title = str(vac.get("job_title") or "Vacancy")
                vac_score = float(vac.get("score") or vac.get("overall_score") or 0.0)
                vac_node_id = f"vacancy:{vac_id}"

                nodes.append(
                    {
                        "id": vac_node_id,
                        "type": "Vacancy",
                        "label": vac_title,
                        "properties": {
                            "score": vac_score,
                            "department": vac.get("department") or vac.get("department_name"),
                            "classification": vac.get("classification"),
                        },
                    }
                )

                edges.append(
                    {
                        "source": cand_node_id,
                        "target": vac_node_id,
                        "relationship": "MATCHES",
                        "properties": {
                            "score": vac_score,
                            "classification": vac.get("classification"),
                            "source_of_truth": "DeterministicScoringEngine",
                        },
                    }
                )

        # 4. Similar Candidates & SEMANTICALLY_SIMILAR Edges (Discovered via vector embeddings)
        similar_cands = r.get("similar_candidates") or []
        for sim in similar_cands[:3]:
            if isinstance(sim, dict):
                other_key = str(sim.get("cv_key"))
                sim_score = float(sim.get("similarity_score") or 0.0)
                other_node_id = f"candidate:{other_key}"

                nodes.append(
                    {
                        "id": other_node_id,
                        "type": "Candidate",
                        "label": sim.get("full_name") or other_key,
                        "properties": {
                            "similarity_score": sim_score,
                            "is_duplicate_flag": sim.get("is_duplicate_flag", False),
                        },
                    }
                )

                edges.append(
                    {
                        "source": cand_node_id,
                        "target": other_node_id,
                        "relationship": "SEMANTICALLY_SIMILAR",
                        "properties": {
                            "similarity": sim_score,
                            "discovery_mechanism": "VectorEmbeddings",
                            "is_duplicate": sim.get("is_duplicate_flag", False),
                        },
                    }
                )

        return {
            "candidate_id": cv_key,
            "full_name": extracted_name,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    @classmethod
    def get_vacancy_360_graph(cls, vacancy_id: str) -> dict[str, Any]:
        vid_str = str(vacancy_id).strip()
        all_jobs = JobRepository.get_all_jobs()
        target_job = None
        for j in all_jobs:
            if str(j.get("vacancy_id")) == vid_str or str(j.get("id")) == vid_str:
                target_job = j
                break

        if not target_job:
            return {"nodes": [], "edges": [], "vacancy_summary": None}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        vac_title = target_job.get("title", "Vacancy")
        dept_name = target_job.get("department_name") or target_job.get("department") or "Engineering"
        vac_node_id = f"vacancy:{vid_str}"

        nodes.append(
            {
                "id": vac_node_id,
                "type": "Vacancy",
                "label": vac_title,
                "properties": {
                    "department": dept_name,
                    "min_experience_years": target_job.get("min_experience_years"),
                },
            }
        )

        # 1. Department Node & BELONGS_TO Edge
        dept_node_id = f"department:{dept_name.lower()}"
        nodes.append(
            {
                "id": dept_node_id,
                "type": "Department",
                "label": dept_name,
                "properties": {},
            }
        )
        edges.append(
            {
                "source": vac_node_id,
                "target": dept_node_id,
                "relationship": "BELONGS_TO",
                "properties": {},
            }
        )

        # 2. Required Skills Nodes & REQUIRES_SKILL Edges
        req_skills = target_job.get("required_skills") or []
        for skill in req_skills:
            if not skill or not isinstance(skill, str):
                continue
            clean_s = skill.strip()
            skill_node_id = f"skill:{clean_s.lower()}"

            nodes.append(
                {
                    "id": skill_node_id,
                    "type": "Skill",
                    "label": clean_s,
                    "properties": {"tier": "MANDATORY"},
                }
            )

            edges.append(
                {
                    "source": vac_node_id,
                    "target": skill_node_id,
                    "relationship": "REQUIRES_SKILL",
                    "properties": {"tier": "MANDATORY"},
                }
            )

        # 3. Top Candidate Matches & MATCHES Edges
        all_results = ResultRepository.list_all_results()
        top_candidates = []
        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            raw_match = r.get("match_analysis")
            match_analysis = raw_match if isinstance(raw_match, dict) else {}
            suitable = match_analysis.get("suitable_openings") or []
            for s in suitable:
                if isinstance(s, dict) and (str(s.get("vacancy_id")) == vid_str or str(s.get("id")) == vid_str):
                    score = float(s.get("score") or s.get("overall_score") or 0.0)
                    top_candidates.append((score, r, s))

        top_candidates.sort(key=lambda x: x[0], reverse=True)
        for score, r, s in top_candidates[:5]:
            cv_key = str(r.get("id") or r.get("filename") or "")
            cand_node_id = f"candidate:{cv_key}"
            resume_json = r.get("resume_json") or {}
            contact_info = resume_json.get("contact_info") or {}
            cname = contact_info.get("name") or contact_info.get("full_name") or cv_key

            nodes.append(
                {
                    "id": cand_node_id,
                    "type": "Candidate",
                    "label": cname,
                    "properties": {
                        "score": score,
                        "classification": s.get("classification"),
                    },
                }
            )

            edges.append(
                {
                    "source": cand_node_id,
                    "target": vac_node_id,
                    "relationship": "MATCHES",
                    "properties": {
                        "score": score,
                        "classification": s.get("classification"),
                    },
                }
            )

        return {
            "vacancy_id": vid_str,
            "title": vac_title,
            "department": dept_name,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    @classmethod
    def get_skill_intelligence_graph(cls, skill_name: str) -> dict[str, Any]:
        clean_skill = skill_name.strip()
        skill_node_id = f"skill:{clean_skill.lower()}"

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        nodes.append(
            {
                "id": skill_node_id,
                "type": "Skill",
                "label": clean_skill,
                "properties": {"category": "technical"},
            }
        )

        # 1. Semantically Similar Skills (Discovered via Vector Embeddings)
        equivalents = DomainEmbeddingService.find_semantic_equivalents(term=clean_skill, category="skills", limit=4)
        for eq in equivalents:
            eq_term = eq["term"]
            eq_sim = float(eq["similarity_score"])
            eq_node_id = f"skill:{eq_term.lower()}"

            nodes.append(
                {
                    "id": eq_node_id,
                    "type": "Skill",
                    "label": eq_term.title(),
                    "properties": {"similarity_score": eq_sim},
                }
            )

            edges.append(
                {
                    "source": skill_node_id,
                    "target": eq_node_id,
                    "relationship": "SEMANTICALLY_SIMILAR",
                    "properties": {
                        "similarity": eq_sim,
                        "discovery_mechanism": "VectorEmbeddings",
                    },
                }
            )

        # 2. Candidate Supply & Vacancy Demand
        all_results = ResultRepository.list_all_results()
        cand_count = 0
        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            r_text = str(r.get("markdown") or "").lower()
            if clean_skill.lower() in r_text:
                cand_count += 1
                if cand_count <= 3:
                    cv_key = str(r.get("id") or r.get("filename") or "")
                    cand_node_id = f"candidate:{cv_key}"
                    contact_info = (r.get("resume_json") or {}).get("contact_info") or {}
                    cname = contact_info.get("name") or cv_key

                    nodes.append(
                        {
                            "id": cand_node_id,
                            "type": "Candidate",
                            "label": cname,
                            "properties": {},
                        }
                    )
                    edges.append(
                        {
                            "source": cand_node_id,
                            "target": skill_node_id,
                            "relationship": "HAS_SKILL",
                            "properties": {},
                        }
                    )

        all_jobs = JobRepository.get_all_jobs()
        vac_count = 0
        for j in all_jobs:
            reqs = [str(s).lower() for s in j.get("required_skills", [])]
            if clean_skill.lower() in reqs:
                vac_count += 1
                if vac_count <= 3:
                    vid = str(j.get("vacancy_id") or j.get("id"))
                    vac_node_id = f"vacancy:{vid}"

                    nodes.append(
                        {
                            "id": vac_node_id,
                            "type": "Vacancy",
                            "label": j.get("title", "Vacancy"),
                            "properties": {},
                        }
                    )
                    edges.append(
                        {
                            "source": vac_node_id,
                            "target": skill_node_id,
                            "relationship": "REQUIRES_SKILL",
                            "properties": {},
                        }
                    )

        return {
            "skill": clean_skill,
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "candidate_supply_count": cand_count,
                "vacancy_demand_count": vac_count,
                "semantic_cluster_count": len(equivalents),
            },
        }

    @classmethod
    def get_recruitment_analytics_graph(cls) -> dict[str, Any]:
        all_results = ResultRepository.list_all_results()
        all_jobs = JobRepository.get_all_jobs()

        skill_freq: dict[str, int] = {}
        dept_dist: dict[str, int] = {}

        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            skills = (r.get("resume_json") or {}).get("skills") or []
            for s in skills:
                if isinstance(s, str):
                    clean = s.strip().title()
                    skill_freq[clean] = skill_freq.get(clean, 0) + 1

            dept = (r.get("match_analysis") or {}).get("primary_department") or "Engineering"
            dept_dist[dept] = dept_dist.get(dept, 0) + 1

        top_skills = sorted(skill_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        total_nodes = len(all_results) + len(all_jobs) + len(skill_freq) + len(dept_dist)
        total_edges = sum(skill_freq.values()) + len(all_jobs)

        return {
            "graph_summary": {
                "total_candidates": len(all_results),
                "total_vacancies": len(all_jobs),
                "total_skills_tracked": len(skill_freq),
                "total_departments": len(dept_dist),
                "total_graph_nodes": total_nodes,
                "total_graph_edges": total_edges,
            },
            "top_candidate_skills": [{"skill": k, "candidate_count": v} for k, v in top_skills],
            "department_distribution": [{"department": k, "candidate_count": v} for k, v in dept_dist.items()],
        }
