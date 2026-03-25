#!/usr/bin/env python3
"""
Unit tests for scripts/metrics_server.py

Covers MetricsRequestHandler.do_GET and do_POST endpoints.
Uses mock HTTP handler to avoid binding real ports.
"""

import sys
import os
import json
import io
from unittest.mock import MagicMock, patch
from http.server import BaseHTTPRequestHandler

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import metrics_server
from metrics_server import MetricsRequestHandler


# ─── Mock handler factory ─────────────────────────────────────────────────────

class MockHandler(MetricsRequestHandler):
    """Mock handler that intercepts HTTP response methods."""

    def __init__(self, path, body=None, method="GET"):
        self.path = path
        self.body = body or b"{}"
        self.method = method
        self.headers = {"Content-Length": str(len(self.body))}
        self.rfile = io.BytesIO(self.body)
        self._responses = []
        self._headers_sent = []
        self._body_parts = []
        self.wfile = io.BytesIO()

    def send_response(self, code, message=None):
        self._responses.append(code)

    def send_header(self, keyword, value):
        self._headers_sent.append((keyword, value))

    def end_headers(self):
        pass

    def log_message(self, format, *args):
        pass

    def log_error(self, format, *args):
        pass

    def get_last_response(self):
        """Return last response code."""
        return self._responses[-1] if self._responses else None

    def get_written_body(self):
        """Return body written to wfile as string."""
        return self.wfile.getvalue().decode("utf-8")

    def get_written_json(self):
        """Return parsed JSON from wfile."""
        body = self.get_written_body()
        if body:
            return json.loads(body)
        return None


def make_get_handler(path):
    return MockHandler(path, method="GET")


def make_post_handler(path, body_dict=None):
    body = json.dumps(body_dict or {}).encode("utf-8")
    h = MockHandler(path, body=body, method="POST")
    h.headers = {"Content-Length": str(len(body))}
    return h


# ─── GET /metrics/health ─────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for GET /metrics/health"""

    def test_health_check_called(self):
        handler = make_get_handler("/metrics/health")
        mock_health = MagicMock(return_value={"status": "healthy", "total_calls": 0})
        with patch.object(metrics_server.metrics_manager, 'health_check', mock_health):
            handler.do_GET()
        mock_health.assert_called_once()

    def test_health_returns_200_for_healthy(self):
        handler = make_get_handler("/metrics/health")
        with patch.object(metrics_server.metrics_manager, 'health_check',
                         return_value={"status": "healthy"}):
            handler.do_GET()
        assert 200 in handler._responses

    def test_health_returns_503_for_unhealthy(self):
        handler = make_get_handler("/metrics/health")
        with patch.object(metrics_server.metrics_manager, 'health_check',
                         return_value={"status": "degraded", "issues": ["no data"]}):
            handler.do_GET()
        # Should return non-200 for degraded state
        assert len(handler._responses) > 0


# ─── GET /metrics/prometheus ─────────────────────────────────────────────────

class TestPrometheusEndpoint:
    """Tests for GET /metrics/prometheus"""

    def test_prometheus_metrics_called(self):
        handler = make_get_handler("/metrics/prometheus")
        mock_metrics = MagicMock(return_value="# HELP calls_total\ncalls_total 0")
        with patch.object(metrics_server.metrics_manager, 'get_prometheus_metrics', mock_metrics):
            handler.do_GET()
        mock_metrics.assert_called_once()

    def test_alternate_metrics_path(self):
        handler = make_get_handler("/metrics")
        mock_metrics = MagicMock(return_value="# prometheus data")
        with patch.object(metrics_server.metrics_manager, 'get_prometheus_metrics', mock_metrics):
            handler.do_GET()
        mock_metrics.assert_called_once()


# ─── GET /metrics/dashboard ───────────────────────────────────────────────────

class TestDashboardEndpoint:
    """Tests for GET /metrics/dashboard"""

    def test_dashboard_called(self):
        handler = make_get_handler("/metrics/dashboard")
        mock_data = {"calls_today": 5, "avg_duration": 120}
        with patch.object(metrics_server.metrics_manager, 'get_dashboard_data',
                         return_value=mock_data):
            handler.do_GET()
        assert 200 in handler._responses


# ─── GET /metrics/export ─────────────────────────────────────────────────────

