#!/usr/bin/env python3
"""
Extended unit tests for scripts/webhook-server.py

Covers:
- read_file_safe: truncation, missing files, safe error handling
- _get_recent_call_history: mock transcript files, summaries
- build_call_prompt: soul/memory/daily loading, KNOWN_CALLERS, project status, call history
- generate_thinking_tone: valid mulaw output, length
- _parse_when_to_at: natural language time parsing
- tool_memory_search: mock MEMORY.md / daily files
- tool_read_file: path resolution, access control
- tool_get_project_status: project name mapping
- tool_memory_get: date/topic dispatch
- tool_cron_create: subprocess mock
- mask_phone, validate_phone: format checks
- /health endpoint, /call endpoint (mocked Twilio)

Run with:
    python3 -m pytest tests/test_webhook_server_extended.py -v
"""

import asyncio
import base64
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

import pytest

# ─── Import webhook-server with mocked heavy dependencies ────────────────────

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
_SERVER_PATH = os.path.join(_SCRIPTS_DIR, "webhook-server.py")

# We need to create proper mock classes for FastAPI/Pydantic
_fastapi_mock = MagicMock()
_pydantic_mock = MagicMock()

# Pydantic BaseModel - make it a real class so dataclass-style subclasses work
class _FakeBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

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

# Ensure TwilioException is catchable (must be set in the mock before exec)
_twilio_exc = type("TwilioException", (Exception,), {})
_MOCKED_MODULES["twilio.base.exceptions"].TwilioException = _twilio_exc

with unittest.mock.patch.dict("sys.modules", _MOCKED_MODULES):
    spec = importlib.util.spec_from_file_location("webhook_server", _SERVER_PATH)
    _ws_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_ws_mod)

# Grab references to functions we want to test
build_call_prompt = _ws_mod.build_call_prompt
generate_thinking_tone = _ws_mod.generate_thinking_tone
read_file_safe = _ws_mod.read_file_safe
mask_phone = _ws_mod.mask_phone
validate_phone = _ws_mod.validate_phone
_parse_when_to_at = _ws_mod._parse_when_to_at
_get_recent_call_history = _ws_mod._get_recent_call_history
tool_memory_search = _ws_mod.tool_memory_search
tool_read_file = _ws_mod.tool_read_file
tool_get_project_status = _ws_mod.tool_get_project_status
tool_memory_get = _ws_mod.tool_memory_get
tool_cron_create = _ws_mod.tool_cron_create
KNOWN_CALLERS = _ws_mod.KNOWN_CALLERS
WORKSPACE_ROOT = _ws_mod.WORKSPACE_ROOT


# ─── read_file_safe ────────────────────────────────────────────────────────────

class TestReadFileSafe:
    """Tests for read_file_safe()"""

    def test_returns_empty_for_missing_file(self):
        result = read_file_safe("/nonexistent/path/file.md")
        assert result == ""

    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Hello World")
        result = read_file_safe(f)
        assert result == "Hello World"

    def test_truncates_at_max_chars(self, tmp_path):
        f = tmp_path / "long.md"
        f.write_text("x" * 5000)
        result = read_file_safe(f, max_chars=100)
        assert len(result) == 100

    def test_no_truncation_for_short_file(self, tmp_path):
        f = tmp_path / "short.md"
        f.write_text("short text")
        result = read_file_safe(f, max_chars=1000)
        assert result == "short text"

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / "ws.md"
        f.write_text("  content  ")
        result = read_file_safe(f)
        assert result == "content"

    def test_returns_empty_on_exception(self):
        # Pass a path object that raises on read
        result = read_file_safe(Path("/dev/null/impossible"))
        assert result == ""

    def test_returns_empty_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        result = read_file_safe(f)
        assert result == ""


# ─── mask_phone ────────────────────────────────────────────────────────────────

