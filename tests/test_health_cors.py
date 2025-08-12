def test_health_endpoint(client):
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json == {'status': 'ok', 'service': 'user-service'}


def test_cors_from_env(monkeypatch):
    monkeypatch.setenv(
        'CORS_ORIGINS', 'http://localhost:5173,http://localhost:5174'
    )
    from src.main import create_app

    app = create_app({'TESTING': True})
    test_client = app.test_client()
    res = test_client.get(
        '/health', headers={'Origin': 'http://localhost:5173'}
    )
    assert (
        res.headers['Access-Control-Allow-Origin']
        == 'http://localhost:5173'
    )
