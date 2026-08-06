import pytest
from sqlalchemy.orm import configure_mappers
from app.models import *

def test_models_import_and_configure_mappers():
    """
    Test that all models can be imported and SQLAlchemy mappers can be configured
    without raising any exceptions. This acts as a startup/import test.
    """
    try:
        configure_mappers()
    except Exception as e:
        pytest.fail(f"configure_mappers() failed: {e}")