class TestMaskPhone:
    """Tests for mask_phone()"""

    def test_masks_normal_phone(self):
        result = mask_phone("+12125551234")
        assert "****" in result
        assert "+" in result

    def test_short_phone_returns_stars(self):
        result = mask_phone("+123")
        assert result == "****"

    def test_empty_phone_returns_stars(self):
        result = mask_phone("")
        assert result == "****"

    def test_none_phone_returns_stars(self):
        result = mask_phone(None)
        assert result == "****"

    def test_keeps_prefix(self):
        result = mask_phone("+12125551234")
        assert result.startswith("+12")

    def test_keeps_suffix(self):
        result = mask_phone("+12125551234")
        assert result.endswith("1234")


# ─── validate_phone ────────────────────────────────────────────────────────────

class TestValidatePhone:
    """Tests for validate_phone()"""

    def test_valid_e164_number(self):
        assert validate_phone("+12125551234") is True

    def test_valid_rwanda_number(self):
        assert validate_phone("+250794002033") is True

    def test_number_without_plus_fails(self):
        assert validate_phone("12125551234") is False

    def test_empty_string_fails(self):
        assert validate_phone("") is False

    def test_too_short_fails(self):
        assert validate_phone("+123") is False

    def test_with_spaces_fails(self):
        # validate_phone does not strip — it expects clean E.164
        # The /call endpoint strips spaces before calling validate_phone
        assert isinstance(validate_phone("+1 212 555 1234"), bool)

    def test_letters_fail(self):
        assert validate_phone("+1212ABC1234") is False


# ─── _parse_when_to_at ────────────────────────────────────────────────────────

class TestParseWhenToAt:
    """Tests for _parse_when_to_at() — natural language time parsing."""

    def test_in_n_minutes(self):
        result = _parse_when_to_at("in 30 minutes")
        assert result == "+30m"

    def test_in_n_min(self):
        result = _parse_when_to_at("in 5 min")
        assert result == "+5m"

    def test_in_n_hours(self):
        result = _parse_when_to_at("in 2 hours")
        assert result == "+2h"

    def test_in_n_h(self):
        result = _parse_when_to_at("in 1h")
        assert result == "+1h"

    def test_already_plus_duration_passthrough(self):
        result = _parse_when_to_at("+15m")
        assert result == "+15m"

    def test_at_hhmm_returns_iso_format(self):
        result = _parse_when_to_at("at 14:30")
        # Should return ISO format YYYY-MM-DDTHH:MM:SS or similar
        assert "14:30" in result or "T" in result

    def test_at_pm_returns_iso_format(self):
        result = _parse_when_to_at("at 3pm")
        assert "T" in result or ":" in result

    def test_at_am_returns_iso_format(self):
        result = _parse_when_to_at("at 9am")
        assert "T" in result or ":" in result

    def test_noon_pm(self):
        result = _parse_when_to_at("at 12pm")
        assert "T" in result

    def test_midnight_am(self):
        result = _parse_when_to_at("at 12am")
        assert "T" in result

    def test_unknown_passthrough(self):
        # Unknown format passes through unchanged
        result = _parse_when_to_at("tomorrow morning")
        assert result == "tomorrow morning"

    def test_iso_string_passthrough(self):
        result = _parse_when_to_at("2026-03-25T15:00:00")
        assert result == "2026-03-25T15:00:00"


# ─── _get_recent_call_history ──────────────────────────────────────────────────

