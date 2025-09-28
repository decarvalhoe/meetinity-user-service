from __future__ import annotations

from src.services.cache import CacheService


class StubRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def set(self, key: str, value: str) -> None:
        self.store[key] = value

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)

    def scan_iter(self, match: str | None = None):
        keys = list(self.store.keys())
        if match is None:
            for key in keys:
                yield key.encode("utf-8")
            return
        if match.endswith("*"):
            prefix = match[:-1]
            for key in keys:
                if key.startswith(prefix):
                    yield key.encode("utf-8")
        elif match in self.store:
            yield match.encode("utf-8")


def test_cache_service_disabled_operations():
    cache = CacheService(None, 10)
    assert cache.enabled is False
    assert cache.get_json("missing") is None
    cache.set_json("unused", {"value": 1})
    cache.invalidate("unused")
    cache.invalidate_prefix("prefix")
    cache._record_metrics("noop", None)


def test_cache_service_store_retrieve_and_invalidate():
    redis = StubRedis()
    cache = CacheService(redis, 5)

    listing_key = cache.listing_key(
        page=1,
        per_page=20,
        sort=("created_at", "desc"),
        filters={"industry": "tech"},
    )
    cache.set_json(listing_key, {"items": [1, 2]})
    assert cache.get_json(listing_key) == {"items": [1, 2]}

    redis.store[listing_key] = b"{\"items\": [3]}"
    assert cache.get_json(listing_key) == {"items": [3]}

    cache.set_json(listing_key, {"items": [4]}, ttl=0)
    assert redis.store[listing_key] == "{\"items\": [4]}"

    cache.invalidate_prefix(cache.key("users", "list"))
    assert listing_key not in redis.store

    profile_key = cache.profile_key(1)
    cache.set_json(profile_key, {"id": 1})
    cache.invalidate_profiles([1])
    assert profile_key not in redis.store

    search_key = cache.search_key(
        query="alice",
        page=1,
        per_page=10,
        sort=("created_at", "desc"),
        filters={},
    )
    cache.set_json(search_key, {"items": []})
    hooks = cache.build_hooks()
    hooks.invalidate_collections()
    assert search_key not in redis.store
    cache.set_json(profile_key, {"id": 2})
    hooks.invalidate_profile(1)
    assert profile_key not in redis.store
