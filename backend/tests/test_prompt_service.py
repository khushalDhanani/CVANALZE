import pytest
import app.models.org
import app.models.recruit
from app.models.prompts import PromptTemplateMaster
from app.services.prompt_service import PromptService
from app.core.error_handlers import PromptError
from app.core.database import SessionLocal

@pytest.fixture(scope="module")
def db_session():
    with SessionLocal() as session:
        yield session

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