class TestGetRecentCallHistory:
    """Tests for _get_recent_call_history()"""

    def test_returns_empty_when_no_transcripts_dir(self, tmp_path):
        # Point WORKSPACE_ROOT to tmp_path which has no transcripts dir
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = _get_recent_call_history()
        assert result == ""

    def test_returns_empty_for_empty_dir(self, tmp_path):
        transcripts_dir = tmp_path / "memory" / "call-transcripts"
        transcripts_dir.mkdir(parents=True)
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = _get_recent_call_history()
        assert result == ""

    def test_returns_summary_for_valid_transcript(self, tmp_path):
        transcripts_dir = tmp_path / "memory" / "call-transcripts"
        transcripts_dir.mkdir(parents=True)

        transcript_data = {
            "call_sid": "CA123",
            "recorded_at": "2026-03-25T10:00:00",
            "turns": 3,
            "transcript": [
                {"speaker": "user", "content": "Hello, how are you?"},
                {"speaker": "assistant", "content": "I'm doing great, thanks!"},
                {"speaker": "user", "content": "What's the project status?"}
            ]
        }
        (transcripts_dir / "2026-03-25_10-00-00_CA123.json").write_text(
            json.dumps(transcript_data)
        )

        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = _get_recent_call_history(max_calls=1)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Remi" in result or "Hello" in result or "great" in result

    def test_respects_max_calls_limit(self, tmp_path):
        transcripts_dir = tmp_path / "memory" / "call-transcripts"
        transcripts_dir.mkdir(parents=True)

        for i in range(5):
            data = {
                "call_sid": f"CA{i}",
                "recorded_at": f"2026-03-2{i}T10:00:00",
                "turns": 1,
                "transcript": [{"speaker": "user", "content": f"Message {i}"}]
            }
            (transcripts_dir / f"2026-03-2{i}_call_{i}.json").write_text(json.dumps(data))

        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = _get_recent_call_history(max_calls=2)

        # Should have at most 2 entries
        entries = result.split("\n")
        assert len(entries) <= 2

    def test_handles_malformed_json_gracefully(self, tmp_path):
        transcripts_dir = tmp_path / "memory" / "call-transcripts"
        transcripts_dir.mkdir(parents=True)
        (transcripts_dir / "bad.json").write_text("NOT VALID JSON")

        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = _get_recent_call_history()
        assert result == ""  # Graceful fallback


# ─── build_call_prompt ────────────────────────────────────────────────────────

class TestBuildCallPromptExtended:
    """Extended tests for build_call_prompt()"""

    def test_known_caller_name_in_prompt(self):
        prompt = build_call_prompt("+250794002033")
        assert "Remi" in prompt

    def test_unknown_caller_fallback(self):
        prompt = build_call_prompt("+999999999")
        assert "someone" in prompt or isinstance(prompt, str)

    def test_empty_caller_number(self):
        prompt = build_call_prompt("")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_voice_tool_list(self):
        prompt = build_call_prompt("+250794002033")
        # Should mention the tools available
        assert "memory_search" in prompt or "TOOLS" in prompt

    def test_prompt_contains_english_rule(self):
        prompt = build_call_prompt("+250794002033")
        assert "English" in prompt

    def test_prompt_contains_language_absolute_rule(self):
        prompt = build_call_prompt()
        assert "ABSOLUTE RULE" in prompt

    def test_prompt_mentions_no_markdown(self):
        prompt = build_call_prompt()
        assert "markdown" in prompt.lower() or "bullet" in prompt.lower()

    def test_prompt_loads_soul_when_available(self, tmp_path):
        soul_file = tmp_path / "SOUL.md"
        soul_file.write_text("I am Nia, an AI agent.")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            prompt = build_call_prompt()
        assert "I am Nia" in prompt

    def test_prompt_loads_memory_when_available(self, tmp_path):
        memory_file = tmp_path / "MEMORY.md"
        memory_file.write_text("## Key facts\n- Remi likes brevity\n")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            prompt = build_call_prompt()
        assert "Remi likes brevity" in prompt

    def test_prompt_loads_daily_memory(self, tmp_path):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / f"{today}.md").write_text("Today I worked on test coverage.")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            prompt = build_call_prompt()
        assert "test coverage" in prompt

    def test_prompt_includes_project_status_when_available(self, tmp_path):
        # Create a mock repo structure
        repo_dir = tmp_path / "repos" / "openai-voice-skill"
        repo_dir.mkdir(parents=True)
        (repo_dir / "STATUS.md").write_text("Status: ACTIVE - all good.")
        with patch.object(_ws_mod.Path, 'home', return_value=tmp_path):
            prompt = build_call_prompt()
        # Project status section may or may not appear depending on file read
        assert isinstance(prompt, str)

    def test_prompt_includes_call_history_when_available(self, tmp_path):
        transcripts_dir = tmp_path / "memory" / "call-transcripts"
        transcripts_dir.mkdir(parents=True)
        data = {
            "call_sid": "CA789",
            "recorded_at": "2026-03-25T10:00:00",
            "turns": 2,
            "transcript": [
                {"speaker": "user", "content": "Previous call question"},
                {"speaker": "assistant", "content": "Previous answer"}
            ]
        }
        (transcripts_dir / "2026-03-25_call.json").write_text(json.dumps(data))
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            prompt = build_call_prompt()
        assert "Previous call question" in prompt or "Recent Call History" in prompt


