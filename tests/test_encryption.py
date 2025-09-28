import pytest

from src.config import get_config
from src.utils.encryption import ApplicationEncryptor, EncryptionError


def test_application_encryptor_roundtrip():
    config = get_config()
    encryptor = ApplicationEncryptor.from_keys(
        primary_key=config.encryption_primary_key,
        fallback_keys=config.encryption_fallback_keys,
        rotation_days=config.encryption_rotation_days,
    )

    secret = "sensitive-payload"
    token = encryptor.encrypt_text(secret)
    assert encryptor.decrypt_text(token) == secret

    digest = encryptor.hash_token("session-token")
    assert encryptor.verify_token("session-token", digest)
    assert not encryptor.verify_token("other", digest)
    assert encryptor.requires_rotation(token) is False


def test_encryptor_supports_fallback_keys():
    config = get_config()
    primary = config.encryption_primary_key
    alternate_encryptor = ApplicationEncryptor.from_keys(primary_key=primary)
    digest = alternate_encryptor.hash_token("legacy")

    rotated_encryptor = ApplicationEncryptor.from_keys(
        primary_key=primary,
        fallback_keys=[primary],
    )
    assert rotated_encryptor.verify_token("legacy", digest)


def test_encryptor_invalid_token_behaviour():
    config = get_config()
    encryptor = ApplicationEncryptor.from_keys(
        primary_key=config.encryption_primary_key
    )
    with pytest.raises(EncryptionError):
        encryptor.decrypt_text("invalid-token")
    assert encryptor.requires_rotation("invalid-token") is True
