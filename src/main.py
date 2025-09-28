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
    if config.redis:
        app.extensions["redis_client"] = config.redis
    init_oauth(app)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        """Handle HTTP exceptions by returning JSON."""
        response = jsonify({"error": err.description})
        response.status_code = err.code
        return response

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        """Handle unexpected exceptions by returning JSON."""
        response = jsonify({"error": str(err)})
        response.status_code = 500
        return response

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

    @app.route("/users")
    def users():
        """Placeholder endpoint returning an empty list of users."""
        return jsonify({"users": []})

    app.register_blueprint(auth_bp)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, port=port)
