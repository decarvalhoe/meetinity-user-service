
def create_user(client, email, **kwargs):
    data = {'email': email, 'name': 'Name'}
    data.update(kwargs)
    res = client.post('/users', json=data)
    assert res.status_code == 201


def test_list_and_filters(client):
    create_user(
        client,
        'a@example.com',
        industry='tech',
        location='NY',
        experience_years=5,
        skills=['python'],
    )
    create_user(
        client,
        'b@example.com',
        industry='finance',
        location='SF',
        experience_years=2,
        skills=['excel'],
    )

    res = client.get('/users')
    assert res.status_code == 200
    assert res.json['total'] == 2

    res = client.get('/users?industry=tech')
    assert res.status_code == 200
    assert res.json['total'] == 1

    res = client.get('/users?skills=python')
    assert res.json['total'] == 1

    res = client.get('/users?min_experience=3')
    assert res.json['total'] == 1
