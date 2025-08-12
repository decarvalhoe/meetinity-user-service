import os
from flask import Flask, jsonify
from flask_cors import CORS

from src.models import db
from src.routes.users import bp as users_bp
from src.config import load_config


def create_app(test_config=None):
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    app.config.setdefault(
        'UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads')
    )
    app.config.setdefault('UPLOAD_BASE_URL', '/uploads')

    db.init_app(app)

    config = load_config()
    CORS(app, origins=config['CORS_ORIGINS'] or '*')

    app.register_blueprint(users_bp)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'user-service'})

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': {'code': 404, 'message': 'not found'}}), 404

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': {'code': 400, 'message': 'bad request'}}), 400

    @app.errorhandler(415)
    def unsupported(error):
        return (
            jsonify(
                {'error': {'code': 415, 'message': 'unsupported media type'}}
            ),
            415,
        )

    @app.errorhandler(422)
    def unprocessable(error):
        return (
            jsonify({'error': {'code': 422, 'message': 'validation error'}}),
            422,
        )

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == '__main__':
    config = load_config()
    app.run(debug=True, port=config['APP_PORT'])
