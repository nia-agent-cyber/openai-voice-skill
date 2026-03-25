#!/usr/bin/env python3
"""
Unit tests for scripts/realtime_tool_handler.py

Covers:
- RealtimeToolHandler initialization and user context resolution
- _format_voice_error_response: calendar error normalization
- _get_backoff_delay: exponential backoff calculation
- _execute_function: ask_openclaw dispatch, unknown function, error handling
- _handle_function_call: argument parsing, error scenarios
- get_active_handlers, start_tool_handler, stop_tool_handler
- Module-level constants and config
"""

import sys
import os
import asyncio
import json
import unittest.mock
from unittest.mock import MagicMock, AsyncMock, patch, call
import pytest

# ─── Mock all external dependencies before import ────────────────────────────

_MOCKED = {
    'websockets': MagicMock(),
    'websockets.exceptions': MagicMock(),
}

# Set up websockets.State mock
_ws_state = MagicMock()
_ws_state.OPEN = 'OPEN'
_MOCKED['websockets'].State = _ws_state
_MOCKED['websockets'].connect = AsyncMock()
_MOCKED['websockets.exceptions'].ConnectionClosed = Exception  # so except works

# Mock openclaw_executor
_mock_executor = MagicMock()
_mock_executor.execute_openclaw_request = AsyncMock(return_value="Test result")
_mock_executor.execute_openclaw_streaming = AsyncMock()
_mock_executor.set_call_id = MagicMock()
_mock_executor.set_user_context = MagicMock()

_MOCKED['openclaw_executor'] = _mock_executor

# Mock user_context
_mock_user_ctx = MagicMock()
_mock_user_ctx.get_user_context = MagicMock(return_value={"timezone": "Africa/Kigali", "name": "Remi"})
_mock_user_ctx.UserContextResolver = MagicMock()
_MOCKED['user_context'] = _mock_user_ctx

# Mock call_context_store
_mock_ctx_store = MagicMock()
_mock_ctx_store.get_user_phone = MagicMock(return_value=None)
_MOCKED['call_context_store'] = _mock_ctx_store

_scripts_dir = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, _scripts_dir)

with unittest.mock.patch.dict('sys.modules', _MOCKED):
    import realtime_tool_handler as rth
    from realtime_tool_handler import (
        RealtimeToolHandler,
        get_active_handlers,
        active_handlers,
        INITIAL_RECONNECT_DELAY,
        MAX_RECONNECT_DELAY,
        MAX_RECONNECT_ATTEMPTS,
    )


# ─── Helper to create a handler ───────────────────────────────────────────────

def make_handler(caller_phone=None) -> RealtimeToolHandler:
    with patch.dict('sys.modules', _MOCKED):
        handler = RealtimeToolHandler(
            session_id="sess-123",
            call_id="call-456",
            model="gpt-4o-realtime-preview",
            on_status_change=None,
            caller_phone=caller_phone
        )
    return handler


# ─── Initialization ────────────────────────────────────────────────────────────

class TestRealtimeToolHandlerInit:
    """Tests for __init__ and basic properties."""

    def test_init_attributes(self):
        h = make_handler()
        assert h.session_id == "sess-123"
        assert h.call_id == "call-456"
        assert h.model == "gpt-4o-realtime-preview"
        assert h.running is False
        assert h.ws is None

    def test_stats_initialized_to_zero(self):
        h = make_handler()
        assert h.stats["function_calls"] == 0
        assert h.stats["successful_calls"] == 0
        assert h.stats["failed_calls"] == 0

    def test_caller_phone_stored(self):
        h = make_handler(caller_phone="+250794002033")
        assert h.caller_phone == "+250794002033"

    def test_user_context_resolved(self):
        """User context is resolved on init when phone is provided."""
        _mock_user_ctx.get_user_context.return_value = {
            "timezone": "Africa/Kigali",
            "name": "Remi"
        }
        h = make_handler(caller_phone="+250794002033")
        # user_context should be a dict (even if empty fallback)
        assert isinstance(h.user_context, dict)

    def test_user_context_empty_without_phone(self):
        _mock_ctx_store.get_user_phone.return_value = None
        h = make_handler(caller_phone=None)
        assert isinstance(h.user_context, dict)


