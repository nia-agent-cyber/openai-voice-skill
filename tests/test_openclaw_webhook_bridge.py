#!/usr/bin/env python3
"""
Unit tests for scripts/openclaw-webhook-bridge.py

Covers:
- Module constants (TYPESCRIPT_WEBHOOK_URL, BRIDGE_PORT, etc.)
- update_session_status: status mapping, transcript storage
- cleanup_session_mapping: dict cleanup
- inject_call_context: context update, error handling
- notify_typescript_plugin: HTTP post, error handling
- startup_event, shutdown_event
"""

import asyncio
import importlib.util
import json
import os
import sys
import unittest.mock
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ─── Import with mocked dependencies ────────────────────────────────────────

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts')
_BRIDGE_PATH = os.path.join(_SCRIPTS_DIR, 'openclaw-webhook-bridge.py')

# Create proper Pydantic mock
_pydantic_mock = MagicMock()

class _FakeBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

_pydantic_mock.BaseModel = _FakeBaseModel

# FastAPI mock — use identity decorator so @app.on_event functions remain callable
def _identity_deco(*args, **kwargs):
    """Returns a decorator that passes the function through unchanged."""
    def decorator(fn):
        return fn
    return decorator

_fake_app = MagicMock()
_fake_app.on_event = _identity_deco
_fake_app.post = _identity_deco
_fake_app.get = _identity_deco
_fake_app.delete = _identity_deco

_fastapi_mock = MagicMock()
_fastapi_mock.FastAPI = MagicMock(return_value=_fake_app)
_fastapi_mock.HTTPException = type('HTTPException', (Exception,), {'__init__': lambda self, status_code=400, detail='': Exception.__init__(self, detail) or setattr(self, 'status_code', status_code) or setattr(self, 'detail', detail)})
_fastapi_mock.BackgroundTasks = MagicMock

# httpx mock - make AsyncClient a proper async context manager
_httpx_mock = MagicMock()
_mock_response = MagicMock()
_mock_response.status_code = 200
_mock_response.json = MagicMock(return_value={"call_id": "test-call-123", "status": "initiated"})
_mock_response.text = "OK"

_mock_async_client = MagicMock()
_mock_async_client.__aenter__ = AsyncMock(return_value=_mock_async_client)
_mock_async_client.__aexit__ = AsyncMock(return_value=False)
_mock_async_client.post = AsyncMock(return_value=_mock_response)
_mock_async_client.get = AsyncMock(return_value=_mock_response)
_mock_async_client.delete = AsyncMock(return_value=_mock_response)
_httpx_mock.AsyncClient = MagicMock(return_value=_mock_async_client)

_MOCKED_MODULES = {
    "fastapi": _fastapi_mock,
    "fastapi.responses": MagicMock(),
    "uvicorn": MagicMock(),
    "httpx": _httpx_mock,
    "pydantic": _pydantic_mock,
}

with unittest.mock.patch.dict("sys.modules", _MOCKED_MODULES):
    spec = importlib.util.spec_from_file_location("openclaw_webhook_bridge", _BRIDGE_PATH)
    _bridge_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_bridge_mod)

# Grab references
openclaw_sessions = _bridge_mod.openclaw_sessions
session_call_map = _bridge_mod.session_call_map
update_session_status = _bridge_mod.update_session_status
cleanup_session_mapping = _bridge_mod.cleanup_session_mapping
inject_call_context = _bridge_mod.inject_call_context
notify_typescript_plugin = _bridge_mod.notify_typescript_plugin
startup_event = _bridge_mod.startup_event
shutdown_event = _bridge_mod.shutdown_event


# ─── Helpers ──────────────────────────────────────────────────────────────────

def setup_session(call_id: str, session_id: str = "sess-1"):
    """Add a session to openclaw_sessions for testing."""
    openclaw_sessions[call_id] = {
        "openclaw_session_id": session_id,
        "phone_number": "+1234567890",
        "context": {},
        "created_at": datetime.now().isoformat(),
        "status": "initiating"
    }
    session_call_map[session_id] = call_id


def teardown_session(call_id: str, session_id: str = "sess-1"):
    """Clean up test session."""
    openclaw_sessions.pop(call_id, None)
    session_call_map.pop(session_id, None)


