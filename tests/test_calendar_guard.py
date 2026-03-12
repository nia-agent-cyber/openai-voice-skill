#!/usr/bin/env python3
"""Regression tests for calendar disconnected/connected guard behavior (Issue #33)."""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestCalendarGuardInExecutor:
    @pytest.mark.asyncio
    async def test_disconnected_calendar_returns_deterministic_error(self):
        from openclaw_executor import CALENDAR_NOT_CONNECTED_CODE, OpenClawExecutor

        executor = OpenClawExecutor(timeout=1)

        with patch.dict(os.environ, {"OPENCLAW_CALENDAR_CONNECTED": "0"}, clear=False):
            with patch("openclaw_executor.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_subprocess:
                result = await executor.execute("Check my calendar for today")

        assert CALENDAR_NOT_CONNECTED_CODE in result
        assert "connect your calendar" in result.lower()
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_connected_calendar_uses_openclaw_path(self):
        from openclaw_executor import OpenClawExecutor

        executor = OpenClawExecutor(timeout=1)

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"You have one meeting at 10 AM.", b"")
        mock_process.returncode = 0

        with patch.dict(os.environ, {"OPENCLAW_CALENDAR_CONNECTED": "true"}, clear=False):
            with patch("openclaw_executor.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process) as mock_subprocess:
                result = await executor.execute("Check my calendar for today")

        assert "one meeting" in result.lower()
        mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnected_calendar_streaming_returns_single_error_chunk(self):
        from openclaw_executor import CALENDAR_NOT_CONNECTED_CODE, OpenClawExecutor

        executor = OpenClawExecutor(timeout=1)

        with patch.dict(os.environ, {"OPENCLAW_CALENDAR_CONNECTED": "off"}, clear=False):
            chunks = [chunk async for chunk in executor.execute_streaming("What meetings do I have today?")]

        assert len(chunks) == 1
        assert CALENDAR_NOT_CONNECTED_CODE in chunks[0]


class TestCalendarGuardVoiceLayer:
    @pytest.mark.asyncio
    async def test_voice_layer_surfaces_not_connected_clearly(self):
        from realtime_tool_handler import RealtimeToolHandler

        handler = RealtimeToolHandler(session_id="test-session", call_id="test-call")

        with patch(
            "realtime_tool_handler.execute_openclaw_request",
            new_callable=AsyncMock,
            return_value="CALENDAR_NOT_CONNECTED: No calendar integration"
        ):
            result = await handler._execute_function("ask_openclaw", {"request": "Check my calendar"})

        assert "isn’t connected" in result or "isn't connected" in result
        assert "connect" in result.lower()
        assert "team sync" not in result.lower()
