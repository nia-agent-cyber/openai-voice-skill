#!/usr/bin/env python3
"""
Tests for Inbound Call Handler (T4)

Tests authorization, context building, and caller history management.
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from inbound_handler import (
    normalize_phone,
    mask_phone,
    check_allowlist,
    authorize_caller,
    build_context,
    AuthorizeResponse,
    ContextRequest,
    CallerHistory,
    caller_history,
)


class TestPhoneNormalization:
    """Test phone number normalization."""
    
    def test_normalize_e164(self):
        """Already E.164 format."""
        assert normalize_phone("+14402915517") == "+14402915517"
    
    def test_normalize_without_plus(self):
        """Add + prefix."""
        assert normalize_phone("14402915517") == "+14402915517"
    
    def test_normalize_with_formatting(self):
        """Remove formatting characters."""
        assert normalize_phone("+1 (440) 291-5517") == "+14402915517"
        assert normalize_phone("1-440-291-5517") == "+14402915517"
    
    def test_normalize_empty(self):
        """Handle empty string."""
        assert normalize_phone("") == ""
    
    def test_mask_phone(self):
        """Test phone masking for PII protection."""
        assert mask_phone("+14402915517") == "+144****5517"
        assert mask_phone("123") == "****"


class TestAllowlistChecking:
    """Test allowlist matching logic."""
    
    def test_exact_match(self):
        """Exact number match."""
        allowlist = ["+14402915517", "+15551234567"]
        assert check_allowlist("+14402915517", allowlist) == "+14402915517"
        assert check_allowlist("+15551234567", allowlist) == "+15551234567"
        assert check_allowlist("+19999999999", allowlist) is None
    
    def test_wildcard(self):
        """Wildcard allows all."""
        allowlist = ["*"]
        assert check_allowlist("+14402915517", allowlist) == "*"
        assert check_allowlist("+19999999999", allowlist) == "*"
    
    def test_prefix_match(self):
        """Prefix matching with trailing *."""
        allowlist = ["+1440*"]
        assert check_allowlist("+14402915517", allowlist) == "+1440*"
        assert check_allowlist("+14401234567", allowlist) == "+1440*"
        assert check_allowlist("+15551234567", allowlist) is None
    
    def test_mixed_allowlist(self):
        """Mix of exact and prefix matches."""
        allowlist = ["+15551234567", "+1440*", "+44*"]
        assert check_allowlist("+15551234567", allowlist) == "+15551234567"
        assert check_allowlist("+14409876543", allowlist) == "+1440*"
        assert check_allowlist("+442071234567", allowlist) == "+44*"
        assert check_allowlist("+61412345678", allowlist) is None
    
    def test_empty_allowlist(self):
        """Empty allowlist matches nothing."""
        assert check_allowlist("+14402915517", []) is None
    
    def test_normalize_during_check(self):
        """Allowlist entries get normalized."""
        allowlist = ["1-440-291-5517"]
        assert check_allowlist("+14402915517", allowlist) == "1-440-291-5517"


class TestAuthorization:
    """Test authorization logic."""
    
    def test_open_policy(self):
        """Open policy accepts all."""
        config = {"policy": "open"}
        result = authorize_caller("+14402915517", config)
        
        assert result.authorized is True
        assert result.reason == "allowed"
        assert result.policy == "open"
    
    def test_allowlist_policy_match(self):
        """Allowlist policy with matching number."""
        config = {
            "policy": "allowlist",
            "allowFrom": ["+14402915517"]
        }
        result = authorize_caller("+14402915517", config)
        
        assert result.authorized is True
        assert result.reason == "allowlist_match"
        assert result.matched_entry == "+14402915517"
        assert result.policy == "allowlist"
    
    def test_allowlist_policy_no_match(self):
        """Allowlist policy with non-matching number."""
        config = {
            "policy": "allowlist",
            "allowFrom": ["+15551234567"]
        }
        result = authorize_caller("+14402915517", config)
        
        assert result.authorized is False
        assert result.reason == "denied"
        assert result.policy == "allowlist"
    
    def test_allowlist_policy_empty(self):
        """Empty allowlist rejects all (secure default)."""
        config = {
            "policy": "allowlist",
            "allowFrom": []
        }
        result = authorize_caller("+14402915517", config)
        
        assert result.authorized is False
        assert result.reason == "not_configured"
    
    def test_allowlist_policy_wildcard(self):
        """Allowlist with wildcard."""
        config = {
            "policy": "allowlist",
            "allowFrom": ["*"]
        }
        result = authorize_caller("+14402915517", config)
        
        assert result.authorized is True
        assert result.matched_entry == "*"
    
    def test_pairing_policy_fallback(self):
        """Pairing policy falls back to allowlist."""
        config = {
            "policy": "pairing",
            "allowFrom": ["+14402915517"]
        }
        result = authorize_caller("+14402915517", config)
        
        assert result.authorized is True
        assert result.policy == "pairing"


class TestContextBuilding:
    """Test session context building."""
    
    def setup_method(self):
        """Clear caller history before each test."""
        caller_history.clear()
    
    def test_new_caller_context(self):
        """Context for new caller."""
        request = ContextRequest(
            caller_phone="+14402915517",
            caller_city="Cleveland",
            caller_state="OH",
            caller_country="US"
        )
        
        context = build_context(request)
        
        assert context.session_key == "voice:14402915517"
        assert context.is_known_caller is False
        assert context.previous_call_count == 0
        assert "NEW CALLER" in context.context_instructions
        assert "Cleveland, OH, US" in context.context_instructions
    
    def test_known_caller_context(self):
        """Context for known caller with history."""
        # Add caller history
        caller_history["+14402915517"] = CallerHistory(
            phone="+14402915517",
            name="John Doe",
            call_count=3,
            last_call_at="2026-02-05T15:30:00Z",
            notes="Interested in API docs"
        )
        
        request = ContextRequest(caller_phone="+14402915517")
        context = build_context(request)
        
        assert context.is_known_caller is True
        assert context.caller_name == "John Doe"
        assert context.previous_call_count == 3
        assert "CALLER HISTORY" in context.context_instructions
        assert "John Doe" in context.context_instructions
        assert "Previous calls: 3" in context.context_instructions
        assert "Interested in API docs" in context.context_instructions
    
    def test_session_key_format(self):
        """Session key uses normalized phone without +."""
        request = ContextRequest(caller_phone="+1 (440) 291-5517")
        context = build_context(request)
        
        # Should strip + and formatting
        assert context.session_key == "voice:14402915517"
    
    def test_caller_name_from_request(self):
        """Use caller name from request for new callers."""
        request = ContextRequest(
            caller_phone="+14402915517",
            caller_name="Jane Smith"
        )
        context = build_context(request)
        
        assert context.caller_name == "Jane Smith"


class TestCallerHistory:
    """Test caller history management."""
    
    def setup_method(self):
        """Clear caller history before each test."""
        caller_history.clear()
    
    def test_history_stored_correctly(self):
        """Caller history is stored with correct fields."""
        caller_history["+14402915517"] = CallerHistory(
            phone="+14402915517",
            name="Test User",
            call_count=5,
            last_call_at="2026-02-06T10:00:00Z",
            notes="Test notes"
        )
        
        history = caller_history.get("+14402915517")
        
        assert history is not None
        assert history.name == "Test User"
        assert history.call_count == 5
        assert history.notes == "Test notes"


class TestSecurityDefaults:
    """Test security-related defaults."""
    
    def test_empty_config_denies(self):
        """Empty/missing config denies calls."""
        result = authorize_caller("+14402915517", {})
        assert result.authorized is False
    
    def test_no_allowlist_denies(self):
        """Missing allowFrom denies calls."""
        config = {"policy": "allowlist"}
        result = authorize_caller("+14402915517", config)
        assert result.authorized is False
        assert result.reason == "not_configured"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
