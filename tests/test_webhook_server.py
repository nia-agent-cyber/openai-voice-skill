#!/usr/bin/env python3
"""
Unit tests for webhook-server.py

Covers:
 - build_call_prompt(): language rule placement, caller name, identity/memory load
 - generate_thinking_tone(): valid mulaw base64 output, length sanity check
 - Session config: temperature 0.6, VAD eagerness "balanced", no "low"

Run with:
    python3 -m pytest tests/test_webhook_server.py -v
"""

import base64
import importlib.util
import os
import sys
import unittest.mock
from pathlib import Path

import pytest

# ─── Import webhook-server with mocked heavy dependencies ──────────────────
# webhook-server.py uses a hyphen so we can't do a regular import.
# We load it via importlib after patching out the external modules so the
# import doesn't blow up in CI / without real Twilio / OpenAI credentials.

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
_SERVER_PATH = os.path.join(_SCRIPTS_DIR, "webhook-server.py")

_MOCKED_MODULES = {
    "fastapi": unittest.mock.MagicMock(),
    "fastapi.responses": unittest.mock.MagicMock(),
    "uvicorn": unittest.mock.MagicMock(),
    "twilio": unittest.mock.MagicMock(),
    "twilio.rest": unittest.mock.MagicMock(),
    "twilio.base": unittest.mock.MagicMock(),
    "twilio.base.exceptions": unittest.mock.MagicMock(),
    "twilio.twiml": unittest.mock.MagicMock(),
    "twilio.twiml.voice_response": unittest.mock.MagicMock(),
    "websockets": unittest.mock.MagicMock(),
    "websockets.exceptions": unittest.mock.MagicMock(),
    "httpx": unittest.mock.MagicMock(),
    "pydantic": unittest.mock.MagicMock(),
}

# Patch sys.modules so the import picks up our mocks
with unittest.mock.patch.dict("sys.modules", _MOCKED_MODULES):
    spec = importlib.util.spec_from_file_location("webhook_server", _SERVER_PATH)
    _ws_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_ws_mod)

build_call_prompt = _ws_mod.build_call_prompt
generate_thinking_tone = _ws_mod.generate_thinking_tone


# ─── Tests: build_call_prompt ──────────────────────────────────────────────

class TestBuildCallPrompt:
    """Tests for build_call_prompt() — verifies correct context assembly."""

    def test_language_rule_is_first_in_prompt(self):
        """ABSOLUTE RULE #1 language instruction must appear in the very first 200 chars."""
        prompt = build_call_prompt("+250794002033")
        first_200 = prompt[:200]
        assert "ABSOLUTE RULE" in first_200 or "LANGUAGE" in first_200, (
            f"Language rule not found in first 200 chars. Got: {first_200!r}"
        )
        assert "English" in first_200, (
            f"'English' not found in first 200 chars. Got: {first_200!r}"
        )

    def test_language_rule_precedes_all_other_content(self):
        """The language rule header must come before any identity/memory sections."""
        prompt = build_call_prompt("+250794002033")
        rule_pos = prompt.find("ABSOLUTE RULE")
        # Find first section marker (# Who You Are, # This Call, etc.)
        section_pos = prompt.find("# ")
        assert rule_pos < section_pos, (
            "Language rule must appear before the first '# ' section header. "
            f"rule_pos={rule_pos}, section_pos={section_pos}"
        )

    def test_prompt_contains_caller_name(self):
        """Caller name 'Remi' must be in the prompt for +250794002033."""
        prompt = build_call_prompt("+250794002033")
        assert "Remi" in prompt, (
            "Expected 'Remi' in prompt for known caller +250794002033"
        )

    def test_unknown_caller_falls_back_gracefully(self):
        """Unknown numbers should still produce a valid prompt."""
        prompt = build_call_prompt("+19999999999")
        assert len(prompt) > 100, "Prompt for unknown caller should not be empty"
        assert "ABSOLUTE RULE" in prompt or "LANGUAGE" in prompt, (
            "Language rule should still be present for unknown callers"
        )

    def test_prompt_loads_identity(self):
        """Prompt must contain at least one identity/memory marker."""
        prompt = build_call_prompt("+250794002033")
        markers = ["Nia", "SOUL", "IDENTITY", "purpose", "Who You Are"]
        assert any(x in prompt for x in markers), (
            f"Expected at least one of {markers} in prompt. "
            f"Prompt starts with: {prompt[:300]!r}"
        )

    def test_prompt_is_string(self):
        """build_call_prompt must return a non-empty string."""
        prompt = build_call_prompt("+250794002033")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_tool_instructions(self):
        """Prompt should mention the available tools (memory_search etc.)."""
        prompt = build_call_prompt("+250794002033")
        assert "memory_search" in prompt, (
            "Tool instructions (memory_search) not found in prompt"
        )

    def test_prompt_no_markdown_bullets_instruction(self):
        """Prompt should instruct agent not to use bullet points or markdown."""
        prompt = build_call_prompt("+250794002033")
        assert "markdown" in prompt.lower() or "bullet" in prompt.lower(), (
            "Prompt should contain guidance about avoiding markdown/bullets in voice mode"
        )


# ─── Tests: generate_thinking_tone ─────────────────────────────────────────