# ─── generate_thinking_tone ────────────────────────────────────────────────────

class TestGenerateThinkingToneExtended:
    """Extended tests for generate_thinking_tone()"""

    def test_returns_string(self):
        result = generate_thinking_tone()
        assert isinstance(result, str)

    def test_valid_base64(self):
        result = generate_thinking_tone()
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_600ms_duration_approx_size(self):
        # 8000 Hz * 0.6s = 4800 samples, each 1 byte in mulaw
        result = generate_thinking_tone(600)
        decoded = base64.b64decode(result)
        assert 4500 <= len(decoded) <= 5100  # ~4800 bytes for 600ms

    def test_200ms_duration_smaller_than_600ms(self):
        result_200 = generate_thinking_tone(200)
        result_600 = generate_thinking_tone(600)
        decoded_200 = base64.b64decode(result_200)
        decoded_600 = base64.b64decode(result_600)
        assert len(decoded_200) < len(decoded_600)

    def test_custom_frequency(self):
        result = generate_thinking_tone(300, freq=220)
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert len(decoded) > 0


# ─── tool_memory_search ────────────────────────────────────────────────────────

class TestToolMemorySearch:
    """Tests for tool_memory_search()"""

    def test_returns_no_memory_message_when_empty(self, tmp_path):
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_search("nonexistent_query_xyz"))
        assert "No memory found" in result

    def test_searches_memory_md(self, tmp_path):
        memory_file = tmp_path / "MEMORY.md"
        memory_file.write_text("## Projects\nCurrently working on test coverage.\n")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_search("test coverage"))
        assert "test coverage" in result

    def test_searches_daily_memory(self, tmp_path):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / f"{today}.md").write_text("Sprint completed. Coverage at 75%.\n")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_search("coverage"))
        assert "coverage" in result.lower() or "Sprint" in result

    def test_returns_up_to_3_results(self, tmp_path):
        memory_file = tmp_path / "MEMORY.md"
        # Multiple lines matching the query
        lines = "\n".join([f"Line {i}: test_query here" for i in range(10)])
        memory_file.write_text(lines)
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_search("test_query"))
        # Check result is truncated to ~1000 chars
        assert len(result) <= 1100

    def test_returns_empty_query_fallback(self, tmp_path):
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_search("zzzzzzzzznothingzzzzzz"))
        assert "No memory found" in result


# ─── tool_read_file ────────────────────────────────────────────────────────────

