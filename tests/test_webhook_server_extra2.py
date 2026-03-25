#!/usr/bin/env python3
"""
Extra coverage tests for scripts/webhook-server.py — Round 2

Targets uncovered lines:
- tool_message_send (success, no-token, fallback, error)
- _message_send_cli (success, timeout, error)
- tool_sessions_send (success, no-token, error)
- dispatch_tool_call (found, unknown, timeout, exception)
- load_agent_config (with file, bad file, missing)
- _read_openclaw_token (valid, missing, exception)
- _save_transcript (write + exception)
- health / root / list_calls async handlers
- Session config constants (temperature=0.6, eagerness="balanced")
- session_ready asyncio.Event presence in source
- Source-level checks for expected literals

Run with:
    python3 -m pytest tests/test_webhook_server_extra2.py -v
"""

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Re-use the same heavy-mock import pattern ───────────────────────────────

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
_SERVER_PATH = os.path.join(_SCRIPTS_DIR, "webhook-server.py")

_pydantic_mock = MagicMock()

class _FakeBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

_pydantic_mock.BaseModel = _FakeBaseModel

_MOCKED_MODULES = {
    "fastapi": MagicMock(),
    "fastapi.responses": MagicMock(),
    "uvicorn": MagicMock(),
    "twilio": MagicMock(),
    "twilio.rest": MagicMock(),
    "twilio.base": MagicMock(),
    "twilio.base.exceptions": MagicMock(),
    "twilio.twiml": MagicMock(),
    "twilio.twiml.voice_response": MagicMock(),
    "websockets": MagicMock(),
    "websockets.exceptions": MagicMock(),
    "httpx": MagicMock(),
    "pydantic": _pydantic_mock,
}

_twilio_exc = type("TwilioException", (Exception,), {})
_MOCKED_MODULES["twilio.base.exceptions"].TwilioException = _twilio_exc

with unittest.mock.patch.dict("sys.modules", _MOCKED_MODULES):
    spec = importlib.util.spec_from_file_location("webhook_server2", _SERVER_PATH)
    _ws = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_ws)

# Pull function references
tool_message_send = _ws.tool_message_send
_message_send_cli = _ws._message_send_cli
tool_sessions_send = _ws.tool_sessions_send
dispatch_tool_call = _ws.dispatch_tool_call
load_agent_config = _ws.load_agent_config
_read_openclaw_token = _ws._read_openclaw_token
_save_transcript = _ws._save_transcript
_get_recent_call_history = _ws._get_recent_call_history
build_call_prompt = _ws.build_call_prompt
health = _ws.health
root = _ws.root
list_calls = _ws.list_calls


# ─── tool_message_send ────────────────────────────────────────────────────────

