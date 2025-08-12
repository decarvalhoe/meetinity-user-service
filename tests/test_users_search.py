
def test_search(client):
    client.post(
        '/users',
        json={
            'email': 'search@example.com',
            'name': 'Alice',
            'bio': 'loves python and flask',
        },
    )
    res = client.get('/users/search?q=python')
    assert res.status_code == 200
    assert res.json['total'] == 1
