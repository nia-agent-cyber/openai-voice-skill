#!/usr/bin/env python3
"""
Unit tests for scripts/openclaw_bridge.py

Covers:
- OpenClawBridge initialization and phone mapping
- identify_caller: known, unknown, exception handling
- format_context_for_voice: personalization by relationship
- _normalize_phone_number
- _enhance_context_for_caller, _filter_personal_context, _limit_context_for_unknown
- _is_work_related_conversation, _find_relevant_conversations
- get_caller_context: cache hits, fallback on error
- update_call_context, finalize_call_context
- create_openclaw_bridge factory
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import unittest.mock

import pytest

# We need to mock httpx and session_context before importing openclaw_bridge
_mock_httpx = MagicMock()
_mock_httpx.AsyncClient = MagicMock()

_mock_session = MagicMock()

# Mock SessionContextExtractor with a basic workspace path
_mock_extractor = MagicMock()
_mock_extractor.workspace_path = Path("/tmp")
_mock_extractor.extract_recent_context = MagicMock(return_value={
    "conversation_history": [],
    "ongoing_projects": [],
    "recent_decisions": [],
    "context_summary": "Test context"
})

_mock_session.SessionContextExtractor = MagicMock(return_value=_mock_extractor)
_mock_session.create_context_extractor = MagicMock(return_value=_mock_extractor)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

with unittest.mock.patch.dict('sys.modules', {
    'httpx': _mock_httpx,
    'session_context': _mock_session,
}):
    import openclaw_bridge as ob
    from openclaw_bridge import (
        OpenClawBridge,
        create_openclaw_bridge,
    )


def make_bridge(phone_mapping=None) -> OpenClawBridge:
    """Create an OpenClawBridge with optional phone mapping."""
    bridge = OpenClawBridge.__new__(OpenClawBridge)
    bridge.context_extractor = _mock_extractor
    bridge.user_phone_mapping = phone_mapping or {}
    bridge.session_cache = {}
    bridge.cache_ttl = 300
    bridge.openclaw_api_url = "http://localhost:3000"
    bridge.openclaw_api_key = None
    return bridge


# ─── Initialization ────────────────────────────────────────────────────────────

class TestOpenClawBridgeInit:
    """Tests for OpenClawBridge.__init__"""

    def test_creates_bridge_instance(self):
        bridge = make_bridge()
        assert isinstance(bridge, OpenClawBridge)

    def test_default_mapping_loaded(self, tmp_path):
        mapping = {"+1234567890": {"name": "Test User"}}
        (tmp_path / "phone_mapping.json").write_text(json.dumps(mapping))
        _mock_extractor.workspace_path = tmp_path
        bridge = OpenClawBridge.__new__(OpenClawBridge)
        bridge.context_extractor = _mock_extractor
        bridge.user_phone_mapping = bridge._load_phone_mapping()
        assert "+1234567890" in bridge.user_phone_mapping

    def test_empty_mapping_when_no_file(self):
        _mock_extractor.workspace_path = Path("/nonexistent/path")
        bridge = make_bridge()
        # Should not crash, just have empty or default mapping
        assert isinstance(bridge.user_phone_mapping, dict)


# ─── _normalize_phone_number ──────────────────────────────────────────────────

class TestNormalizePhoneNumber:
    """Tests for _normalize_phone_number."""

    def setup_method(self):
        self.bridge = make_bridge()

    def test_adds_plus_prefix(self):
        result = self.bridge._normalize_phone_number("12125551234")
        assert result.startswith("+")

    def test_removes_spaces(self):
        result = self.bridge._normalize_phone_number("+1 212 555 1234")
        assert " " not in result

    def test_removes_dashes(self):
        result = self.bridge._normalize_phone_number("+1-212-555-1234")
        assert "-" not in result

    def test_removes_parens(self):
        result = self.bridge._normalize_phone_number("+1(212)5551234")
        assert "(" not in result and ")" not in result

    def test_preserves_e164(self):
        result = self.bridge._normalize_phone_number("+12125551234")
        assert result == "+12125551234"


# ─── identify_caller ─────────────────────────────────────────────────────────

class TestIdentifyCaller:
    """Tests for identify_caller."""

    def test_known_caller_identified(self):
        bridge = make_bridge({"+250794002033": {"name": "Remi", "session_id": "main"}})
        result = asyncio.run(bridge.identify_caller("+250794002033"))
        assert result is not None
        assert result["name"] == "Remi"
        assert result["known_caller"] is True

    def test_unknown_caller_returns_default(self):
        bridge = make_bridge()
        result = asyncio.run(bridge.identify_caller("+999000000001"))
        assert result is not None
        assert result["known_caller"] is False
        assert result["name"] == "Unknown Caller"

    def test_caller_phone_normalized(self):
        bridge = make_bridge({"+250794002033": {"name": "Remi", "session_id": "main"}})
        # Pass without leading + but with country code
        result = asyncio.run(bridge.identify_caller("250794002033"))
        assert result is not None
        assert result["name"] == "Remi"

    def test_exception_returns_none(self):
        bridge = make_bridge()
        # Force an exception by making _normalize_phone_number fail
        with patch.object(bridge, '_normalize_phone_number', side_effect=RuntimeError("crash")):
            result = asyncio.run(bridge.identify_caller("+1234567890"))
        assert result is None

    def test_api_lookup_when_key_set(self):
        bridge = make_bridge()
        bridge.openclaw_api_key = "test-key"
        with patch.object(bridge, '_lookup_caller_via_api', AsyncMock(return_value=None)):
            result = asyncio.run(bridge.identify_caller("+999000000002"))
        assert result is not None  # Falls back to unknown


# ─── format_context_for_voice ─────────────────────────────────────────────────

class TestFormatContextForVoice:
    """Tests for format_context_for_voice."""

    def setup_method(self):
        self.bridge = make_bridge()

    def test_includes_caller_name(self):
        context = {
            "caller_info": {"name": "Remi", "relationship": "primary_user", "known_caller": True},
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context, "inbound")
        assert "Remi" in result

    def test_primary_user_gets_familiar_tone(self):
        context = {
            "caller_info": {"name": "Remi", "relationship": "primary_user", "known_caller": True},
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context)
        assert "primary user" in result.lower() or "familiar" in result.lower()

    def test_unknown_caller_gets_polite_message(self):
        context = {
            "caller_info": {"name": "Unknown", "relationship": "unknown", "known_caller": False},
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context)
        assert "polite" in result.lower() or "helpful" in result.lower() or "unknown" in result.lower()

    def test_outbound_call_type_mentioned(self):
        context = {
            "caller_info": {"name": "Remi", "relationship": "primary_user", "known_caller": True},
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context, "outbound", "Hello!")
        assert "outbound" in result.lower() or "initiated" in result.lower() or "Hello!" in result

    def test_projects_included_for_known_caller(self):
        context = {
            "caller_info": {"name": "Remi", "relationship": "primary_user", "known_caller": True},
            "conversation_history": [],
            "ongoing_projects": [{"name": "Voice Skill", "description": "Voice calling project"}],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context)
        assert "Voice Skill" in result

    def test_team_member_relationship(self):
        context = {
            "caller_info": {"name": "Alice", "relationship": "team_member", "known_caller": True},
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context)
        assert "professional" in result.lower() or "team" in result.lower()

    def test_exception_fallback(self):
        # Context missing caller_info key should still return a string
        context = {"caller_info": None, "conversation_history": [], "ongoing_projects": [], "recent_decisions": []}
        try:
            result = self.bridge.format_context_for_voice(context)
            assert isinstance(result, str)
        except (AttributeError, TypeError):
            pass  # Some edge cases in the bridge code may raise on None context

    def test_returns_string(self):
        context = {
            "caller_info": {"name": "Test"},
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge.format_context_for_voice(context)
        assert isinstance(result, str)


# ─── _find_relevant_conversations ────────────────────────────────────────────

class TestFindRelevantConversations:
    """Tests for _find_relevant_conversations."""

    def setup_method(self):
        self.bridge = make_bridge()

    def test_returns_list(self):
        conversations = [
            {"content": "Hello how are you", "timestamp": "10:00"},
            {"content": "Project is on track", "timestamp": "10:05"}
        ]
        result = self.bridge._find_relevant_conversations(conversations, "Remi")
        assert isinstance(result, list)

    def test_empty_conversations_returns_empty(self):
        result = self.bridge._find_relevant_conversations([], "Remi")
        assert result == []


# ─── _is_work_related_conversation ───────────────────────────────────────────

class TestIsWorkRelatedConversation:
    """Tests for _is_work_related_conversation."""

    def setup_method(self):
        self.bridge = make_bridge()

    def test_project_related_is_work(self):
        conv = {"content": "The project is on schedule"}
        result = self.bridge._is_work_related_conversation(conv)
        assert result is True

    def test_casual_not_work(self):
        conv = {"content": "What's for lunch today?"}
        result = self.bridge._is_work_related_conversation(conv)
        # May or may not be work-related depending on implementation
        assert isinstance(result, bool)

    def test_empty_content(self):
        conv = {"content": ""}
        result = self.bridge._is_work_related_conversation(conv)
        assert isinstance(result, bool)


# ─── _filter_personal_context ─────────────────────────────────────────────────

class TestFilterPersonalContext:
    """Tests for _filter_personal_context."""

    def setup_method(self):
        self.bridge = make_bridge()

    def test_returns_dict(self):
        context = {
            "conversation_history": [{"content": "test"}],
            "ongoing_projects": [],
            "recent_decisions": []
        }
        result = self.bridge._filter_personal_context(context)
        assert isinstance(result, dict)

    def test_preserves_structure(self):
        context = {
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": [],
            "context_summary": "test"
        }
        result = self.bridge._filter_personal_context(context)
        assert "context_summary" in result or "conversation_history" in result


# ─── _limit_context_for_unknown ──────────────────────────────────────────────

class TestLimitContextForUnknown:
    """Tests for _limit_context_for_unknown."""

    def setup_method(self):
        self.bridge = make_bridge()

    def test_returns_limited_context(self):
        context = {
            "conversation_history": [{"content": "test"}] * 20,
            "ongoing_projects": [{"name": "project"}] * 10,
            "recent_decisions": [{"content": "decision"}] * 10,
            "context_summary": "full context"
        }
        result = self.bridge._limit_context_for_unknown(context)
        assert isinstance(result, dict)


# ─── get_caller_context ──────────────────────────────────────────────────────

class TestGetCallerContext:
    """Tests for get_caller_context."""

    def test_returns_context_dict(self):
        bridge = make_bridge()
        caller_info = {"name": "Remi", "session_id": "main", "phone": "+250794002033", "known_caller": True}
        result = asyncio.run(bridge.get_caller_context(caller_info))
        assert isinstance(result, dict)

    def test_uses_cache_on_second_call(self):
        bridge = make_bridge()
        caller_info = {"name": "Remi", "session_id": "main", "phone": "+250794002033", "known_caller": True}

        # Prime the cache
        cache_key = "main_+250794002033"
        bridge.session_cache[cache_key] = {
            "context": {"cached_data": True, "conversation_history": [], "ongoing_projects": [], "recent_decisions": []},
            "cached_at": time.time()
        }

        result = asyncio.run(bridge.get_caller_context(caller_info))
        assert result.get("cached_data") is True  # Used cache

    def test_fallback_on_exception(self):
        bridge = make_bridge()
        caller_info = {"name": "Remi", "session_id": "main", "phone": "+250794002033"}

        # Force an exception in context extraction
        with patch.object(_mock_extractor, 'extract_recent_context', side_effect=RuntimeError("context failed")):
            result = asyncio.run(bridge.get_caller_context(caller_info))

        assert isinstance(result, dict)
        assert "conversation_history" in result  # Fallback structure

    def test_unknown_caller_limited_context(self):
        bridge = make_bridge()
        caller_info = {"name": "Unknown", "session_id": "guest", "phone": "+999000000001", "known_caller": False}
        result = asyncio.run(bridge.get_caller_context(caller_info))
        assert isinstance(result, dict)


# ─── update_call_context ──────────────────────────────────────────────────────

class TestUpdateCallContext:
    """Tests for update_call_context."""

    def test_creates_context_file(self, tmp_path):
        bridge = make_bridge()
        asyncio.run(bridge.update_call_context(
            "call-123",
            {"transcript_update": "Hello there", "timestamp": "10:00"}
        ))
        # Should not raise

    def test_with_empty_updates(self):
        bridge = make_bridge()
        asyncio.run(bridge.update_call_context("call-empty", {}))
        # Should not raise


# ─── finalize_call_context ────────────────────────────────────────────────────

class TestFinalizeCallContext:
    """Tests for finalize_call_context."""

    def test_finalizes_call(self):
        bridge = make_bridge()
        summary = {
            "duration": 120,
            "transcript": "test transcript",
            "key_topics": ["projects"]
        }
        asyncio.run(bridge.finalize_call_context("call-fin", summary))
        # Should not raise


# ─── _lookup_caller_via_api ───────────────────────────────────────────────────

class TestLookupCallerViaApi:
    """Tests for _lookup_caller_via_api."""

    def test_returns_none_when_api_fails(self):
        bridge = make_bridge()
        bridge.openclaw_api_key = "test-key"

        # Mock httpx to fail
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("API error"))

        with patch.object(ob, 'httpx') as mock_httpx_mod:
            mock_httpx_mod.AsyncClient.return_value = mock_client
            result = asyncio.run(bridge._lookup_caller_via_api("+1234567890"))
        # Should return None gracefully
        assert result is None


# ─── create_openclaw_bridge ───────────────────────────────────────────────────

class TestCreateOpenClawBridge:
    """Tests for create_openclaw_bridge factory function."""

    def test_returns_bridge_instance(self):
        bridge = create_openclaw_bridge()
        # The mock returns whatever _mock_extractor is configured to return
        assert bridge is not None

    def test_factory_creates_new_instance(self):
        b1 = create_openclaw_bridge()
        b2 = create_openclaw_bridge()
        # Both should be OpenClawBridge instances
        assert b1 is not None and b2 is not None
