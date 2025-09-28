"""Helpers for serializing string lists."""

from __future__ import annotations

import json
from typing import Iterable


def normalize_string_list(values: Iterable[str] | None) -> list[str]:
    """Normalize a collection of strings into a unique, ordered list."""

    normalized: list[str] = []
    seen: set[str] = set()
    if not values:
        return normalized
    for value in values:
        if value is None:
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        normalized.append(lowered)
        seen.add(lowered)
    return normalized


def encode_string_list(values: Iterable[str] | None) -> str | None:
    """Serialize a collection of strings as JSON for persistence."""

    normalized = normalize_string_list(values)
    if not normalized:
        return None
    return json.dumps(normalized, separators=(",", ":"))


def decode_string_list(raw: str | None) -> list[str]:
    """Decode a JSON-encoded list of strings."""

    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(item) for item in data if isinstance(item, str)]
    return []
