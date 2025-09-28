import pytest

from src.models.repositories import RepositoryError, UserRepository
from src.services.transactions import transactional_session


def test_nested_transaction_reuses_same_session():
    with transactional_session(name="outer") as outer_session:
        with transactional_session(name="nested") as nested_session:
            assert nested_session is outer_session


def test_nested_transaction_rollback_on_repository_error():
    with pytest.raises(RepositoryError):
        with transactional_session(name="outer") as session:
            repo = UserRepository(session)
            repo.create_user(email="outer@example.com")
            with transactional_session(name="nested") as nested:
                nested_repo = UserRepository(nested)
                nested_repo.create_user(email="outer@example.com")

    with transactional_session(name="check") as session:
        repo = UserRepository(session)
        assert repo.get_by_email("outer@example.com") is None
