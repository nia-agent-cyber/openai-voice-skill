#!/usr/bin/env python3
"""
Tests for comprehensive error handling in the tool handler (Issue #35).

These tests verify that:
1. Tool execution errors are caught and return graceful messages
2. Streaming failures fall back to non-streaming
3. No exceptions propagate to crash the application
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


class TestExecuteFunctionErrorHandling:
    """Test _execute_function error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_request_returns_graceful_message(self):
        """Empty request should return a user-friendly message, not crash."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        result = await handler._execute_function("ask_openclaw", {"request": ""})
        
        assert "didn't receive" in result.lower()
        assert handler.stats["failed_calls"] == 0  # Not counted as failure
    
    @pytest.mark.asyncio
    async def test_execution_error_returns_graceful_message(self):
        """Execution error should return graceful message, not raise."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        # Mock the executor to raise an exception
        with patch('realtime_tool_handler.execute_openclaw_request', 
                   new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Simulated web search error")
            
            result = await handler._execute_function("ask_openclaw", {"request": "search web"})
            
            # Should return error message, not raise
            assert isinstance(result, str)
            assert "problem" in result.lower() or "wrong" in result.lower()
            assert handler.stats["failed_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_timeout_error_returns_graceful_message(self):
        """Timeout error should return graceful message."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        with patch('realtime_tool_handler.execute_openclaw_request',
                   new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = asyncio.TimeoutError()
            
            result = await handler._execute_function("ask_openclaw", {"request": "complex query"})
            
            assert isinstance(result, str)
            assert "long" in result.lower() or "simpler" in result.lower()
            assert handler.stats["failed_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_unknown_function_returns_graceful_message(self):
        """Unknown function should return helpful message."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        result = await handler._execute_function("unknown_tool", {})
        
        assert isinstance(result, str)
        assert "don't know" in result.lower()


class TestHandleFunctionCallErrorHandling:
    """Test _handle_function_call comprehensive error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_arguments_handled(self):
        """Invalid JSON arguments should be handled gracefully."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        # Mock send method
        handler._send_function_result_safe = AsyncMock()
        handler._execute_streaming_function = AsyncMock(side_effect=Exception("Stream failed"))
        handler._execute_function = AsyncMock(return_value="Fallback response")
        
        event = {
            "call_id": "func-123",
            "name": "ask_openclaw",
            "arguments": "{invalid json"  # Bad JSON
        }
        
        # Should not raise
        await handler._handle_function_call(event)
        
        # Should have attempted to send a response
        assert handler._send_function_result_safe.called or handler._execute_function.called
    
    @pytest.mark.asyncio
    async def test_streaming_failure_falls_back_to_nonstreaming(self):
        """When streaming fails, should fall back to non-streaming."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        handler._send_function_result_safe = AsyncMock()
        handler._execute_streaming_function = AsyncMock(side_effect=Exception("Stream failed"))
        handler._execute_function = AsyncMock(return_value="Non-streaming response")
        
        event = {
            "call_id": "func-123",
            "name": "ask_openclaw",
            "arguments": '{"request": "test request"}'
        }
        
        await handler._handle_function_call(event)
        
        # Should have called non-streaming fallback
        handler._execute_function.assert_called_once()
        # Should have sent the result
        handler._send_function_result_safe.assert_called()
    
    @pytest.mark.asyncio
    async def test_complete_failure_still_sends_error_response(self):
        """Even if everything fails, should send error response to user."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        # Track all calls to _send_function_result_safe
        send_calls = []
        
        async def track_send(call_id, message):
            send_calls.append(message)
        
        handler._send_function_result_safe = track_send
        handler._execute_streaming_function = AsyncMock(side_effect=Exception("Stream failed"))
        handler._execute_function = AsyncMock(side_effect=Exception("Non-stream also failed"))
        
        event = {
            "call_id": "func-123",
            "name": "ask_openclaw",
            "arguments": '{"request": "test request"}'
        }
        
        # Should NOT raise - must handle gracefully
        await handler._handle_function_call(event)
        
        # Should have tried to send an error message
        assert len(send_calls) > 0
        assert any("error" in msg.lower() or "sorry" in msg.lower() for msg in send_calls)


class TestSendFunctionResultSafe:
    """Test the safe send method."""
    
    @pytest.mark.asyncio
    async def test_safe_send_does_not_raise(self):
        """_send_function_result_safe should never raise."""
        from realtime_tool_handler import RealtimeToolHandler
        
        handler = RealtimeToolHandler(
            session_id="test-session",
            call_id="test-call"
        )
        
        # Make _send_function_result raise
        handler._send_function_result = AsyncMock(side_effect=Exception("WebSocket error"))
        
        # Should NOT raise
        await handler._send_function_result_safe("func-123", "Test message")
        
        # Method was called
        handler._send_function_result.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
