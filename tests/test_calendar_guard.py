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


class TestCalendarGuardRegressions:
    """Regression tests to ensure non-calendar requests are never blocked."""
    
    @pytest.mark.asyncio
    async def test_calculate_request_not_blocked(self):
        """Ensure 'calculate' is not mistaken for calendar intent."""
        from openclaw_executor import OpenClawExecutor, CALENDAR_NOT_CONNECTED_CODE

        executor = OpenClawExecutor(timeout=1)
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"4", b"")
        mock_process.returncode = 0

        with patch.dict(os.environ, {"OPENCLAW_CALENDAR_CONNECTED": "0"}, clear=False):
            with patch("openclaw_executor.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process) as mock_subprocess:
                result = await executor.execute("Can you calculate 2+2?")

        # Should NOT trigger calendar guard
        assert CALENDAR_NOT_CONNECTED_CODE not in result
        # Should execute normally through OpenClaw
        mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_request_not_blocked(self):
        """Ensure 'call' is not mistaken for calendar intent."""
        from openclaw_executor import OpenClawExecutor, CALENDAR_NOT_CONNECTED_CODE

        executor = OpenClawExecutor(timeout=1)
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Calling mom now", b"")
        mock_process.returncode = 0

        with patch.dict(os.environ, {"OPENCLAW_CALENDAR_CONNECTED": "0"}, clear=False):
            with patch("openclaw_executor.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process) as mock_subprocess:
                result = await executor.execute("Please call mom")

        # Should NOT trigger calendar guard
        assert CALENDAR_NOT_CONNECTED_CODE not in result
        # Should execute normally through OpenClaw
        mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_calculate_streaming_not_blocked(self):
        """Ensure 'calculate' doesn't trigger guard in streaming mode."""
        from openclaw_executor import OpenClawExecutor, CALENDAR_NOT_CONNECTED_CODE

        executor = OpenClawExecutor(timeout=1)
        
        mock_process = AsyncMock()
        mock_process.stdout.readline = AsyncMock(side_effect=[b"4\n", b""])
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        with patch.dict(os.environ, {"OPENCLAW_CALENDAR_CONNECTED": "0"}, clear=False):
            with patch("openclaw_executor.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process) as mock_subprocess:
                chunks = [chunk async for chunk in executor.execute_streaming("Calculate 5 * 5")]

        # Should NOT return calendar guard error
        assert not any(CALENDAR_NOT_CONNECTED_CODE in chunk for chunk in chunks)
        # Should execute subprocess normally
        mock_subprocess.assert_called_once()


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

        # Check for "not connected" (handles both "isn't" and "is not" with any apostrophe type)
        result_lower = result.lower()
        assert ("connected" in result_lower and "not" in result_lower) or "isn" in result_lower
        assert "connect" in result_lower
        assert "team sync" not in result_lower