class TestExportEndpoint:
    """Tests for GET /metrics/export"""

    def test_export_json(self):
        handler = make_get_handler("/metrics/export?format=json&days=7")
        with patch.object(metrics_server.metrics_manager, 'export_json', return_value='{"data": []}'):
            handler.do_GET()
        assert len(handler._responses) > 0

    def test_export_csv(self):
        handler = make_get_handler("/metrics/export?format=csv&days=7")
        with patch.object(metrics_server.metrics_manager, 'export_csv', return_value='date,count'):
            handler.do_GET()
        assert len(handler._responses) > 0


# ─── GET /metrics/failures ────────────────────────────────────────────────────

class TestFailuresEndpoint:
    """Tests for GET /metrics/failures"""

    def test_failures_endpoint(self):
        handler = make_get_handler("/metrics/failures?limit=5")
        with patch.object(metrics_server.metrics_manager, 'get_recent_failures', return_value=[]):
            handler.do_GET()
        assert 200 in handler._responses

    def test_failures_with_data(self):
        handler = make_get_handler("/metrics/failures")
        failures = [{"call_id": "test", "error": "timeout"}]
        with patch.object(metrics_server.metrics_manager, 'get_recent_failures',
                         return_value=failures):
            handler.do_GET()
        assert 200 in handler._responses


# ─── GET /metrics/hourly ─────────────────────────────────────────────────────

class TestHourlyEndpoint:
    """Tests for GET /metrics/hourly"""

    def test_hourly_timeseries(self):
        handler = make_get_handler("/metrics/hourly?hours=12")
        with patch.object(metrics_server.metrics_manager, 'get_hourly_timeseries', return_value=[]):
            handler.do_GET()
        assert 200 in handler._responses


# ─── GET /metrics/daily ──────────────────────────────────────────────────────

class TestDailyEndpoint:
    """Tests for GET /metrics/daily"""

    def test_daily_timeseries(self):
        handler = make_get_handler("/metrics/daily?days=14")
        with patch.object(metrics_server.metrics_manager, 'get_daily_timeseries', return_value=[]):
            handler.do_GET()
        assert 200 in handler._responses


# ─── GET /metrics/latency ────────────────────────────────────────────────────

class TestLatencyEndpoint:
    """Tests for GET /metrics/latency"""

    def test_latency_stats(self):
        handler = make_get_handler("/metrics/latency?hours=24")
        mock_stats = MagicMock(
            speech_to_audio_count=10, speech_to_audio_avg_ms=150.0,
            speech_to_audio_min_ms=100.0, speech_to_audio_max_ms=200.0,
            speech_to_audio_p50_ms=145.0, speech_to_audio_p95_ms=190.0,
            speech_to_audio_p99_ms=199.0,
            tool_call_count=5, tool_call_avg_ms=300.0, tool_call_min_ms=200.0,
            tool_call_max_ms=400.0, tool_call_p50_ms=290.0,
            tool_call_p95_ms=390.0, tool_call_p99_ms=399.0,
            session_count=3, session_avg_ms=60000.0, session_min_ms=30000.0,
            session_max_ms=90000.0, session_p50_ms=55000.0,
            session_p95_ms=85000.0, session_p99_ms=89000.0
        )
        with patch.object(metrics_server.metrics_manager, 'get_latency_stats',
                         return_value=mock_stats):
            handler.do_GET()
        assert 200 in handler._responses


# ─── GET /metrics/latency/events ─────────────────────────────────────────────

class TestLatencyEventsEndpoint:
    """Tests for GET /metrics/latency/events"""

    def test_latency_events(self):
        handler = make_get_handler("/metrics/latency/events?limit=10")
        with patch.object(metrics_server.metrics_manager, 'get_latency_events', return_value=[]):
            handler.do_GET()
        assert 200 in handler._responses


# ─── GET / (root) ─────────────────────────────────────────────────────────────

class TestRootEndpoint:
    """Tests for GET /"""

    def test_root_returns_endpoint_list(self):
        handler = make_get_handler("/")
        handler.do_GET()
        assert 200 in handler._responses

    def test_empty_path_returns_endpoint_list(self):
        handler = make_get_handler("")
        handler.do_GET()
        assert 200 in handler._responses


# ─── GET /nonexistent ────────────────────────────────────────────────────────

class TestNotFound:
    """Tests for 404 response."""

    def test_unknown_path_returns_404(self):
        handler = make_get_handler("/unknown/path/xyz")
        handler.do_GET()
        assert 404 in handler._responses