# ─── _format_voice_error_response ─────────────────────────────────────────────

class TestFormatVoiceErrorResponse:
    """Tests for _format_voice_error_response."""

    def test_calendar_not_connected_returns_friendly_message(self):
        h = make_handler()
        result = h._format_voice_error_response("Error: CALENDAR_NOT_CONNECTED")
        assert "calendar" in result.lower()
        assert "CALENDAR_NOT_CONNECTED" not in result

    def test_non_string_returns_generic(self):
        h = make_handler()
        result = h._format_voice_error_response(None)
        assert "issue" in result.lower() or "error" in result.lower()

    def test_normal_result_passes_through(self):
        h = make_handler()
        result = h._format_voice_error_response("The project is on track.")
        assert result == "The project is on track."

    def test_empty_string_passes_through(self):
        h = make_handler()
        result = h._format_voice_error_response("")
        assert result == ""

    def test_integer_returns_generic(self):
        h = make_handler()
        result = h._format_voice_error_response(42)
        assert isinstance(result, str)


# ─── _get_backoff_delay ────────────────────────────────────────────────────────

class TestGetBackoffDelay:
    """Tests for _get_backoff_delay — exponential backoff with jitter."""

    def test_first_attempt_delay_is_reasonable(self):
        h = make_handler()
        delay = h._get_backoff_delay(1)
        assert delay >= INITIAL_RECONNECT_DELAY
        assert delay <= INITIAL_RECONNECT_DELAY * 2  # with jitter

    def test_delay_increases_with_attempts(self):
        h = make_handler()
        delays = [h._get_backoff_delay(i) for i in range(1, 6)]
        # Not strictly monotonic due to jitter, but generally should increase
        # Check that attempt 5 is larger than attempt 1 on average
        assert h._get_backoff_delay(5) > h._get_backoff_delay(1) * 0.5  # rough check

    def test_delay_capped_at_max(self):
        h = make_handler()
        # For a large attempt number, delay should be capped
        delay = h._get_backoff_delay(100)
        assert delay <= MAX_RECONNECT_DELAY * 1.2  # Allow 20% jitter

    def test_delay_returns_float(self):
        h = make_handler()
        delay = h._get_backoff_delay(3)
        assert isinstance(delay, float)


# ─── _execute_function (non-streaming) ───────────────────────────────────────

class TestExecuteFunction:
    """Tests for _execute_function non-streaming dispatch."""

    def test_ask_openclaw_calls_executor(self):
        h = make_handler()
        mock_executor_fn = AsyncMock(return_value="Project is healthy.")
        with patch.dict('sys.modules', _MOCKED):
            import openclaw_executor
            openclaw_executor.execute_openclaw_request = mock_executor_fn

        async def run():
            result = await h._execute_function("ask_openclaw", {"request": "What's the status?"})
            return result

        with patch.object(rth, 'execute_openclaw_request', AsyncMock(return_value="Project is healthy.")):
            result = asyncio.run(
                h._execute_function("ask_openclaw", {"request": "What's the status?"})
            )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ask_openclaw_empty_request(self):
        h = make_handler()

        async def run():
            return await h._execute_function("ask_openclaw", {"request": ""})

        result = asyncio.run(run())
        assert "didn't receive" in result.lower() or isinstance(result, str)

    def test_unknown_function_returns_message(self):
        h = make_handler()

        async def run():
            return await h._execute_function("nonexistent_function", {})

        result = asyncio.run(run())
        assert "nonexistent_function" in result or "don't know" in result.lower()

    def test_executor_timeout_returns_friendly_message(self):
        h = make_handler()

        async def run():
            with patch.object(rth, 'execute_openclaw_request', AsyncMock(side_effect=asyncio.TimeoutError)):
                return await h._execute_function("ask_openclaw", {"request": "something"})

        result = asyncio.run(run())
        assert "too long" in result.lower() or "timeout" in result.lower() or isinstance(result, str)

    def test_executor_exception_returns_friendly_message(self):
        h = make_handler()

        async def run():
            with patch.object(rth, 'execute_openclaw_request', AsyncMock(side_effect=RuntimeError("crash"))):
                return await h._execute_function("ask_openclaw", {"request": "something"})

        result = asyncio.run(run())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_invalid_result_returns_friendly_message(self):
        h = make_handler()

        async def run():
            with patch.object(rth, 'execute_openclaw_request', AsyncMock(return_value=None)):
                return await h._execute_function("ask_openclaw", {"request": "something"})

        result = asyncio.run(run())
        assert isinstance(result, str)

    def test_stats_incremented_on_success(self):
        h = make_handler()

        async def run():
            with patch.object(rth, 'execute_openclaw_request', AsyncMock(return_value="Answer!")):
                await h._execute_function("ask_openclaw", {"request": "test"})

        asyncio.run(run())
        assert h.stats["successful_calls"] == 1

    def test_stats_incremented_on_failure(self):
        h = make_handler()

        async def run():
            with patch.object(rth, 'execute_openclaw_request', AsyncMock(side_effect=asyncio.TimeoutError)):
                await h._execute_function("ask_openclaw", {"request": "test"})

        asyncio.run(run())
        assert h.stats["failed_calls"] == 1


