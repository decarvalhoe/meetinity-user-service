import os
from datetime import datetime, timezone

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from src.auth.oauth import init_oauth
from src.routes.auth import auth_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET", "dev")

    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
    CORS(app, origins=origins)
    init_oauth(app)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        response = jsonify({"error": err.description})
        response.status_code = err.code
        return response

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        response = jsonify({"error": str(err)})
        response.status_code = 500
        return response

    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "user-service",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @app.route("/users")
    def users():
        return jsonify({"users": []})

    app.register_blueprint(auth_bp)
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, port=port)
