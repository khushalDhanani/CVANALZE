import os
import tempfile
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.ollama_transport import OllamaTransport


@pytest.fixture(autouse=True)
def isolate_ollama_transport(monkeypatch):
    """Keep every ordinary test offline, serialized, and free of shared clients."""
    OllamaTransport.close()
    live_enabled = os.environ.get("OLLAMA_LIVE_TESTS_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    monkeypatch.setattr(settings, "OLLAMA_LIVE_TESTS_ENABLED", live_enabled)
    monkeypatch.setattr(settings, "OLLAMA_LOCK_FILE", Path(tempfile.gettempdir()) / "cv-analyzer-pytest-ollama.lock")
    monkeypatch.setattr(settings, "OLLAMA_LOCK_TIMEOUT_SECONDS", 1.0)
    yield
    OllamaTransport.close()
    EmbeddingService._failed_models_cache.clear()

@pytest.fixture(autouse=True)
def mock_rule_config_manager(monkeypatch):
    """Ensure tests always have a loaded rule config since the fallback was removed from runtime."""
    from app.core.rule_config_manager import RuleConfigManager
    import json
    from pathlib import Path
    
    original_load_config = RuleConfigManager.load_config
    
    def mocked_load_config(cls, candidate_dict=None, tenant_id=None):
        rule_config_path = Path(__file__).resolve().parent.parent / "app" / "core" / "rule_config.json"
        
        from app.core.cache import config_cache_manager
        cache_key = f"rule_config_profile_{tenant_id or 'GLOBAL'}"
        
        if candidate_dict is not None:
            config_cache_manager.set(cache_key, candidate_dict)
        elif rule_config_path.exists():
            with open(rule_config_path, "rb") as f:
                raw_data = json.loads(f.read().decode("utf-8"))
            config_cache_manager.set(cache_key, raw_data)
            
        return original_load_config(tenant_id=tenant_id)

    monkeypatch.setattr(RuleConfigManager, "load_config", classmethod(mocked_load_config))
    
    if not RuleConfigManager._active_configs:
        RuleConfigManager.load_config()

@pytest.fixture(autouse=True)
def mock_department_domain_repo(monkeypatch):
    """Ensure tests always have taxonomy domains since the fallback was removed."""
    from app.repositories.department_domain import DepartmentDomainRepository
    import json
    from pathlib import Path
    from app.schemas.domain import DepartmentDomain
    
    def mocked_load_from_db(self):
        seed_path = Path(__file__).resolve().parent.parent / "app" / "data" / "department_domains_seed.json"
        if not seed_path.exists():
            return []
        with open(seed_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        domains = []
        for i, d in enumerate(raw.get("domains", []), start=1):
            domains.append(
                DepartmentDomain(
                    id=i,
                    department_id=d.get("department_id"),
                    department_name=d.get("department_name"),
                    domain_name=d.get("domain_name"),
                    keywords=d.get("keywords", []),
                    default_roles=d.get("default_roles", []),
                    priority=d.get("priority", 0)
                )
            )
        return domains
        
    monkeypatch.setattr(DepartmentDomainRepository, "_load_from_db", mocked_load_from_db)

@pytest.fixture(autouse=True)
def mock_prompt_service(monkeypatch, request):
    if request.module and "test_prompt_service" in request.module.__name__:
        return
        
    from app.services.prompt_service import PromptService
    
    def mocked_fetch_prompt_from_db(cls, prompt_name, tenant_id, model, target_schema, language, environment):
        return "NO_SUITABLE_MATCH recommended_department MUST be selected from EVIDENCE CITATION"
        
    monkeypatch.setattr(PromptService, "_fetch_prompt_from_db", classmethod(mocked_fetch_prompt_from_db))
