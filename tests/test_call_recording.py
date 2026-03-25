#!/usr/bin/env python3
"""
Unit tests for scripts/call_recording.py

Covers:
- CallRecord and TranscriptEntry dataclasses
- CallRecordingManager: init, start/end recording, transcripts, list, delete, stats
- cleanup_stale_calls, get_zombie_calls
"""

import asyncio
import json
import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Patch aiofiles before importing call_recording
import unittest.mock
_aiofiles_mock = unittest.mock.MagicMock()

# Create proper async context manager for aiofiles.open
class _FakeAioFile:
    def __init__(self, content=None):
        self._content = content or ""
        self._written = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def read(self):
        return self._content

    async def write(self, data):
        self._written.append(data)

def _fake_aiofiles_open(path, mode='r'):
    return _FakeAioFile(content="[]" if 'r' in mode else None)

_aiofiles_mock.open = _fake_aiofiles_open

with unittest.mock.patch.dict('sys.modules', {'aiofiles': _aiofiles_mock}):
    import call_recording as cr
    from call_recording import (
        CallRecord,
        TranscriptEntry,
        CallRecordingManager,
        ENABLE_RECORDING,
        ENABLE_TRANSCRIPTION,
    )


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_manager(tmp_path) -> CallRecordingManager:
    """Create a CallRecordingManager with a fresh test database."""
    db_path = tmp_path / "test_calls.db"
    recordings_dir = tmp_path / "recordings"
    with patch.object(cr, 'DATABASE_PATH', db_path):
        with patch.object(cr, 'RECORDINGS_DIR', recordings_dir):
            mgr = CallRecordingManager.__new__(CallRecordingManager)
            mgr.db_path = db_path
            mgr.recordings_dir = recordings_dir
            recordings_dir.mkdir(parents=True, exist_ok=True)
            mgr._init_database()
            return mgr


# ─── CallRecord dataclass ─────────────────────────────────────────────────────

class TestCallRecord:
    """Tests for CallRecord dataclass."""

    def test_create_call_record(self):
        record = CallRecord(
            call_id="test-123",
            call_type="inbound",
            caller_number="+1234567890",
            callee_number="+0987654321",
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration_seconds=None,
            status="active",
            recording_path=None,
            transcript_path=None
        )
        assert record.call_id == "test-123"
        assert record.call_type == "inbound"
        assert record.status == "active"
        assert record.has_audio is False
        assert record.has_transcript is False

    def test_call_record_with_metadata(self):
        record = CallRecord(
            call_id="test-456",
            call_type="outbound",
            caller_number=None,
            callee_number="+1234567890",
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration_seconds=None,
            status="active",
            recording_path=None,
            transcript_path=None,
            metadata={"initial_message": "Hello!"}
        )
        assert record.metadata["initial_message"] == "Hello!"


# ─── TranscriptEntry dataclass ────────────────────────────────────────────────

class TestTranscriptEntry:
    """Tests for TranscriptEntry dataclass."""

    def test_create_transcript_entry(self):
        entry = TranscriptEntry(
            call_id="test-123",
            timestamp=datetime.now(timezone.utc),
            speaker="user",
            content="Hello, how are you?",
            event_type="speech"
        )
        assert entry.call_id == "test-123"
        assert entry.speaker == "user"
        assert entry.content == "Hello, how are you?"
        assert entry.metadata is None


# ─── CallRecordingManager._init_database ──────────────────────────────────────

class TestInitDatabase:
    """Tests for _init_database."""

    def test_creates_calls_table(self, tmp_path):
        mgr = make_manager(tmp_path)
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calls'")
            assert cursor.fetchone() is not None

    def test_creates_transcripts_table(self, tmp_path):
        mgr = make_manager(tmp_path)
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts'")
            assert cursor.fetchone() is not None

    def test_creates_indexes(self, tmp_path):
        mgr = make_manager(tmp_path)
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]
            assert any("idx_calls" in idx for idx in indexes)


# ─── start_call_recording ─────────────────────────────────────────────────────

