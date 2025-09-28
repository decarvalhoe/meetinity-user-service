"""Application configuration helpers."""

from __future__ import annotations

import os

from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from redis import Redis


load_dotenv()


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_origins(raw: Optional[str]) -> List[str]:
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Central application configuration."""

    database_url: str
    redis_url: Optional[str]
    app_port: int = 5001
    sqlalchemy_echo: bool = False
    flask_secret: str = "dev"
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    redis_cache_ttl: int = 300
    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60

    @cached_property
    def redis(self) -> Optional[Redis]:
        """Create a Redis client if a URL is configured."""

        if not self.redis_url:
            return None
        return Redis.from_url(self.redis_url, decode_responses=True)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton configuration instance."""

    default_db = "sqlite+pysqlite:///:memory:"
    return Config(
        database_url=os.getenv("DATABASE_URL", default_db),
        redis_url=os.getenv("REDIS_URL"),
        app_port=_parse_int(os.getenv("APP_PORT"), 5001),
        sqlalchemy_echo=_parse_bool(os.getenv("SQLALCHEMY_ECHO")),
        flask_secret=os.getenv("FLASK_SECRET", "dev"),
        cors_origins=_parse_origins(os.getenv("CORS_ORIGINS")),
        redis_cache_ttl=_parse_int(os.getenv("REDIS_CACHE_TTL"), 300),
        jwt_secret=os.getenv("JWT_SECRET", "change_me"),
        jwt_algorithm=os.getenv("JWT_ALGO", "HS256"),
        jwt_ttl_minutes=_parse_int(os.getenv("JWT_TTL_MIN"), 60),
    )


def reset_config(
    overrides: Optional[dict[str, Optional[str]]] = None,
) -> Config:
    """Reset cached configuration and optionally override env vars."""

    if overrides:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    get_config.cache_clear()
    return get_config()
