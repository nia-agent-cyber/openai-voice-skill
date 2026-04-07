"""
Tests for scripts/mcp_server.py — MCP tool functions.

All httpx network calls are mocked so no live server is required.

Run with:
    python3 -m pytest tests/test_mcp_server.py -v
"""

import asyncio
import json
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Path setup ──────────────────────────────────────────────────────────────

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, _SCRIPTS_DIR)


# ─── Helper ──────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _mock_response(payload: dict, status_code: int = 200):
    """Return a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def _mock_async_client(response):
    """Return a context-manager mock for httpx.AsyncClient."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)
    client.get = AsyncMock(return_value=response)
    return client


# ─── Import mcp_server (stub out mcp if not installed) ───────────────────────

# Inject stubs into sys.modules BEFORE importing mcp_server so the module
# loads cleanly even when the `mcp` package is not installed in the venv.
# Using setdefault means: if `mcp` IS installed, the real package is used.
_fake_mcp_pkg = MagicMock()
_fake_fastmcp_cls = MagicMock()
_fake_fastmcp_instance = MagicMock()
_fake_fastmcp_cls.return_value = _fake_fastmcp_instance
# tool() decorator must return the original function unchanged
_fake_fastmcp_instance.tool = lambda: (lambda fn: fn)
_fake_mcp_pkg.server.fastmcp.FastMCP = _fake_fastmcp_cls

sys.modules.setdefault("mcp", _fake_mcp_pkg)
sys.modules.setdefault("mcp.server", _fake_mcp_pkg.server)
sys.modules.setdefault("mcp.server.fastmcp", _fake_mcp_pkg.server.fastmcp)

import mcp_server as ms


# ─── make_call ────────────────────────────────────────────────────────────────

class TestMakeCall:

    def test_make_call_success(self):
        payload = {"call_sid": "CA123", "status": "queued"}
        mock_client = _mock_async_client(_mock_response(payload))

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            result = run(ms.make_call("+12025551234", "Hello world"))

        assert result == payload
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert "/call" in call_args[0][0]
        assert call_args[1]["json"]["to"] == "+12025551234"
        assert call_args[1]["json"]["message"] == "Hello world"

    def test_make_call_no_message(self):
        payload = {"call_sid": "CA456", "status": "queued"}
        mock_client = _mock_async_client(_mock_response(payload))

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            result = run(ms.make_call("+19995550000"))

        assert result["call_sid"] == "CA456"
        posted = mock_client.post.call_args[1]["json"]
        assert posted["message"] == ""

    def test_make_call_http_error_propagates(self):
        resp = _mock_response({}, status_code=500)
        resp.raise_for_status.side_effect = Exception("Server error")
        mock_client = _mock_async_client(resp)

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Server error"):
                run(ms.make_call("+12025551234"))

    def test_make_call_uses_webhook_base(self):
        payload = {"call_sid": "CA789", "status": "queued"}
        mock_client = _mock_async_client(_mock_response(payload))

        with patch("mcp_server.WEBHOOK_BASE", "http://example.com:9999"):
            with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
                run(ms.make_call("+10000000000"))

        url = mock_client.post.call_args[0][0]
        assert url.startswith("http://example.com:9999")


# ─── call_status ──────────────────────────────────────────────────────────────

class TestCallStatus:

    def test_call_status_success(self):
        payload = {"status": "in-progress", "duration": "42"}
        mock_client = _mock_async_client(_mock_response(payload))

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            result = run(ms.call_status("CA123"))

        assert result["status"] == "in-progress"
        mock_client.get.assert_awaited_once()
        url = mock_client.get.call_args[0][0]
        assert "CA123" in url

    def test_call_status_not_found_propagates(self):
        resp = _mock_response({}, status_code=404)
        resp.raise_for_status.side_effect = Exception("Not found")
        mock_client = _mock_async_client(resp)
        mock_client.get = AsyncMock(return_value=resp)

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Not found"):
                run(ms.call_status("CA_MISSING"))


