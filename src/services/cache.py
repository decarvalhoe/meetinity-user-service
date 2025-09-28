"""Centralized Redis cache helpers and instrumentation."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence

from prometheus_client import Counter, Histogram
from redis import Redis


logger = logging.getLogger(__name__)

CACHE_NAMESPACE = "user-service"

_CACHE_HITS = Counter(
    "user_service_cache_hits_total",
    "Total number of cache hits.",
    labelnames=("namespace",),
)
_CACHE_MISSES = Counter(
    "user_service_cache_misses_total",
    "Total number of cache misses.",
    labelnames=("namespace",),
)
_CACHE_OPERATIONS = Counter(
    "user_service_cache_operations_total",
    "Number of cache operations performed.",
    labelnames=("namespace", "operation"),
)
_CACHE_LATENCY = Histogram(
    "user_service_cache_operation_seconds",
    "Duration of cache operations in seconds.",
    labelnames=("namespace", "operation"),
)


@dataclass(slots=True)
class CacheHooks:
    """Functions repositories can call to invalidate caches."""

    invalidate_profile: Callable[[int], None]
    invalidate_collections: Callable[[], None]


class CacheService:
    """High level API for interacting with the shared Redis cache."""

    def __init__(
        self,
        client: Redis | None,
        default_ttl: int,
        *,
        namespace: str = CACHE_NAMESPACE,
    ) -> None:
        self.client = client
        self.default_ttl = max(default_ttl, 0)
        self.namespace = namespace
        self._hooks: CacheHooks | None = None

    # ------------------------------------------------------------------
    # Derived keys
    # ------------------------------------------------------------------
    def key(self, *parts: object) -> str:
        """Return a namespaced cache key composed from ``parts``."""

        stringified = [str(part) for part in parts if part not in (None, "")]
        return ":".join([self.namespace, *stringified])

    def profile_key(self, user_id: int) -> str:
        return self.key("users", "profile", user_id)

    def listing_key(
        self,
        *,
        page: int,
        per_page: int,
        sort: Sequence[str],
        filters: Mapping[str, object],
    ) -> str:
        payload = {
            "filters": filters,
            "page": int(page),
            "per_page": int(per_page),
            "sort": list(sort),
        }
        digest = self._hash_payload(payload)
        return self.key("users", "list", digest)

    def search_key(
        self,
        *,
        query: str,
        page: int,
        per_page: int,
        sort: Sequence[str],
        filters: Mapping[str, object],
    ) -> str:
        payload = {
            "query": query,
            "filters": filters,
            "page": int(page),
            "per_page": int(per_page),
            "sort": list(sort),
        }
        digest = self._hash_payload(payload)
        return self.key("users", "search", digest)

    # ------------------------------------------------------------------
    # Basic operations
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self.client is not None

    def get_json(self, key: str) -> Any | None:
        """Fetch a JSON encoded payload from the cache."""

        if not self.enabled:
            return None
        start = time.perf_counter()
        try:
            value = self.client.get(key)
        except Exception:  # pragma: no cover - instrumentation only
            logger.exception("cache.get failed key=%s", key)
            return None
        finally:
            self._record_metrics("get", start)
        if value is None:
            _CACHE_MISSES.labels(self.namespace).inc()
            return None
        _CACHE_HITS.labels(self.namespace).inc()
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        try:
            return json.loads(value)
        except json.JSONDecodeError:  # pragma: no cover - unexpected payloads
            logger.warning("cache.get invalid json key=%s", key)
            return None

    def set_json(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | None = None,
    ) -> None:
        """Store ``value`` encoded as JSON under ``key``."""

        if not self.enabled:
            return
        payload = json.dumps(value, sort_keys=True)
        ttl = self.default_ttl if ttl is None else max(int(ttl), 0)
        start = time.perf_counter()
        try:
            if ttl:
                self.client.setex(key, ttl, payload)
            else:
                self.client.set(key, payload)
        except Exception:  # pragma: no cover - instrumentation only
            logger.exception("cache.set failed key=%s", key)
        finally:
            self._record_metrics("set", start)

    def invalidate(self, *keys: str) -> None:
        if not self.enabled or not keys:
            return
        start = time.perf_counter()
        try:
            self.client.delete(*keys)
        except Exception:  # pragma: no cover - instrumentation only
            logger.exception("cache.delete failed keys=%s", keys)
        finally:
            self._record_metrics("delete", start)

    def invalidate_prefix(self, prefix: str) -> None:
        if not self.enabled:
            return
        pattern = f"{prefix}" + ":*"
        start = time.perf_counter()
        try:
            to_delete: list[str] = []
            for key in self.client.scan_iter(match=pattern):
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                to_delete.append(key)
            if to_delete:
                self.client.delete(*to_delete)
        except AttributeError:  # pragma: no cover - fallback for stubs
            client = self.client
            store: MutableMapping[str, Any] | None = getattr(
                client,
                "store",
                None,
            )
            if store is None:
                return
            keys = [key for key in store if key.startswith(prefix)]
            for key in keys:
                store.pop(key, None)
        except Exception:  # pragma: no cover - instrumentation only
            logger.exception(
                "cache.invalidate_prefix failed prefix=%s",
                prefix,
            )
        finally:
            self._record_metrics("delete", start)

    # ------------------------------------------------------------------
    # High level helpers
    # ------------------------------------------------------------------
    def invalidate_profile(self, user_id: int) -> None:
        self.invalidate(self.profile_key(user_id))

    def invalidate_profiles(self, user_ids: Iterable[int]) -> None:
        keys = [self.profile_key(user_id) for user_id in user_ids]
        self.invalidate(*keys)

    def invalidate_user_collections(self) -> None:
        self.invalidate_prefix(self.key("users", "list"))
        self.invalidate_prefix(self.key("users", "search"))

    def build_hooks(self) -> CacheHooks:
        if self._hooks is None:
            self._hooks = CacheHooks(
                invalidate_profile=self.invalidate_profile,
                invalidate_collections=self.invalidate_user_collections,
            )
        return self._hooks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _hash_payload(self, payload: Mapping[str, object]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    def _record_metrics(self, operation: str, start: float | None) -> None:
        _CACHE_OPERATIONS.labels(self.namespace, operation).inc()
        if start is None:
            return
        duration = time.perf_counter() - start
        _CACHE_LATENCY.labels(self.namespace, operation).observe(duration)


__all__ = ["CacheService", "CacheHooks"]