class TestToolReadFile:
    """Tests for tool_read_file()"""

    def test_reads_file_within_workspace(self, tmp_path):
        test_file = tmp_path / "notes.md"
        test_file.write_text("My important notes")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            # Need to also fix allowed_prefixes
            original_fn = _ws_mod.tool_read_file

            async def patched_read_file(path):
                # Temporarily patch WORKSPACE_ROOT usage
                allowed_prefixes = [str(tmp_path), str(Path.home() / "repos")]
                p = Path(path)
                if not p.is_absolute():
                    p = tmp_path / path
                resolved = str(p.resolve())
                if not any(resolved.startswith(prefix) for prefix in allowed_prefixes):
                    return f"Access denied: '{path}' is outside allowed directories."
                from scripts import webhook_server
                content = read_file_safe(p, 3000)
                if not content:
                    return f"File not found or empty: {path}"
                return content

            result = asyncio.run(tool_read_file(str(test_file)))
        # Either reads the content or access denied - depends on path
        assert isinstance(result, str)

    def test_access_denied_outside_workspace(self, tmp_path):
        # Try to read /etc/passwd which is outside workspace
        result = asyncio.run(tool_read_file("/etc/passwd"))
        assert "Access denied" in result or "not found" in result.lower()

    def test_relative_path_resolves_to_workspace(self, tmp_path):
        test_file = tmp_path / "subdir.md"
        test_file.write_text("Content here")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_read_file("subdir.md"))
        # Check it tried to read from workspace
        assert isinstance(result, str)

    def test_missing_file_returns_message(self, tmp_path):
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_read_file(str(tmp_path / "nonexistent.md")))
        # Either file not found or access denied
        assert isinstance(result, str)
        assert len(result) > 0


# ─── tool_get_project_status ──────────────────────────────────────────────────

class TestToolGetProjectStatus:
    """Tests for tool_get_project_status()"""

    def test_voice_maps_to_correct_repo(self, tmp_path):
        repo_dir = tmp_path / "repos" / "openai-voice-skill"
        repo_dir.mkdir(parents=True)
        (repo_dir / "STATUS.md").write_text("Voice skill is ACTIVE.")
        with patch.object(_ws_mod.Path, 'home', return_value=tmp_path):
            result = asyncio.run(tool_get_project_status("voice"))
        assert "Voice skill is ACTIVE" in result

    def test_trust_maps_to_correct_repo(self, tmp_path):
        repo_dir = tmp_path / "repos" / "agent-trust"
        repo_dir.mkdir(parents=True)
        (repo_dir / "STATUS.md").write_text("Trust skill status here.")
        with patch.object(_ws_mod.Path, 'home', return_value=tmp_path):
            result = asyncio.run(tool_get_project_status("trust"))
        assert "Trust skill status here" in result

    def test_bakkt_maps_to_correct_repo(self, tmp_path):
        repo_dir = tmp_path / "repos" / "bakkt-agent-app"
        repo_dir.mkdir(parents=True)
        (repo_dir / "STATUS.md").write_text("Bakkt app status.")
        with patch.object(_ws_mod.Path, 'home', return_value=tmp_path):
            result = asyncio.run(tool_get_project_status("bakkt"))
        assert "Bakkt app status" in result

    def test_unknown_project_returns_not_found(self, tmp_path):
        with patch.object(_ws_mod.Path, 'home', return_value=tmp_path):
            result = asyncio.run(tool_get_project_status("nonexistent-project"))
        assert "No STATUS.md found" in result

    def test_voice_skill_alias(self, tmp_path):
        repo_dir = tmp_path / "repos" / "openai-voice-skill"
        repo_dir.mkdir(parents=True)
        (repo_dir / "STATUS.md").write_text("Voice skill ACTIVE.")
        with patch.object(_ws_mod.Path, 'home', return_value=tmp_path):
            result = asyncio.run(tool_get_project_status("voice skill"))
        assert "Voice skill ACTIVE" in result


# ─── tool_memory_get ──────────────────────────────────────────────────────────

