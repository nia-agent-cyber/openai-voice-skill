#!/usr/bin/env python3
"""
Unit tests for scripts/cleanup_zombie_calls.py

Covers the main() function and CLI parsing via argument injection.
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
import unittest.mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Must import call_recording first with aiofiles mock
_aiofiles_mock = MagicMock()

class _FakeAioFile:
    def __init__(self, content=None):
        self._content = content or "[]"
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def read(self): return self._content
    async def write(self, data): pass

_aiofiles_mock.open = lambda path, mode='r': _FakeAioFile()

with unittest.mock.patch.dict('sys.modules', {'aiofiles': _aiofiles_mock}):
    import call_recording as cr

# Now import cleanup_zombie_calls
import cleanup_zombie_calls as czc
from cleanup_zombie_calls import main


# ─── Helper to set up a test recording_manager ────────────────────────────────

def setup_test_manager(tmp_path) -> cr.CallRecordingManager:
    """Create a test CallRecordingManager with fresh DB."""
    mgr = cr.CallRecordingManager.__new__(cr.CallRecordingManager)
    mgr.db_path = tmp_path / "test.db"
    mgr.recordings_dir = tmp_path / "recordings"
    mgr.recordings_dir.mkdir(parents=True, exist_ok=True)
    mgr._init_database()
    return mgr


# ─── main() function ──────────────────────────────────────────────────────────

class TestCleanupMain:
    """Tests for main() function."""

    def test_no_zombies_exits_cleanly(self, tmp_path):
        """When there are no zombies, main() returns 0."""
        mgr = setup_test_manager(tmp_path)

        async def run():
            with patch.object(czc, 'recording_manager', mgr):
                with patch('sys.argv', ['cleanup_zombie_calls.py']):
                    return await main()

        result = asyncio.run(run())
        assert result == 0

    def test_dry_run_shows_zombies_without_cleaning(self, tmp_path):
        """--dry-run shows zombie info but doesn't clean them."""
        mgr = setup_test_manager(tmp_path)

        # Insert a stale call
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
        with sqlite3.connect(mgr.db_path) as conn:
            conn.execute(
                'INSERT INTO calls (call_id, call_type, started_at, status) VALUES (?, ?, ?, ?)',
                ("zombie-dry-1", "inbound", old_time, "active")
            )
            conn.commit()

        async def run():
            with patch.object(czc, 'recording_manager', mgr):
                with patch('sys.argv', ['cleanup_zombie_calls.py', '--dry-run']):
                    return await main()

        result = asyncio.run(run())
        assert result == 0

        # Zombie should still be active (not cleaned)
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT status FROM calls WHERE call_id = ?", ("zombie-dry-1",))
            row = cursor.fetchone()
        assert row[0] == "active"  # Unchanged

    def test_live_mode_cleans_zombies(self, tmp_path):
        """Without --dry-run, main() actually cleans zombies."""
        mgr = setup_test_manager(tmp_path)

        # Insert a stale call
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()
        with sqlite3.connect(mgr.db_path) as conn:
            conn.execute(
                'INSERT INTO calls (call_id, call_type, started_at, status) VALUES (?, ?, ?, ?)',
                ("zombie-live-1", "inbound", old_time, "active")
            )
            conn.commit()

        async def run():
            with patch.object(czc, 'recording_manager', mgr):
                with patch('sys.argv', ['cleanup_zombie_calls.py']):
                    return await main()

        result = asyncio.run(run())
        assert result == 0

        # Zombie should now be cleaned
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT status FROM calls WHERE call_id = ?", ("zombie-live-1",))
            row = cursor.fetchone()
        assert row[0] == "timeout"

    def test_custom_threshold(self, tmp_path):
        """Custom --threshold arg is respected."""
        mgr = setup_test_manager(tmp_path)

        async def run():
            with patch.object(czc, 'recording_manager', mgr):
                with patch('sys.argv', ['cleanup_zombie_calls.py', '--threshold', '300']):
                    return await main()

        result = asyncio.run(run())
        assert result == 0

    def test_multiple_zombies(self, tmp_path):
        """Multiple zombie calls are all cleaned."""
        mgr = setup_test_manager(tmp_path)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=7200)).isoformat()

        with sqlite3.connect(mgr.db_path) as conn:
            for i in range(3):
                conn.execute(
                    'INSERT INTO calls (call_id, call_type, started_at, status) VALUES (?, ?, ?, ?)',
                    (f"zombie-multi-{i}", "inbound", old_time, "active")
                )
            conn.commit()

        async def run():
            with patch.object(czc, 'recording_manager', mgr):
                with patch('sys.argv', ['cleanup_zombie_calls.py']):
                    return await main()

        result = asyncio.run(run())
        assert result == 0

        # All three should be cleaned
        with sqlite3.connect(mgr.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'timeout'")
            count = cursor.fetchone()[0]
        assert count == 3

    def test_stats_displayed_before_cleanup(self, tmp_path):
        """Stats are read before cleanup (testing code path)."""
        mgr = setup_test_manager(tmp_path)
        asyncio.run(mgr.start_call_recording("call-stats", "inbound"))

        async def run():
            with patch.object(czc, 'recording_manager', mgr):
                with patch('sys.argv', ['cleanup_zombie_calls.py', '--dry-run']):
                    return await main()

        result = asyncio.run(run())
        assert result == 0


# ─── Module-level imports ─────────────────────────────────────────────────────

class TestModuleImport:
    """Test that module-level code is imported correctly."""

    def test_main_function_exists(self):
        assert callable(main)

    def test_stale_threshold_constant_accessible(self):
        from cleanup_zombie_calls import STALE_CALL_THRESHOLD_SECONDS
        assert STALE_CALL_THRESHOLD_SECONDS > 0

    def test_recording_manager_accessible(self):
        # The module should have recording_manager from call_recording
        assert hasattr(czc, 'recording_manager')
