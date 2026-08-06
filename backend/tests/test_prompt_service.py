import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import app.models.mssql.organization
import app.models.mssql.candidate
from app.models.prompts import PromptTemplateMaster
from app.services.prompt_service import PromptService
from app.core.error_handlers import PromptError
from app.core.database import PostgresAppBase

engine = create_engine("sqlite:///:memory:")

@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS cvai")

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session(monkeypatch):
    PostgresAppBase.metadata.create_all(bind=engine)
    
    import app.services.prompt_service
    monkeypatch.setattr(app.services.prompt_service, "PostgresAppSession", TestingSessionLocal)
    
    with TestingSessionLocal() as session:
        yield session
        
    PostgresAppBase.metadata.drop_all(bind=engine)

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
