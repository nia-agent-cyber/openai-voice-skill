#!/usr/bin/env python3
"""
Call Metrics and Observability Module

Provides production-ready call metrics, analytics, and monitoring hooks.
Designed for dashboard integration and debugging.

Features:
- Aggregate metrics (success rate, duration percentiles, failure reasons)
- Time-series data for dashboards (hourly/daily buckets)
- Structured logging for debugging
- CSV/JSON exports for analytics
- Real-time call status monitoring
- **Latency tracking (speech_end_to_first_audio, tool_call_duration, session_duration)**

Usage:
    from call_metrics import metrics_manager
    
    # Get dashboard data
    dashboard = metrics_manager.get_dashboard_data()
    
    # Export for analytics
    csv_data = metrics_manager.export_csv(days=30)
    
    # Record latency event
    metrics_manager.record_latency_event(
        call_id="call123",
        event_type="speech_end_to_first_audio",
        duration_ms=450.5
    )
    
    # Get latency statistics
    latency_stats = metrics_manager.get_latency_stats()
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
from pathlib import Path
import statistics

# Import from call_recording for database access
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "call_history.db"))

logger = logging.getLogger(__name__)

# Configure structured logging
class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production debugging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'call_id'):
            log_entry['call_id'] = record.call_id
        if hasattr(record, 'call_type'):
            log_entry['call_type'] = record.call_type
        if hasattr(record, 'duration_seconds'):
            log_entry['duration_seconds'] = record.duration_seconds
        if hasattr(record, 'status'):
            log_entry['status'] = record.status
        if hasattr(record, 'error_category'):
            log_entry['error_category'] = record.error_category
        if hasattr(record, 'phone_number'):
            log_entry['phone_number'] = record.phone_number
        if hasattr(record, 'metrics'):
            log_entry['metrics'] = record.metrics
            
        return json.dumps(log_entry)


class CallStatus(Enum):
    """Standardized call status values."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"  # Zombie calls cleaned up


class FailureReason(Enum):
    """Categorized failure reasons for debugging."""
    TIMEOUT = "timeout"
    USER_HANGUP = "user_hangup"
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    UNKNOWN = "unknown"


class LatencyEventType(Enum):
    """Types of latency events for tracking voice UX metrics."""
    SPEECH_END_TO_FIRST_AUDIO = "speech_end_to_first_audio"  # Core UX metric
    TOOL_CALL_DURATION = "tool_call_duration"  # Time spent in tool execution
    SESSION_DURATION = "session_duration"  # Total call length


@dataclass
class CallMetrics:
    """Aggregate call metrics for a time period."""
    period_start: datetime
    period_end: datetime
    total_calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    cancelled_calls: int = 0
    active_calls: int = 0
    inbound_calls: int = 0
    outbound_calls: int = 0
    
    # Duration metrics (in seconds)
    total_duration: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0
    p50_duration: float = 0.0
    p95_duration: float = 0.0
    p99_duration: float = 0.0
    
    # Transcript metrics
    calls_with_transcript: int = 0
    transcript_rate: float = 0.0
    
    # Success rate
    success_rate: float = 0.0
    
    # Failure breakdown
    failure_reasons: Dict[str, int] = field(default_factory=dict)


@dataclass
class HourlyBucket:
    """Hourly aggregated metrics for time-series charts."""
    hour: str  # ISO format: "2026-02-06T10:00:00Z"
    total: int = 0
    completed: int = 0
    failed: int = 0
    avg_duration: float = 0.0


@dataclass
class DailyBucket:
    """Daily aggregated metrics for trend analysis."""
    date: str  # ISO format: "2026-02-06"
    total: int = 0
    completed: int = 0
    failed: int = 0
    avg_duration: float = 0.0
    success_rate: float = 0.0


