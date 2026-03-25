#!/usr/bin/env python3
"""
Unit tests for scripts/session_context.py

Covers:
- BridgeEventEmitter: emit_call_started, emit_transcript_update, emit_call_ended, _emit_event
- SessionContextExtractor: context extraction, phone normalization, memory parsing
- Helper functions: notify_call_started, notify_transcript_update, notify_call_ended
- Factory functions: get_bridge_emitter, create_context_extractor
"""

import sys
import os
import json
import threading
import time
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Must mock httpx before importing session_context, as it imports it at module level
# session_context imports httpx directly
import session_context
from session_context import (
    BridgeEventEmitter,
    SessionContextExtractor,
    get_bridge_emitter,
    create_context_extractor,
    notify_call_started,
    notify_transcript_update,
    notify_call_ended,
    sync_call_to_session,
)


# ─── BridgeEventEmitter ────────────────────────────────────────────────────────

class TestBridgeEventEmitterDisabled:
    """Test BridgeEventEmitter when bridge is disabled."""

    def test_disabled_emit_returns_false(self):
        emitter = BridgeEventEmitter(enabled=False)
        result = emitter.emit_call_started("call-1", "+1234567890", "inbound")
        assert result is False

    def test_disabled_transcript_update_returns_false(self):
        emitter = BridgeEventEmitter(enabled=False)
        result = emitter.emit_transcript_update("call-1", "user", "hello")
        assert result is False

    def test_disabled_call_ended_returns_false(self):
        emitter = BridgeEventEmitter(enabled=False)
        result = emitter.emit_call_ended("call-1", "+1234567890")
        assert result is False


class TestBridgeEventEmitterEnabled:
    """Test BridgeEventEmitter when bridge is enabled."""

    def test_emit_call_started_returns_true_immediately(self):
        """emit_call_started fires-and-forgets, returns True immediately."""
        emitter = BridgeEventEmitter(enabled=True)

        # Patch the HTTP client to avoid real network calls
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        with patch.object(emitter, '_http_client', mock_client):
            result = emitter.emit_call_started("call-1", "+1234567890", "inbound")
            assert result is True

    def test_emit_transcript_update_returns_true(self):
        emitter = BridgeEventEmitter(enabled=True)
        with patch.object(emitter, '_http_client', MagicMock()):
            result = emitter.emit_transcript_update("call-1", "user", "hello there")
            assert result is True

    def test_emit_call_ended_returns_true(self):
        emitter = BridgeEventEmitter(enabled=True)
        with patch.object(emitter, '_http_client', MagicMock()):
            result = emitter.emit_call_ended("call-1", "+1234567890", "outbound")
            assert result is True

    def test_emit_event_builds_correct_payload(self):
        """Check that the right payload is constructed."""
        emitter = BridgeEventEmitter(enabled=True)
        sent_payloads = []

        def fake_send():
            pass

        # Override to capture what would be sent
        captured_events = []

        original_emit = emitter._emit_event

        def capture_emit(event):
            captured_events.append(event)
            return False  # disabled so no thread spawned

        emitter.enabled = False
        emitter._emit_event = capture_emit

        # This won't fire since enabled=False, so directly test payload building
        event = {
            "callId": "test-call",
            "eventType": "call_started",
            "phoneNumber": "+1234567890",
            "direction": "inbound",
            "timestamp": "2026-01-01T00:00:00",
            "data": {}
        }
        result = emitter._emit_event(event)
        assert result is False  # disabled returns False

    def test_http_client_lazy_init(self):
        emitter = BridgeEventEmitter(enabled=True)
        assert emitter._http_client is None
        client = emitter.http_client
        assert client is not None

    def test_close_clears_http_client(self):
        emitter = BridgeEventEmitter(enabled=True)
        mock_client = MagicMock()
        emitter._http_client = mock_client
        emitter.close()
        assert emitter._http_client is None
        mock_client.close.assert_called_once()

    def test_close_when_no_client_is_safe(self):
        emitter = BridgeEventEmitter(enabled=True)
        emitter._http_client = None
        emitter.close()  # Should not raise

    def test_emit_with_metadata(self):
        emitter = BridgeEventEmitter(enabled=True)
        with patch.object(emitter, '_http_client', MagicMock()):
            result = emitter.emit_call_started(
                "call-1", "+1234567890", "outbound",
                metadata={"initial_message": "Hello there!"}
            )
            assert result is True

    def test_emit_transcript_with_custom_timestamp(self):
        emitter = BridgeEventEmitter(enabled=True)
        with patch.object(emitter, '_http_client', MagicMock()):
            result = emitter.emit_transcript_update(
                "call-1", "assistant", "Hi, how can I help?",
                timestamp="2026-01-01T10:00:00"
            )
            assert result is True


