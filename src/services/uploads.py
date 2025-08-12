import os
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def save_photo(storage, user_id):
    filename = secure_filename(storage.filename)
    if not filename:
        raise ValueError('no filename')
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError('invalid extension')
    folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(folder, exist_ok=True)
    final_name = f'user_{user_id}.{ext}'
    path = os.path.join(folder, final_name)
    storage.save(path)
    base_url = current_app.config.get('UPLOAD_BASE_URL', '/uploads')
    return f"{base_url}/{final_name}"