@dataclass
class LatencyEvent:
    """Individual latency event record."""
    id: Optional[int] = None
    call_id: str = ""
    event_type: str = ""  # LatencyEventType value
    duration_ms: float = 0.0
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LatencyStats:
    """Aggregate latency statistics for a time period."""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Speech end to first audio (core UX metric)
    speech_to_audio_count: int = 0
    speech_to_audio_avg_ms: float = 0.0
    speech_to_audio_min_ms: float = 0.0
    speech_to_audio_max_ms: float = 0.0
    speech_to_audio_p50_ms: float = 0.0
    speech_to_audio_p95_ms: float = 0.0
    speech_to_audio_p99_ms: float = 0.0
    
    # Tool call duration
    tool_call_count: int = 0
    tool_call_avg_ms: float = 0.0
    tool_call_min_ms: float = 0.0
    tool_call_max_ms: float = 0.0
    tool_call_p50_ms: float = 0.0
    tool_call_p95_ms: float = 0.0
    tool_call_p99_ms: float = 0.0
    
    # Session duration (total call length)
    session_count: int = 0
    session_avg_ms: float = 0.0
    session_min_ms: float = 0.0
    session_max_ms: float = 0.0
    session_p50_ms: float = 0.0
    session_p95_ms: float = 0.0
    session_p99_ms: float = 0.0


