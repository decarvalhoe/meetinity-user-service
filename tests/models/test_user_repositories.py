import pytest
from sqlalchemy.exc import IntegrityError
from unittest.mock import MagicMock

from src.db.session import session_scope
from src.models.repositories import RepositoryError, UserRepository
from src.models.repositories.preferences import UserPreferenceRepository
from src.models.repositories.sessions import UserSessionRepository
from src.models.repositories.users import UserCoreRepository
from src.models.user import User, UserPreference


def test_set_preferences_updates_and_removes_entries():
    session = MagicMock()
    repo = UserPreferenceRepository(session)
    user = User(email="user@example.com")

    keep = UserPreference(key="newsletter", value="1")
    remove = UserPreference(key="theme", value="light")
    user.preferences.append(keep)
    user.preferences.append(remove)

    updated_user = repo.set_preferences(
        user,
        {"newsletter": "0", "locale": None},
    )

    assert updated_user is user
    assert keep.value == "0"
    keys = {pref.key for pref in user.preferences}
    assert "newsletter" in keys
    assert any(pref.key == "locale" for pref in user.preferences)
    session.delete.assert_called_once_with(remove)
    session.flush.assert_called_once()


def test_repository_error_on_integrity_failure_triggers_rollback():
    session = MagicMock()
    session.flush.side_effect = IntegrityError("stmt", {}, Exception("boom"))
    repo = UserSessionRepository(session)
    user = User(email="session@example.com")

    with pytest.raises(RepositoryError) as excinfo:
        repo.create_session(user, session_token="token")

    session.rollback.assert_called_once()
    assert excinfo.value.status_code == 409


def test_user_repository_delegates_to_components(monkeypatch):
    session = MagicMock()
    repo = UserRepository(session)

    session.get.return_value = "user"
    assert repo.get(1) == "user"
    session.get.assert_called_once()

    with pytest.raises(AttributeError):
        getattr(repo, "nonexistent")


def test_user_repository_allows_class_level_monkeypatch(monkeypatch):
    captured: list[int] = []

    def fake_get(self, user_id: int):
        captured.append(user_id)
        return "patched"

    monkeypatch.setattr(UserRepository, "get", fake_get)
    repo = UserRepository(MagicMock())
    assert repo.get(42) == "patched"
    assert captured == [42]


def test_user_repository_getattr_delegation(monkeypatch):
    monkeypatch.delattr(UserRepository, "get")
    session = MagicMock()
    repo = UserRepository(session)
    session.get.return_value = "delegated"
    assert repo.get(5) == "delegated"


def test_delegate_registration_branches():
    import src.models.repositories as repo_module

    UserCoreRepository.temp_value = 1
    UserPreferenceRepository.temp_callable = lambda self: None
    setattr(UserRepository, "temp_callable", lambda self: "existing")
    removed_create_user = False
    if hasattr(UserRepository, "create_user"):
        delattr(UserRepository, "create_user")
        removed_create_user = True

    try:
        for repository in repo_module._DELEGATED_REPOSITORIES:
            for name, attr in repository.__dict__.items():
                if name.startswith("_"):
                    continue
                if not callable(attr):
                    continue
                if hasattr(UserRepository, name):
                    continue
                setattr(UserRepository, name, repo_module._make_delegate(name))
    finally:
        delattr(UserCoreRepository, "temp_value")
        delattr(UserPreferenceRepository, "temp_callable")
        delattr(UserRepository, "temp_callable")
        if removed_create_user:
            setattr(
                UserRepository,
                "create_user",
                repo_module._make_delegate("create_user"),
            )


def test_bulk_import_users_creates_and_updates_records():
    with session_scope() as session:
        repo = UserRepository(session)
        created = repo.bulk_import_users(
            [
                {
                    "email": "bulk-one@example.com",
                    "name": "Bulk One",
                    "location": "Paris",
                },
                {
                    "email": "bulk-two@example.com",
                    "name": "Bulk Two",
                    "industry": "Finance",
                },
            ]
        )
        assert len(created) == 2
        ids = {user.id for user in created}
        assert len(ids) == 2

    with session_scope() as session:
        repo = UserRepository(session)
        updated = repo.bulk_import_users(
            [
                {
                    "email": "bulk-one@example.com",
                    "name": "Bulk Uno",
                    "location": "Berlin",
                },
                {
                    "email": "bulk-three@example.com",
                    "name": "Bulk Three",
                    "industry": "Technology",
                },
            ]
        )
        assert len(updated) == 2
        refreshed = repo.get_by_email("bulk-one@example.com")
        assert refreshed is not None
        assert refreshed.name == "Bulk Uno"
        assert refreshed.location == "Berlin"
        third = repo.get_by_email("bulk-three@example.com")
        assert third is not None
