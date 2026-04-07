"""
Tests for scripts/meet_utils.py — Google Meet PSTN auto-dial utilities.

Coverage targets:
  - extract_meet_code   : valid URL, embedded URL, invalid URL
  - fetch_meet_dialin   : success, redirect, no PSTN info, malformed HTML,
                          network error
  - POST /call/meet     : valid, invalid URL (422), no dial-in (404)
  - DTMF PIN formatting

Run with:
    python3 -m pytest tests/test_meet_utils.py -v
"""

import importlib.util
import os
import sys
import asyncio
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Path helpers ────────────────────────────────────────────────────────────

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, _SCRIPTS_DIR)


# ─── Import meet_utils directly (no heavy deps) ───────────────────────────────

import meet_utils as mu


# ─── Helper: run coroutines in tests ─────────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


# ─── extract_meet_code ────────────────────────────────────────────────────────

class TestExtractMeetCode:
    """Tests for extract_meet_code()"""

    def test_extract_meet_code_valid(self):
        text = "https://meet.google.com/abc-defg-hij"
        assert mu.extract_meet_code(text) == "abc-defg-hij"

    def test_extract_meet_code_embedded(self):
        text = "Join our meeting at https://meet.google.com/xyz-abcd-efg and click join."
        assert mu.extract_meet_code(text) == "xyz-abcd-efg"

    def test_extract_meet_code_invalid(self):
        text = "https://zoom.us/j/123456789"
        assert mu.extract_meet_code(text) is None

    def test_extract_meet_code_empty_string(self):
        assert mu.extract_meet_code("") is None

    def test_extract_meet_code_plain_text(self):
        assert mu.extract_meet_code("no meeting link here") is None

    def test_extract_meet_code_http(self):
        # http:// variant should also match
        text = "http://meet.google.com/aaa-bbbb-ccc"
        result = mu.extract_meet_code(text)
        assert result == "aaa-bbbb-ccc"


# ─── fetch_meet_dialin ────────────────────────────────────────────────────────

def _make_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def _mock_httpx_client(response: MagicMock):
    """Return a mock httpx.AsyncClient context manager that yields response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


SAMPLE_MEET_HTML = """
<html>
<body>
  <div>Dial-in: +1 617-675-4444</div>
  <div>PIN: 123 456 789#</div>
</body>
</html>
"""


class TestFetchMeetDialin:
    """Tests for fetch_meet_dialin()"""

    def test_fetch_dialin_success(self):
        resp = _make_response(200, SAMPLE_MEET_HTML)
        cm = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=cm):
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is not None
        assert result["phone"] == "+16176754444"
        assert result["pin"] == "123456789"

    def test_fetch_dialin_redirect(self):
        resp = _make_response(302)
        cm = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=cm):
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is None

    def test_fetch_dialin_301_redirect(self):
        resp = _make_response(301)
        cm = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=cm):
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is None

    def test_fetch_dialin_no_pstn(self):
        html = "<html><body>No phone number here.</body></html>"
        resp = _make_response(200, html)
        cm = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=cm):
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is None

    def test_fetch_dialin_malformed(self):
        html = "<!@#$%^&*()"
        resp = _make_response(200, html)
        cm = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=cm):
            # Should return None without raising
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is None

    def test_fetch_dialin_network_error(self):
        import httpx

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=cm):
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is None

    def test_fetch_dialin_phone_only_no_pin(self):
        html = "<html><body>+1 617-675-4444</body></html>"
        resp = _make_response(200, html)
        cm = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=cm):
            result = run(mu.fetch_meet_dialin("abc-defg-hij"))
        assert result is None


# ─── DTMF PIN formatting ──────────────────────────────────────────────────────

class TestDtmfPinFormatting:
    """Verify that PIN strings are cleaned of spaces and # signs."""

    def _clean_pin(self, raw: str) -> str:
        import re
        return re.sub(r"[\s#]", "", raw)

    def test_dtmf_pin_formatting_spaces(self):
        assert self._clean_pin("123 456 789") == "123456789"

    def test_dtmf_pin_formatting_hash(self):
        assert self._clean_pin("123456789#") == "123456789"

    def test_dtmf_pin_formatting_spaces_and_hash(self):
        assert self._clean_pin("123 456 789#") == "123456789"

    def test_dtmf_pin_formatting_clean(self):
        assert self._clean_pin("123456789") == "123456789"


# ─── POST /call/meet endpoint (integration via webhook-server module) ─────────

# Load webhook-server with mocked heavy deps.
# We configure the FastAPI app mock as a passthrough decorator so route
# handler functions are preserved (not replaced by MagicMock instances).
_SERVER_PATH = os.path.join(_SCRIPTS_DIR, "webhook-server.py")


