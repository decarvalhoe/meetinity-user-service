"""Application-level encryption and token hashing utilities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Sequence

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(RuntimeError):
    """Raised when encryption or decryption fails."""


def _load_key(key: str) -> tuple[Fernet, bytes]:
    """Instantiate a ``Fernet`` instance from a base64 encoded key."""

    key_bytes = key.strip().encode()
    fernet = Fernet(key_bytes)
    raw = base64.urlsafe_b64decode(key_bytes)
    return fernet, raw


@dataclass(slots=True)
class ApplicationEncryptor:
    """Helper responsible for encrypting payloads and hashing tokens."""

    _primary: Fernet
    _fallbacks: Sequence[Fernet]
    _primary_hash_key: bytes
    _fallback_hash_keys: Sequence[bytes]
    rotation_days: int = 90

    @classmethod
    def from_keys(
        cls,
        *,
        primary_key: str,
        fallback_keys: Iterable[str] | None = None,
        rotation_days: int = 90,
    ) -> "ApplicationEncryptor":
        """Build an encryptor from textual keys.

        Args:
            primary_key: Base64 encoded primary key.
            fallback_keys: Optional iterable of historical keys for
                rotation.
            rotation_days: Maximum age (in days) before re-encryption is
                advised.
        """

        if not primary_key:
            raise ValueError("primary encryption key is required")
        primary, primary_hash = _load_key(primary_key)
        fallback_instances: list[Fernet] = []
        fallback_hashes: list[bytes] = []
        for key in fallback_keys or []:
            if not key:
                continue
            instance, hash_key = _load_key(key)
            fallback_instances.append(instance)
            fallback_hashes.append(hash_key)
        return cls(
            _primary=primary,
            _fallbacks=fallback_instances,
            _primary_hash_key=primary_hash,
            _fallback_hash_keys=fallback_hashes,
            rotation_days=rotation_days,
        )

    def encrypt_text(self, value: str) -> str:
        """Encrypt textual data with the primary key."""

        token = self._primary.encrypt(value.encode())
        return token.decode()

    def decrypt_text(self, value: str) -> str:
        """Attempt to decrypt a text payload using all configured keys."""

        token = value.encode()
        candidates = [self._primary, *self._fallbacks]
        for fernet in candidates:
            try:
                return fernet.decrypt(token).decode()
            except InvalidToken:
                continue
        raise EncryptionError("unable to decrypt payload with available keys")

    def encrypt_json(self, payload: dict[str, object] | list[object]) -> str:
        """Encrypt a JSON-serialisable payload."""

        serialized = json.dumps(
            payload, separators=(",", ":")
        )
        return self.encrypt_text(serialized)

    def decrypt_json(self, payload: str) -> object:
        """Decrypt a payload previously produced by :meth:`encrypt_json`."""

        decrypted = self.decrypt_text(payload)
        return json.loads(decrypted)

    def hash_token(self, token: str) -> str:
        """Generate a deterministic digest for ``token``."""

        digest = hmac.new(
            self._primary_hash_key,
            msg=token.encode(),
            digestmod=hashlib.sha256,
        )
        return digest.hexdigest()

    def token_candidates(self, token: str) -> List[str]:
        """Return all possible digests for ``token`` across rotated keys."""

        digests = [self.hash_token(token)]
        for key in self._fallback_hash_keys:
            digests.append(
                hmac.new(
                    key,
                    msg=token.encode(),
                    digestmod=hashlib.sha256,
                ).hexdigest()
            )
        return digests

    def verify_token(self, token: str, expected: str) -> bool:
        """Return ``True`` if any rotated hash matches ``expected``."""

        for digest in self.token_candidates(token):
            if hmac.compare_digest(digest, expected):
                return True
        return False

    def requires_rotation(self, encrypted_token: str) -> bool:
        """Return True when the encrypted token exceeds the rotation window."""

        try:
            issued_at = datetime.fromtimestamp(
                self._primary.extract_timestamp(encrypted_token.encode()),
                timezone.utc,
            )
        except (InvalidToken, ValueError):
            return True
        age = datetime.now(timezone.utc) - issued_at
        return age > timedelta(days=self.rotation_days)


__all__ = ["ApplicationEncryptor", "EncryptionError"]
