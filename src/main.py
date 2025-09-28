# -*- coding: utf-8 -*-
"""Main application file for the User Service."""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from src.auth.oauth import init_oauth
from src.config import Config, get_config
from src.routes.auth import auth_bp
from src.routes.helpers import error_response
from src.routes.users import users_bp


def create_app(config: Config | None = None) -> Flask:
    """Create and configure the Flask application.

    Returns:
        Flask: The configured Flask application.
    """
    config = config or get_config()
    app = Flask(__name__)
    app.secret_key = config.flask_secret
    app.config["APP_CONFIG"] = config

    CORS(app, origins=config.cors_origins)
    upload_folder = app.config.setdefault(
        "UPLOAD_FOLDER",
        os.path.join(app.instance_path, "uploads"),
    )
    os.makedirs(upload_folder, exist_ok=True)
    app.config.setdefault("UPLOAD_URL_PREFIX", "/uploads")
    if config.redis:
        app.extensions["redis_client"] = config.redis
    init_oauth(app)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        """Handle HTTP exceptions by returning JSON."""
        message = err.description or err.name
        return error_response(err.code or 500, message)

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        """Handle unexpected exceptions by returning JSON."""
        return error_response(500, str(err))

    @app.route("/health")
    def health():
        """Health check endpoint."""
        return jsonify(
            {
                "status": "ok",
                "service": "user-service",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=app.config["APP_CONFIG"].app_port)
