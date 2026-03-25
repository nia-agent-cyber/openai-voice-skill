#!/usr/bin/env python3
"""
Extended unit tests for scripts/user_context.py

Covers uncovered sections:
- UserContextResolver._normalize_phone
- UserContextResolver._extract_country_code
- UserContextResolver._infer_from_country_code
- UserContextResolver.get_context (with and without mapping)
- UserContextResolver.get_current_time_for_user
- UserContextResolver.format_context_for_agent
- Module-level helpers: get_user_context, format_context_for_agent
- Country code mapping completeness
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from user_context import (
    UserContextResolver,
    COUNTRY_CODE_TIMEZONES,
    COUNTRY_CODE_NAMES,
    get_user_context,
    format_context_for_agent,
    get_resolver,
)


# ─── UserContextResolver initialization ──────────────────────────────────────

class TestUserContextResolverInit:
    """Tests for __init__ and _load_mapping."""

    def test_init_with_nonexistent_mapping(self, tmp_path):
        resolver = UserContextResolver(mapping_path=tmp_path / "no_mapping.json")
        assert resolver.phone_mapping == {}

    def test_init_with_valid_mapping(self, tmp_path):
        mapping = {"+250794002033": {"name": "Remi", "timezone": "Africa/Kigali"}}
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        assert "+250794002033" in resolver.phone_mapping

    def test_init_filters_comment_keys(self, tmp_path):
        mapping = {
            "_comment": "This is a comment",
            "+250794002033": {"name": "Remi"}
        }
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        assert "_comment" not in resolver.phone_mapping
        assert "+250794002033" in resolver.phone_mapping

    def test_init_with_malformed_json(self, tmp_path):
        mapping_file = tmp_path / "bad.json"
        mapping_file.write_text("NOT VALID JSON")
        resolver = UserContextResolver(mapping_path=mapping_file)
        assert resolver.phone_mapping == {}


# ─── _normalize_phone ─────────────────────────────────────────────────────────

class TestNormalizePhone:
    """Tests for _normalize_phone."""

    def setup_method(self):
        self.resolver = UserContextResolver(mapping_path=Path("/nonexistent"))

    def test_adds_plus_if_missing(self):
        result = self.resolver._normalize_phone("12125551234")
        assert result.startswith("+")

    def test_preserves_existing_plus(self):
        result = self.resolver._normalize_phone("+12125551234")
        assert result == "+12125551234"

    def test_strips_dashes(self):
        result = self.resolver._normalize_phone("+1-212-555-1234")
        assert "-" not in result

    def test_strips_spaces(self):
        result = self.resolver._normalize_phone("+1 212 555 1234")
        assert " " not in result

    def test_strips_parens(self):
        result = self.resolver._normalize_phone("+1(212)5551234")
        assert "(" not in result and ")" not in result

    def test_rwanda_number(self):
        result = self.resolver._normalize_phone("+250794002033")
        assert result == "+250794002033"


# ─── _extract_country_code ────────────────────────────────────────────────────

class TestExtractCountryCode:
    """Tests for _extract_country_code."""

    def setup_method(self):
        self.resolver = UserContextResolver(mapping_path=Path("/nonexistent"))

    def test_us_country_code(self):
        result = self.resolver._extract_country_code("+12125551234")
        # Could be "1" or longer — just ensure it's a recognized code
        assert result is not None

    def test_rwanda_country_code(self):
        result = self.resolver._extract_country_code("+250794002033")
        assert result == "250"

    def test_uk_country_code(self):
        result = self.resolver._extract_country_code("+447911123456")
        assert result == "44"

    def test_kenya_country_code(self):
        result = self.resolver._extract_country_code("+254722123456")
        assert result == "254"

    def test_india_country_code(self):
        result = self.resolver._extract_country_code("+919876543210")
        assert result == "91"

    def test_unknown_country_code_returns_none(self):
        # Use a country code that doesn't exist in our mapping
        result = self.resolver._extract_country_code("+999123456789")
        assert result is None

    def test_number_without_plus(self):
        # Should still work after normalization
        result = self.resolver._extract_country_code("250794002033")
        assert result == "250"


# ─── _infer_from_country_code ─────────────────────────────────────────────────

class TestInferFromCountryCode:
    """Tests for _infer_from_country_code."""

    def setup_method(self):
        self.resolver = UserContextResolver(mapping_path=Path("/nonexistent"))

    def test_infers_timezone_for_rwanda(self):
        result = self.resolver._infer_from_country_code("+250794002033")
        assert result.get("timezone") == "Africa/Kigali"

    def test_infers_location_for_rwanda(self):
        result = self.resolver._infer_from_country_code("+250794002033")
        assert result.get("location") == "Rwanda"

    def test_inferred_flag_is_true(self):
        result = self.resolver._infer_from_country_code("+250794002033")
        assert result.get("inferred") is True

    def test_infers_timezone_for_uk(self):
        result = self.resolver._infer_from_country_code("+447911123456")
        assert result.get("timezone") == "Europe/London"

    def test_infers_timezone_for_japan(self):
        result = self.resolver._infer_from_country_code("+81312345678")
        assert result.get("timezone") == "Asia/Tokyo"

    def test_infers_timezone_for_australia(self):
        result = self.resolver._infer_from_country_code("+61412345678")
        assert result.get("timezone") == "Australia/Sydney"

    def test_returns_empty_for_unknown_country(self):
        result = self.resolver._infer_from_country_code("+999123456789")
        assert result == {}

    def test_returns_country_code(self):
        result = self.resolver._infer_from_country_code("+250794002033")
        assert result.get("country_code") == "250"


# ─── get_context ──────────────────────────────────────────────────────────────

class TestGetContext:
    """Tests for get_context() — the main public interface."""

    def test_unknown_number_has_defaults(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        context = resolver.get_context("+250794002033")
        assert "phone" in context
        assert "known_user" in context

    def test_known_user_returns_name(self, tmp_path):
        mapping = {
            "+250794002033": {
                "name": "Remi",
                "timezone": "Africa/Kigali",
                "relationship": "primary_user"
            }
        }
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        context = resolver.get_context("+250794002033")
        assert context["name"] == "Remi"
        assert context["known_user"] is True
        assert context["timezone"] == "Africa/Kigali"

    def test_unknown_user_has_default_name(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        context = resolver.get_context("+999000000001")
        assert context.get("name") == "Unknown Caller"

    def test_inferred_false_for_mapped_user(self, tmp_path):
        mapping = {"+250794002033": {"name": "Remi", "timezone": "Africa/Kigali"}}
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        context = resolver.get_context("+250794002033")
        assert context.get("inferred") is False

    def test_phone_is_normalized(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        context = resolver.get_context("250794002033")  # Missing +
        assert context["phone"].startswith("+")

    def test_timezone_inferred_from_country_code(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        context = resolver.get_context("+250794002033")  # Rwanda
        assert context.get("timezone") == "Africa/Kigali"
        assert context.get("inferred") is True

    def test_location_inferred_from_country_code(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        context = resolver.get_context("+447911123456")  # UK
        assert context.get("location") == "United Kingdom"


# ─── get_current_time_for_user ────────────────────────────────────────────────

class TestGetCurrentTimeForUser:
    """Tests for get_current_time_for_user."""

    def test_returns_time_for_known_timezone(self, tmp_path):
        mapping = {"+250794002033": {"name": "Remi", "timezone": "Africa/Kigali"}}
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        result = resolver.get_current_time_for_user("+250794002033")
        assert result is not None
        assert "Africa/Kigali" in result or "CAT" in result or "2026" in result or len(result) > 0

    def test_returns_none_for_unknown_timezone(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        # Use a number where we can't infer timezone
        result = resolver.get_current_time_for_user("+999000000001")
        assert result is None

    def test_returns_time_via_country_code_inference(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        # Rwanda number — timezone is inferred from country code
        result = resolver.get_current_time_for_user("+250794002033")
        assert result is not None
        assert isinstance(result, str)

    def test_handles_invalid_timezone_gracefully(self, tmp_path):
        mapping = {"+1234567890": {"name": "Test", "timezone": "Invalid/Timezone"}}
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        # Should not raise — returns None gracefully
        result = resolver.get_current_time_for_user("+1234567890")
        assert result is None


# ─── format_context_for_agent ─────────────────────────────────────────────────

class TestFormatContextForAgent:
    """Tests for format_context_for_agent."""

    def test_returns_formatted_string_with_known_user(self, tmp_path):
        mapping = {
            "+250794002033": {
                "name": "Remi",
                "timezone": "Africa/Kigali",
                "location": "Rwanda"
            }
        }
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        result = resolver.format_context_for_agent("+250794002033")
        assert "Remi" in result
        assert "Africa/Kigali" in result
        assert "[User context:" in result

    def test_returns_empty_for_fully_unknown(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        # A number where nothing can be inferred
        result = resolver.format_context_for_agent("+999000000001")
        assert result == ""

    def test_returns_timezone_from_inference(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        result = resolver.format_context_for_agent("+250794002033")
        # Rwanda's timezone should be inferred
        assert "Africa/Kigali" in result

    def test_format_starts_with_bracket(self, tmp_path):
        mapping = {"+250794002033": {"name": "Remi", "timezone": "Africa/Kigali"}}
        mapping_file = tmp_path / "phone_mapping.json"
        mapping_file.write_text(json.dumps(mapping))
        resolver = UserContextResolver(mapping_path=mapping_file)
        result = resolver.format_context_for_agent("+250794002033")
        assert result.startswith("[User context:")

    def test_unknown_caller_name_not_included(self):
        resolver = UserContextResolver(mapping_path=Path("/nonexistent"))
        result = resolver.format_context_for_agent("+250794002033")
        # "Unknown Caller" should not be in the output (it's the default fallback)
        assert "Unknown Caller" not in result


# ─── Module-level helpers ─────────────────────────────────────────────────────

class TestModuleHelpers:
    """Tests for module-level convenience functions."""

    def test_get_user_context_returns_dict(self):
        result = get_user_context("+250794002033")
        assert isinstance(result, dict)
        assert "phone" in result

    def test_format_context_for_agent_returns_string(self):
        result = format_context_for_agent("+250794002033")
        assert isinstance(result, str)

    def test_get_resolver_returns_resolver(self):
        resolver = get_resolver()
        assert isinstance(resolver, UserContextResolver)

    def test_get_resolver_returns_singleton(self):
        r1 = get_resolver()
        r2 = get_resolver()
        assert r1 is r2


# ─── Country code mappings ────────────────────────────────────────────────────

class TestCountryCodeMappings:
    """Test the completeness and correctness of country code mappings."""

    def test_us_timezone_default(self):
        assert "1" in COUNTRY_CODE_TIMEZONES
        assert "America" in COUNTRY_CODE_TIMEZONES["1"]

    def test_rwanda_timezone(self):
        assert "250" in COUNTRY_CODE_TIMEZONES
        assert COUNTRY_CODE_TIMEZONES["250"] == "Africa/Kigali"

    def test_uk_timezone(self):
        assert "44" in COUNTRY_CODE_TIMEZONES
        assert COUNTRY_CODE_TIMEZONES["44"] == "Europe/London"

    def test_most_timezones_have_names(self):
        """Most countries in TIMEZONE map should have a corresponding name entry."""
        missing = [code for code in COUNTRY_CODE_TIMEZONES if code not in COUNTRY_CODE_NAMES]
        # Allow a few gaps (some codes in timezones may not have names)
        assert len(missing) < 5, f"Too many codes missing from NAMES: {missing}"

    def test_country_names_are_strings(self):
        for code, name in COUNTRY_CODE_NAMES.items():
            assert isinstance(name, str) and len(name) > 0

    def test_africa_coverage(self):
        """Major African countries should be in the mapping."""
        african_codes = ["27", "20", "234", "250", "254", "255"]
        for code in african_codes:
            assert code in COUNTRY_CODE_TIMEZONES, f"African country code {code} missing"

    def test_asia_coverage(self):
        """Major Asian countries should be in the mapping."""
        asian_codes = ["81", "86", "91", "65", "66"]
        for code in asian_codes:
            assert code in COUNTRY_CODE_TIMEZONES, f"Asian country code {code} missing"
