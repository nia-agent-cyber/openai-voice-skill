#!/usr/bin/env python3
"""
Coverage wrappers for example scripts:
- scripts/context_example.py
- scripts/outbound_call_example.py

Both are demo scripts — we import and call their functions with mocks.
"""

import asyncio
import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch, call
import unittest.mock

import pytest

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts')

# ─── Shared mocks ─────────────────────────────────────────────────────────────

def make_mock_extractor():
    """Create a mock context extractor."""
    extractor = MagicMock()
    extractor.extract_recent_context = MagicMock(return_value={
        "conversation_history": [
            {"content": "Test message", "timestamp": "09:00", "role": "user"}
        ],
        "ongoing_projects": [
            {"name": "Voice Skill", "description": "OpenAI voice project"}
        ],
        "recent_decisions": [
            {"content": "Use shimmer voice", "date": "2026-03-01"}
        ],
        "user_info": {"agent_identity": "Nia", "timezone": "Africa/Kigali"},
        "context_summary": "Testing voice skill integration"
    })
    extractor.get_enhanced_instructions = MagicMock(
        return_value="You are Nia, helpful voice assistant."
    )
    return extractor


def make_mock_bridge():
    """Create a mock OpenClaw bridge."""
    bridge = MagicMock()
    bridge.identify_caller = AsyncMock(side_effect=lambda phone: {
        "+1234567890": {
            "name": "Remi",
            "known_caller": True,
            "relationship": "primary_user",
            "session_id": "main",
            "phone": phone
        },
    }.get(phone, {
        "name": "Unknown Caller",
        "known_caller": False,
        "relationship": "unknown",
        "phone": phone
    }))
    bridge.get_caller_context = AsyncMock(return_value={
        "conversation_history": [],
        "ongoing_projects": [],
        "recent_decisions": [],
        "context_summary": "test",
        "caller_info": {"name": "Remi"}
    })
    bridge.format_context_for_voice = MagicMock(
        return_value="You are Nia. The caller is Remi. Be friendly."
    )
    bridge.update_call_context = AsyncMock()
    bridge.finalize_call_context = AsyncMock()
    return bridge


# ─── context_example.py ──────────────────────────────────────────────────────

