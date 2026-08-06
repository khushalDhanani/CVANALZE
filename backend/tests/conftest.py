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
    from pathlib import Path
    
    original_load_config = RuleConfigManager.load_config
    
    def mocked_load_config(cls, candidate_dict=None, tenant_id=None):
        from tests.mock_rule_config import MOCK_RULE_CONFIG
        
        from app.core.cache import config_cache_manager
        cache_key = f"rule_config_profile_{tenant_id or 'GLOBAL'}"
        
        if candidate_dict is not None:
            config_cache_manager.set(cache_key, candidate_dict)
        else:
            config_cache_manager.set(cache_key, MOCK_RULE_CONFIG)
            
        return original_load_config(tenant_id=tenant_id)

    monkeypatch.setattr(RuleConfigManager, "load_config", classmethod(mocked_load_config))
    
    if not RuleConfigManager._active_configs:
        RuleConfigManager.load_config()

@pytest.fixture(autouse=True)
def mock_department_domain_repo(monkeypatch):
    """Ensure tests always have taxonomy domains since the fallback was removed."""
    from app.repositories.department_domain import DepartmentDomainRepository
    from app.schemas.domain import DepartmentDomain
    
    def mocked_load_from_db(self):
        domains = [
            DepartmentDomain(
                id=1, department_id=9, department_name="CIS Team", domain_name="Information Technology & Software",
                keywords=["developer", "flutter", "dotnet", "full stack", "ui/ux", "desktop support", "software engineer", "machine learning"],
                default_roles=["Software Developer"], priority=1
            ),
            DepartmentDomain(
                id=2, department_id=8, department_name="Finance Team", domain_name="Finance & Accounting",
                keywords=["finance", "tally", "ledger", "valuation"],
                default_roles=["Finance Executive"], priority=2
            ),
            DepartmentDomain(
                id=3, department_id=7, department_name="Engineering Team", domain_name="Engineering",
                keywords=["civil", "mechanical", "engineering"],
                default_roles=["Engineer"], priority=3
            ),
            DepartmentDomain(id=4, department_id=4, department_name="Sales", domain_name="Sales", keywords=["sales"], default_roles=[], priority=4),
            DepartmentDomain(id=5, department_id=5, department_name="HR", domain_name="HR", keywords=["hr"], default_roles=[], priority=5),
            DepartmentDomain(id=6, department_id=6, department_name="Operations", domain_name="Operations", keywords=["operations"], default_roles=[], priority=6),
            DepartmentDomain(id=7, department_id=7, department_name="Legal", domain_name="Legal", keywords=["legal"], default_roles=[], priority=7),
            DepartmentDomain(id=8, department_id=8, department_name="Other", domain_name="Other", keywords=["other"], default_roles=[], priority=8)
        ]
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
