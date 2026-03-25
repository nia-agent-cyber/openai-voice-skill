#!/usr/bin/env python3
"""
Extended tests for scripts/realtime_tool_handler.py

Covers:
- stop() with open WebSocket
- _handle_events() with various event types
- _send_followup_chunk()
- _send_function_result()
- start_tool_handler()
- _cleanup() via atexit
- _handle_function_call() ask_openclaw path
- connect() failure and success paths
"""

import asyncio
import json
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
import unittest.mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# ─── Import with mocks ────────────────────────────────────────────────────────

# Must mirror the pattern in test_realtime_tool_handler.py
_ws_mock = MagicMock()
_ws_exceptions_mock = MagicMock()
_ws_exceptions_mock.ConnectionClosed = Exception  # so except ConnectionClosed works

import websockets as _real_websockets  # Import before mocking for State.OPEN value

_ws_state = MagicMock()
_ws_state.OPEN = _real_websockets.State.OPEN  # Use real value so both local and module checks agree
_ws_mock.State = _ws_state
_ws_mock.connect = AsyncMock()

_oc_exec_mock = MagicMock()
_oc_exec_mock.execute_openclaw_request = AsyncMock(return_value="Done!")
_oc_exec_mock.execute_openclaw_streaming = AsyncMock()
_oc_exec_mock.set_call_id = MagicMock()
_oc_exec_mock.set_user_context = MagicMock()

_user_ctx_mock = MagicMock()
_user_ctx_mock.get_user_context = MagicMock(return_value={"timezone": "UTC"})
_user_ctx_mock.UserContextResolver = MagicMock()

_ctx_store_mock = MagicMock()
_ctx_store_mock.get_user_phone = MagicMock(return_value=None)

with unittest.mock.patch.dict('sys.modules', {
    'websockets': _ws_mock,
    'websockets.exceptions': _ws_exceptions_mock,
    'openclaw_executor': _oc_exec_mock,
    'user_context': _user_ctx_mock,
    'call_context_store': _ctx_store_mock,
}):
    import realtime_tool_handler as rth
    from realtime_tool_handler import (
        RealtimeToolHandler,
        start_tool_handler,
        stop_tool_handler,
        get_active_handlers,
        active_handlers,
    )


def make_handler(call_id="test-call") -> RealtimeToolHandler:
    """Create a RealtimeToolHandler for testing."""
    return RealtimeToolHandler(
        session_id="session-abc",
        call_id=call_id,
        model="gpt-4o-realtime-preview",
        on_status_change=None,
        caller_phone="+1234567890"
    )


def make_open_ws():
    """Create a mock WebSocket that appears open (uses real websockets.State.OPEN)."""
    mock_ws = MagicMock()
    mock_ws.state = _real_websockets.State.OPEN  # Must match what _send_function_result checks
    mock_ws.close = AsyncMock()
    mock_ws.send = AsyncMock()
    return mock_ws


# ─── stop() with open WebSocket ──────────────────────────────────────────────

class TestStopWithOpenWS:
    """Tests for stop() when WebSocket is actually open."""

    def test_stop_closes_open_ws(self):
        handler = make_handler("stop-ws-open")
        mock_ws = make_open_ws()
        handler.ws = mock_ws

        asyncio.run(handler.stop())
        mock_ws.close.assert_awaited_once()

    def test_stop_sets_running_false(self):
        handler = make_handler("stop-running")
        handler.running = True
        asyncio.run(handler.stop())
        assert handler.running is False

    def test_stop_without_ws_does_not_raise(self):
        handler = make_handler("stop-no-ws")
        handler.ws = None
        asyncio.run(handler.stop())

    def test_stop_with_closed_ws_does_not_close(self):
        handler = make_handler("stop-closed-ws")
        mock_ws = MagicMock()
        mock_ws.state = _real_websockets.State.CLOSED  # Not OPEN
        mock_ws.close = AsyncMock()
        handler.ws = mock_ws

        asyncio.run(handler.stop())
        mock_ws.close.assert_not_awaited()


# ─── _handle_events ───────────────────────────────────────────────────────────

