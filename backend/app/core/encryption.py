"""Encryption utilities for sensitive data."""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _get_encryption_key() -> bytes:
    """Derive a Fernet key from the JWT secret.

    Uses the JWT secret as the base for the encryption key.
    In production, use a separate ENCRYPTION_KEY environment variable.
    """
    settings = get_settings()
    # Use SHA256 to get 32 bytes, then base64 encode for Fernet
    key = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token for secure storage.

    Args:
        plaintext: The token to encrypt.

    Returns:
        Base64-encoded encrypted token.
    """
    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored token.

    Args:
        ciphertext: The encrypted token.

    Returns:
        The original plaintext token.

    Raises:
        ValueError: If decryption fails.
    """
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt token: {e}") from e
