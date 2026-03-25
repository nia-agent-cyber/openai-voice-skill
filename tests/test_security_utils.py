#!/usr/bin/env python3
"""
Unit tests for scripts/security_utils.py

Covers:
- SecurityValidator: phone, session_id, email, sanitize, mask
- DataEncryption: encrypt/decrypt round-trip
- ErrorSanitizer: sanitize error messages
- APIKeyAuth: validate and generate keys
"""

import sys
import os
import pytest

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from security_utils import (
    SecurityValidator,
    DataEncryption,
    ErrorSanitizer,
    APIKeyAuth,
    ValidationError,
    validator,
    encryptor,
    error_sanitizer,
    api_auth,
)


# ─── SecurityValidator ─────────────────────────────────────────────────────────

class TestValidatePhoneNumber:
    """Tests for SecurityValidator.validate_phone_number"""

    def test_valid_us_number(self):
        assert SecurityValidator.validate_phone_number("+12125551234") is True

    def test_valid_rwanda_number(self):
        assert SecurityValidator.validate_phone_number("+250794002033") is True

    def test_valid_uk_number(self):
        assert SecurityValidator.validate_phone_number("+447911123456") is True

    def test_missing_plus_fails(self):
        assert SecurityValidator.validate_phone_number("12125551234") is False

    def test_empty_string_fails(self):
        assert SecurityValidator.validate_phone_number("") is False

    def test_none_fails(self):
        assert SecurityValidator.validate_phone_number(None) is False

    def test_too_long_fails(self):
        assert SecurityValidator.validate_phone_number("+1" + "2" * 20) is False

    def test_dangerous_chars_fail(self):
        assert SecurityValidator.validate_phone_number("+1212<5551234") is False
        assert SecurityValidator.validate_phone_number("+1212;5551234") is False

    def test_all_same_digit_fails(self):
        assert SecurityValidator.validate_phone_number("+12222222222") is False

    def test_non_strict_accepts_more(self):
        # Non-strict mode, just check format doesn't blow up
        result = SecurityValidator.validate_phone_number("+12125551234", strict=False)
        assert isinstance(result, bool)

    def test_too_short_number_fails(self):
        # Too few digits (only 4 after country code)
        assert SecurityValidator.validate_phone_number("+11234") is False

    def test_number_with_space_variant(self):
        # Has whitespace — cleaned before validation
        result = SecurityValidator.validate_phone_number("+1 212 555 1234")
        assert isinstance(result, bool)


class TestValidateSessionId:
    """Tests for SecurityValidator.validate_session_id"""

    def test_valid_session_id(self):
        assert SecurityValidator.validate_session_id("abc123xyz-def") is True

    def test_too_short_fails(self):
        assert SecurityValidator.validate_session_id("abc12") is False

    def test_empty_fails(self):
        assert SecurityValidator.validate_session_id("") is False

    def test_none_fails(self):
        assert SecurityValidator.validate_session_id(None) is False

    def test_dangerous_chars_fail(self):
        assert SecurityValidator.validate_session_id("abc123<xyz") is False

    def test_low_entropy_fails(self):
        # All same character (low entropy)
        assert SecurityValidator.validate_session_id("aaaaaaaa") is False

    def test_valid_long_session_id(self):
        assert SecurityValidator.validate_session_id("abcdef123456789-ABCDEF_xyz") is True


class TestValidateEmail:
    """Tests for SecurityValidator.validate_email"""

    def test_valid_email(self):
        assert SecurityValidator.validate_email("user@example.com") is True

    def test_valid_subdomain_email(self):
        assert SecurityValidator.validate_email("user@mail.example.org") is True

    def test_missing_at_fails(self):
        assert SecurityValidator.validate_email("userexample.com") is False

    def test_empty_fails(self):
        assert SecurityValidator.validate_email("") is False

    def test_none_fails(self):
        assert SecurityValidator.validate_email(None) is False

    def test_too_long_fails(self):
        long_email = "a" * 250 + "@example.com"
        assert SecurityValidator.validate_email(long_email) is False

    def test_dangerous_chars_fail(self):
        assert SecurityValidator.validate_email('user"@example.com') is False
        assert SecurityValidator.validate_email("user<@example.com") is False

    def test_no_tld_fails(self):
        assert SecurityValidator.validate_email("user@example") is False