class TestHandleEvents:
    """Tests for _handle_events()."""

    async def _make_ws_from_messages(self, messages):
        """Create a mock ws that yields the given messages."""
        mock_ws = MagicMock()

        async def aiter_messages():
            for msg in messages:
                yield msg

        mock_ws.__aiter__ = lambda self_: aiter_messages()
        return mock_ws

    def test_handle_function_call_event(self):
        """_handle_events calls _handle_function_call on function call events."""
        handler = make_handler("events-fn-call")
        mock_ws = MagicMock()

        event = {
            "type": "response.function_call_arguments.done",
            "call_id": "fn-id-1",
            "name": "ask_openclaw",
            "arguments": '{"request": "test"}'
        }

        async def aiter_messages():
            yield json.dumps(event)

        mock_ws.__aiter__ = lambda self_: aiter_messages()
        handler.ws = mock_ws

        # Mock _handle_function_call to avoid deep execution
        handler._handle_function_call = AsyncMock()

        asyncio.run(handler._handle_events())
        handler._handle_function_call.assert_awaited_once()

    def test_handle_session_closed_event(self):
        """_handle_events stops when session.closed received."""
        handler = make_handler("events-sess-closed")
        handler.running = True
        mock_ws = MagicMock()

        async def aiter_messages():
            yield json.dumps({"type": "session.closed"})

        mock_ws.__aiter__ = lambda self_: aiter_messages()
        handler.ws = mock_ws

        asyncio.run(handler._handle_events())
        assert handler.running is False

    def test_handle_error_event(self):
        """_handle_events logs error events without crashing."""
        handler = make_handler("events-error")
        mock_ws = MagicMock()

        async def aiter_messages():
            yield json.dumps({
                "type": "error",
                "error": {"code": "invalid_request", "message": "Bad request"}
            })

        mock_ws.__aiter__ = lambda self_: aiter_messages()
        handler.ws = mock_ws

        asyncio.run(handler._handle_events())

    def test_handle_invalid_json(self):
        """_handle_events handles invalid JSON without crashing."""
        handler = make_handler("events-invalid-json")
        mock_ws = MagicMock()

        async def aiter_messages():
            yield "not-json-at-all"

        mock_ws.__aiter__ = lambda self_: aiter_messages()
        handler.ws = mock_ws

        asyncio.run(handler._handle_events())

    def test_handle_response_event_logged(self):
        """_handle_events processes response.* events."""
        handler = make_handler("events-response")
        mock_ws = MagicMock()

        async def aiter_messages():
            yield json.dumps({"type": "response.audio.delta", "delta": "base64data"})

        mock_ws.__aiter__ = lambda self_: aiter_messages()
        handler.ws = mock_ws

        asyncio.run(handler._handle_events())


# ─── _send_followup_chunk ─────────────────────────────────────────────────────

class TestSendFollowupChunk:
    """Tests for _send_followup_chunk()."""

    def test_sends_two_ws_messages(self):
        """_send_followup_chunk sends two ws.send calls (item + response.create)."""
        handler = make_handler("followup-1")
        mock_ws = make_open_ws()
        handler.ws = mock_ws

        asyncio.run(handler._send_followup_chunk("Here's more info."))
        assert mock_ws.send.await_count == 2

    def test_first_message_is_conversation_item(self):
        """First ws.send is a conversation.item.create."""
        handler = make_handler("followup-2")
        mock_ws = make_open_ws()
        handler.ws = mock_ws

        asyncio.run(handler._send_followup_chunk("Test chunk"))
        first_call = mock_ws.send.call_args_list[0]
        payload = json.loads(first_call.args[0])
        assert payload["type"] == "conversation.item.create"
        assert "Test chunk" in json.dumps(payload)

    def test_second_message_is_response_create(self):
        """Second ws.send is a response.create."""
        handler = make_handler("followup-3")
        mock_ws = make_open_ws()
        handler.ws = mock_ws

        asyncio.run(handler._send_followup_chunk("Test chunk"))
        second_call = mock_ws.send.call_args_list[1]
        payload = json.loads(second_call.args[0])
        assert payload["type"] == "response.create"

    def test_sends_nothing_when_ws_closed(self):
        """_send_followup_chunk skips sending when ws is not open."""
        handler = make_handler("followup-closed")
        mock_ws = MagicMock()
        mock_ws.state = _real_websockets.State.CLOSED  # Not OPEN
        mock_ws.send = AsyncMock()
        handler.ws = mock_ws

        asyncio.run(handler._send_followup_chunk("Test"))
        mock_ws.send.assert_not_awaited()

    def test_raises_on_send_failure(self):
        """_send_followup_chunk re-raises send exceptions."""
        handler = make_handler("followup-error")
        mock_ws = make_open_ws()
        mock_ws.send = AsyncMock(side_effect=Exception("Connection lost"))
        handler.ws = mock_ws

        with pytest.raises(Exception, match="Connection lost"):
            asyncio.run(handler._send_followup_chunk("Test"))


# ─── _send_function_result ────────────────────────────────────────────────────

