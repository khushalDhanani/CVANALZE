import re

with open("app/core/rule_config_manager.py", "r") as f:
    content = f.read()

# 1. Update state variables
content = content.replace("_active_config: UnifiedRuleConfig | None = None", "_active_configs: dict[str, UnifiedRuleConfig] = {}")
content = content.replace("_cache: MappingProxyType | None = None", "_caches: dict[str, MappingProxyType] = {}")

# 2. Update get_config signature
content = re.sub(
    r"def get_config\(cls\) -> UnifiedRuleConfig:",
    "def get_config(cls, tenant_id: str | None = None) -> UnifiedRuleConfig:",
    content
)
# Update get_config body
content = re.sub(
    r"if cls\._active_config is None:\n\s+cls\.load_config\(\)\n\s+return cls\._active_config",
    "tenant_key = tenant_id or 'GLOBAL'\n        if tenant_key not in cls._active_configs:\n            cls.load_config(tenant_id=tenant_id)\n        return cls._active_configs[tenant_key]",
    content
)

# 3. Update load_config to accept tenant_id
content = re.sub(
    r"def load_config\(\n\s+cls,\n\s+config_source: dict\[str, Any\] \| Path \| str \| None = None,\n\s+\) -> UnifiedRuleConfig:",
    "def load_config(\n        cls,\n        config_source: dict[str, Any] | Path | str | None = None,\n        tenant_id: str | None = None,\n    ) -> UnifiedRuleConfig:",
    content
)

# In load_config, change active_profile query to include tenant_id
content = content.replace(
    "active_profile = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True).first()",
    "query = db.query(RuleConfigProfile).filter(RuleConfigProfile.is_active == True)\n                    if tenant_id:\n                        query = query.filter(RuleConfigProfile.tenant_id == tenant_id)\n                    else:\n                        query = query.filter(RuleConfigProfile.tenant_id.is_(None))\n                    active_profile = query.first()"
)

# In load_config, swap active config to dictionary
content = content.replace(
    "cls._active_config = candidate_config",
    "tenant_key = tenant_id or 'GLOBAL'\n            cls._active_configs[tenant_key] = candidate_config"
)
content = content.replace(
    "cls._cache = candidate_cache",
    "cls._caches[tenant_key] = candidate_cache"
)
content = content.replace(
    "return cls._active_config",
    "return cls._active_configs[tenant_key]"
)

# 4. Update all getter methods to take tenant_id: str | None = None
getters = [
    "get_scoring",
    "get_match_rules",
    "get_prefilter_rules",
    "get_taxonomy_rules",
    "get_resume_quality_rules",
    "get_domain_embedding_rules",
    "_get_cache",
    "get_term_matching_assets",
    "get_cross_domain_guard_assets",
    "get_compiled_section_patterns",
    "get_compiled_heading_normalizations",
    "get_recommendations",
    "get_scoring_parameters",
    "get_compiled_cross_domain_guard",
]

for getter in getters:
    # Modify signature
    content = re.sub(
        rf"def {getter}\(cls\)",
        f"def {getter}(cls, tenant_id: str | None = None)",
        content
    )
    # Modify body calls to pass tenant_id
    if getter == "_get_cache":
        # _get_cache body:
        content = re.sub(
            r"if cls\._cache is None or cls\._cache\.get\(\"config\"\) is not cls\._active_config:\n\s+cls\.load_config\(\)\n\s+return cls\._cache",
            "tenant_key = tenant_id or 'GLOBAL'\n            if tenant_key not in cls._caches or cls._caches[tenant_key].get('config') is not cls._active_configs.get(tenant_key):\n                cls.load_config(tenant_id=tenant_id)\n            return cls._caches[tenant_key]",
            content
        )
    else:
        # replace cls.get_config(). with cls.get_config(tenant_id).
        content = content.replace(
            f"cls.get_config().",
            f"cls.get_config(tenant_id)."
        )
        # replace cls._get_cache()[" with cls._get_cache(tenant_id)["
        content = content.replace(
            f"cls._get_cache()[\"",
            f"cls._get_cache(tenant_id)[\""
        )
        # replace cls.get_scoring(). with cls.get_scoring(tenant_id).
        content = content.replace(
            f"cls.get_scoring().",
            f"cls.get_scoring(tenant_id)."
        )

with open("app/core/rule_config_manager.py", "w") as f:
    f.write(content)

print("Done refactoring rule_config_manager.py")
