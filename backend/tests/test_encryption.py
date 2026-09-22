"""Tests for encryption utilities."""

import pytest

from app.core.encryption import decrypt_token, encrypt_token


class TestEncryption:
    """Tests for token encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encryption and decryption are reversible."""
        original = "ghp_test_token_12345"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_encrypted_differs_from_original(self) -> None:
        """Test that encrypted token is different from original."""
        original = "ghp_test_token_12345"
        encrypted = encrypt_token(original)
        assert encrypted != original

    def test_different_tokens_produce_different_ciphertext(self) -> None:
        """Test that different tokens produce different ciphertext."""
        token1 = "ghp_token_1"
        token2 = "ghp_token_2"
        encrypted1 = encrypt_token(token1)
        encrypted2 = encrypt_token(token2)
        assert encrypted1 != encrypted2

    def test_same_token_produces_different_ciphertext(self) -> None:
        """Test that same token produces different ciphertext (due to random IV)."""
        token = "ghp_same_token"
        encrypted1 = encrypt_token(token)
        encrypted2 = encrypt_token(token)
        # Fernet uses random IV, so ciphertexts should differ
        assert encrypted1 != encrypted2

    def test_decrypt_both_ciphertexts_of_same_token(self) -> None:
        """Test that both ciphertexts of same token decrypt correctly."""
        token = "ghp_same_token"
        encrypted1 = encrypt_token(token)
        encrypted2 = encrypt_token(token)
        assert decrypt_token(encrypted1) == token
        assert decrypt_token(encrypted2) == token

    def test_decrypt_invalid_ciphertext(self) -> None:
        """Test that decrypting invalid ciphertext raises ValueError."""
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_token("not_a_valid_ciphertext")

    def test_encrypt_empty_string(self) -> None:
        """Test encrypting empty string."""
        encrypted = encrypt_token("")
        decrypted = decrypt_token(encrypted)
        assert decrypted == ""

    def test_encrypt_long_token(self) -> None:
        """Test encrypting a very long token."""
        long_token = "ghp_" + "a" * 1000
        encrypted = encrypt_token(long_token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == long_token

    def test_encrypt_unicode(self) -> None:
        """Test encrypting token with unicode characters."""
        unicode_token = "token_with_émojis_🔐"
        encrypted = encrypt_token(unicode_token)
        decrypted = decrypt_token(encrypted)
        assert decrypted == unicode_token
