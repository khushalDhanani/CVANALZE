import sys
import re

with open('backend/app/services/job_taxonomy.py', 'r') as f:
    content = f.read()

# 1. Remove _branch_matches, _rule_matches, _condition_matches, _classify_vacancy_cached, classify_candidate_by_full_text
content = re.sub(r'    @staticmethod\n    def _condition_matches.*?(?=    @classmethod\n    def classify_vacancy_dto)', '', content, flags=re.DOTALL)

# 2. Modify classify_vacancy_dto
content = re.sub(
    r'        if dyn_res\.match_source != "legacy_fallback":.*?return TaxonomyClassification\([^)]*\)\n\n        # 2\. Fallback to static rule classification.*?return TaxonomyClassification\([^)]*\)',
    '''        if dyn_res.match_status == "DB_MATCH":
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            matched_kw = dyn_res.evidence[0].matched_term if dyn_res.evidence else ""
            domain = dyn_res.industry_domain or "Unknown"
            family = dyn_res.db_department_name or "Unknown"
            return TaxonomyClassification(
                domain=domain,
                job_family=family,
                compatible_families=(family,),
                matched_rule=f"dynamic:{dyn_res.match_source}",
                matched_branch=0,
                matched_keywords=(matched_kw,) if matched_kw else (),
            )

        # 2. Return fallback if dynamic resolution failed
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=(),
            matched_rule="NO_SUITABLE_MATCH",
            matched_branch=0,
            matched_keywords=(),
        )''',
    content,
    flags=re.DOTALL
)

# 3. Modify classify_candidate_dto
content = re.sub(
    r'        if dyn_res\.match_source != "legacy_fallback":.*?return TaxonomyClassification\([^)]*\)\n\n        # 2\. Fallback to static rule classification.*?return TaxonomyClassification\([^)]*\)',
    '''        if dyn_res.match_status == "DB_MATCH":
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
            domain = dyn_res.industry_domain or "Unknown"
            family = dyn_res.db_department_name or "Unknown"
            return TaxonomyClassification(
                domain=domain,
                job_family=family,
                compatible_families=(family,),
                matched_rule=f"dynamic:{dyn_res.match_source}",
            )

        # 2. Return fallback if dynamic resolution failed
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=(),
            matched_rule="NO_SUITABLE_MATCH",
        )''',
    content,
    flags=re.DOTALL
)

with open('backend/app/services/job_taxonomy.py', 'w') as f:
    f.write(content)

