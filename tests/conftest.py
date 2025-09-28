"""Pytest fixtures for the user service tests."""

import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SQLALCHEMY_ECHO", "false")
os.environ.setdefault("JWT_SECRET", "testsecret")
os.environ.setdefault(
    "GOOGLE_REDIRECT_URI", "http://localhost/auth/google/callback"
)
os.environ.setdefault(
    "LINKEDIN_REDIRECT_URI", "http://localhost/auth/linkedin/callback"
)

from src.db.session import Base, get_engine, reset_engine  # noqa: E402
from src.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    application = create_app()
    application.config.update({"TESTING": True})
    yield application
    Base.metadata.drop_all(bind=engine)
    reset_engine()


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def _db_cleanup():
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