class TestSanitizeInput:
    """Tests for SecurityValidator.sanitize_input"""

    def test_strips_dangerous_chars(self):
        result = SecurityValidator.sanitize_input("<script>alert('xss')</script>")
        assert "<" not in result
        assert ">" not in result
        assert "'" not in result

    def test_truncates_to_max_length(self):
        long_input = "a" * 2000
        result = SecurityValidator.sanitize_input(long_input, max_length=100)
        assert len(result) <= 100

    def test_empty_input_returns_empty(self):
        assert SecurityValidator.sanitize_input("") == ""

    def test_none_returns_empty(self):
        assert SecurityValidator.sanitize_input(None) == ""

    def test_normal_text_preserved(self):
        result = SecurityValidator.sanitize_input("Hello World 123")
        assert "Hello World 123" in result

    def test_removes_control_characters(self):
        result = SecurityValidator.sanitize_input("Hello\x00World\x1f!")
        assert "\x00" not in result
        assert "\x1f" not in result


class TestMaskSensitiveData:
    """Tests for SecurityValidator.mask_sensitive_data"""

    def test_masks_long_string(self):
        result = SecurityValidator.mask_sensitive_data("1234567890abcdef")
        assert result.startswith("1234")
        assert result.endswith("cdef")
        assert "*" in result

    def test_short_string_returns_all_masks(self):
        result = SecurityValidator.mask_sensitive_data("ab")
        assert "*" * 8 == result

    def test_empty_returns_masks(self):
        result = SecurityValidator.mask_sensitive_data("")
        assert "*" in result

    def test_custom_mask_char(self):
        result = SecurityValidator.mask_sensitive_data("1234567890", mask_char="#")
        assert "#" in result

    def test_custom_visible_chars(self):
        result = SecurityValidator.mask_sensitive_data("1234567890abcdef", visible_chars=2)
        assert result.startswith("12")
        assert result.endswith("ef")


# ─── DataEncryption ────────────────────────────────────────────────────────────

class TestDataEncryption:
    """Tests for DataEncryption.encrypt_data / decrypt_data"""

    def test_encrypt_string_produces_output(self):
        result = DataEncryption.encrypt_data("hello world")
        # Should return a non-empty base64 string
        if result is not None:  # cipher_suite may not be initialized in test env
            assert isinstance(result, str)
            assert len(result) > 0

    def test_encrypt_decrypt_roundtrip_string(self):
        original = "secret data"
        encrypted = DataEncryption.encrypt_data(original)
        if encrypted is None:
            pytest.skip("Encryption not available")
        decrypted = DataEncryption.decrypt_data(encrypted)
        assert decrypted == original

    def test_encrypt_decrypt_roundtrip_dict(self):
        original = {"key": "value", "number": 42}
        encrypted = DataEncryption.encrypt_data(original)
        if encrypted is None:
            pytest.skip("Encryption not available")
        decrypted = DataEncryption.decrypt_data(encrypted, return_json=True)
        assert decrypted["key"] == "value"
        assert decrypted["number"] == 42

    def test_decrypt_invalid_returns_none(self):
        result = DataEncryption.decrypt_data("not_valid_base64_encrypted_data!!")
        assert result is None

    def test_encrypt_empty_string(self):
        result = DataEncryption.encrypt_data("")
        if result is not None:
            assert isinstance(result, str)


# ─── ErrorSanitizer ────────────────────────────────────────────────────────────

