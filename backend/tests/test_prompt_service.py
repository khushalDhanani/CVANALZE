import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.error_handlers import PromptError
from app.models.prompts import PromptTemplateMaster
from app.services.prompt_service import PromptService

engine = create_engine("sqlite:///:memory:")

@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS cvai")

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session(monkeypatch):
    PromptTemplateMaster.__table__.create(bind=engine)
    
    import app.services.prompt_service
    monkeypatch.setattr(app.services.prompt_service, "PostgresAppSession", TestingSessionLocal)
    
    with TestingSessionLocal() as session:
        yield session
        
    PromptTemplateMaster.__table__.drop(bind=engine)

@pytest.fixture(autouse=True)
def cleanup(db_session):
    # Cleanup before and after each test
    db_session.query(PromptTemplateMaster).filter(PromptTemplateMaster.prompt_name == "test_prompt").delete()
    db_session.commit()
    from app.core.cache import config_cache_manager
    config_cache_manager.clear()
    yield
    db_session.query(PromptTemplateMaster).filter(PromptTemplateMaster.prompt_name == "test_prompt").delete()
    db_session.commit()

def test_placeholder_extraction():
    template = "Hello {name}, your score is {score}."
    placeholders = PromptService.get_placeholders(template)
    assert placeholders == {"name", "score"}

def test_prompt_fallback_chain(db_session):
    p_generic = PromptTemplateMaster(
        prompt_name="test_prompt",
        version_tag="1.0",
        system_instruction="Generic: {val}",
        is_active=True
    )
    db_session.add(p_generic)
    db_session.commit()

    res = PromptService.get_prompt("test_prompt", {"val": "1"})
    assert res == "Generic: 1"

    p_model = PromptTemplateMaster(
        prompt_name="test_prompt",
        version_tag="1.1",
        model="gpt-4",
        system_instruction="Model: {val}",
        is_active=True
    )
    db_session.add(p_model)
    db_session.commit()

    from app.core.cache import config_cache_manager
    config_cache_manager.clear()

    res = PromptService.get_prompt("test_prompt", {"val": "2"}, model="gpt-4")
    assert res == "Model: 2"
    
    res = PromptService.get_prompt("test_prompt", {"val": "2"}, model="qwen")
    assert res == "Generic: 2"


def test_optimized_prompt_cache_key_includes_required_version(monkeypatch):
    from app.core.cache import config_cache_manager
    from app.core.config import settings
    from app.services.prompt_service import PromptReadiness

    monkeypatch.setattr(settings, "OPTIMIZED_PROMPT_VERSION", "3.6")
    monkeypatch.setattr(PromptService, "check_required_optimized_match_prompt", classmethod(lambda cls: PromptReadiness(True, "READY")))
    monkeypatch.setattr(PromptService, "_fetch_prompt_from_db", classmethod(lambda cls, *args, **kwargs: "Prompt: {input_json}"))
    cache_get = MagicMock(return_value=None)
    monkeypatch.setattr(config_cache_manager, "get", cache_get)
    monkeypatch.setattr(config_cache_manager, "set", MagicMock())

    result = PromptService.get_prompt(
        "optimized_match",
        {"input_json": "{}", "domain_list_str": "IT", "dept_list_str": "Engineering"},
    )

    assert result == "Prompt: {}"
    assert ":3.6:" in cache_get.call_args.args[0]


def test_prompt_resolution_returns_active_database_version(db_session):
    prompt = PromptTemplateMaster(
        prompt_name="hiring_risk_explanation",
        version_tag="7.2.1",
        system_instruction="Risks: {prompt_payload}",
        is_active=True,
    )
    db_session.add(prompt)
    db_session.commit()

    resolved = PromptService.get_prompt_with_version("hiring_risk_explanation", {"prompt_payload": "[]"})

    assert resolved.prompt == "Risks: []"
    assert resolved.version_tag == "7.2.1"
    assert PromptService.get_active_prompt_version("hiring_risk_explanation") == "7.2.1"
    assert PromptService.get_active_prompt_identity("hiring_risk_explanation").startswith("7.2.1:")