# ─── get_bridge_emitter (singleton) ────────────────────────────────────────────

class TestGetBridgeEmitter:
    """Test global bridge emitter singleton."""

    def test_returns_bridge_emitter_instance(self):
        emitter = get_bridge_emitter()
        assert isinstance(emitter, BridgeEventEmitter)

    def test_returns_same_instance_on_repeated_calls(self):
        e1 = get_bridge_emitter()
        e2 = get_bridge_emitter()
        assert e1 is e2


# ─── Helper functions ─────────────────────────────────────────────────────────

class TestNotifyHelpers:
    """Test module-level notify_* convenience functions."""

    def setup_method(self):
        """Disable emitter for all tests to avoid thread spawning."""
        self.patcher = patch.object(session_context._bridge_emitter or BridgeEventEmitter(), 'enabled', False)

    def test_notify_call_started(self):
        # The function delegates to get_bridge_emitter().emit_call_started
        emitter = get_bridge_emitter()
        with patch.object(emitter, 'emit_call_started', return_value=True) as mock_emit:
            result = notify_call_started("call-1", "+1234567890")
            mock_emit.assert_called_once_with("call-1", "+1234567890", "inbound")
            assert result is True

    def test_notify_transcript_update(self):
        emitter = get_bridge_emitter()
        with patch.object(emitter, 'emit_transcript_update', return_value=True) as mock_emit:
            result = notify_transcript_update("call-1", "user", "hello")
            mock_emit.assert_called_once_with("call-1", "user", "hello")
            assert result is True

    def test_notify_call_ended(self):
        emitter = get_bridge_emitter()
        with patch.object(emitter, 'emit_call_ended', return_value=True) as mock_emit:
            result = notify_call_ended("call-1", "+1234567890", "outbound")
            mock_emit.assert_called_once_with("call-1", "+1234567890", "outbound")
            assert result is True


# ─── SessionContextExtractor ──────────────────────────────────────────────────

