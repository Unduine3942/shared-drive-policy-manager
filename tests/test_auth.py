"""Unit tests for shared_drive_manager.core.auth module."""
import pytest

from shared_drive_manager.core.auth import (
    generate_salt,
    hash_password,
    verify_password,
)


class TestGenerateSalt:
    """Tests for generate_salt()."""

    def test_generates_non_empty_salt(self):
        """Salt should be a non-empty string."""
        salt = generate_salt()
        assert isinstance(salt, str)
        assert len(salt) > 0

    def test_generates_unique_salts(self):
        """Successive calls should generate different salts."""
        salt1 = generate_salt()
        salt2 = generate_salt()
        assert salt1 != salt2

    def test_salt_is_hex_string(self):
        """Salt should be a valid hex string (32 chars for 16 bytes)."""
        salt = generate_salt()
        # 16 bytes = 32 hex characters
        assert len(salt) == 32
        try:
            int(salt, 16)
        except ValueError:
            pytest.fail("Salt is not a valid hex string")


class TestHashPassword:
    """Tests for hash_password()."""

    def test_hash_non_empty_password(self):
        """Hashing a non-empty password should produce a hash."""
        password = "MySecurePassword"
        salt = generate_salt()
        hash_result = hash_password(password, salt)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_hash_is_deterministic(self):
        """Same password + salt should always produce the same hash."""
        password = "TestPassword123"
        salt = generate_salt()
        hash1 = hash_password(password, salt)
        hash2 = hash_password(password, salt)
        assert hash1 == hash2

    def test_different_passwords_produce_different_hashes(self):
        """Different passwords with same salt should produce different hashes."""
        salt = generate_salt()
        hash1 = hash_password("password1", salt)
        hash2 = hash_password("password2", salt)
        assert hash1 != hash2

    def test_different_salts_produce_different_hashes(self):
        """Same password with different salts should produce different hashes."""
        password = "SamePassword"
        hash1 = hash_password(password, generate_salt())
        hash2 = hash_password(password, generate_salt())
        assert hash1 != hash2

    def test_hash_empty_password(self):
        """Hashing an empty password should work (viewer role scenario)."""
        password = ""
        salt = generate_salt()
        hash_result = hash_password(password, salt)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_hash_unicode_password(self):
        """Hashing passwords with unicode characters should work."""
        password = "Pässwörd_with_ümlauts_和中文"
        salt = generate_salt()
        hash_result = hash_password(password, salt)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_hash_special_characters(self):
        """Hashing passwords with special characters should work."""
        password = "!@#$%^&*()_+-=[]{}|;:',.<>?/`~"
        salt = generate_salt()
        hash_result = hash_password(password, salt)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_hash_long_password(self):
        """Hashing a very long password should work."""
        password = "x" * 10000
        salt = generate_salt()
        hash_result = hash_password(password, salt)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_hash_is_sha256_hex(self):
        """Hash should be a SHA-256 hex string (64 characters)."""
        password = "TestPassword"
        salt = generate_salt()
        hash_result = hash_password(password, salt)
        assert len(hash_result) == 64
        try:
            int(hash_result, 16)
        except ValueError:
            pytest.fail("Hash is not a valid hex string")


class TestVerifyPassword:
    """Tests for verify_password()."""

    def test_verify_correct_password(self):
        """Correct password should verify successfully."""
        password = "CorrectPassword123"
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        assert verify_password(password, stored_hash, salt) is True

    def test_verify_incorrect_password(self):
        """Incorrect password should fail verification."""
        password = "CorrectPassword123"
        wrong_password = "WrongPassword456"
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        assert verify_password(wrong_password, stored_hash, salt) is False

    def test_verify_empty_password(self):
        """Empty password verification should work (viewer role)."""
        password = ""
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        assert verify_password(password, stored_hash, salt) is True

    def test_verify_with_wrong_salt(self):
        """Using a different salt should fail verification."""
        password = "TestPassword"
        salt1 = generate_salt()
        salt2 = generate_salt()
        stored_hash = hash_password(password, salt1)
        assert verify_password(password, stored_hash, salt2) is False

    def test_verify_case_sensitive(self):
        """Password verification should be case-sensitive."""
        password = "MyPassword"
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        assert verify_password("mypassword", stored_hash, salt) is False
        assert verify_password("MYPASSWORD", stored_hash, salt) is False

    def test_verify_tampered_hash(self):
        """Modifying a single character of the hash should fail."""
        password = "TestPassword123"
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        # Flip a bit in the hash
        tampered = stored_hash[:-1] + ("0" if stored_hash[-1] != "0" else "1")
        assert verify_password(password, tampered, salt) is False

    def test_verify_unicode_password(self):
        """Verifying unicode passwords should work correctly."""
        password = "Pässwörd_和中文"
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        assert verify_password(password, stored_hash, salt) is True
        assert verify_password("wrongpassword", stored_hash, salt) is False

    def test_verify_special_characters_password(self):
        """Verifying passwords with special characters should work."""
        password = "!@#$%^&*()"
        salt = generate_salt()
        stored_hash = hash_password(password, salt)
        assert verify_password(password, stored_hash, salt) is True
        assert verify_password("!@#$%^&*(", stored_hash, salt) is False


class TestPasswordWorkflow:
    """Integration tests for complete password workflow."""

    def test_full_signup_and_login_workflow(self):
        """Simulate a user signup and login flow."""
        # User signs up
        new_password = "BrandNewPassword!23"
        salt = generate_salt()
        stored_hash = hash_password(new_password, salt)

        # User logs in with correct password
        assert verify_password(new_password, stored_hash, salt) is True

        # User tries to login with wrong password
        assert verify_password("WrongPassword123", stored_hash, salt) is False

    def test_multiple_users_different_salts(self):
        """Different users should have different salts even with same password."""
        password = "CommonPassword"
        salt1 = generate_salt()
        salt2 = generate_salt()

        hash1 = hash_password(password, salt1)
        hash2 = hash_password(password, salt2)

        # Both should verify correctly
        assert verify_password(password, hash1, salt1) is True
        assert verify_password(password, hash2, salt2) is True

        # But hashes are different
        assert hash1 != hash2

        # Each hash only works with its own salt
        assert verify_password(password, hash1, salt2) is False
        assert verify_password(password, hash2, salt1) is False
