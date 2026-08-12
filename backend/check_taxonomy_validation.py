import os
import sys

from app.core.rule_config_manager import RuleConfigManager
from app.repositories.department_domain import department_domain_repository
from app.schemas.domain import DepartmentDomain, KeywordConfig, MatchType

domains = department_domain_repository.get_all_domains()
stop_words = set(RuleConfigManager.get_prefilter_rules().stop_words)

for domain in domains:
    for kw in domain.keywords:
        if kw.term.lower() in stop_words and kw.match_type != MatchType.CASE_SENSITIVE_ACRONYM:
            print(f"ERROR: {kw.term} in domain {domain.domain_name} matches stop word but is not CASE_SENSITIVE_ACRONYM!")

print("Validation complete.")