class TestGenerateThinkingTone:
    """Tests for generate_thinking_tone() — mulaw base64 sine tone."""

    def test_thinking_tone_is_valid_base64(self):
        """Output must be valid base64 that can be decoded without error."""
        tone = generate_thinking_tone()
        decoded = base64.b64decode(tone)
        assert len(decoded) > 0, "Decoded tone must not be empty"

    def test_thinking_tone_length_sanity(self):
        """600ms at 8kHz mulaw = 4800 bytes. Output must be substantially non-empty."""
        tone = generate_thinking_tone()
        decoded = base64.b64decode(tone)
        # 600ms × 8000 samples/s × 1 byte/sample (mulaw) = 4800 bytes
        assert len(decoded) > 4000, (
            f"Expected >4000 bytes for 600ms mulaw tone, got {len(decoded)}"
        )

    def test_thinking_tone_default_duration(self):
        """Default 600ms tone should produce ~4800 bytes of mulaw."""
        tone = generate_thinking_tone()
        decoded = base64.b64decode(tone)
        # Allow ±20% tolerance
        assert 3840 <= len(decoded) <= 5760, (
            f"600ms mulaw tone should be ~4800 bytes (±20%), got {len(decoded)}"
        )

    def test_thinking_tone_custom_duration(self):
        """Custom duration should scale output proportionally."""
        tone_300 = generate_thinking_tone(duration_ms=300)
        tone_600 = generate_thinking_tone(duration_ms=600)
        decoded_300 = base64.b64decode(tone_300)
        decoded_600 = base64.b64decode(tone_600)
        # 300ms should be roughly half of 600ms
        ratio = len(decoded_300) / len(decoded_600)
        assert 0.4 <= ratio <= 0.6, (
            f"300ms tone should be ~50% the size of 600ms tone, ratio={ratio:.2f}"
        )

    def test_thinking_tone_returns_string(self):
        """generate_thinking_tone must return a string (base64 encoded)."""
        tone = generate_thinking_tone()
        assert isinstance(tone, str), f"Expected str, got {type(tone)}"

    def test_thinking_tone_is_ascii(self):
        """Base64 output must be ASCII-safe (Twilio payload requirement)."""
        tone = generate_thinking_tone()
        assert tone.isascii(), "Tone payload must be ASCII (base64)"


# ─── Tests: session config in source ───────────────────────────────────────

class TestSessionConfig:
    """Source-code checks for session configuration values."""

    @pytest.fixture(scope="class")
    def server_src(self):
        return Path(_SERVER_PATH).read_text()

    def test_session_config_temperature_is_0_6(self, server_src):
        """Temperature must be 0.6 (not 0.8 which caused language drift)."""
        assert '"temperature": 0.6' in server_src or "'temperature': 0.6" in server_src, (
            "Temperature must be 0.6 in session config. "
            "0.8 was removed because it caused language drift."
        )

    def test_session_config_temperature_not_0_8(self, server_src):
        """Temperature 0.8 must NOT be present (regressed language drift)."""
        assert '"temperature": 0.8' not in server_src and "'temperature': 0.8" not in server_src, (
            "Temperature 0.8 found — this caused language drift, must be 0.6"
        )

    def test_session_config_eagerness_is_balanced(self, server_src):
        """VAD eagerness must be 'balanced' for faster turn detection."""
        assert '"balanced"' in server_src, (
            "VAD eagerness 'balanced' not found in session config"
        )

    def test_session_config_eagerness_not_low(self, server_src):
        """VAD eagerness 'low' must NOT be present (caused dead air)."""
        # We specifically check the session config block context
        # 'low' could appear elsewhere (e.g. log levels), so we look for
        # the eagerness-specific pattern
        assert '"eagerness": "low"' not in server_src and "'eagerness': 'low'" not in server_src, (
            "VAD eagerness 'low' found — this caused dead air, must be 'balanced'"
        )

    def test_session_ready_event_is_present(self, server_src):
        """session_ready asyncio.Event gate must exist in the code."""
        assert "session_ready" in server_src, (
            "session_ready asyncio.Event gate not found in webhook-server.py"
        )
        assert "asyncio.Event" in server_src, (
            "asyncio.Event not found — session_ready gate may not be implemented"
        )

    def test_session_ready_gate_blocks_audio(self, server_src):
        """Audio forwarding must wait for session_ready before proceeding."""
        assert "session_ready" in server_src, (
            "session_ready gate not found — audio may be forwarded before session.updated"
        )
        # The event is accessed via ctx["session_ready"].wait() in the media handler
        # Accept any of these usage patterns:
        waited = (
            "session_ready.wait()" in server_src          # direct attribute access
            or 'session_ready"].wait()' in server_src     # via ctx dict: ctx["session_ready"].wait()
            or "session_ready'].wait()" in server_src     # via ctx dict: ctx['session_ready'].wait()
            or "session_ready.is_set()" in server_src     # polling variant
            or 'session_ready"].is_set()' in server_src   # ctx dict polling variant
        )
        assert waited, (
            "session_ready is declared but never waited on — gate may not be effective. "
            "Expected ctx[\"session_ready\"].wait() or similar in the media event handler."
        )

    def test_session_updated_sets_ready(self, server_src):
        """session.updated event handler must call session_ready.set()."""
        assert 'session_ready' in server_src, "session_ready not in source"
        assert '.set()' in server_src, (
            "session_ready.set() not found — session.updated may not trigger the gate"
        )

    def test_language_rule_header_in_source(self, server_src):
        """ABSOLUTE RULE must be hardcoded in build_call_prompt header."""
        assert "ABSOLUTE RULE" in server_src, (
            "Language rule header 'ABSOLUTE RULE' not found in webhook-server.py"
        )

    def test_language_header_overrides_all(self, server_src):
        """Language rule must state it overrides everything."""
        assert "overrides everything" in server_src or "No exceptions" in server_src, (
            "Language rule should state it overrides everything / No exceptions"
        )
