import re

with open('app/repositories/department_domain.py', 'r') as f:
    content = f.read()

# Update import
content = content.replace(
    'from app.schemas.domain import DepartmentDomain',
    'from app.schemas.domain import DepartmentDomain, MatchType'
)

# Update get_version
content = content.replace(
    '"keywords": sorted(domain.keywords),',
    '"keywords": sorted([kw.model_dump() for kw in domain.keywords], key=lambda k: k["term"]),'
)

# Update _validate_domains
validate_code = """
    @staticmethod
    def _validate_domains(domains: list[DepartmentDomain]) -> None:
        from app.core.rule_config_manager import RuleConfigManager
        stop_words = set(RuleConfigManager.get_prefilter_rules().stop_words)
        for domain in domains:
            for kw in domain.keywords:
                if kw.term.lower() in stop_words and kw.match_type != MatchType.CASE_SENSITIVE_ACRONYM:
                    from app.core.logging import logger
                    logger.error(f"[TAXONOMY_VALIDATION] Ambiguous keyword '{kw.term}' found in domain '{domain.domain_name}'. This keyword matches a common stop word and requires explicit 'CASE_SENSITIVE_ACRONYM' configuration to prevent false positives.")
                    raise ValueError(f"Unsafe ambiguous keyword '{kw.term}' detected in taxonomy configuration.")

    def _create_session(self) -> Session | None:"""

content = content.replace(
    '    def _create_session(self) -> Session | None:',
    validate_code
)

# Call _validate_domains in _reload_locked
content = content.replace(
    '        self._domains = domains\n        self._matchers = self._build_matchers(domains)',
    '        self._validate_domains(domains)\n        self._domains = domains\n        self._matchers = self._build_matchers(domains)'
)

# Update _build_matchers
old_build_matchers = """    @staticmethod
    def _build_matchers(domains: list[DepartmentDomain]) -> list[DomainMatcher]:
        return [
            DomainMatcher(
                domain=domain,
                _keyword_patterns=tuple(
                    re.compile(
                        r"(?:\\b|_)" + re.escape(keyword) + r"(?:\\b|_)",
                        re.IGNORECASE,
                    )
                    for keyword in domain.keywords
                ),
                _keyword_words=frozenset(domain.keywords),
            )
            for domain in domains
        ]"""

new_build_matchers = """    @staticmethod
    def _build_matchers(domains: list[DepartmentDomain]) -> list[DomainMatcher]:
        patterns = []
        for domain in domains:
            domain_patterns = []
            keyword_strings = []
            for kw in domain.keywords:
                keyword_strings.append(kw.term)
                if kw.match_type == MatchType.CASE_SENSITIVE_ACRONYM:
                    domain_patterns.append(
                        re.compile(r"(?:\\b|_)" + re.escape(kw.term) + r"(?:\\b|_)")
                    )
                else:
                    domain_patterns.append(
                        re.compile(r"(?:\\b|_)" + re.escape(kw.term) + r"(?:\\b|_)", re.IGNORECASE)
                    )
            patterns.append(
                DomainMatcher(
                    domain=domain,
                    _keyword_patterns=tuple(domain_patterns),
                    _keyword_words=frozenset(keyword_strings),
                )
            )
        return patterns"""

content = content.replace(old_build_matchers, new_build_matchers)

with open('app/repositories/department_domain.py', 'w') as f:
    f.write(content)