# ─── Module constants ─────────────────────────────────────────────────────────

class TestModuleConstants:
    """Test module-level constants are correct."""

    def test_bridge_port_default(self):
        assert _bridge_mod.BRIDGE_PORT == 8082

    def test_typescript_webhook_url_default(self):
        assert "localhost:8081" in _bridge_mod.TYPESCRIPT_WEBHOOK_URL

    def test_openclaw_sessions_is_dict(self):
        assert isinstance(openclaw_sessions, dict)

    def test_session_call_map_is_dict(self):
        assert isinstance(session_call_map, dict)


# ─── update_session_status ────────────────────────────────────────────────────

class TestUpdateSessionStatus:
    """Tests for update_session_status."""

    def setup_method(self):
        setup_session("call-us-1")

    def teardown_method(self):
        teardown_session("call-us-1")

    def test_call_answered_sets_active(self):
        update_session_status("call-us-1", "call_answered", {})
        assert openclaw_sessions["call-us-1"]["status"] == "active"

    def test_call_ended_sets_ended(self):
        update_session_status("call-us-1", "call_ended", {})
        assert openclaw_sessions["call-us-1"]["status"] == "ended"

    def test_call_failed_sets_failed(self):
        update_session_status("call-us-1", "call_failed", {})
        assert openclaw_sessions["call-us-1"]["status"] == "failed"

    def test_call_ringing_sets_ringing(self):
        update_session_status("call-us-1", "call_ringing", {})
        assert openclaw_sessions["call-us-1"]["status"] == "ringing"

    def test_unknown_event_does_not_change_status(self):
        original_status = openclaw_sessions["call-us-1"]["status"]
        update_session_status("call-us-1", "unknown_event", {})
        assert openclaw_sessions["call-us-1"]["status"] == original_status

    def test_unknown_call_does_nothing(self):
        # Should not raise
        update_session_status("nonexistent-call", "call_answered", {})

    def test_last_event_recorded(self):
        update_session_status("call-us-1", "call_answered", {})
        assert openclaw_sessions["call-us-1"]["last_event"] == "call_answered"

    def test_last_updated_set(self):
        update_session_status("call-us-1", "call_answered", {})
        assert "last_updated" in openclaw_sessions["call-us-1"]

    def test_transcript_stored_on_transcript_update(self):
        transcript_data = {
            "transcript": "Hello, how are you?",
            "speaker": "user",
            "confidence": 0.95
        }
        update_session_status("call-us-1", "transcript_updated", transcript_data)
        assert "transcript_entries" in openclaw_sessions["call-us-1"]
        entries = openclaw_sessions["call-us-1"]["transcript_entries"]
        assert len(entries) == 1
        assert entries[0]["text"] == "Hello, how are you?"
        assert entries[0]["speaker"] == "user"

    def test_multiple_transcripts_accumulated(self):
        for i in range(3):
            update_session_status("call-us-1", "transcript_updated", {
                "transcript": f"Message {i}",
                "speaker": "user" if i % 2 == 0 else "assistant"
            })
        assert len(openclaw_sessions["call-us-1"]["transcript_entries"]) == 3


# ─── cleanup_session_mapping ──────────────────────────────────────────────────

class TestCleanupSessionMapping:
    """Tests for cleanup_session_mapping."""

    def test_removes_from_openclaw_sessions(self):
        setup_session("call-clean-1", "sess-clean-1")
        cleanup_session_mapping("call-clean-1", "sess-clean-1")
        assert "call-clean-1" not in openclaw_sessions

    def test_removes_from_session_call_map(self):
        setup_session("call-clean-2", "sess-clean-2")
        cleanup_session_mapping("call-clean-2", "sess-clean-2")
        assert "sess-clean-2" not in session_call_map

    def test_nonexistent_call_does_not_raise(self):
        cleanup_session_mapping("nonexistent-call", "nonexistent-sess")
        # Should not raise


# ─── inject_call_context ──────────────────────────────────────────────────────