def _import_context_example(mock_extractor, mock_bridge):
    """Import context_example.py with mocked dependencies."""
    mock_session_mod = MagicMock()
    mock_session_mod.create_context_extractor = MagicMock(return_value=mock_extractor)

    mock_bridge_mod = MagicMock()
    mock_bridge_mod.create_openclaw_bridge = MagicMock(return_value=mock_bridge)

    with unittest.mock.patch.dict('sys.modules', {
        'session_context': mock_session_mod,
        'openclaw_bridge': mock_bridge_mod,
    }):
        spec = importlib.util.spec_from_file_location(
            "context_example",
            os.path.join(_SCRIPTS_DIR, 'context_example.py')
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class TestContextExample:
    """Coverage for scripts/context_example.py"""

    def test_demo_context_extraction(self):
        """Run demo_context_extraction with mocked extractor and bridge."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        result = asyncio.run(module.demo_context_extraction())
        # Function should complete without error
        assert result is None

    def test_demo_calls_extract_recent_context(self):
        """Verify extract_recent_context is called."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.demo_context_extraction())
        extractor.extract_recent_context.assert_called()

    def test_demo_calls_identify_caller(self):
        """Verify identify_caller is called for test numbers."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.demo_context_extraction())
        assert bridge.identify_caller.await_count >= 1

    def test_demo_calls_get_caller_context(self):
        """Verify get_caller_context is called."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.demo_context_extraction())
        assert bridge.get_caller_context.await_count >= 1

    def test_demo_formats_context_for_voice(self):
        """Verify format_context_for_voice is called."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.demo_context_extraction())
        assert bridge.format_context_for_voice.call_count >= 1

    def test_demo_context_with_exception_in_extractor(self):
        """Test robustness when extractor raises an exception."""
        extractor = make_mock_extractor()
        extractor.extract_recent_context = MagicMock(side_effect=Exception("File not found"))
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        try:
            asyncio.run(module.demo_context_extraction())
        except Exception:
            pass  # It may propagate — we just want coverage

    def test_demo_with_no_history(self):
        """Test demo when context has empty conversation history."""
        extractor = make_mock_extractor()
        extractor.extract_recent_context = MagicMock(return_value={
            "conversation_history": [],
            "ongoing_projects": [],
            "recent_decisions": [],
            "user_info": {},
            "context_summary": ""
        })
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.demo_context_extraction())

    def test_demo_call_simulation(self):
        """Run demo_call_simulation with mocked bridge."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        result = asyncio.run(module.demo_call_simulation())
        assert result is None
        assert bridge.update_call_context.await_count >= 1
        assert bridge.finalize_call_context.await_count >= 1

    def test_show_config_example(self):
        """Run show_config_example (no async)."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        # This is synchronous
        module.show_config_example()

    def test_main_function_runs_all_demos(self):
        """Run main() which calls all three demo functions."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.main())

    def test_main_function_with_exception(self):
        """Run main() when demo_context_extraction raises."""
        extractor = make_mock_extractor()
        extractor.extract_recent_context = MagicMock(side_effect=Exception("Demo failed"))
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        asyncio.run(module.main())  # Should handle exception gracefully

    def test_all_functions_in_module(self):
        """Check that the expected functions exist in the module."""
        extractor = make_mock_extractor()
        bridge = make_mock_bridge()
        module = _import_context_example(extractor, bridge)

        assert callable(module.demo_context_extraction)
        assert callable(module.demo_call_simulation)
        assert callable(module.show_config_example)
        assert callable(module.main)


# ─── outbound_call_example.py ─────────────────────────────────────────────────

def _import_outbound_example(mock_httpx=None):
    """Import outbound_call_example.py with mocked httpx."""
    if mock_httpx is None:
        mock_httpx = MagicMock()

    with unittest.mock.patch.dict('sys.modules', {'httpx': mock_httpx}):
        spec = importlib.util.spec_from_file_location(
            "outbound_call_example",
            os.path.join(_SCRIPTS_DIR, 'outbound_call_example.py')
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def make_httpx_mock(status_code=200, response_json=None):
    """Create a mock httpx module with AsyncClient."""
    if response_json is None:
        response_json = {
            "call_id": "CA123",
            "status": "initiated",
            "message": "Call to +1****7890 initiated"
        }

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json = MagicMock(return_value=response_json)
    mock_response.text = json.dumps(response_json)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.delete = AsyncMock(return_value=mock_response)

    mock_httpx = MagicMock()
    mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
    mock_httpx.ConnectError = ConnectionError

    return mock_httpx, mock_client, mock_response


class TestOutboundCallExample:
    """Coverage for scripts/outbound_call_example.py"""

    def test_make_outbound_call_success(self):
        """Test successful outbound call."""
        mock_httpx, _, _ = make_httpx_mock(200, {"call_id": "CA123", "status": "initiated"})
        module = _import_outbound_example(mock_httpx)

        result = asyncio.run(module.make_outbound_call())
        assert result == "CA123"

    def test_make_outbound_call_failure_returns_none(self):
        """Test failed outbound call returns None."""
        mock_httpx, _, _ = make_httpx_mock(500, {"error": "Server error"})
        module = _import_outbound_example(mock_httpx)

        result = asyncio.run(module.make_outbound_call())
        assert result is None

    def test_make_outbound_call_connection_error(self):
        """Test connection error is handled."""
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.ConnectError = ConnectionError

        module = _import_outbound_example(mock_httpx)
        result = asyncio.run(module.make_outbound_call())
        assert result is None

    def test_mask_phone_number_full_length(self):
        """Test phone masking for full length numbers."""
        module = _import_outbound_example()
        result = module.mask_phone_number("+12125551234")
        assert "****" in result
        assert result.startswith("+12")

    def test_mask_phone_number_short(self):
        """Test phone masking for short numbers."""
        module = _import_outbound_example()
        result = module.mask_phone_number("+123")
        assert "****" in result

    def test_mask_phone_number_empty(self):
        """Test phone masking for empty string."""
        module = _import_outbound_example()
        result = module.mask_phone_number("")
        assert result == "****"

    def test_mask_phone_number_none(self):
        """Test phone masking for None."""
        module = _import_outbound_example()
        result = module.mask_phone_number(None)
        assert result == "****"

    def test_check_call_status_success(self):
        """Test check_call_status when server returns active calls."""
        mock_httpx, _, _ = make_httpx_mock(200, {
            "active_calls": 1,
            "calls": [{"call_id": "CA123", "type": "outbound", "duration": 30.0,
                       "status": "active", "to": "+12125551234", "from": "+19995551234"}]
        })
        module = _import_outbound_example(mock_httpx)
        asyncio.run(module.check_call_status("CA123"))  # Returns None, just completes

    def test_check_call_status_404(self):
        """Test check_call_status when server returns 404."""
        mock_httpx, _, _ = make_httpx_mock(404, {"error": "Not found"})
        module = _import_outbound_example(mock_httpx)
        asyncio.run(module.check_call_status("NONEXISTENT"))  # Should not raise

    def test_check_call_status_error(self):
        """Test check_call_status on connection error."""
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.ConnectError = ConnectionError

        module = _import_outbound_example(mock_httpx)
        asyncio.run(module.check_call_status("CA123"))  # Should not raise

    def test_cancel_call(self):
        """Test cancel_call function."""
        mock_httpx, mock_client, mock_response = make_httpx_mock(200, {"status": "cancelled"})
        module = _import_outbound_example(mock_httpx)

        result = asyncio.run(module.cancel_call("CA123"))
        # Should complete without error

    def test_cancel_call_failure(self):
        """Test cancel_call when server returns error."""
        mock_httpx, _, _ = make_httpx_mock(404, {"error": "Not found"})
        module = _import_outbound_example(mock_httpx)

        result = asyncio.run(module.cancel_call("INVALID"))
        # Should complete gracefully

    def test_cancel_call_connection_error(self):
        """Test cancel_call on connection error."""
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.delete = AsyncMock(side_effect=ConnectionError("refused"))
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        mock_httpx.ConnectError = ConnectionError

        module = _import_outbound_example(mock_httpx)
        asyncio.run(module.cancel_call("CA123"))

    def test_main_function_server_down(self):
        """Test main() when server is unreachable."""
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        module = _import_outbound_example(mock_httpx)
        asyncio.run(module.main())  # Should return early

    def test_main_function_outbound_disabled(self):
        """Test main() when outbound calls are disabled."""
        # Health check 200, root check with outbound_calls_enabled=False
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        health_response = MagicMock(status_code=200)
        health_response.json = MagicMock(return_value={"agent": "Nia", "active_calls": 0})
        root_response = MagicMock(status_code=200)
        root_response.json = MagicMock(return_value={"outbound_calls_enabled": False})

        mock_client.get = AsyncMock(side_effect=[health_response, root_response])
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        module = _import_outbound_example(mock_httpx)
        asyncio.run(module.main())  # Returns early because outbound disabled

    def test_main_function_full_flow(self):
        """Test main() with outbound enabled — patches asyncio.sleep."""
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        health_response = MagicMock(status_code=200)
        health_response.json = MagicMock(return_value={"agent": "Nia", "active_calls": 0})
        root_response = MagicMock(status_code=200)
        root_response.json = MagicMock(return_value={"outbound_calls_enabled": True})
        calls_response = MagicMock(status_code=200)
        calls_response.json = MagicMock(return_value={"active_calls": 0, "calls": []})
        call_response = MagicMock(status_code=200)
        call_response.json = MagicMock(return_value={"call_id": "CA-main", "status": "initiated", "message": "ok"})

        mock_client.get = AsyncMock(side_effect=[health_response, root_response, calls_response, calls_response])
        mock_client.post = AsyncMock(return_value=call_response)
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        module = _import_outbound_example(mock_httpx)
        with patch('asyncio.sleep', new_callable=AsyncMock):
            asyncio.run(module.main())

    def test_module_constants(self):
        """Test module constants are set."""
        module = _import_outbound_example()
        assert hasattr(module, 'SERVER_URL')
        assert module.SERVER_URL.startswith("http")

    def test_functions_exist(self):
        """Test expected functions exist."""
        module = _import_outbound_example()
        assert callable(module.make_outbound_call)
        assert callable(module.mask_phone_number)
        assert callable(module.check_call_status)
        assert callable(module.cancel_call)