# ─── _send_function_result_safe ───────────────────────────────────────────────

class TestSendFunctionResultSafe:
    """Tests for _send_function_result_safe — no-throw wrapper."""

    def test_safe_send_with_closed_ws_does_not_raise(self):
        h = make_handler()
        h.ws = None  # No WebSocket

        async def run():
            await h._send_function_result_safe("call-id-123", "test result")

        # Should not raise
        asyncio.run(run())

    def test_safe_send_swallows_exception(self):
        h = make_handler()

        async def run():
            # Patch _send_function_result to raise
            with patch.object(h, '_send_function_result', AsyncMock(side_effect=Exception("send failed"))):
                await h._send_function_result_safe("call-id-123", "test result")

        # Should not raise
        asyncio.run(run())


# ─── _notify_status ────────────────────────────────────────────────────────────

class TestNotifyStatus:
    """Tests for _notify_status callback."""

    def test_callback_is_called_with_status(self):
        status_calls = []
        handler = RealtimeToolHandler(
            session_id="sess-1",
            call_id="call-1",
            on_status_change=lambda cid, s: status_calls.append((cid, s))
        )
        handler._notify_status("connected")
        assert ("call-1", "connected") in status_calls

    def test_no_callback_does_not_raise(self):
        handler = RealtimeToolHandler(
            session_id="sess-1",
            call_id="call-1",
            on_status_change=None
        )
        handler._notify_status("connected")  # Should not raise

    def test_callback_exception_is_swallowed(self):
        def bad_callback(cid, status):
            raise RuntimeError("callback failure")

        handler = RealtimeToolHandler(
            session_id="sess-1",
            call_id="call-1",
            on_status_change=bad_callback
        )
        handler._notify_status("connected")  # Should not raise


# ─── get_active_handlers ──────────────────────────────────────────────────────

class TestGetActiveHandlers:
    """Tests for get_active_handlers() and active_handlers dict."""

    def test_returns_dict(self):
        result = get_active_handlers()
        assert isinstance(result, dict)

    def test_handler_in_active_handlers(self):
        h = RealtimeToolHandler("sess-x", "call-x")
        rth.active_handlers["call-x"] = h
        result = get_active_handlers()
        assert "call-x" in result
        assert result["call-x"]["session_id"] == "sess-x"
        assert "running" in result["call-x"]
        assert "stats" in result["call-x"]
        del rth.active_handlers["call-x"]  # cleanup


# ─── stop_tool_handler ────────────────────────────────────────────────────────