# ─── join_google_meet ─────────────────────────────────────────────────────────

class TestJoinGoogleMeet:

    def test_join_google_meet_success(self):
        payload = {"call_sid": "CAabc", "dial_in_number": "+18005551234"}
        mock_client = _mock_async_client(_mock_response(payload))

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            result = run(ms.join_google_meet("https://meet.google.com/abc-defg-hij"))

        assert result == payload
        posted = mock_client.post.call_args[1]["json"]
        assert posted["meet_url"] == "https://meet.google.com/abc-defg-hij"

    def test_join_google_meet_posts_to_correct_endpoint(self):
        payload = {"call_sid": "CAdef", "dial_in_number": "+18005559999"}
        mock_client = _mock_async_client(_mock_response(payload))

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            run(ms.join_google_meet("https://meet.google.com/xyz-abcd-efg"))

        url = mock_client.post.call_args[0][0]
        assert url.endswith("/call/meet")

    def test_join_google_meet_error_propagates(self):
        resp = _mock_response({}, status_code=422)
        resp.raise_for_status.side_effect = Exception("Unprocessable")
        mock_client = _mock_async_client(resp)

        with patch("mcp_server.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Unprocessable"):
                run(ms.join_google_meet("not-a-meet-url"))


# ─── get_call_history ─────────────────────────────────────────────────────────

class TestGetCallHistory:

    def test_get_call_history_from_call_log_list(self, tmp_path):
        call_log = tmp_path / "call_log.json"
        records = [{"call_sid": f"CA{i}", "status": "completed"} for i in range(10)]
        call_log.write_text(json.dumps(records))

        with patch("mcp_server.CALL_LOG_PATH", call_log):
            result = run(ms.get_call_history(limit=3))

        assert len(result) == 3
        assert result[0]["call_sid"] == "CA0"

    def test_get_call_history_from_call_log_dict(self, tmp_path):
        call_log = tmp_path / "call_log.json"
        records = [{"call_sid": "CA99", "status": "completed"}]
        call_log.write_text(json.dumps({"calls": records}))

        with patch("mcp_server.CALL_LOG_PATH", call_log):
            result = run(ms.get_call_history())

        assert result[0]["call_sid"] == "CA99"

    def test_get_call_history_falls_back_to_memory_files(self, tmp_path):
        # call_log does not exist
        fake_log = tmp_path / "nonexistent.json"
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        for i in range(3):
            f = memory_dir / f"call_{i}.json"
            f.write_text(json.dumps({"call_sid": f"MEM{i}"}))

        with patch("mcp_server.CALL_LOG_PATH", fake_log):
            with patch("mcp_server.MEMORY_DIR", memory_dir):
                result = run(ms.get_call_history(limit=2))

        assert len(result) == 2

    def test_get_call_history_empty_when_no_sources(self, tmp_path):
        fake_log = tmp_path / "nonexistent.json"
        fake_memory = tmp_path / "no_memory"

        with patch("mcp_server.CALL_LOG_PATH", fake_log):
            with patch("mcp_server.MEMORY_DIR", fake_memory):
                result = run(ms.get_call_history())

        assert result == []

    def test_get_call_history_handles_malformed_log(self, tmp_path):
        call_log = tmp_path / "call_log.json"
        call_log.write_text("not valid json{{{")
        fake_memory = tmp_path / "no_memory"

        with patch("mcp_server.CALL_LOG_PATH", call_log):
            with patch("mcp_server.MEMORY_DIR", fake_memory):
                result = run(ms.get_call_history())

        assert result == []

    def test_get_call_history_default_limit_is_5(self, tmp_path):
        call_log = tmp_path / "call_log.json"
        records = [{"call_sid": f"CA{i}"} for i in range(20)]
        call_log.write_text(json.dumps(records))

        with patch("mcp_server.CALL_LOG_PATH", call_log):
            result = run(ms.get_call_history())

        assert len(result) == 5
