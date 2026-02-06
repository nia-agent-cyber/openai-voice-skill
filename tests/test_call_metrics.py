#!/usr/bin/env python3
"""
Tests for Call Metrics Module

Run with: python -m pytest tests/test_call_metrics.py -v
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Set up test database path before imports
TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = TEST_DB

# Import from scripts module (handle path variations)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from call_metrics import (
    CallMetricsManager,
    CallMetrics,
    HourlyBucket,
    DailyBucket,
    CallStatus,
    FailureReason,
    StructuredFormatter,
)


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    # Initialize the database with the schema from call_recording
    conn = sqlite3.connect(TEST_DB)
    
    # Create tables
    conn.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            call_id TEXT PRIMARY KEY,
            call_type TEXT NOT NULL,
            caller_number TEXT,
            callee_number TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_seconds REAL,
            status TEXT NOT NULL,
            recording_path TEXT,
            transcript_path TEXT,
            has_audio BOOLEAN DEFAULT FALSE,
            has_transcript BOOLEAN DEFAULT FALSE,
            metadata TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            speaker TEXT NOT NULL,
            content TEXT NOT NULL,
            event_type TEXT NOT NULL,
            metadata TEXT,
            FOREIGN KEY (call_id) REFERENCES calls (call_id)
        )
    ''')
    
    # Insert sample calls
    now = datetime.utcnow()
    sample_calls = [
        # Completed calls
        ("call-001", "outbound", "+14402915517", "+1234567890", 
         (now - timedelta(hours=2)).isoformat(), now.isoformat(), 120.5, "completed", True),
        ("call-002", "outbound", "+14402915517", "+1234567891", 
         (now - timedelta(hours=4)).isoformat(), (now - timedelta(hours=3, minutes=58)).isoformat(), 
         45.3, "completed", True),
        ("call-003", "inbound", "+1234567892", "+14402915517", 
         (now - timedelta(hours=6)).isoformat(), (now - timedelta(hours=5, minutes=55)).isoformat(), 
         300.0, "completed", False),
        # Failed call
        ("call-004", "outbound", "+14402915517", "+1234567893", 
         (now - timedelta(hours=3)).isoformat(), (now - timedelta(hours=2, minutes=59)).isoformat(), 
         5.0, "failed", False),
        # Timeout (zombie cleaned up)
        ("call-005", "outbound", "+14402915517", "+1234567894", 
         (now - timedelta(hours=5)).isoformat(), (now - timedelta(hours=1)).isoformat(), 
         14400.0, "timeout", False),
        # Active call
        ("call-006", "outbound", "+14402915517", "+1234567895", 
         (now - timedelta(minutes=5)).isoformat(), None, None, "active", False),
    ]
    
    for call in sample_calls:
        conn.execute('''
            INSERT INTO calls (call_id, call_type, caller_number, callee_number,
                             started_at, ended_at, duration_seconds, status, has_transcript)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', call)
    
    conn.commit()
    conn.close()
    
    yield TEST_DB
    
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def metrics_manager(test_db):
    """Create metrics manager with test database."""
    return CallMetricsManager(db_path=Path(test_db))


class TestCallMetrics:
    """Test call metrics aggregation."""
    
    def test_get_metrics_total_calls(self, metrics_manager):
        """Test total call count."""
        metrics = metrics_manager.get_metrics()
        assert metrics.total_calls == 6
    
    def test_get_metrics_status_breakdown(self, metrics_manager):
        """Test call status breakdown."""
        metrics = metrics_manager.get_metrics()
        assert metrics.completed_calls == 3
        assert metrics.failed_calls == 1
        assert metrics.timeout_calls == 1
        assert metrics.active_calls == 1
    
    def test_get_metrics_type_breakdown(self, metrics_manager):
        """Test call type breakdown."""
        metrics = metrics_manager.get_metrics()
        assert metrics.outbound_calls == 5
        assert metrics.inbound_calls == 1
    
    def test_get_metrics_duration_stats(self, metrics_manager):
        """Test duration statistics."""
        metrics = metrics_manager.get_metrics()
        # Only completed calls should be counted for duration
        assert metrics.avg_duration > 0
        assert metrics.min_duration > 0
        assert metrics.max_duration >= metrics.min_duration
        assert metrics.p50_duration > 0
    
    def test_get_metrics_success_rate(self, metrics_manager):
        """Test success rate calculation."""
        metrics = metrics_manager.get_metrics()
        # 3 completed out of 6 total = 50%
        assert metrics.success_rate == 50.0
    
    def test_get_metrics_transcript_rate(self, metrics_manager):
        """Test transcript rate calculation."""
        metrics = metrics_manager.get_metrics()
        # 2 with transcript out of 6 total
        expected_rate = (2 / 6) * 100
        assert abs(metrics.transcript_rate - expected_rate) < 0.1


class TestTimeseries:
    """Test timeseries data generation."""
    
    def test_hourly_timeseries_length(self, metrics_manager):
        """Test hourly timeseries returns correct number of buckets."""
        timeseries = metrics_manager.get_hourly_timeseries(hours=24)
        # Should have 25 buckets (24 hours + current hour)
        assert len(timeseries) >= 24
    
    def test_hourly_bucket_structure(self, metrics_manager):
        """Test hourly bucket has correct structure."""
        timeseries = metrics_manager.get_hourly_timeseries(hours=6)
        for bucket in timeseries:
            assert isinstance(bucket, HourlyBucket)
            assert bucket.hour is not None
            assert isinstance(bucket.total, int)
            assert isinstance(bucket.completed, int)
            assert isinstance(bucket.failed, int)
    
    def test_daily_timeseries_length(self, metrics_manager):
        """Test daily timeseries returns correct number of buckets."""
        timeseries = metrics_manager.get_daily_timeseries(days=7)
        assert len(timeseries) == 7
    
    def test_daily_bucket_success_rate(self, metrics_manager):
        """Test daily bucket calculates success rate."""
        timeseries = metrics_manager.get_daily_timeseries(days=1)
        # Today's bucket should have our test calls
        today_bucket = timeseries[-1]
        if today_bucket.total > 0:
            assert 0 <= today_bucket.success_rate <= 100


class TestDashboardData:
    """Test dashboard data generation."""
    
    def test_dashboard_structure(self, metrics_manager):
        """Test dashboard data has required structure."""
        dashboard = metrics_manager.get_dashboard_data()
        
        assert "generated_at" in dashboard
        assert "period" in dashboard
        assert "summary" in dashboard
        assert "breakdown" in dashboard
        assert "duration" in dashboard
        assert "transcript" in dashboard
        assert "timeseries" in dashboard
    
    def test_dashboard_summary(self, metrics_manager):
        """Test dashboard summary fields."""
        dashboard = metrics_manager.get_dashboard_data()
        summary = dashboard["summary"]
        
        assert "total_calls" in summary
        assert "success_rate" in summary
        assert "avg_duration" in summary
        assert "active_now" in summary
    
    def test_dashboard_deltas(self, metrics_manager):
        """Test dashboard includes delta calculations."""
        dashboard = metrics_manager.get_dashboard_data()
        summary = dashboard["summary"]
        
        assert "total_calls_delta" in summary
        assert "success_rate_delta" in summary
        assert "avg_duration_delta" in summary


class TestExports:
    """Test data export functionality."""
    
    def test_csv_export_format(self, metrics_manager):
        """Test CSV export has correct format."""
        csv_data = metrics_manager.export_csv(days=7)
        
        lines = csv_data.strip().split("\n")
        assert len(lines) >= 1  # At least header
        
        # Check header
        header = lines[0]
        assert "call_id" in header
        assert "status" in header
        assert "duration_seconds" in header
    
    def test_csv_export_content(self, metrics_manager):
        """Test CSV export contains expected data."""
        csv_data = metrics_manager.export_csv(days=7)
        
        lines = csv_data.strip().split("\n")
        # Should have header + 6 calls
        assert len(lines) == 7
    
    def test_json_export_format(self, metrics_manager):
        """Test JSON export has correct format."""
        json_data = metrics_manager.export_json(days=7)
        
        data = json.loads(json_data)
        assert "exported_at" in data
        assert "period_days" in data
        assert "call_count" in data
        assert "calls" in data
    
    def test_json_export_content(self, metrics_manager):
        """Test JSON export contains expected data."""
        json_data = metrics_manager.export_json(days=7)
        
        data = json.loads(json_data)
        assert data["call_count"] == 6


class TestPrometheusMetrics:
    """Test Prometheus metrics generation."""
    
    def test_prometheus_format(self, metrics_manager):
        """Test Prometheus output format."""
        prom = metrics_manager.get_prometheus_metrics()
        
        # Should contain metric names and values
        assert "voice_calls_total" in prom
        assert "voice_calls_success_rate" in prom
        assert "voice_calls_active" in prom
        assert "voice_call_duration_seconds" in prom
    
    def test_prometheus_types(self, metrics_manager):
        """Test Prometheus type annotations."""
        prom = metrics_manager.get_prometheus_metrics()
        
        assert "# TYPE voice_calls_total counter" in prom
        assert "# TYPE voice_calls_success_rate gauge" in prom
        assert "# TYPE voice_calls_active gauge" in prom
    
    def test_prometheus_quantiles(self, metrics_manager):
        """Test Prometheus quantile values."""
        prom = metrics_manager.get_prometheus_metrics()
        
        assert 'quantile="0.5"' in prom
        assert 'quantile="0.95"' in prom
        assert 'quantile="0.99"' in prom


class TestHealthCheck:
    """Test health check functionality."""
    
    def test_health_check_structure(self, metrics_manager):
        """Test health check response structure."""
        health = metrics_manager.health_check()
        
        assert "status" in health
        assert "timestamp" in health
        assert "indicators" in health
        assert "warnings" in health
    
    def test_health_check_status(self, metrics_manager):
        """Test health check returns valid status."""
        health = metrics_manager.health_check()
        
        assert health["status"] in ("healthy", "degraded")
    
    def test_health_check_indicators(self, metrics_manager):
        """Test health check includes indicators."""
        health = metrics_manager.health_check()
        indicators = health["indicators"]
        
        assert "calls_last_hour" in indicators
        assert "success_rate" in indicators
        assert "active_calls" in indicators


class TestRecentFailures:
    """Test recent failures retrieval."""
    
    def test_recent_failures_content(self, metrics_manager):
        """Test recent failures returns failed calls."""
        failures = metrics_manager.get_recent_failures(limit=10)
        
        # Should include our failed and timeout calls
        statuses = [f["status"] for f in failures]
        assert "failed" in statuses or "timeout" in statuses
    
    def test_recent_failures_limit(self, metrics_manager):
        """Test recent failures respects limit."""
        failures = metrics_manager.get_recent_failures(limit=1)
        
        assert len(failures) <= 1


class TestStructuredLogging:
    """Test structured logging formatter."""
    
    def test_json_format(self):
        """Test log output is valid JSON."""
        formatter = StructuredFormatter()
        
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert "timestamp" in data
        assert "level" in data
        assert "message" in data
    
    def test_extra_fields(self):
        """Test extra fields are included."""
        formatter = StructuredFormatter()
        
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.call_id = "test-123"
        record.status = "completed"
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["call_id"] == "test-123"
        assert data["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