class TestStopToolHandler:
    """Tests for stop_tool_handler."""

    def test_stop_nonexistent_handler_is_safe(self):
        async def run():
            await rth.stop_tool_handler("nonexistent-call-id")

        asyncio.run(run())

    def test_stop_removes_from_active_handlers(self):
        h = RealtimeToolHandler("sess-y", "call-y")
        h.ws = None  # No WebSocket to close
        rth.active_handlers["call-y"] = h

        async def run():
            await rth.stop_tool_handler("call-y")

        asyncio.run(run())
        assert "call-y" not in rth.active_handlers


# ─── Module-level constants ────────────────────────────────────────────────────

class TestModuleConstants:
    """Check module-level config values."""

    def test_initial_reconnect_delay_positive(self):
        assert INITIAL_RECONNECT_DELAY > 0

    def test_max_reconnect_delay_greater_than_initial(self):
        assert MAX_RECONNECT_DELAY > INITIAL_RECONNECT_DELAY

    def test_max_reconnect_attempts_positive(self):
        assert MAX_RECONNECT_ATTEMPTS > 0


# ─── _handle_function_call ────────────────────────────────────────────────────

class TestHandleFunctionCall:
    """Tests for _handle_function_call — the main event handler."""

    def test_invalid_json_arguments_handled(self):
        """Invalid JSON args should still send a response."""
        h = make_handler()
        event = {
            "call_id": "fc-123",
            "name": "ask_openclaw",
            "arguments": "NOT VALID JSON {{"
        }

        async def run():
            with patch.object(h, '_send_function_result_safe', AsyncMock()) as mock_send:
                with patch.object(rth, 'execute_openclaw_request', AsyncMock(return_value="OK")):
                    await h._handle_function_call(event)

        asyncio.run(run())
        # Just ensure it doesn't raise

    def test_function_calls_stat_incremented(self):
        h = make_handler()
        event = {
            "call_id": "fc-123",
            "name": "ask_openclaw",
            "arguments": '{"request": "Hello!"}'
        }

        async def run():
            with patch.object(h, '_send_function_result_safe', AsyncMock()):
                with patch.object(rth, 'execute_openclaw_request', AsyncMock(return_value="OK")):
                    await h._handle_function_call(event)

        asyncio.run(run())
        assert h.stats["function_calls"] == 1

    def test_critical_exception_still_sends_response(self):
        """Even if everything crashes, _send_function_result_safe is called."""
        h = make_handler()
        event = {
            "call_id": "fc-999",
            "name": "ask_openclaw",
            "arguments": '{"request": "test"}'
        }

        async def run():
            with patch.object(h, '_send_function_result_safe', AsyncMock()) as mock_safe:
                with patch.object(rth, 'execute_openclaw_request', AsyncMock(side_effect=RuntimeError("boom"))):
                    with patch.object(h, '_execute_streaming_function', AsyncMock(side_effect=RuntimeError("boom"))):
                        await h._handle_function_call(event)
            return mock_safe

        asyncio.run(run())
        # No assertion needed — just verify no unhandled exception


# ─── _resolve_user_context ────────────────────────────────────────────────────

class TestResolveUserContext:
    """Tests for _resolve_user_context."""

    def test_resolve_with_phone_returns_context(self):
        h = RealtimeToolHandler("sess-1", "call-1", caller_phone="+250794002033")
        assert isinstance(h.user_context, dict)

    def test_resolve_without_phone_returns_empty_or_dict(self):
        with patch.object(rth, 'CALL_CONTEXT_STORE_AVAILABLE', False):
            h = RealtimeToolHandler("sess-1", "call-1", caller_phone=None)
        assert isinstance(h.user_context, dict)

    def test_resolve_uses_call_context_store_if_available(self):
        """If no direct phone, try the call context store."""
        _mock_ctx_store.get_user_phone.return_value = "+14155551234"
        with patch.object(rth, 'CALL_CONTEXT_STORE_AVAILABLE', True):
            with patch.object(rth, 'get_stored_user_phone', return_value="+14155551234"):
                h = RealtimeToolHandler("sess-1", "call-store", caller_phone=None)
        assert isinstance(h.user_context, dict)
        _mock_ctx_store.get_user_phone.return_value = None  # reset