class TestInjectCallContext:
    """Tests for inject_call_context."""

    def setup_method(self):
        setup_session("call-ctx-1")

    def teardown_method(self):
        teardown_session("call-ctx-1")

    def test_updates_context_for_known_call(self):
        context = {"project": "voice_skill", "status": "testing"}
        asyncio.run(inject_call_context("call-ctx-1", context))
        assert openclaw_sessions["call-ctx-1"]["context"].get("project") == "voice_skill"

    def test_handles_unknown_call_gracefully(self):
        asyncio.run(inject_call_context("nonexistent-call", {"key": "value"}))
        # Should not raise

    def test_merges_context_with_existing(self):
        openclaw_sessions["call-ctx-1"]["context"] = {"existing": "value"}
        asyncio.run(inject_call_context("call-ctx-1", {"new": "data"}))
        assert "existing" in openclaw_sessions["call-ctx-1"]["context"]
        assert "new" in openclaw_sessions["call-ctx-1"]["context"]


# ─── notify_typescript_plugin ─────────────────────────────────────────────────

class TestNotifyTypescriptPlugin:
    """Tests for notify_typescript_plugin."""

    def test_sends_webhook_event(self):
        asyncio.run(notify_typescript_plugin("call_started", {"call_id": "test"}))
        # Should not raise

    def test_handles_connection_error_gracefully(self):
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(_bridge_mod.httpx, 'AsyncClient', return_value=mock_client):
            asyncio.run(notify_typescript_plugin("call_ended", {"call_id": "test"}))
        # Should not raise

    def test_includes_event_type_in_payload(self):
        sent_payloads = []

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock(status_code=200)

        async def capture_post(url, json=None, timeout=None):
            sent_payloads.append(json)
            return mock_response

        mock_client.post = capture_post

        with patch.object(_bridge_mod.httpx, 'AsyncClient', return_value=mock_client):
            asyncio.run(notify_typescript_plugin(
                "transcript_updated",
                {"call_id": "test-call", "speaker": "user", "text": "Hello"}
            ))

        if sent_payloads:
            assert sent_payloads[0]["event_type"] == "transcript_updated"


# ─── startup_event ────────────────────────────────────────────────────────────

class TestStartupEvent:
    """Tests for startup_event."""

    def test_startup_completes_without_error(self):
        asyncio.run(startup_event())

    def test_startup_handles_unreachable_server(self):
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        with patch.object(_bridge_mod.httpx, 'AsyncClient', return_value=mock_client):
            asyncio.run(startup_event())
        # Should not raise


# ─── shutdown_event ───────────────────────────────────────────────────────────

class TestShutdownEvent:
    """Tests for shutdown_event."""

    def test_shutdown_with_active_sessions(self):
        # Setup some sessions
        setup_session("call-shutdown-1", "sess-shutdown-1")
        setup_session("call-shutdown-2", "sess-shutdown-2")

        asyncio.run(shutdown_event())

        # Sessions should be cleaned up
        assert "call-shutdown-1" not in openclaw_sessions
        assert "call-shutdown-2" not in openclaw_sessions

    def test_shutdown_with_no_sessions(self):
        # Clear all sessions first
        openclaw_sessions.clear()
        session_call_map.clear()

        asyncio.run(shutdown_event())
        # Should not raise


# ─── Endpoint functions (preserved by identity decorator) ─────────────────────