def test_hiring_risk_prompt_uses_stable_builtin_default_when_database_record_is_missing(monkeypatch):
    monkeypatch.setattr(PromptService, "_fetch_prompt_record_from_db", classmethod(lambda cls, *args, **kwargs: None))

    resolved = PromptService.get_prompt_with_version("hiring_risk_explanation", {"prompt_payload": "[]"})
    version = PromptService.get_active_prompt_version("hiring_risk_explanation")
    identity = PromptService.get_active_prompt_identity("hiring_risk_explanation")

    assert "INPUT:\n[]" in resolved.prompt
    assert resolved.version_tag == PromptService.HIRING_RISK_DEFAULT_VERSION
    assert version == PromptService.HIRING_RISK_DEFAULT_VERSION
    assert identity == PromptService._get_default_prompt_identity("hiring_risk_explanation")
    assert identity.startswith(f"{PromptService.HIRING_RISK_DEFAULT_VERSION}:")


def test_cached_missing_hiring_risk_metadata_resolves_to_builtin_default(monkeypatch):
    from app.core.cache import config_cache_manager

    monkeypatch.setattr(config_cache_manager, "get", MagicMock(return_value="__MISSING__"))

    assert PromptService.get_active_prompt_version("hiring_risk_explanation") == PromptService.HIRING_RISK_DEFAULT_VERSION
    assert PromptService.get_active_prompt_identity("hiring_risk_explanation") == PromptService._get_default_prompt_identity("hiring_risk_explanation")

def test_missing_placeholder(db_session):
    p = PromptTemplateMaster(
        prompt_name="test_prompt",
        version_tag="1.0",
        system_instruction="Hello {name}",
        is_active=True
    )
    db_session.add(p)
    db_session.commit()

    with pytest.raises(PromptError) as excinfo:
        PromptService.get_prompt("test_prompt", {"wrong": "val"})
    assert "Missing required placeholder" in str(excinfo.value)

def test_activation_validation(db_session):
    p = PromptTemplateMaster(
        prompt_name="test_prompt",
        version_tag="1.0",
        system_instruction="Hello {name}",
        is_active=False
    )
    db_session.add(p)
    db_session.commit()

    with pytest.raises(ValueError) as excinfo:
        PromptService.activate_prompt(db_session, p.prompt_id, {"name", "score"})
    assert "Missing required placeholders" in str(excinfo.value)
    
    active_p = PromptService.activate_prompt(db_session, p.prompt_id, {"name"})
    assert active_p.is_active is True


def test_required_optimized_match_prompt_validates_version_placeholders_and_schema(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OPTIMIZED_PROMPT_VERSION", "3.6")
    assert PromptService.check_required_optimized_match_prompt().ready is False

    prompt = PromptTemplateMaster(
        prompt_name="optimized_match",
        version_tag="3.6",
        system_instruction="{input_json} {domain_list_str} {dept_list_str}",
        expected_schema_json=json.dumps(
            {
                "$id": PromptService.OPTIMIZED_MATCH_SCHEMA_ID,
                "type": "object",
                "required": sorted(PromptService.OPTIMIZED_MATCH_SCHEMA_FIELDS),
                "properties": {field: {} for field in PromptService.OPTIMIZED_MATCH_SCHEMA_FIELDS},
            }
        ),
        is_active=True,
    )
    db_session.add(prompt)
    db_session.commit()

    assert PromptService.check_required_optimized_match_prompt().ready is True
    prompt.system_instruction = "/think\n{input_json} {domain_list_str} {dept_list_str}"
    db_session.commit()
    assert PromptService.check_required_optimized_match_prompt().ready is False
    prompt.system_instruction = "{input_json} {domain_list_str} {dept_list_str}"
    prompt.expected_schema_json = "{}"
    db_session.commit()
    assert PromptService.check_required_optimized_match_prompt().ready is False
    with pytest.raises(PromptError, match="PROMPT_UNAVAILABLE"):
        PromptService.get_prompt(
            "optimized_match",
            {"input_json": "{}", "domain_list_str": "IT", "dept_list_str": "Engineering"},
        )
