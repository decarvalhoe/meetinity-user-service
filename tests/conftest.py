import pytest

from src.main import create_app, db


@pytest.fixture
def app():
    app = create_app(
        {'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'}
    )
    yield app


@pytest.fixture(autouse=True)
def clean_db(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()