class TestEndpointFunctions:
    """Tests for the FastAPI endpoint functions (preserved by identity decorator)."""

    def setup_method(self):
        openclaw_sessions.clear()
        session_call_map.clear()

    def test_get_openclaw_sessions_empty(self):
        """get_openclaw_sessions returns empty list when none active."""
        get_openclaw_sessions = _bridge_mod.get_openclaw_sessions
        result = asyncio.run(get_openclaw_sessions())
        assert result["active_sessions"] == 0
        assert result["sessions"] == []

    def test_get_openclaw_sessions_with_data(self):
        """get_openclaw_sessions returns all active sessions."""
        setup_session("call-list-1", "sess-list-1")
        setup_session("call-list-2", "sess-list-2")
        get_openclaw_sessions = _bridge_mod.get_openclaw_sessions

        result = asyncio.run(get_openclaw_sessions())
        assert result["active_sessions"] == 2
        assert len(result["sessions"]) == 2

        teardown_session("call-list-1", "sess-list-1")
        teardown_session("call-list-2", "sess-list-2")

    def test_inject_context_creates_session(self):
        """inject_context creates a new session if not present."""
        inject_context = _bridge_mod.inject_context

        class FakeRequest:
            call_id = "call-new-inject"
            openclaw_session_id = "sess-inject-new"
            context = {"key": "value"}

        result = asyncio.run(inject_context(FakeRequest()))
        assert result["status"] == "context_injected"
        assert result["call_id"] == "call-new-inject"
        assert "call-new-inject" in openclaw_sessions

    def test_inject_context_updates_existing(self):
        """inject_context updates context for existing session."""
        setup_session("call-inject-exist", "sess-inject-exist")
        openclaw_sessions["call-inject-exist"]["context"] = {"existing": "data"}

        inject_context = _bridge_mod.inject_context

        class FakeRequest:
            call_id = "call-inject-exist"
            openclaw_session_id = "sess-inject-exist"
            context = {"new": "data"}

        result = asyncio.run(inject_context(FakeRequest()))
        assert result["status"] == "context_injected"
        assert "existing" in openclaw_sessions["call-inject-exist"]["context"]
        assert "new" in openclaw_sessions["call-inject-exist"]["context"]

        teardown_session("call-inject-exist", "sess-inject-exist")

    def test_get_openclaw_session_not_found(self):
        """get_openclaw_session raises HTTPException when not found."""
        get_openclaw_session = _bridge_mod.get_openclaw_session
        HTTPException = _bridge_mod.fastapi.HTTPException if hasattr(_bridge_mod, 'fastapi') else Exception

        with pytest.raises(Exception):
            asyncio.run(get_openclaw_session("nonexistent-session"))

    def test_get_openclaw_session_found(self):
        """get_openclaw_session returns session data."""
        setup_session("call-get-sess", "sess-get-1")
        get_openclaw_session = _bridge_mod.get_openclaw_session

        # Mock the httpx client to fail (avoids actual HTTP)
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("no server"))

        with patch.object(_bridge_mod.httpx, 'AsyncClient', return_value=mock_client):
            result = asyncio.run(get_openclaw_session("sess-get-1"))

        assert result["openclaw_session_id"] == "sess-get-1"
        teardown_session("call-get-sess", "sess-get-1")

    def test_forward_webhook_event_non_openclaw_call(self):
        """forward_webhook_event ignores events for calls not managed by OpenClaw."""
        forward_webhook_event = _bridge_mod.forward_webhook_event

        class FakeBackgroundTasks:
            def add_task(self, fn, *args, **kwargs):
                pass

        class FakeRequest:
            call_id = "call-not-managed"
            event_type = "call_answered"
            data = {}

        result = asyncio.run(forward_webhook_event(FakeRequest(), FakeBackgroundTasks()))
        assert result["status"] == "forwarded"

    def test_forward_webhook_event_openclaw_managed(self):
        """forward_webhook_event routes OpenClaw-managed calls."""
        setup_session("call-fwd-managed", "sess-fwd-1")
        forward_webhook_event = _bridge_mod.forward_webhook_event
        tasks_added = []

        class FakeBackgroundTasks:
            def add_task(self, fn, *args, **kwargs):
                tasks_added.append((fn, args, kwargs))

        class FakeRequest:
            call_id = "call-fwd-managed"
            event_type = "call_answered"
            data = {"status": "active"}

        result = asyncio.run(forward_webhook_event(FakeRequest(), FakeBackgroundTasks()))
        assert result["status"] == "forwarded"
        assert len(tasks_added) >= 1  # notify_typescript_plugin was queued
        teardown_session("call-fwd-managed", "sess-fwd-1")

    def test_forward_webhook_event_call_ended_cleans_up(self):
        """forward_webhook_event cleans up sessions when call ends."""
        setup_session("call-fwd-end", "sess-fwd-end")
        forward_webhook_event = _bridge_mod.forward_webhook_event

        class FakeBackgroundTasks:
            def add_task(self, fn, *args, **kwargs):
                pass

        class FakeRequest:
            call_id = "call-fwd-end"
            event_type = "call_ended"
            data = {}

        asyncio.run(forward_webhook_event(FakeRequest(), FakeBackgroundTasks()))
        # Session should be cleaned up
        assert "call-fwd-end" not in openclaw_sessions