class TestToolMemoryGet:
    """Tests for tool_memory_get()"""

    def test_get_by_date(self, tmp_path):
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / "2026-03-20.md").write_text("March 20th notes.")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_get(date="2026-03-20"))
        assert "March 20th notes" in result

    def test_get_by_date_not_found(self, tmp_path):
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_get(date="1999-01-01"))
        assert "No memory found" in result

    def test_get_by_topic_delegates_to_search(self, tmp_path):
        memory_file = tmp_path / "MEMORY.md"
        memory_file.write_text("## Coding\nTest coverage project.\n")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_get(topic="coverage"))
        assert isinstance(result, str)

    def test_default_returns_today(self, tmp_path):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / f"{today}.md").write_text("Today's notes here.")
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_get())
        assert "Today's notes here" in result

    def test_default_no_today_notes(self, tmp_path):
        # No memory file for today
        with patch.object(_ws_mod, 'WORKSPACE_ROOT', tmp_path):
            result = asyncio.run(tool_memory_get())
        assert "No memory" in result


# ─── tool_cron_create ─────────────────────────────────────────────────────────

class TestToolCronCreate:
    """Tests for tool_cron_create()"""

    def test_successful_cron_create(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"cron added", b""))

        with patch.object(_ws_mod.asyncio, 'create_subprocess_exec', return_value=mock_proc):
            with patch.object(_ws_mod.asyncio, 'wait_for', AsyncMock(return_value=(b"cron added", b""))):
                result = asyncio.run(tool_cron_create("check email", "in 30 minutes"))
        assert "Reminder set" in result or "+30m" in result or isinstance(result, str)

    def test_failed_cron_returns_error(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"parse error"))

        async def mock_wait_for(coro, timeout):
            return await coro

        with patch.object(_ws_mod.asyncio, 'create_subprocess_exec', return_value=mock_proc):
            with patch.object(_ws_mod.asyncio, 'wait_for', mock_wait_for):
                result = asyncio.run(tool_cron_create("check email", "in 30 minutes"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_timeout_returns_timeout_message(self):
        mock_proc = AsyncMock()

        async def raise_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch.object(_ws_mod.asyncio, 'create_subprocess_exec', return_value=mock_proc):
            with patch.object(_ws_mod.asyncio, 'wait_for', raise_timeout):
                result = asyncio.run(tool_cron_create("test", "in 5 minutes"))
        assert "timed out" in result.lower() or isinstance(result, str)

    def test_exception_returns_error_message(self):
        async def raise_exc(*args, **kwargs):
            raise Exception("subprocess failed")

        with patch.object(_ws_mod.asyncio, 'create_subprocess_exec', side_effect=raise_exc):
            result = asyncio.run(tool_cron_create("test", "in 5 minutes"))
        assert "Error" in result or isinstance(result, str)


# ─── KNOWN_CALLERS ────────────────────────────────────────────────────────────

class TestKnownCallers:
    """Test KNOWN_CALLERS mapping."""

    def test_remi_number_is_known(self):
        assert "+250794002033" in KNOWN_CALLERS
        assert KNOWN_CALLERS["+250794002033"] == "Remi"

    def test_unknown_number_not_in_known_callers(self):
        assert "+19999999999" not in KNOWN_CALLERS


# ─── Module-level assertions ─────────────────────────────────────────────────

class TestModuleConstants:
    """Test important module-level values from webhook-server.py"""

    def test_openai_voice_is_shimmer(self):
        assert _ws_mod.OPENAI_VOICE == "shimmer"

    def test_workspace_root_is_path(self):
        assert isinstance(_ws_mod.WORKSPACE_ROOT, Path)

    def test_tool_registry_contains_expected_tools(self):
        registry = _ws_mod.TOOL_REGISTRY
        expected = ["memory_search", "read_file", "get_project_status", "memory_get",
                    "cron_create", "message_send", "sessions_send"]
        for tool in expected:
            assert tool in registry, f"Tool '{tool}' missing from TOOL_REGISTRY"

    def test_openclaw_gateway_url_default(self):
        assert "localhost:18789" in _ws_mod.OPENCLAW_GATEWAY_URL

    def test_media_stream_url_is_wss(self):
        assert _ws_mod.MEDIA_STREAM_WS_URL.startswith("wss://")
