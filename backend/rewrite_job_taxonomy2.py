import sys
import re

with open('backend/app/services/job_taxonomy.py', 'r') as f:
    content = f.read()

# Make sure we don't use RuleConfigManager inside classify_vacancy_dto
content = re.sub(
    r'        if dyn_res\.match_source != "legacy_fallback":\n            elapsed_ms = \(time\.perf_counter\(\) - t0\) \* 1000\.0\n            TaxonomyMetrics\.record_hit\(cache_hit=False, duration_ms=elapsed_ms\)\n            matched_kw = dyn_res\.evidence\[0\]\.matched_term if dyn_res\.evidence else ""\n            domain = dyn_res\.industry_domain or RuleConfigManager\.get_taxonomy_rules\(\)\.default_domain\n            family = dyn_res\.db_department_name or RuleConfigManager\.get_taxonomy_rules\(\)\.default_family\n            return TaxonomyClassification\(\n                domain=domain,\n                job_family=family,\n                compatible_families=\(family,\),\n                matched_rule=f"dynamic:{dyn_res\.match_source}",\n                matched_branch=0,\n                matched_keywords=\(matched_kw,\) if matched_kw else \(\),\n            \)\n\n        # 2\. Fallback to static rule classification.*?(?=    @classmethod\n    def classify_vacancy\()',
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

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=(),
            matched_rule="NO_SUITABLE_MATCH",
            matched_branch=0,
            matched_keywords=(),
        )

''',
    content,
    flags=re.DOTALL
)

# And for classify_candidate_dto
content = re.sub(
    r'        if dyn_res\.match_source != "legacy_fallback":\n            elapsed_ms = \(time\.perf_counter\(\) - t0\) \* 1000\.0\n            TaxonomyMetrics\.record_hit\(cache_hit=False, duration_ms=elapsed_ms\)\n            matched_kw = dyn_res\.evidence\[0\]\.matched_term if dyn_res\.evidence else ""\n            domain = dyn_res\.industry_domain or RuleConfigManager\.get_taxonomy_rules\(\)\.default_domain\n            family = dyn_res\.db_department_name or RuleConfigManager\.get_taxonomy_rules\(\)\.default_family\n            return TaxonomyClassification\(\n                domain=domain,\n                job_family=family,\n                compatible_families=\(family,\),\n                matched_rule=f"dynamic:{dyn_res\.match_source}",\n            \)\n\n        # 2\. Fallback to static rule classification.*?(?=    @classmethod\n    def classify_candidate\()',
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

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        TaxonomyMetrics.record_hit(cache_hit=False, duration_ms=elapsed_ms)
        return TaxonomyClassification(
            domain="Unknown",
            job_family="Unknown",
            compatible_families=(),
            matched_rule="NO_SUITABLE_MATCH",
        )

''',
    content,
    flags=re.DOTALL
)

with open('backend/app/services/job_taxonomy.py', 'w') as f:
    f.write(content)

