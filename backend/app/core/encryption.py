"""Symmetric encryption helpers for user-provided API keys.

Uses Fernet (AES-128-CBC + HMAC-SHA256). The master key is read from
``settings.AI_KEYS_ENCRYPTION_KEY``. If absent, a deterministic key derived
from ``settings.SECRET_KEY`` is used (acceptable for dev, not recommended
for production).
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    """Return a Fernet instance using the configured encryption key."""
    raw = settings.AI_KEYS_ENCRYPTION_KEY
    if raw:
        # Accept both raw Fernet keys and arbitrary strings.
        try:
            return Fernet(raw.encode() if isinstance(raw, str) else raw)
        except (ValueError, Exception):
            pass
    # Fallback: derive a Fernet-compatible key from SECRET_KEY.
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt a plain-text API key. Returns a base64-encoded ciphertext string."""
    f = _get_fernet()
    return f.encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an encrypted API key back to plain text.

    Raises ``ValueError`` if the key cannot be decrypted.
    """
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_key.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt API key — encryption key may have changed") from exc


def mask_api_key(plain_key: str) -> str:
    """Return a masked version of the key for display purposes.

    Shows first 4 and last 4 characters with dots in between.
    """
    if len(plain_key) <= 10:
        return plain_key[:2] + "…" + plain_key[-2:]
    return plain_key[:4] + "…" + plain_key[-4:]