class CallMetricsManager:
    """Manages call metrics collection, aggregation, and export."""
    
    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self._setup_structured_logging()
        self._init_latency_table()
    
    def _init_latency_table(self):
        """Initialize latency_events table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS latency_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (call_id) REFERENCES calls (call_id)
                )
            ''')
            # Indexes for efficient queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_latency_call_id ON latency_events(call_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_latency_event_type ON latency_events(event_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_latency_timestamp ON latency_events(timestamp)')
            conn.commit()
    
    def _setup_structured_logging(self):
        """Configure structured logging for observability."""
        metrics_logger = logging.getLogger("voice.metrics")
        
        # Check if already configured
        if not metrics_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())
            metrics_logger.addHandler(handler)
            metrics_logger.setLevel(logging.INFO)
        
        self.metrics_logger = metrics_logger
    
    def log_call_event(self, event_type: str, call_id: str, **kwargs):
        """Emit structured log event for call lifecycle."""
        extra = {"call_id": call_id, **kwargs}
        record = self.metrics_logger.makeRecord(
            "voice.metrics", logging.INFO, "", 0, 
            f"call_{event_type}", (), None
        )
        for key, value in extra.items():
            setattr(record, key, value)
        self.metrics_logger.handle(record)
    
    def get_metrics(self, 
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None) -> CallMetrics:
        """
        Get aggregate call metrics for a time period.
        
        Args:
            start_time: Start of period (default: 24 hours ago)
            end_time: End of period (default: now)
        
        Returns:
            CallMetrics with all aggregate data
        """
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(hours=24)
        
        metrics = CallMetrics(period_start=start_time, period_end=end_time)
        durations: List[float] = []
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all calls in the time period
            cursor = conn.execute('''
                SELECT call_id, call_type, started_at, ended_at, 
                       duration_seconds, status, has_transcript
                FROM calls
                WHERE started_at >= ? AND started_at < ?
                ORDER BY started_at ASC
            ''', (start_time.isoformat(), end_time.isoformat()))
            
            for row in cursor.fetchall():
                call_id, call_type, started_at, ended_at, duration, status, has_transcript = row
                
                metrics.total_calls += 1
                
                # Count by type
                if call_type == "inbound":
                    metrics.inbound_calls += 1
                else:
                    metrics.outbound_calls += 1
                
                # Count by status
                if status == "completed":
                    metrics.completed_calls += 1
                    if duration:
                        durations.append(duration)
                        metrics.total_duration += duration
                elif status == "failed":
                    metrics.failed_calls += 1
                    reason = self._categorize_failure(call_id)
                    metrics.failure_reasons[reason] = metrics.failure_reasons.get(reason, 0) + 1
                elif status == "timeout":
                    metrics.timeout_calls += 1
                elif status == "cancelled":
                    metrics.cancelled_calls += 1
                elif status == "active":
                    metrics.active_calls += 1
                
                # Transcript metrics
                if has_transcript:
                    metrics.calls_with_transcript += 1
        
        # Calculate duration statistics
        if durations:
            metrics.avg_duration = statistics.mean(durations)
            metrics.min_duration = min(durations)
            metrics.max_duration = max(durations)
            
            sorted_durations = sorted(durations)
            n = len(sorted_durations)
            metrics.p50_duration = sorted_durations[n // 2]
            metrics.p95_duration = sorted_durations[int(n * 0.95)] if n > 1 else sorted_durations[-1]
            metrics.p99_duration = sorted_durations[int(n * 0.99)] if n > 1 else sorted_durations[-1]
        
        # Calculate rates
        if metrics.total_calls > 0:
            metrics.success_rate = metrics.completed_calls / metrics.total_calls * 100
            metrics.transcript_rate = metrics.calls_with_transcript / metrics.total_calls * 100
        
        return metrics
    
    def _categorize_failure(self, call_id: str) -> str:
        """Categorize failure reason from call metadata or heuristics."""
        # For now, return unknown - can be extended with call metadata
        # In production, webhook-server.py would log failure reasons
        return FailureReason.UNKNOWN.value
    
    def get_hourly_timeseries(self, hours: int = 24) -> List[HourlyBucket]:
        """
        Get hourly metrics for time-series visualization.
        
        Args:
            hours: Number of hours to include (default: 24)
        
        Returns:
            List of HourlyBucket objects
        """
        end_time = datetime.now(timezone.utc)
        # Round to current hour
        end_time = end_time.replace(minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=hours)
        
        buckets: Dict[str, HourlyBucket] = {}
        
        # Initialize all buckets
        current = start_time
        while current <= end_time:
            hour_key = current.strftime("%Y-%m-%dT%H:00:00Z")
            buckets[hour_key] = HourlyBucket(hour=hour_key)
            current += timedelta(hours=1)
        
        # Fill buckets with data
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT started_at, duration_seconds, status
                FROM calls
                WHERE started_at >= ? AND started_at < ?
            ''', (start_time.isoformat(), end_time.isoformat()))
            
            duration_by_hour: Dict[str, List[float]] = {}
            
            for row in cursor.fetchall():
                started_at, duration, status = row
                dt = datetime.fromisoformat(started_at)
                hour_key = dt.strftime("%Y-%m-%dT%H:00:00Z")
                
                if hour_key in buckets:
                    buckets[hour_key].total += 1
                    if status == "completed":
                        buckets[hour_key].completed += 1
                        if duration:
                            if hour_key not in duration_by_hour:
                                duration_by_hour[hour_key] = []
                            duration_by_hour[hour_key].append(duration)
                    elif status in ("failed", "timeout"):
                        buckets[hour_key].failed += 1
            
            # Calculate averages
            for hour_key, durations in duration_by_hour.items():
                if durations:
                    buckets[hour_key].avg_duration = statistics.mean(durations)
        
        return [buckets[k] for k in sorted(buckets.keys())]
    
    def get_daily_timeseries(self, days: int = 30) -> List[DailyBucket]:
        """
        Get daily metrics for trend analysis.
        
        Args:
            days: Number of days to include (default: 30)
        
        Returns:
            List of DailyBucket objects
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days - 1)
        
        buckets: Dict[str, DailyBucket] = {}
        
        # Initialize all buckets
        current = start_date
        while current <= end_date:
            date_key = current.isoformat()
            buckets[date_key] = DailyBucket(date=date_key)
            current += timedelta(days=1)
        
        # Fill buckets with data
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT started_at, duration_seconds, status
                FROM calls
                WHERE date(started_at) >= ? AND date(started_at) <= ?
            ''', (start_date.isoformat(), end_date.isoformat()))
            
            duration_by_day: Dict[str, List[float]] = {}
            
            for row in cursor.fetchall():
                started_at, duration, status = row
                dt = datetime.fromisoformat(started_at)
                date_key = dt.date().isoformat()
                
                if date_key in buckets:
                    buckets[date_key].total += 1
                    if status == "completed":
                        buckets[date_key].completed += 1
                        if duration:
                            if date_key not in duration_by_day:
                                duration_by_day[date_key] = []
                            duration_by_day[date_key].append(duration)
                    elif status in ("failed", "timeout"):
                        buckets[date_key].failed += 1
            
            # Calculate averages and success rates
            for date_key in buckets:
                bucket = buckets[date_key]
                if bucket.total > 0:
                    bucket.success_rate = bucket.completed / bucket.total * 100
                if date_key in duration_by_day and duration_by_day[date_key]:
                    bucket.avg_duration = statistics.mean(duration_by_day[date_key])
        
        return [buckets[k] for k in sorted(buckets.keys())]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data in a single call.
        
        Returns:
            Dict with all metrics for dashboard rendering
        """
        now = datetime.now(timezone.utc)
        
        # Current metrics (last 24 hours)
        current_metrics = self.get_metrics(
            start_time=now - timedelta(hours=24),
            end_time=now
        )
        
        # Previous period for comparison (24-48 hours ago)
        prev_metrics = self.get_metrics(
            start_time=now - timedelta(hours=48),
            end_time=now - timedelta(hours=24)
        )
        
        # Calculate deltas
        def calc_delta(current: float, previous: float) -> float:
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return ((current - previous) / previous) * 100
        
        # Get active calls right now
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM calls WHERE status = 'active'"
            )
            active_now = cursor.fetchone()[0]
        
        return {
            "generated_at": now.isoformat() + "Z",
            "period": {
                "start": current_metrics.period_start.isoformat() + "Z",
                "end": current_metrics.period_end.isoformat() + "Z"
            },
            "summary": {
                "total_calls": current_metrics.total_calls,
                "total_calls_delta": calc_delta(
                    current_metrics.total_calls, prev_metrics.total_calls
                ),
                "success_rate": round(current_metrics.success_rate, 1),
                "success_rate_delta": calc_delta(
                    current_metrics.success_rate, prev_metrics.success_rate
                ),
                "avg_duration": round(current_metrics.avg_duration, 1),
                "avg_duration_delta": calc_delta(
                    current_metrics.avg_duration, prev_metrics.avg_duration
                ),
                "active_now": active_now,
            },
            "breakdown": {
                "by_status": {
                    "completed": current_metrics.completed_calls,
                    "failed": current_metrics.failed_calls,
                    "timeout": current_metrics.timeout_calls,
                    "cancelled": current_metrics.cancelled_calls,
                    "active": current_metrics.active_calls,
                },
                "by_type": {
                    "inbound": current_metrics.inbound_calls,
                    "outbound": current_metrics.outbound_calls,
                },
                "failure_reasons": current_metrics.failure_reasons,
            },
            "duration": {
                "avg": round(current_metrics.avg_duration, 1),
                "min": round(current_metrics.min_duration, 1),
                "max": round(current_metrics.max_duration, 1),
                "p50": round(current_metrics.p50_duration, 1),
                "p95": round(current_metrics.p95_duration, 1),
                "p99": round(current_metrics.p99_duration, 1),
                "total_seconds": round(current_metrics.total_duration, 0),
            },
            "transcript": {
                "calls_with_transcript": current_metrics.calls_with_transcript,
                "transcript_rate": round(current_metrics.transcript_rate, 1),
            },
            "timeseries": {
                "hourly": [asdict(b) for b in self.get_hourly_timeseries(24)],
            },
            "latency": self._get_latency_summary(now),
        }
    
    def _get_latency_summary(self, now: datetime) -> Dict[str, Any]:
        """Get latency summary for dashboard."""
        stats = self.get_latency_stats(
            start_time=now - timedelta(hours=24),
            end_time=now
        )
        
        return {
            "speech_end_to_first_audio_ms": {
                "count": stats.speech_to_audio_count,
                "avg": round(stats.speech_to_audio_avg_ms, 1),
                "p50": round(stats.speech_to_audio_p50_ms, 1),
                "p95": round(stats.speech_to_audio_p95_ms, 1),
                "p99": round(stats.speech_to_audio_p99_ms, 1),
                "min": round(stats.speech_to_audio_min_ms, 1),
                "max": round(stats.speech_to_audio_max_ms, 1),
            },
            "tool_call_duration_ms": {
                "count": stats.tool_call_count,
                "avg": round(stats.tool_call_avg_ms, 1),
                "p50": round(stats.tool_call_p50_ms, 1),
                "p95": round(stats.tool_call_p95_ms, 1),
                "p99": round(stats.tool_call_p99_ms, 1),
                "min": round(stats.tool_call_min_ms, 1),
                "max": round(stats.tool_call_max_ms, 1),
            },
            "session_duration_ms": {
                "count": stats.session_count,
                "avg": round(stats.session_avg_ms, 1),
                "p50": round(stats.session_p50_ms, 1),
                "p95": round(stats.session_p95_ms, 1),
                "p99": round(stats.session_p99_ms, 1),
                "min": round(stats.session_min_ms, 1),
                "max": round(stats.session_max_ms, 1),
            },
        }
    
    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            String in Prometheus exposition format
        """
        metrics = self.get_metrics()
        
        lines = [
            "# HELP voice_calls_total Total number of calls",
            "# TYPE voice_calls_total counter",
            f"voice_calls_total {metrics.total_calls}",
            "",
            "# HELP voice_calls_success_rate Call success rate percentage",
            "# TYPE voice_calls_success_rate gauge",
            f"voice_calls_success_rate {metrics.success_rate:.2f}",
            "",
            "# HELP voice_calls_active Currently active calls",
            "# TYPE voice_calls_active gauge",
            f"voice_calls_active {metrics.active_calls}",
            "",
            "# HELP voice_call_duration_seconds Call duration statistics",
            "# TYPE voice_call_duration_seconds summary",
            f'voice_call_duration_seconds{{quantile="0.5"}} {metrics.p50_duration:.2f}',
            f'voice_call_duration_seconds{{quantile="0.95"}} {metrics.p95_duration:.2f}',
            f'voice_call_duration_seconds{{quantile="0.99"}} {metrics.p99_duration:.2f}',
            f"voice_call_duration_seconds_sum {metrics.total_duration:.2f}",
            f"voice_call_duration_seconds_count {metrics.completed_calls}",
            "",
            "# HELP voice_calls_by_status Number of calls by status",
            "# TYPE voice_calls_by_status gauge",
            f'voice_calls_by_status{{status="completed"}} {metrics.completed_calls}',
            f'voice_calls_by_status{{status="failed"}} {metrics.failed_calls}',
            f'voice_calls_by_status{{status="timeout"}} {metrics.timeout_calls}',
            f'voice_calls_by_status{{status="cancelled"}} {metrics.cancelled_calls}',
            "",
            "# HELP voice_calls_by_type Number of calls by type",
            "# TYPE voice_calls_by_type gauge",
            f'voice_calls_by_type{{type="inbound"}} {metrics.inbound_calls}',
            f'voice_calls_by_type{{type="outbound"}} {metrics.outbound_calls}',
            "",
            "# HELP voice_transcript_rate Percentage of calls with transcripts",
            "# TYPE voice_transcript_rate gauge",
            f"voice_transcript_rate {metrics.transcript_rate:.2f}",
        ]
        
        # Add latency metrics
        latency_lines = self.get_latency_prometheus_metrics()
        
        return "\n".join(lines) + "\n\n" + latency_lines
    
    def export_csv(self, 
                   days: int = 30,
                   include_metadata: bool = False) -> str:
        """
        Export call data as CSV for analytics.
        
        Args:
            days: Number of days to export
            include_metadata: Include metadata column (JSON)
        
        Returns:
            CSV string
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        headers = [
            "call_id", "call_type", "caller_number", "callee_number",
            "started_at", "ended_at", "duration_seconds", "status",
            "has_transcript", "has_audio"
        ]
        if include_metadata:
            headers.append("metadata")
        
        lines = [",".join(headers)]
        
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT call_id, call_type, caller_number, callee_number,
                       started_at, ended_at, duration_seconds, status,
                       has_transcript, has_audio
            '''
            if include_metadata:
                query += ", metadata"
            
            query += '''
                FROM calls
                WHERE started_at >= ?
                ORDER BY started_at ASC
            '''
            
            cursor = conn.execute(query, (start_date.isoformat(),))
            
            for row in cursor.fetchall():
                values = [str(v) if v is not None else "" for v in row]
                # Escape commas in values
                values = [f'"{v}"' if "," in v or '"' in v else v for v in values]
                lines.append(",".join(values))
        
        return "\n".join(lines) + "\n"
    
    def export_json(self, days: int = 30) -> str:
        """
        Export call data as JSON for analytics.
        
        Args:
            days: Number of days to export
        
        Returns:
            JSON string
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        calls = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT call_id, call_type, caller_number, callee_number,
                       started_at, ended_at, duration_seconds, status,
                       has_transcript, has_audio, metadata
                FROM calls
                WHERE started_at >= ?
                ORDER BY started_at ASC
            ''', (start_date.isoformat(),))
            
            for row in cursor.fetchall():
                call = {
                    "call_id": row[0],
                    "call_type": row[1],
                    "caller_number": row[2],
                    "callee_number": row[3],
                    "started_at": row[4],
                    "ended_at": row[5],
                    "duration_seconds": row[6],
                    "status": row[7],
                    "has_transcript": bool(row[8]),
                    "has_audio": bool(row[9]),
                }
                if row[10]:
                    call["metadata"] = json.loads(row[10])
                calls.append(call)
        
        return json.dumps({
            "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
            "period_days": days,
            "call_count": len(calls),
            "calls": calls
        }, indent=2)
    
    def get_recent_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent failed calls for debugging.
        
        Args:
            limit: Maximum number of failures to return
        
        Returns:
            List of failed call records with context
        """
        failures = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT call_id, call_type, caller_number, callee_number,
                       started_at, ended_at, duration_seconds, status, metadata
                FROM calls
                WHERE status IN ('failed', 'timeout')
                ORDER BY started_at DESC
                LIMIT ?
            ''', (limit,))
            
            for row in cursor.fetchall():
                failures.append({
                    "call_id": row[0],
                    "call_type": row[1],
                    "caller_number": row[2],
                    "callee_number": row[3],
                    "started_at": row[4],
                    "ended_at": row[5],
                    "duration_seconds": row[6],
                    "status": row[7],
                    "metadata": json.loads(row[8]) if row[8] else None,
                    "failure_reason": self._categorize_failure(row[0])
                })
        
        return failures
    
    # ========================================
    # LATENCY TRACKING METHODS
    # Based on VisionClaw competitive analysis
    # ========================================
    
    def record_latency_event(self, call_id: str, event_type: str, duration_ms: float,
                            metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record a latency event for a call.
        
        Args:
            call_id: The call identifier
            event_type: Type of latency event (speech_end_to_first_audio, tool_call_duration, session_duration)
            duration_ms: Duration in milliseconds
            metadata: Optional additional metadata (e.g., tool name for tool_call_duration)
        
        Returns:
            True if recorded successfully
        """
        try:
            timestamp = datetime.now(timezone.utc)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO latency_events (call_id, event_type, duration_ms, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    call_id,
                    event_type,
                    duration_ms,
                    timestamp.isoformat(),
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
            
            # Emit structured log for real-time monitoring
            self.log_call_event(
                "latency",
                call_id,
                latency_type=event_type,
                duration_ms=duration_ms,
                latency_metadata=metadata
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording latency event: {e}")
            return False
    
    def get_latency_stats(self, 
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> LatencyStats:
        """
        Get aggregate latency statistics for a time period.
        
        Args:
            start_time: Start of period (default: 24 hours ago)
            end_time: End of period (default: now)
        
        Returns:
            LatencyStats with all latency metrics
        """
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(hours=24)
        
        stats = LatencyStats(period_start=start_time, period_end=end_time)
        
        # Collect durations by event type
        speech_to_audio: List[float] = []
        tool_call: List[float] = []
        session: List[float] = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT event_type, duration_ms
                FROM latency_events
                WHERE timestamp >= ? AND timestamp < ?
            ''', (start_time.isoformat(), end_time.isoformat()))
            
            for row in cursor.fetchall():
                event_type, duration_ms = row
                if event_type == LatencyEventType.SPEECH_END_TO_FIRST_AUDIO.value:
                    speech_to_audio.append(duration_ms)
                elif event_type == LatencyEventType.TOOL_CALL_DURATION.value:
                    tool_call.append(duration_ms)
                elif event_type == LatencyEventType.SESSION_DURATION.value:
                    session.append(duration_ms)
        
        # Calculate statistics for each metric type
        def calc_percentile(sorted_list: List[float], p: float) -> float:
            if not sorted_list:
                return 0.0
            n = len(sorted_list)
            idx = int(n * p)
            return sorted_list[min(idx, n - 1)]
        
        # Speech to audio stats
        if speech_to_audio:
            sorted_sta = sorted(speech_to_audio)
            stats.speech_to_audio_count = len(sorted_sta)
            stats.speech_to_audio_avg_ms = statistics.mean(sorted_sta)
            stats.speech_to_audio_min_ms = min(sorted_sta)
            stats.speech_to_audio_max_ms = max(sorted_sta)
            stats.speech_to_audio_p50_ms = calc_percentile(sorted_sta, 0.50)
            stats.speech_to_audio_p95_ms = calc_percentile(sorted_sta, 0.95)
            stats.speech_to_audio_p99_ms = calc_percentile(sorted_sta, 0.99)
        
        # Tool call stats
        if tool_call:
            sorted_tc = sorted(tool_call)
            stats.tool_call_count = len(sorted_tc)
            stats.tool_call_avg_ms = statistics.mean(sorted_tc)
            stats.tool_call_min_ms = min(sorted_tc)
            stats.tool_call_max_ms = max(sorted_tc)
            stats.tool_call_p50_ms = calc_percentile(sorted_tc, 0.50)
            stats.tool_call_p95_ms = calc_percentile(sorted_tc, 0.95)
            stats.tool_call_p99_ms = calc_percentile(sorted_tc, 0.99)
        
        # Session duration stats
        if session:
            sorted_sess = sorted(session)
            stats.session_count = len(sorted_sess)
            stats.session_avg_ms = statistics.mean(sorted_sess)
            stats.session_min_ms = min(sorted_sess)
            stats.session_max_ms = max(sorted_sess)
            stats.session_p50_ms = calc_percentile(sorted_sess, 0.50)
            stats.session_p95_ms = calc_percentile(sorted_sess, 0.95)
            stats.session_p99_ms = calc_percentile(sorted_sess, 0.99)
        
        return stats
    
    def get_latency_events(self, call_id: Optional[str] = None, 
                          event_type: Optional[str] = None,
                          limit: int = 100) -> List[LatencyEvent]:
        """
        Get latency events with optional filtering.
        
        Args:
            call_id: Filter by call ID (optional)
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return
        
        Returns:
            List of LatencyEvent objects
        """
        events = []
        
        query = 'SELECT id, call_id, event_type, duration_ms, timestamp, metadata FROM latency_events WHERE 1=1'
        params = []
        
        if call_id:
            query += ' AND call_id = ?'
            params.append(call_id)
        
        if event_type:
            query += ' AND event_type = ?'
            params.append(event_type)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            
            for row in cursor.fetchall():
                events.append(LatencyEvent(
                    id=row[0],
                    call_id=row[1],
                    event_type=row[2],
                    duration_ms=row[3],
                    timestamp=datetime.fromisoformat(row[4]) if row[4] else None,
                    metadata=json.loads(row[5]) if row[5] else None
                ))
        
        return events
    
    def get_latency_prometheus_metrics(self) -> str:
        """
        Export latency metrics in Prometheus format.
        
        Returns:
            String in Prometheus exposition format
        """
        stats = self.get_latency_stats()
        
        lines = [
            "# HELP voice_speech_to_audio_ms Time from user speech end to first AI audio",
            "# TYPE voice_speech_to_audio_ms summary",
            f'voice_speech_to_audio_ms{{quantile="0.5"}} {stats.speech_to_audio_p50_ms:.2f}',
            f'voice_speech_to_audio_ms{{quantile="0.95"}} {stats.speech_to_audio_p95_ms:.2f}',
            f'voice_speech_to_audio_ms{{quantile="0.99"}} {stats.speech_to_audio_p99_ms:.2f}',
            f"voice_speech_to_audio_ms_count {stats.speech_to_audio_count}",
            "",
            "# HELP voice_tool_call_duration_ms Duration of tool call execution",
            "# TYPE voice_tool_call_duration_ms summary",
            f'voice_tool_call_duration_ms{{quantile="0.5"}} {stats.tool_call_p50_ms:.2f}',
            f'voice_tool_call_duration_ms{{quantile="0.95"}} {stats.tool_call_p95_ms:.2f}',
            f'voice_tool_call_duration_ms{{quantile="0.99"}} {stats.tool_call_p99_ms:.2f}',
            f"voice_tool_call_duration_ms_count {stats.tool_call_count}",
            "",
            "# HELP voice_session_duration_ms Total session/call duration",
            "# TYPE voice_session_duration_ms summary",
            f'voice_session_duration_ms{{quantile="0.5"}} {stats.session_p50_ms:.2f}',
            f'voice_session_duration_ms{{quantile="0.95"}} {stats.session_p95_ms:.2f}',
            f'voice_session_duration_ms{{quantile="0.99"}} {stats.session_p99_ms:.2f}',
            f"voice_session_duration_ms_count {stats.session_count}",
        ]
        
        return "\n".join(lines) + "\n"
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for monitoring systems.
        
        Returns:
            Health status with key indicators
        """
        now = datetime.now(timezone.utc)
        metrics = self.get_metrics(
            start_time=now - timedelta(hours=1),
            end_time=now
        )
        
        # Define health thresholds
        is_healthy = True
        warnings = []
        
        # Check success rate
        if metrics.total_calls > 0 and metrics.success_rate < 80:
            warnings.append(f"Low success rate: {metrics.success_rate:.1f}%")
            is_healthy = False
        
        # Check for zombie calls
        if metrics.active_calls > 10:
            warnings.append(f"High active calls: {metrics.active_calls}")
        
        # Check for recent failures
        recent_failures = self.get_recent_failures(5)
        if len(recent_failures) > 3:
            warnings.append(f"Multiple recent failures: {len(recent_failures)} in last 10")
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": now.isoformat() + "Z",
            "indicators": {
                "calls_last_hour": metrics.total_calls,
                "success_rate": round(metrics.success_rate, 1),
                "active_calls": metrics.active_calls,
                "avg_duration": round(metrics.avg_duration, 1),
            },
            "warnings": warnings,
        }


# Global instance
metrics_manager = CallMetricsManager()


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Call Metrics CLI")
    parser.add_argument("command", choices=[
        "dashboard", "metrics", "prometheus", "export-csv", "export-json",
        "failures", "health", "hourly", "daily", "latency", "latency-events"
    ])
    parser.add_argument("--days", type=int, default=30, help="Days for export")
    parser.add_argument("--hours", type=int, default=24, help="Hours for timeseries")
    parser.add_argument("--call-id", type=str, help="Filter by call ID")
    parser.add_argument("--event-type", type=str, help="Filter by event type")
    parser.add_argument("--limit", type=int, default=100, help="Limit results")
    
    args = parser.parse_args()
    
    if args.command == "dashboard":
        print(json.dumps(metrics_manager.get_dashboard_data(), indent=2))
    elif args.command == "metrics":
        metrics = metrics_manager.get_metrics()
        print(json.dumps(asdict(metrics), indent=2, default=str))
    elif args.command == "prometheus":
        print(metrics_manager.get_prometheus_metrics())
    elif args.command == "export-csv":
        print(metrics_manager.export_csv(days=args.days))
    elif args.command == "export-json":
        print(metrics_manager.export_json(days=args.days))
    elif args.command == "failures":
        print(json.dumps(metrics_manager.get_recent_failures(), indent=2))
    elif args.command == "health":
        print(json.dumps(metrics_manager.health_check(), indent=2))
    elif args.command == "hourly":
        data = [asdict(b) for b in metrics_manager.get_hourly_timeseries(args.hours)]
        print(json.dumps(data, indent=2))
    elif args.command == "daily":
        data = [asdict(b) for b in metrics_manager.get_daily_timeseries(args.days)]
        print(json.dumps(data, indent=2))
    elif args.command == "latency":
        stats = metrics_manager.get_latency_stats()
        print(json.dumps(asdict(stats), indent=2, default=str))
    elif args.command == "latency-events":
        events = metrics_manager.get_latency_events(
            call_id=args.call_id,
            event_type=args.event_type,
            limit=args.limit
        )
        print(json.dumps([asdict(e) for e in events], indent=2, default=str))
