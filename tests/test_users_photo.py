import io


def test_photo_upload(client):
    res = client.post(
        '/users',
        json={'email': 'photo@example.com', 'name': 'Photo'},
    )
    user_id = res.json['user']['id']

    data = {
        'photo': (io.BytesIO(b'mockdata'), 'pic.png')
    }
    res = client.post(
        f'/users/{user_id}/photo',
        data=data,
        content_type='multipart/form-data',
    )
    assert res.status_code == 201
    assert 'photo_url' in res.json
