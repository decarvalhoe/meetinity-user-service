# -*- coding: utf-8 -*-
"""Main application file for the User Service."""

import os
import time
from datetime import datetime, timezone

from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from src.auth.oauth import init_oauth
from src.config import Config, get_config
from src.routes.auth import auth_bp
from src.routes.helpers import error_response
from src.routes.users import users_bp
from src.services.cache import CacheService
from src.utils.encryption import ApplicationEncryptor

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)


REQUEST_COUNT = Counter(
    "user_service_requests_total",
    "Total number of HTTP requests processed.",
    labelnames=("method", "endpoint", "status"),
)
REQUEST_LATENCY = Histogram(
    "user_service_request_duration_seconds",
    "Request latency in seconds.",
    labelnames=("method", "endpoint"),
)


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
    app.extensions["cache_service"] = CacheService(
        app.extensions.get("redis_client"),
        config.redis_cache_ttl,
    )
    app.extensions["encryptor"] = ApplicationEncryptor.from_keys(
        primary_key=config.encryption_primary_key,
        fallback_keys=config.encryption_fallback_keys,
        rotation_days=config.encryption_rotation_days,
    )
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

    @app.route("/metrics")
    def metrics() -> Response:
        """Expose Prometheus metrics."""
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.before_request
    def start_timer() -> None:
        g._request_start_time = time.perf_counter()

    @app.after_request
    def log_and_record(response: Response) -> Response:
        endpoint = request.endpoint or "unknown"
        method = request.method
        status = str(response.status_code)
        start = getattr(g, "_request_start_time", None)
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=status,
        ).inc()
        if start is not None:
            duration = time.perf_counter() - start
            REQUEST_LATENCY.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)
            app.logger.info(
                "request.completed",
                extra={
                    "endpoint": endpoint,
                    "method": method,
                    "status": status,
                    "duration_ms": duration * 1000,
                },
            )
        return response

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=app.config["APP_CONFIG"].app_port)