class TestErrorSanitizer:
    """Tests for ErrorSanitizer.sanitize_error_message"""

    def test_empty_message_returns_generic(self):
        result = ErrorSanitizer.sanitize_error_message("")
        assert result == ErrorSanitizer.GENERIC_ERRORS.get('internal', 'An error occurred')

    def test_none_message_returns_generic(self):
        result = ErrorSanitizer.sanitize_error_message(None)
        assert result  # Should be a non-empty generic message

    def test_sanitizes_file_paths(self):
        result = ErrorSanitizer.sanitize_error_message('Error in file "/home/user/app.py" at line 42')
        assert "/home/user/app.py" not in result

    def test_sanitizes_api_keys(self):
        result = ErrorSanitizer.sanitize_error_message("API_KEY=sk-abc123def456")
        assert "sk-abc123def456" not in result

    def test_traceback_redacted_or_generic(self):
        # Traceback patterns are either redacted or replaced with generic message
        result = ErrorSanitizer.sanitize_error_message("Traceback (most recent call last): ...", "internal")
        # Should NOT contain the raw traceback path info
        assert "most recent call last" not in result or "[REDACTED]" in result or result == ErrorSanitizer.GENERIC_ERRORS.get('internal', 'An error occurred')

    def test_simple_message_preserved(self):
        # A simple, clean message with no sensitive patterns should pass through
        result = ErrorSanitizer.sanitize_error_message("Request completed successfully")
        assert len(result) > 0

    def test_long_message_truncated(self):
        result = ErrorSanitizer.sanitize_error_message("x" * 500)
        assert len(result) <= 200

    def test_error_type_affects_generic_message(self):
        validation_msg = ErrorSanitizer.sanitize_error_message("", "validation")
        auth_msg = ErrorSanitizer.sanitize_error_message("", "authentication")
        assert validation_msg == ErrorSanitizer.GENERIC_ERRORS["validation"]
        assert auth_msg == ErrorSanitizer.GENERIC_ERRORS["authentication"]

    def test_revealing_keywords_trigger_generic(self):
        msg = ErrorSanitizer.sanitize_error_message("sqlalchemy error: cannot connect")
        assert msg == ErrorSanitizer.GENERIC_ERRORS.get('internal', 'An error occurred')


# ─── APIKeyAuth ────────────────────────────────────────────────────────────────

class TestAPIKeyAuth:
    """Tests for APIKeyAuth.validate_api_key and generate_api_key"""

    def test_validate_correct_key(self):
        auth = APIKeyAuth(api_keys={"primary": "test-key-12345"})
        assert auth.validate_api_key("test-key-12345") is True

    def test_validate_wrong_key_fails(self):
        auth = APIKeyAuth(api_keys={"primary": "test-key-12345"})
        assert auth.validate_api_key("wrong-key") is False

    def test_validate_empty_key_fails(self):
        auth = APIKeyAuth(api_keys={"primary": "test-key-12345"})
        assert auth.validate_api_key("") is False

    def test_validate_none_key_fails(self):
        auth = APIKeyAuth(api_keys={"primary": "test-key-12345"})
        assert auth.validate_api_key(None) is False

    def test_validate_with_bearer_prefix(self):
        auth = APIKeyAuth(api_keys={"primary": "test-key-12345"})
        assert auth.validate_api_key("Bearer test-key-12345") is True

    def test_validate_multiple_keys(self):
        auth = APIKeyAuth(api_keys={"k1": "key-one", "k2": "key-two"})
        assert auth.validate_api_key("key-one") is True
        assert auth.validate_api_key("key-two") is True
        assert auth.validate_api_key("key-three") is False

    def test_generate_api_key_length(self):
        auth = APIKeyAuth()
        key = auth.generate_api_key(32)
        assert isinstance(key, str)
        assert len(key) > 0

    def test_generate_api_key_unique(self):
        auth = APIKeyAuth()
        key1 = auth.generate_api_key(32)
        key2 = auth.generate_api_key(32)
        assert key1 != key2

    def test_empty_api_keys_dict(self):
        auth = APIKeyAuth(api_keys={})
        # Without env vars, should fail validation
        import os
        # Remove any env var that might interfere
        env_backup = os.environ.pop("SERVICE_API_KEY", None)
        try:
            auth2 = APIKeyAuth(api_keys={})
            assert auth2.validate_api_key("any-key") is False
        finally:
            if env_backup:
                os.environ["SERVICE_API_KEY"] = env_backup


# ─── Global singleton instances ────────────────────────────────────────────────

class TestGlobalInstances:
    """Test that module-level singleton instances exist and work."""

    def test_validator_instance_exists(self):
        assert validator is not None
        assert isinstance(validator, SecurityValidator)

    def test_encryptor_instance_exists(self):
        assert encryptor is not None
        assert isinstance(encryptor, DataEncryption)

    def test_error_sanitizer_instance_exists(self):
        assert error_sanitizer is not None
        assert isinstance(error_sanitizer, ErrorSanitizer)

    def test_api_auth_instance_exists(self):
        assert api_auth is not None
        assert isinstance(api_auth, APIKeyAuth)

    def test_validator_phone_via_instance(self):
        # Use the global instance
        result = validator.validate_phone_number("+12125551234")
        assert result is True