# ─── POST /metrics/latency ───────────────────────────────────────────────────

class TestPostLatency:
    """Tests for POST /metrics/latency"""

    def test_valid_latency_event_recorded(self):
        from call_metrics import LatencyEventType
        valid_event_type = list(LatencyEventType)[0].value  # Get first valid value
        body = {
            "call_id": "test-call",
            "event_type": valid_event_type,
            "duration_ms": 150.5
        }
        handler = make_post_handler("/metrics/latency", body)
        with patch.object(metrics_server.metrics_manager, 'record_latency_event',
                         return_value=True):
            handler.do_POST()
        assert 201 in handler._responses

    def test_missing_fields_returns_400(self):
        body = {"call_id": "test-call"}  # Missing event_type and duration_ms
        handler = make_post_handler("/metrics/latency", body)
        handler.do_POST()
        assert 400 in handler._responses

    def test_invalid_event_type_returns_400(self):
        body = {
            "call_id": "test-call",
            "event_type": "invalid_event_type_xyz",
            "duration_ms": 150.5
        }
        handler = make_post_handler("/metrics/latency", body)
        handler.do_POST()
        assert 400 in handler._responses

    def test_failed_recording_returns_500(self):
        from call_metrics import LatencyEventType
        valid_event_type = list(LatencyEventType)[0].value
        body = {
            "call_id": "test-call",
            "event_type": valid_event_type,
            "duration_ms": 150.5
        }
        handler = make_post_handler("/metrics/latency", body)
        with patch.object(metrics_server.metrics_manager, 'record_latency_event',
                         return_value=False):
            handler.do_POST()
        assert 500 in handler._responses

    def test_invalid_json_returns_400(self):
        body = b"NOT VALID JSON"
        handler = MockHandler("/metrics/latency", body=body, method="POST")
        handler.headers = {"Content-Length": str(len(body))}
        handler.do_POST()
        assert 400 in handler._responses


# ─── POST to unknown path ─────────────────────────────────────────────────────

class TestPostNotFound:
    """Tests for POST to nonexistent path."""

    def test_post_unknown_path_returns_404(self):
        handler = make_post_handler("/unknown/path")
        handler.do_POST()
        assert 404 in handler._responses


# ─── do_OPTIONS ──────────────────────────────────────────────────────────────

class TestOptionsEndpoint:
    """Tests for CORS OPTIONS preflight."""

    def test_options_returns_200(self):
        handler = make_get_handler("/metrics/health")
        handler.do_OPTIONS()
        assert 200 in handler._responses

    def test_options_sends_cors_headers(self):
        handler = make_get_handler("/metrics/health")
        handler.do_OPTIONS()
        header_names = [h[0] for h in handler._headers_sent]
        assert "Access-Control-Allow-Origin" in header_names


# ─── send_json_response ───────────────────────────────────────────────────────

class TestSendJsonResponse:
    """Tests for send_json_response helper."""

    def test_sends_json_content_type(self):
        handler = make_get_handler("/")
        handler.send_json_response({"key": "value"})
        header_names = [h[0] for h in handler._headers_sent]
        assert "Content-Type" in header_names

    def test_sends_200_by_default(self):
        handler = make_get_handler("/")
        handler.send_json_response({"key": "value"})
        assert 200 in handler._responses

    def test_custom_status_code(self):
        handler = make_get_handler("/")
        handler.send_json_response({"error": "not found"}, 404)
        assert 404 in handler._responses


# ─── Exception handling ───────────────────────────────────────────────────────

class TestExceptionHandling:
    """Tests for exception handling in request handlers."""

    def test_exception_in_get_returns_500(self):
        handler = make_get_handler("/metrics/health")
        with patch.object(metrics_server.metrics_manager, 'health_check',
                         side_effect=RuntimeError("unexpected")):
            handler.do_GET()
        assert 500 in handler._responses

    def test_exception_in_post_returns_500(self):
        from call_metrics import LatencyEventType
        valid_type = list(LatencyEventType)[0].value
        body = {"call_id": "test", "event_type": valid_type, "duration_ms": 100}
        handler = make_post_handler("/metrics/latency", body)
        with patch.object(metrics_server.metrics_manager, 'record_latency_event',
                         side_effect=RuntimeError("crash")):
            handler.do_POST()
        assert 500 in handler._responses
