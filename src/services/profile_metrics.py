"""Helpers to compute derived profile metrics for users."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.user import User
from src.utils.lists import decode_string_list


def calculate_profile_completeness(user: User) -> int:
    """Return a percentage describing how complete a profile is."""

    attributes: list[bool] = [
        bool(user.name and user.name.strip()),
        bool(user.title and user.title.strip()),
        bool(user.company and user.company.strip()),
        bool(user.location and user.location.strip()),
        bool(user.industry and user.industry.strip()),
        bool(user.bio and user.bio.strip()),
        bool(user.linkedin_url and user.linkedin_url.strip()),
        bool(_has_values(user.skills)),
        bool(_has_values(user.interests)),
        bool(user.photo_url and user.photo_url.strip()),
    ]
    completed = sum(1 for filled in attributes if filled)
    total = len(attributes)
    if total == 0:
        return 0
    return int(round((completed / total) * 100))


def calculate_trust_score(user: User) -> int:
    """Combine signals to compute a simple trust indicator."""

    score = 0
    score += min(40, (user.reputation_score or 0))
    score += min(30, (user.engagement_score or 0))
    score += min(20, (user.login_count or 0) * 2)
    if any(
        verification.status == "verified"
        for verification in user.verifications
    ):
        score += 10
    return max(0, min(100, score))


def infer_privacy_level(user: User) -> str:
    """Infer a privacy level based on stored preferences."""

    privacy_settings = user.privacy_settings or {}
    visibility = str(privacy_settings.get("profile_visibility", "")).lower()
    tokens_count = len(user.active_tokens or [])
    if visibility in {"private", "hidden"}:
        return "high"
    if visibility in {"network", "connections"}:
        return "medium"
    if tokens_count == 0:
        return "high"
    if tokens_count <= 1:
        return "medium"
    return "standard"


def update_profile_metrics(
    user: User,
    *,
    now: datetime | None = None,
) -> None:
    """Recalculate derived metrics on the given user."""

    user.profile_completeness = calculate_profile_completeness(user)
    user.trust_score = calculate_trust_score(user)
    user.privacy_level = infer_privacy_level(user)
    if user.deactivated_at and user.is_active:
        # Clear stale deactivation timestamps when reactivating the profile.
        user.deactivated_at = None
        user.reactivation_at = None
    if not user.is_active and user.deactivated_at is None:
        user.deactivated_at = _ensure_tz(now or datetime.now(timezone.utc))


def _ensure_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _has_values(encoded: str | None) -> bool:
    if not encoded:
        return False
    decoded = decode_string_list(encoded)
    return bool([item for item in decoded if item])