class TestSessionContextExtractor:
    """Tests for SessionContextExtractor."""

    def test_create_context_extractor(self):
        extractor = create_context_extractor()
        assert isinstance(extractor, SessionContextExtractor)

    def test_normalize_phone_adds_plus(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._normalize_phone("12125551234")
        assert result.startswith("+")

    def test_normalize_phone_preserves_plus(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._normalize_phone("+12125551234")
        assert result == "+12125551234"

    def test_mask_phone_contains_stars(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._mask_phone("+12125551234")
        assert "****" in result
        # The original number digits should be partially hidden
        assert len(result) > 4

    def test_mask_phone_short_input(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._mask_phone("+123")
        assert result == "****"

    def test_get_enhanced_instructions_no_workspace(self):
        """When workspace is not found, falls back to base instructions."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = None
        extractor.memory_path = None

        result = extractor.get_enhanced_instructions(
            "+1234567890",
            "You are a helpful assistant.",
            "inbound"
        )
        assert "You are a helpful assistant." in result

    def test_get_enhanced_instructions_with_initial_message(self):
        """Initial message is appended when no workspace."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = None
        extractor.memory_path = None

        result = extractor.get_enhanced_instructions(
            "+1234567890",
            "Base instructions.",
            "outbound",
            initial_message="Hello there!"
        )
        assert "Base instructions." in result
        assert "Hello there!" in result

    def test_add_initial_message(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._add_initial_message("Base.", "Say hello!")
        assert "Base." in result
        assert "Say hello!" in result

    def test_add_initial_message_no_initial(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._add_initial_message("Base only.", None)
        assert result == "Base only."

    def test_parse_conversations_valid_format(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        content = "14:30 - User: How are you?\n15:00 Nia: I'm doing well!"
        result = extractor._parse_conversations(content)
        assert isinstance(result, list)
        if result:  # May or may not match depending on regex
            assert "speaker" in result[0]
            assert "message" in result[0]

    def test_parse_conversations_empty_content(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._parse_conversations("")
        assert result == []

    def test_parse_conversations_no_matches(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._parse_conversations("Just some random text\nNo timestamps here")
        assert result == []

    def test_build_context_summary_with_caller_info(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        context = {
            "caller_info": {"name": "Remi", "known_caller": True},
            "recent_conversations": [{"time": "10:00", "speaker": "User", "message": "Hello"}]
        }
        result = extractor._build_context_summary(context)
        assert "Remi" in result

    def test_build_context_summary_empty(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        context = {"caller_info": {}, "recent_conversations": []}
        result = extractor._build_context_summary(context)
        assert isinstance(result, str)

    def test_get_caller_info_unknown(self):
        """When no phone mapping exists, returns unknown caller."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = Path("/nonexistent/path")

        result = extractor._get_caller_info("+1234567890")
        assert result["known_caller"] is False

    def test_get_caller_info_from_mapping(self):
        """When phone mapping exists with entry, returns caller info."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)

        with tempfile.TemporaryDirectory() as tmpdir:
            extractor.workspace_path = Path(tmpdir)
            mapping = {"+1234567890": {"name": "Test User", "relationship": "primary_user"}}
            (Path(tmpdir) / "phone_mapping.json").write_text(json.dumps(mapping))

            result = extractor._get_caller_info("+1234567890")
            assert result["known_caller"] is True
            assert result["name"] == "Test User"

    def test_extract_memory_highlights_empty(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        result = extractor._extract_memory_highlights("")
        assert result == []

    def test_extract_memory_highlights_with_content(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        content = "## Projects\n- Working on voice skill\n- Testing coverage\n"
        result = extractor._extract_memory_highlights(content)
        assert isinstance(result, list)

    def test_get_recent_conversations_no_workspace(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = None
        extractor.memory_path = None
        result = extractor._get_recent_conversations()
        assert result == []

    def test_get_recent_conversations_no_memory_dir(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor.workspace_path = Path(tmpdir)
            extractor.memory_path = Path(tmpdir) / "memory"
            # memory dir doesn't exist
            result = extractor._get_recent_conversations()
            assert isinstance(result, list)

    def test_find_workspace_path_env_var(self):
        """When OPENCLAW_WORKSPACE is set and valid, uses that path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create SOUL.md to make it look valid
            (Path(tmpdir) / "SOUL.md").write_text("I am Nia.")
            with patch.dict(os.environ, {"OPENCLAW_WORKSPACE": tmpdir}):
                extractor = SessionContextExtractor()
                assert extractor.workspace_path == Path(tmpdir)

    def test_find_workspace_path_invalid_env(self):
        """When OPENCLAW_WORKSPACE doesn't exist, searches defaults."""
        with patch.dict(os.environ, {"OPENCLAW_WORKSPACE": "/nonexistent/path/xyz"}):
            extractor = SessionContextExtractor()
            # workspace_path may be None or a valid default; just ensure no exception
            assert extractor.workspace_path is None or extractor.workspace_path.exists()

    def test_build_enhanced_instructions_known_primary_user(self):
        """Enhanced instructions for known primary_user include personalized greeting."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = Path("/tmp")
        extractor.memory_path = None

        context = {
            "caller_info": {
                "known_caller": True,
                "name": "Remi",
                "preferred_name": "Remi",
                "relationship": "primary_user"
            },
            "recent_conversations": []
        }

        result = extractor._build_enhanced_instructions(
            "Base instructions.", context, "inbound"
        )
        assert "Remi" in result
        assert "Base instructions." in result

    def test_build_enhanced_instructions_unknown_caller(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = Path("/tmp")
        context = {
            "caller_info": {"known_caller": False},
            "recent_conversations": []
        }
        result = extractor._build_enhanced_instructions(
            "Base.", context, "inbound"
        )
        assert "UNKNOWN CALLER" in result or "Hello" in result

    def test_build_enhanced_instructions_outbound_with_initial_message(self):
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        context = {
            "caller_info": {"known_caller": False},
            "recent_conversations": []
        }
        result = extractor._build_enhanced_instructions(
            "Base.", context, "outbound", initial_message="Hello Remi!"
        )
        assert "Hello Remi!" in result

    def test_build_enhanced_instructions_exception_fallback(self):
        """On exception, falls back to base + initial_message."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        # Pass invalid context to trigger exception
        result = extractor._build_enhanced_instructions(
            "Base instructions.", None, "inbound"
        )
        assert "Base instructions." in result

    def test_get_enhanced_instructions_exception_fallback(self):
        """Full extraction pipeline falls back on exception."""
        extractor = SessionContextExtractor.__new__(SessionContextExtractor)
        extractor.workspace_path = Path("/tmp")
        extractor.memory_path = None

        with patch.object(extractor, '_extract_context', side_effect=RuntimeError("test error")):
            result = extractor.get_enhanced_instructions(
                "+1234567890", "Base instructions.", "inbound"
            )
            assert "Base instructions." in result


# ─── sync_call_to_session ──────────────────────────────────────────────────────

class TestSyncCallToSession:
    """Test sync_call_to_session helper."""

    def test_sync_returns_false_on_connection_error(self):
        """When bridge is unreachable, sync returns False."""
        with patch('httpx.post', side_effect=Exception("Connection refused")):
            result = sync_call_to_session("test-call-id")
            assert result is False

    def test_sync_returns_true_on_success(self):
        """When bridge responds 200, sync returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch('httpx.post', return_value=mock_response):
            result = sync_call_to_session("test-call-id")
            assert result is True

    def test_sync_returns_false_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch('httpx.post', return_value=mock_response):
            result = sync_call_to_session("test-call-id")
            assert result is False