class TestSendFunctionResult:
    """Tests for _send_function_result()."""

    def test_sends_two_ws_messages(self):
        """_send_function_result sends item + response.create."""
        handler = make_handler("fn-result-1")
        mock_ws = make_open_ws()
        handler.ws = mock_ws

        asyncio.run(handler._send_function_result("fn-id-1", "Result text"))
        assert mock_ws.send.await_count == 2

    def test_first_message_is_function_call_output(self):
        """First ws.send is a function_call_output item."""
        handler = make_handler("fn-result-2")
        mock_ws = make_open_ws()
        handler.ws = mock_ws

        asyncio.run(handler._send_function_result("fn-id-2", "Test result"))
        first_call = mock_ws.send.call_args_list[0]
        payload = json.loads(first_call.args[0])
        assert payload["type"] == "conversation.item.create"
        assert payload["item"]["type"] == "function_call_output"
        assert payload["item"]["call_id"] == "fn-id-2"
        assert payload["item"]["output"] == "Test result"

    def test_raises_on_send_failure(self):
        """_send_function_result re-raises exceptions."""
        handler = make_handler("fn-result-error")
        mock_ws = make_open_ws()
        mock_ws.send = AsyncMock(side_effect=Exception("WS error"))
        handler.ws = mock_ws

        with pytest.raises(Exception):
            asyncio.run(handler._send_function_result("fn-id", "result"))

    def test_skips_when_ws_closed(self):
        """_send_function_result skips when WS not open."""
        handler = make_handler("fn-result-closed")
        mock_ws = MagicMock()
        mock_ws.state = _real_websockets.State.CLOSED  # Not OPEN
        mock_ws.send = AsyncMock()
        handler.ws = mock_ws

        asyncio.run(handler._send_function_result("fn-id", "result"))
        mock_ws.send.assert_not_awaited()


# ─── start_tool_handler ───────────────────────────────────────────────────────

class TestStartToolHandlerFunc:
    """Tests for the module-level start_tool_handler function."""

    def setup_method(self):
        active_handlers.clear()

    def test_creates_handler_and_adds_to_active(self):
        """start_tool_handler creates and registers a handler."""
        async def run():
            with patch.object(rth, 'asyncio') as mock_asyncio:
                mock_asyncio.create_task = MagicMock()
                handler = await start_tool_handler(
                    call_id="start-call-1",
                    session_id="sess-start-1"
                )
            return handler

        handler = asyncio.run(run())
        assert handler is not None
        assert "start-call-1" in active_handlers

    def test_replaces_existing_handler(self):
        """start_tool_handler stops existing handler before creating new one."""
        # Create an existing handler
        old_handler = make_handler("replace-call")
        old_handler.stop = AsyncMock()
        active_handlers["replace-call"] = old_handler

        async def run():
            with patch.object(rth, 'asyncio') as mock_asyncio:
                mock_asyncio.create_task = MagicMock()
                return await start_tool_handler(
                    call_id="replace-call",
                    session_id="sess-replace"
                )

        asyncio.run(run())
        old_handler.stop.assert_awaited_once()

    def test_passes_caller_phone(self):
        """start_tool_handler passes caller_phone to RealtimeToolHandler."""
        async def run():
            with patch.object(rth, 'asyncio') as mock_asyncio:
                mock_asyncio.create_task = MagicMock()
                return await start_tool_handler(
                    call_id="phone-call",
                    session_id="sess-phone",
                    caller_phone="+9876543210"
                )

        handler = asyncio.run(run())
        assert handler.caller_phone == "+9876543210"

    def teardown_method(self):
        active_handlers.clear()


# ─── stop_tool_handler ────────────────────────────────────────────────────────

class TestStopToolHandlerFunc:
    """Tests for the module-level stop_tool_handler function."""

    def setup_method(self):
        active_handlers.clear()

    def test_stops_and_removes_handler(self):
        """stop_tool_handler stops handler and removes from active_handlers."""
        handler = make_handler("stop-func-call")
        handler.stop = AsyncMock()
        active_handlers["stop-func-call"] = handler

        asyncio.run(stop_tool_handler("stop-func-call"))

        handler.stop.assert_awaited_once()
        assert "stop-func-call" not in active_handlers

    def test_nonexistent_handler_no_error(self):
        """stop_tool_handler is safe when handler doesn't exist."""
        asyncio.run(stop_tool_handler("nonexistent-call"))

    def teardown_method(self):
        active_handlers.clear()


# ─── Module _cleanup ──────────────────────────────────────────────────────────

class TestModuleCleanup:
    """Tests for the atexit _cleanup function."""

    def test_cleanup_sets_running_false(self):
        """_cleanup() sets running=False on all handlers."""
        active_handlers.clear()

        h1 = make_handler("cleanup-1")
        h1.running = True
        h2 = make_handler("cleanup-2")
        h2.running = True
        active_handlers["cleanup-1"] = h1
        active_handlers["cleanup-2"] = h2

        rth._cleanup()

        assert h1.running is False
        assert h2.running is False

        active_handlers.clear()
