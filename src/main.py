import os

from flask import Flask, jsonify
from flask_cors import CORS

from src.auth.oauth import init_oauth
from src.routes.auth import auth_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET", "dev")
    CORS(app)
    init_oauth(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "user-service"})

    @app.route("/users")
    def users():
        return jsonify({"users": []})

    app.register_blueprint(auth_bp)
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, port=port)