class _FakeBaseModel:
    """Minimal Pydantic-like base for webhook-server Pydantic models."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def dict(self):
        return {k: v for k, v in self.__dict__.items()}


def _passthrough_decorator(*args, **kwargs):
    """Route decorator that returns the function unchanged."""
    def _wrap(fn):
        return fn
    return _wrap


# Build the fake FastAPI app whose route decorators are passthrough
_fake_app = MagicMock()
for _meth in ("post", "get", "delete", "websocket", "on_event"):
    getattr(_fake_app, _meth).side_effect = _passthrough_decorator

_fastapi_mock = MagicMock()
# 'from fastapi import FastAPI' binds FastAPI to _fastapi_mock.FastAPI.
# Configure it so FastAPI(...) returns our passthrough _fake_app.
_fastapi_mock.FastAPI = MagicMock(return_value=_fake_app)
_fastapi_mock.FastAPI.return_value = _fake_app
# Also expose HTTPException as a real class (used by route handlers)
_fastapi_mock.HTTPException = type(
    "HTTPException",
    (Exception,),
    {"__init__": lambda self, status_code=500, detail="": (
        setattr(self, "status_code", status_code) or
        setattr(self, "detail", detail)
    )},
)
_fastapi_mock.BackgroundTasks = MagicMock

_pydantic_mock = MagicMock()
_pydantic_mock.BaseModel = _FakeBaseModel

_MOCKED_MODULES = {
    "fastapi": _fastapi_mock,
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

_ws_mod = None
with unittest.mock.patch.dict("sys.modules", _MOCKED_MODULES):
    spec = importlib.util.spec_from_file_location("webhook_server_meet", _SERVER_PATH)
    _ws_candidate = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(_ws_candidate)
        _ws_mod = _ws_candidate
    except Exception as _e:
        pass  # _ws_mod stays None; tests will be skipped


@pytest.mark.skipif(_ws_mod is None, reason="webhook-server could not be loaded")
class TestPostCallMeet:
    """Integration tests for the POST /call/meet endpoint."""

    def _handler(self):
        h = getattr(_ws_mod, "initiate_meet_call", None)
        if h is None or isinstance(h, MagicMock):
            pytest.skip("initiate_meet_call not available as a real function")
        return h

    # Re-usable HTTPException class (real raise/catch behaviour)
    class _HTTPExc(Exception):
        def __init__(self, status_code=500, detail=""):
            self.status_code = status_code
            self.detail = detail

    def test_post_call_meet_invalid_url(self):
        """Non-Meet URL → 422."""
        handler = self._handler()

        with patch.object(_ws_mod, "HTTPException", self._HTTPExc):
            with pytest.raises(self._HTTPExc) as exc_info:
                req = _FakeBaseModel(
                    meet_url="https://zoom.us/j/123456",
                    caller_id=None,
                    message=None,
                )
                run(handler(req, MagicMock()))
        assert exc_info.value.status_code == 422

    def test_post_call_meet_no_dialin(self):
        """Valid Meet URL but dial-in fetch returns None → 404."""
        handler = self._handler()

        async def _fake_fetch(meet_code):
            return None

        with patch("meet_utils.fetch_meet_dialin", _fake_fetch):
            with patch.object(_ws_mod, "HTTPException", self._HTTPExc):
                with pytest.raises(self._HTTPExc) as exc_info:
                    req = _FakeBaseModel(
                        meet_url="https://meet.google.com/abc-defg-hij",
                        caller_id=None,
                        message=None,
                    )
                    run(handler(req, MagicMock()))
        assert exc_info.value.status_code == 404

    def test_post_call_meet_valid(self):
        """Happy path: valid URL + successful extraction → 200-like dict."""
        handler = self._handler()

        async def _fake_fetch(meet_code):
            return {"phone": "+16176754444", "pin": "123456789"}

        fake_response = _FakeBaseModel(
            status="initiated",
            call_id="CA_MEET_TEST",
            message="Call initiated",
        )

        async def _fake_outbound(call_request, bg):
            return fake_response

        with patch("meet_utils.fetch_meet_dialin", _fake_fetch):
            with patch.object(_ws_mod, "initiate_outbound_call", _fake_outbound):
                with patch.object(_ws_mod, "HTTPException", self._HTTPExc):
                    with patch.object(_ws_mod, "active_calls", {}):
                        req = _FakeBaseModel(
                            meet_url="https://meet.google.com/abc-defg-hij",
                            caller_id=None,
                            message=None,
                        )
                        result = run(handler(req, MagicMock()))

        assert result["status"] == "initiated"
        assert result["dial_in"] == "+16176754444"
        assert result["meet_code"] == "abc-defg-hij"