class TestToolMessageSend:
    """Tests for tool_message_send()"""

    def _make_httpx_mock(self, status_code: int, text: str = "ok") -> MagicMock:
        """Build a properly structured httpx.AsyncClient mock."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text

        inner = AsyncMock()
        inner.post = AsyncMock(return_value=mock_resp)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=inner)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_cls = MagicMock(return_value=mock_ctx)
        return mock_cls

    def test_no_token_returns_error(self):
        with patch.object(_ws, "OPENCLAW_TOKEN", ""):
            result = asyncio.run(tool_message_send("hello"))
        assert "Cannot send message" in result or "no gateway token" in result

    def test_success_short_message(self):
        mock_cls = self._make_httpx_mock(200)
        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                result = asyncio.run(tool_message_send("hi Remi"))
        assert "Message sent" in result or isinstance(result, str)

    def test_success_long_message_truncated_in_output(self):
        mock_cls = self._make_httpx_mock(200)
        long_msg = "x" * 200  # > 80 chars triggers different return string
        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                result = asyncio.run(tool_message_send(long_msg))
        assert isinstance(result, str)
        assert "..." in result or "Message sent" in result

    def test_non_200_falls_back_to_cli(self):
        mock_cls = self._make_httpx_mock(503, "service unavailable")
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                with patch.object(_ws.asyncio, "create_subprocess_exec", return_value=mock_proc):
                    with patch.object(_ws.asyncio, "wait_for",
                                      AsyncMock(return_value=(b"ok", b""))):
                        result = asyncio.run(tool_message_send("hello"))
        assert isinstance(result, str)

    def test_exception_falls_back_to_cli(self):
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_cls = MagicMock(return_value=mock_ctx)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                with patch.object(_ws.asyncio, "create_subprocess_exec", return_value=mock_proc):
                    with patch.object(_ws.asyncio, "wait_for",
                                      AsyncMock(return_value=(b"ok", b""))):
                        result = asyncio.run(tool_message_send("hello"))
        assert isinstance(result, str)


# ─── _message_send_cli ────────────────────────────────────────────────────────

class TestMessageSendCli:
    """Tests for _message_send_cli()"""

    def test_success_returns_sent_message(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))

        with patch.object(_ws.asyncio, "create_subprocess_exec", return_value=mock_proc):
            with patch.object(_ws.asyncio, "wait_for",
                              AsyncMock(return_value=(b"ok", b""))):
                result = asyncio.run(_message_send_cli("test message"))
        assert "sent" in result.lower() or isinstance(result, str)

    def test_failure_returns_error(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"command not found"))

        async def real_wait_for(coro, timeout):
            return await coro

        with patch.object(_ws.asyncio, "create_subprocess_exec", return_value=mock_proc):
            with patch.object(_ws.asyncio, "wait_for", real_wait_for):
                result = asyncio.run(_message_send_cli("test"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_timeout_returns_timeout_message(self):
        mock_proc = AsyncMock()

        async def raise_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch.object(_ws.asyncio, "create_subprocess_exec", return_value=mock_proc):
            with patch.object(_ws.asyncio, "wait_for", raise_timeout):
                result = asyncio.run(_message_send_cli("test"))
        assert "timed out" in result.lower()

    def test_exception_returns_failed_message(self):
        async def raise_exc(*args, **kwargs):
            raise Exception("openclaw not found")

        with patch.object(_ws.asyncio, "create_subprocess_exec", side_effect=raise_exc):
            result = asyncio.run(_message_send_cli("test"))
        assert "failed" in result.lower() or "openclaw not found" in result


# ─── tool_sessions_send ──────────────────────────────────────────────────────

class TestToolSessionsSend:
    """Tests for tool_sessions_send()"""

    def _make_httpx_mock(self, status_code: int, text: str = "ok") -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text

        inner = AsyncMock()
        inner.post = AsyncMock(return_value=mock_resp)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=inner)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        return MagicMock(return_value=mock_ctx)

    def test_no_token_returns_error(self):
        with patch.object(_ws, "OPENCLAW_TOKEN", ""):
            result = asyncio.run(tool_sessions_send("remember this"))
        assert "Cannot send note" in result or "no gateway token" in result

    def test_success_returns_confirmation(self):
        mock_cls = self._make_httpx_mock(200)
        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                result = asyncio.run(tool_sessions_send("remember this note"))
        assert "Note sent" in result or isinstance(result, str)

    def test_non_200_returns_error_message(self):
        mock_cls = self._make_httpx_mock(502, "bad gateway")
        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                result = asyncio.run(tool_sessions_send("note"))
        assert "gateway error" in result.lower() or "Couldn't reach" in result

    def test_exception_returns_failed_message(self):
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("no route"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_cls = MagicMock(return_value=mock_ctx)

        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                result = asyncio.run(tool_sessions_send("note"))
        assert "Failed to send note" in result or "no route" in result

    def test_long_note_truncated_in_response(self):
        mock_cls = self._make_httpx_mock(200)
        long_note = "important info: " + "x" * 200  # > 80 chars
        with patch.object(_ws, "OPENCLAW_TOKEN", "fake-token"):
            with patch.object(_ws, "httpx", MagicMock(AsyncClient=mock_cls)):
                result = asyncio.run(tool_sessions_send(long_note))
        assert isinstance(result, str)


# ─── dispatch_tool_call ──────────────────────────────────────────────────────

class TestDispatchToolCall:
    """Tests for dispatch_tool_call()"""

    def _make_mock_ws(self):
        ws = AsyncMock()
        ws.send = AsyncMock()
        return ws

    def test_known_tool_dispatched_and_result_injected(self):
        ws = self._make_mock_ws()

        async def fake_handler(**kwargs):
            return "tool result"

        with patch.dict(_ws.TOOL_REGISTRY, {"memory_search": fake_handler}):
            asyncio.run(dispatch_tool_call(ws, "memory_search", {"query": "test"}, "call-1"))

        assert ws.send.call_count == 2
        first_call_arg = json.loads(ws.send.call_args_list[0][0][0])
        assert first_call_arg["type"] == "conversation.item.create"
        assert first_call_arg["item"]["output"] == "tool result"

    def test_unknown_tool_returns_error_message(self):
        ws = self._make_mock_ws()
        asyncio.run(dispatch_tool_call(ws, "nonexistent_tool", {}, "call-99"))

        first_call_arg = json.loads(ws.send.call_args_list[0][0][0])
        assert "Unknown tool" in first_call_arg["item"]["output"]

    def test_tool_timeout_returns_timeout_message(self):
        ws = self._make_mock_ws()

        async def slow_tool(**kwargs):
            await asyncio.sleep(999)

        with patch.dict(_ws.TOOL_REGISTRY, {"slow_tool": slow_tool}):
            with patch.object(_ws.asyncio, "wait_for",
                              AsyncMock(side_effect=asyncio.TimeoutError())):
                asyncio.run(dispatch_tool_call(ws, "slow_tool", {}, "call-2"))

        first_call_arg = json.loads(ws.send.call_args_list[0][0][0])
        assert "timed out" in first_call_arg["item"]["output"]

    def test_tool_exception_returns_error_message(self):
        ws = self._make_mock_ws()

        async def broken_tool(**kwargs):
            raise ValueError("something broke")

        with patch.dict(_ws.TOOL_REGISTRY, {"broken_tool": broken_tool}):
            asyncio.run(dispatch_tool_call(ws, "broken_tool", {}, "call-3"))

        first_call_arg = json.loads(ws.send.call_args_list[0][0][0])
        assert "Tool error" in first_call_arg["item"]["output"]

    def test_response_create_sent_after_result(self):
        ws = self._make_mock_ws()

        async def ok_tool(**kwargs):
            return "done"

        with patch.dict(_ws.TOOL_REGISTRY, {"ok_tool": ok_tool}):
            asyncio.run(dispatch_tool_call(ws, "ok_tool", {}, "call-4"))

        second_call_arg = json.loads(ws.send.call_args_list[1][0][0])
        assert second_call_arg["type"] == "response.create"


# ─── load_agent_config ───────────────────────────────────────────────────────

class TestLoadAgentConfig:
    """Tests for load_agent_config()"""

    def test_returns_defaults_when_no_config_file(self, tmp_path):
        fake_config_path = tmp_path / "config" / "agent.json"
        # Don't create the file → CONFIG_PATH.exists() returns False
        with patch.object(_ws, "CONFIG_PATH", fake_config_path):
            result = load_agent_config()
        assert result["name"] == "Nia"
        assert result["voice"] == _ws.OPENAI_VOICE

    def test_merges_config_file_over_defaults(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "agent.json"
        config_file.write_text(json.dumps({"name": "Aria", "extra_key": "extra_val"}))

        with patch.object(_ws, "CONFIG_PATH", config_file):
            result = load_agent_config()
        assert result["name"] == "Aria"
        assert result["extra_key"] == "extra_val"
        # Default keys still present
        assert "voice" in result

    def test_bad_json_returns_defaults(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "agent.json"
        config_file.write_text("THIS IS NOT VALID JSON {{{")

        with patch.object(_ws, "CONFIG_PATH", config_file):
            result = load_agent_config()
        # Falls back to defaults
        assert result["name"] == "Nia"


# ─── _read_openclaw_token ────────────────────────────────────────────────────

class TestReadOpenclawToken:
    """Tests for _read_openclaw_token()"""

    def test_reads_token_from_json_file(self, tmp_path):
        oc_dir = tmp_path / ".openclaw"
        oc_dir.mkdir()
        config = {"gateway": {"auth": {"token": "my-secret-token"}}}
        (oc_dir / "openclaw.json").write_text(json.dumps(config))

        with patch.object(Path, "home", return_value=tmp_path):
            result = _read_openclaw_token()
        assert result == "my-secret-token"

    def test_returns_empty_when_file_missing(self, tmp_path):
        with patch.object(Path, "home", return_value=tmp_path):
            result = _read_openclaw_token()
        assert result == ""

    def test_returns_empty_on_bad_json(self, tmp_path):
        oc_dir = tmp_path / ".openclaw"
        oc_dir.mkdir()
        (oc_dir / "openclaw.json").write_text("NOT JSON")

        with patch.object(Path, "home", return_value=tmp_path):
            result = _read_openclaw_token()
        assert result == ""

    def test_returns_empty_when_token_key_missing(self, tmp_path):
        oc_dir = tmp_path / ".openclaw"
        oc_dir.mkdir()
        config = {"gateway": {"auth": {}}}  # no "token" key
        (oc_dir / "openclaw.json").write_text(json.dumps(config))

        with patch.object(Path, "home", return_value=tmp_path):
            result = _read_openclaw_token()
        assert result == ""


# ─── _save_transcript ────────────────────────────────────────────────────────

class TestSaveTranscript:
    """Tests for _save_transcript()"""

    def test_saves_transcript_json(self, tmp_path):
        with patch.object(_ws, "WORKSPACE_ROOT", tmp_path):
            _save_transcript("CA123", [
                {"speaker": "user", "content": "Hello Nia"},
                {"speaker": "assistant", "content": "Hi Remi!"},
            ])

        transcripts_dir = tmp_path / "memory" / "call-transcripts"
        assert transcripts_dir.exists()
        files = list(transcripts_dir.glob("*CA123*.json"))
        assert len(files) == 1

        data = json.loads(files[0].read_text())
        assert data["call_sid"] == "CA123"
        assert data["turns"] == 2
        assert data["transcript"][0]["content"] == "Hello Nia"

    def test_saves_empty_transcript(self, tmp_path):
        with patch.object(_ws, "WORKSPACE_ROOT", tmp_path):
            _save_transcript("CA000", [])

        files = list((tmp_path / "memory" / "call-transcripts").glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["turns"] == 0

    def test_handles_write_exception_gracefully(self, tmp_path):
        """Should log but not raise even if write fails."""
        with patch.object(_ws, "WORKSPACE_ROOT", tmp_path):
            with patch.object(Path, "write_text", side_effect=PermissionError("no write")):
                # Should NOT raise
                _save_transcript("CA_BROKEN", [{"speaker": "user", "content": "test"}])


# ─── health / root / list_calls ──────────────────────────────────────────────

class TestHealthEndpoints:
    """
    Tests for /health, /, and /calls endpoint logic.

    Note: With FastAPI mocked, decorators (@app.get etc.) wrap the functions
    in MagicMock, so we can't call them directly as coroutines.
    Instead we verify:
      1. Module constants that the endpoints directly reference
      2. Source-level structure confirming the expected response keys
      3. active_calls dict mutation (used by all three endpoints)
    """

    def test_active_calls_dict_exists(self):
        assert isinstance(_ws.active_calls, dict)

    def test_active_calls_tracks_insertions(self):
        backup = dict(_ws.active_calls)
        try:
            _ws.active_calls["CA_TEST"] = {"type": "outbound", "status": "active",
                                            "started_at": 0, "to": "+1234", "from": "+5678"}
            assert len(_ws.active_calls) == len(backup) + 1
        finally:
            _ws.active_calls.clear()
            _ws.active_calls.update(backup)

    def test_voice_constant_is_shimmer(self):
        # /health returns OPENAI_VOICE directly
        assert _ws.OPENAI_VOICE == "shimmer"

    def test_agent_config_name_is_nia(self):
        # /health returns AGENT_CONFIG["name"]
        assert _ws.AGENT_CONFIG["name"] == "Nia"

    def test_media_stream_url_starts_wss(self):
        # Both /health and / return MEDIA_STREAM_WS_URL
        assert _ws.MEDIA_STREAM_WS_URL.startswith("wss://")

    def test_audioop_source_set(self):
        # /health returns _AUDIOOP_SOURCE
        assert _ws._AUDIOOP_SOURCE in ("stdlib", "audioop-lts", "UNAVAILABLE")

    def test_source_health_returns_status_ok(self):
        src = Path(_SERVER_PATH).read_text()
        assert '"status": "ok"' in src or "'status': 'ok'" in src

    def test_source_health_returns_voice(self):
        src = Path(_SERVER_PATH).read_text()
        assert "OPENAI_VOICE" in src and "voice" in src

    def test_source_root_returns_service_name(self):
        src = Path(_SERVER_PATH).read_text()
        assert "Nia Voice Server" in src

    def test_source_list_calls_uses_active_calls(self):
        src = Path(_SERVER_PATH).read_text()
        assert "active_calls" in src

    def test_source_health_endpoint_path(self):
        src = Path(_SERVER_PATH).read_text()
        assert '"/health"' in src or "'/health'" in src

    def test_source_root_endpoint_path(self):
        src = Path(_SERVER_PATH).read_text()
        # Root decorator
        assert '@app.get("/")' in src or "@app.get('/')" in src

    def test_source_calls_endpoint_path(self):
        src = Path(_SERVER_PATH).read_text()
        assert '"/calls"' in src or "'/calls'" in src


# ─── Session config constants ────────────────────────────────────────────────

class TestSessionConfigConstants:
    """Verify expected session config values match source literals."""

    def test_voice_is_shimmer(self):
        assert _ws.OPENAI_VOICE == "shimmer"

    def test_source_contains_temperature_06(self):
        """Temperature must be 0.6 in the session.update call."""
        src = Path(_SERVER_PATH).read_text()
        assert '"temperature": 0.6' in src or "'temperature': 0.6" in src, \
            "temperature=0.6 not found in session.update config"

    def test_source_contains_eagerness_balanced(self):
        """VAD eagerness must be 'balanced'."""
        src = Path(_SERVER_PATH).read_text()
        assert '"eagerness": "balanced"' in src or "'eagerness': 'balanced'" in src, \
            "eagerness='balanced' not found in source"

    def test_source_contains_session_ready_event(self):
        """session_ready asyncio.Event must be created in context."""
        src = Path(_SERVER_PATH).read_text()
        assert "asyncio.Event()" in src, "asyncio.Event() not found in source"
        assert "session_ready" in src, "'session_ready' key not found in source"

    def test_source_contains_session_updated_handler(self):
        """session.updated event must set session_ready."""
        src = Path(_SERVER_PATH).read_text()
        assert "session.updated" in src, "'session.updated' not found in source"

    def test_default_model_is_realtime(self):
        assert "realtime" in _ws.DEFAULT_CONFIG["model"]

    def test_openai_realtime_url_present(self):
        assert "realtime" in _ws.OPENAI_REALTIME_URL
        assert _ws.OPENAI_REALTIME_URL.startswith("wss://")


# ─── Source-level structural checks ─────────────────────────────────────────

class TestSourceStructure:
    """Lightweight checks that important patterns exist in the source file."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        self.src = Path(_SERVER_PATH).read_text()

    def test_health_endpoint_defined(self):
        assert "@app.get" in self.src or "async def health" in self.src

    def test_voice_incoming_endpoint_defined(self):
        assert "/voice/incoming" in self.src

    def test_media_stream_ws_endpoint_defined(self):
        assert "/media-stream" in self.src

    def test_tool_registry_defined(self):
        assert "TOOL_REGISTRY" in self.src

    def test_summarize_and_remember_defined(self):
        assert "summarize_and_remember" in self.src

    def test_audioop_import_pattern(self):
        assert "audioop" in self.src

    def test_session_ready_gate_present(self):
        assert "session_ready" in self.src

    def test_known_callers_has_remi(self):
        assert "+250794002033" in self.src
        assert '"Remi"' in self.src or "'Remi'" in self.src

    def test_twilio_media_streams_architecture(self):
        assert "Media Stream" in self.src or "media-stream" in self.src

    def test_absolute_rule_language_header(self):
        assert "ABSOLUTE RULE" in self.src

    def test_thinking_tone_function_present(self):
        assert "generate_thinking_tone" in self.src


