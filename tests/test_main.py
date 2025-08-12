import pytest
from src.main import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'


def test_users(client):
    response = client.get('/users')
    assert response.status_code == 200
    assert 'users' in response.json