class TestStartCallRecording:
    """Tests for start_call_recording."""

    def test_creates_call_record(self, tmp_path):
        mgr = make_manager(tmp_path)
        with patch.object(cr, 'ENABLE_RECORDING', True):
            record = asyncio.run(mgr.start_call_recording("call-1", "inbound", "+1234567890"))
        assert record is not None
        assert record.call_id == "call-1"
        assert record.status == "active"
        assert record.call_type == "inbound"

    def test_stores_in_database(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-db-1", "inbound"))
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT call_id FROM calls WHERE call_id = ?", ("call-db-1",))
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "call-db-1"

    def test_returns_none_when_recording_disabled(self, tmp_path):
        mgr = make_manager(tmp_path)
        with patch.object(cr, 'ENABLE_RECORDING', False):
            record = asyncio.run(mgr.start_call_recording("call-x", "inbound"))
        assert record is None

    def test_sets_recording_path_when_enabled(self, tmp_path):
        mgr = make_manager(tmp_path)
        with patch.object(cr, 'ENABLE_RECORDING', True):
            record = asyncio.run(mgr.start_call_recording("call-path", "inbound"))
        assert record is not None
        assert record.recording_path is not None
        assert "call-path" in record.recording_path

    def test_sets_transcript_path_when_transcription_enabled(self, tmp_path):
        mgr = make_manager(tmp_path)
        with patch.object(cr, 'ENABLE_RECORDING', True), patch.object(cr, 'ENABLE_TRANSCRIPTION', True):
            record = asyncio.run(mgr.start_call_recording("call-tx", "outbound"))
        assert record is not None
        assert record.transcript_path is not None

    def test_outbound_call(self, tmp_path):
        mgr = make_manager(tmp_path)
        record = asyncio.run(mgr.start_call_recording(
            "call-out", "outbound",
            callee_number="+9876543210"
        ))
        assert record is not None
        assert record.call_type == "outbound"
        assert record.callee_number == "+9876543210"


# ─── end_call_recording ──────────────────────────────────────────────────────

class TestEndCallRecording:
    """Tests for end_call_recording."""

    def test_ends_active_call(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-e1", "inbound"))
        import time; time.sleep(0.01)  # ensure some duration
        record = asyncio.run(mgr.end_call_recording("call-e1"))
        assert record is not None
        assert record.status == "completed"
        assert record.ended_at is not None

    def test_duration_calculated(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-dur", "inbound"))
        import time; time.sleep(0.05)
        record = asyncio.run(mgr.end_call_recording("call-dur"))
        assert record is not None
        assert record.duration_seconds > 0

    def test_returns_none_for_nonexistent_call(self, tmp_path):
        mgr = make_manager(tmp_path)
        record = asyncio.run(mgr.end_call_recording("nonexistent-call"))
        assert record is None

    def test_custom_status(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-fail", "inbound"))
        record = asyncio.run(mgr.end_call_recording("call-fail", status="failed"))
        assert record is not None
        assert record.status == "failed"


# ─── add_transcript_entry ────────────────────────────────────────────────────

class TestAddTranscriptEntry:
    """Tests for add_transcript_entry."""

    def test_adds_transcript_entry(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-tr1", "inbound"))
        with patch.object(cr, 'ENABLE_TRANSCRIPTION', True):
            result = asyncio.run(mgr.add_transcript_entry(
                "call-tr1", "user", "Hello!", "speech"
            ))
        assert result is True

    def test_returns_false_when_disabled(self, tmp_path):
        mgr = make_manager(tmp_path)
        with patch.object(cr, 'ENABLE_TRANSCRIPTION', False):
            result = asyncio.run(mgr.add_transcript_entry(
                "call-tr-off", "user", "Hello", "speech"
            ))
        assert result is False

    def test_stores_in_database(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-tr2", "inbound"))
        with patch.object(cr, 'ENABLE_TRANSCRIPTION', True):
            asyncio.run(mgr.add_transcript_entry("call-tr2", "assistant", "Hi there!", "speech"))
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT content FROM transcripts WHERE call_id = ?", ("call-tr2",))
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Hi there!"

    def test_marks_call_has_transcript(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-tr3", "inbound"))
        with patch.object(cr, 'ENABLE_TRANSCRIPTION', True):
            asyncio.run(mgr.add_transcript_entry("call-tr3", "user", "Test", "speech"))
        record = asyncio.run(mgr.get_call_record("call-tr3"))
        assert record.has_transcript is True


# ─── get_call_record ─────────────────────────────────────────────────────────

class TestGetCallRecord:
    """Tests for get_call_record."""

    def test_returns_record_for_existing_call(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-g1", "inbound", "+1234567890"))
        record = asyncio.run(mgr.get_call_record("call-g1"))
        assert record is not None
        assert record.call_id == "call-g1"
        assert record.caller_number == "+1234567890"

    def test_returns_none_for_nonexistent(self, tmp_path):
        mgr = make_manager(tmp_path)
        record = asyncio.run(mgr.get_call_record("nonexistent"))
        assert record is None


# ─── list_calls ──────────────────────────────────────────────────────────────

class TestListCalls:
    """Tests for list_calls."""

    def test_lists_all_calls(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-l1", "inbound"))
        asyncio.run(mgr.start_call_recording("call-l2", "outbound"))
        calls = asyncio.run(mgr.list_calls())
        call_ids = [c.call_id for c in calls]
        assert "call-l1" in call_ids
        assert "call-l2" in call_ids

    def test_filters_by_call_type(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-in1", "inbound"))
        asyncio.run(mgr.start_call_recording("call-out1", "outbound"))
        inbound_calls = asyncio.run(mgr.list_calls(call_type="inbound"))
        assert all(c.call_type == "inbound" for c in inbound_calls)

    def test_pagination(self, tmp_path):
        mgr = make_manager(tmp_path)
        for i in range(5):
            asyncio.run(mgr.start_call_recording(f"call-p{i}", "inbound"))
        calls = asyncio.run(mgr.list_calls(limit=2, offset=0))
        assert len(calls) <= 2

    def test_empty_database(self, tmp_path):
        mgr = make_manager(tmp_path)
        calls = asyncio.run(mgr.list_calls())
        assert calls == []


# ─── get_call_transcript ─────────────────────────────────────────────────────

class TestGetCallTranscript:
    """Tests for get_call_transcript."""

    def test_returns_entries_in_order(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-tx1", "inbound"))
        with patch.object(cr, 'ENABLE_TRANSCRIPTION', True):
            asyncio.run(mgr.add_transcript_entry("call-tx1", "user", "First message", "speech"))
            asyncio.run(mgr.add_transcript_entry("call-tx1", "assistant", "Response", "speech"))
        entries = asyncio.run(mgr.get_call_transcript("call-tx1"))
        assert len(entries) == 2
        assert entries[0].speaker == "user"
        assert entries[1].speaker == "assistant"

    def test_returns_empty_for_nonexistent_call(self, tmp_path):
        mgr = make_manager(tmp_path)
        entries = asyncio.run(mgr.get_call_transcript("nonexistent"))
        assert entries == []


# ─── delete_call_record ──────────────────────────────────────────────────────

class TestDeleteCallRecord:
    """Tests for delete_call_record."""

    def test_deletes_existing_call(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-del1", "inbound"))
        result = asyncio.run(mgr.delete_call_record("call-del1"))
        assert result is True
        record = asyncio.run(mgr.get_call_record("call-del1"))
        assert record is None

    def test_returns_false_for_nonexistent(self, tmp_path):
        mgr = make_manager(tmp_path)
        result = asyncio.run(mgr.delete_call_record("nonexistent"))
        assert result is False

    def test_also_deletes_transcripts(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-del2", "inbound"))
        with patch.object(cr, 'ENABLE_TRANSCRIPTION', True):
            asyncio.run(mgr.add_transcript_entry("call-del2", "user", "Test", "speech"))
        asyncio.run(mgr.delete_call_record("call-del2"))
        entries = asyncio.run(mgr.get_call_transcript("call-del2"))
        assert entries == []


# ─── get_storage_stats ───────────────────────────────────────────────────────

class TestGetStorageStats:
    """Tests for get_storage_stats."""

    def test_returns_dict_with_expected_keys(self, tmp_path):
        mgr = make_manager(tmp_path)
        stats = mgr.get_storage_stats()
        assert "total_calls" in stats
        assert "active_calls" in stats
        assert "calls_with_audio" in stats
        assert "calls_with_transcripts" in stats
        assert "recordings_directory" in stats

    def test_counts_correctly(self, tmp_path):
        mgr = make_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-s1", "inbound"))
        asyncio.run(mgr.start_call_recording("call-s2", "outbound"))
        stats = mgr.get_storage_stats()
        assert stats["total_calls"] == 2
        assert stats["active_calls"] == 2

    def test_empty_database(self, tmp_path):
        mgr = make_manager(tmp_path)
        stats = mgr.get_storage_stats()
        assert stats["total_calls"] == 0
        assert stats["active_calls"] == 0


# ─── cleanup_stale_calls ──────────────────────────────────────────────────────

class TestCleanupStaleCalls:
    """Tests for cleanup_stale_calls."""

    def test_cleans_up_old_active_calls(self, tmp_path):
        mgr = make_manager(tmp_path)
        # Insert a stale call directly
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
        with sqlite3.connect(mgr.db_path) as conn:
            conn.execute('''
                INSERT INTO calls (call_id, call_type, started_at, status)
                VALUES (?, ?, ?, ?)
            ''', ("stale-call-1", "inbound", old_time, "active"))
            conn.commit()

        result = asyncio.run(mgr.cleanup_stale_calls(threshold_seconds=3600))
        assert result["cleaned_count"] == 1
        assert any(c["call_id"] == "stale-call-1" for c in result["cleaned_calls"])

    def test_does_not_clean_recent_calls(self, tmp_path):
        mgr = make_manager(tmp_path)
        # Recent active call
        asyncio.run(mgr.start_call_recording("recent-call", "inbound"))
        result = asyncio.run(mgr.cleanup_stale_calls(threshold_seconds=3600))
        assert result["cleaned_count"] == 0

    def test_marks_cleaned_calls_as_timeout(self, tmp_path):
        mgr = make_manager(tmp_path)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
        with sqlite3.connect(mgr.db_path) as conn:
            conn.execute('''
                INSERT INTO calls (call_id, call_type, started_at, status)
                VALUES (?, ?, ?, ?)
            ''', ("stale-2", "inbound", old_time, "active"))
            conn.commit()

        asyncio.run(mgr.cleanup_stale_calls(threshold_seconds=3600))

        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT status FROM calls WHERE call_id = ?", ("stale-2",))
            row = cursor.fetchone()
        assert row[0] == "timeout"

    def test_returns_result_structure(self, tmp_path):
        mgr = make_manager(tmp_path)
        result = asyncio.run(mgr.cleanup_stale_calls())
        assert "cleaned_count" in result
        assert "cleaned_calls" in result
        assert "threshold_seconds" in result
        assert "errors" in result


# ─── get_zombie_calls ────────────────────────────────────────────────────────

class TestGetZombieCalls:
    """Tests for get_zombie_calls."""

    def test_returns_empty_when_no_zombies(self, tmp_path):
        mgr = make_manager(tmp_path)
        zombies = mgr.get_zombie_calls(threshold_seconds=3600)
        assert zombies == []

    def test_returns_stale_calls(self, tmp_path):
        mgr = make_manager(tmp_path)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
        with sqlite3.connect(mgr.db_path) as conn:
            conn.execute('''
                INSERT INTO calls (call_id, call_type, started_at, status, caller_number)
                VALUES (?, ?, ?, ?, ?)
            ''', ("zombie-1", "inbound", old_time, "active", "+1234567890"))
            conn.commit()

        zombies = mgr.get_zombie_calls(threshold_seconds=3600)
        assert len(zombies) == 1
        assert zombies[0]["call_id"] == "zombie-1"
        assert "duration_seconds" in zombies[0]

    def test_uses_default_threshold(self, tmp_path):
        mgr = make_manager(tmp_path)
        zombies = mgr.get_zombie_calls()  # Uses default threshold
        assert isinstance(zombies, list)