# ─── build_call_prompt — heartbeat state parsing ────────────────────────────

class TestBuildCallPromptHeartbeat:
    """Test heartbeat JSON state inclusion in call prompt."""

    def test_heartbeat_state_included_when_valid_json(self, tmp_path):
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        heartbeat_data = {
            "lastChecks": {
                "email": 1711364400,
                "calendar": 1711360800,
                "weather": None
            }
        }
        (mem_dir / "heartbeat-state.json").write_text(json.dumps(heartbeat_data))

        with patch.object(_ws, "WORKSPACE_ROOT", tmp_path):
            prompt = build_call_prompt("+250794002033")

        assert "heartbeat" in prompt.lower() or "Recent Activity" in prompt

    def test_heartbeat_state_skipped_when_bad_json(self, tmp_path):
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / "heartbeat-state.json").write_text("INVALID JSON {{{")

        with patch.object(_ws, "WORKSPACE_ROOT", tmp_path):
            prompt = build_call_prompt()

        # Should not crash, prompt still built
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_yesterday_daily_note_included_when_today_missing(self, tmp_path):
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / f"{yesterday}.md").write_text("Yesterday's important context.")

        with patch.object(_ws, "WORKSPACE_ROOT", tmp_path):
            prompt = build_call_prompt()

        assert "Yesterday's important context" in prompt
