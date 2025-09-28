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


@dataclass(frozen=True)
class Config:
    """Central application configuration."""

    database_url: str
    redis_url: Optional[str]
    sqlalchemy_echo: bool = False
    flask_secret: str = "dev"
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    redis_cache_ttl: int = 300

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
        sqlalchemy_echo=_parse_bool(os.getenv("SQLALCHEMY_ECHO")),
        flask_secret=os.getenv("FLASK_SECRET", "dev"),
        cors_origins=_parse_origins(os.getenv("CORS_ORIGINS")),
        redis_cache_ttl=int(os.getenv("REDIS_CACHE_TTL", "300")),
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
