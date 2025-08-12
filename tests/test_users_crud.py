

def test_user_crud(client):
    # create
    res = client.post(
        '/users',
        json={
            'email': 'test@example.com',
            'name': 'Test User',
            'skills': ['python'],
        },
    )
    assert res.status_code == 201
    user_id = res.json['user']['id']
    assert res.json['user']['created_at'].endswith('+00:00')

    # retrieve
    res = client.get(f'/users/{user_id}')
    assert res.status_code == 200
    assert res.json['user']['email'] == 'test@example.com'

    # update
    res = client.put(f'/users/{user_id}', json={'title': 'Dev'})
    assert res.status_code == 200
    assert res.json['user']['title'] == 'Dev'

    # delete
    res = client.delete(f'/users/{user_id}')
    assert res.status_code == 204
    res = client.get(f'/users/{user_id}')
    assert res.status_code == 404
