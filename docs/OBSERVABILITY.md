# Call Observability Guide

Production-ready observability for voice calls. Enables debugging, monitoring, and analytics.

## Quick Start

### Start Metrics Server

```bash
cd /path/to/openai-voice-skill/scripts
python metrics_server.py --port 8083
```

### Access Metrics

```bash
# Dashboard data (JSON)
curl http://localhost:8083/metrics/dashboard

# Prometheus metrics
curl http://localhost:8083/metrics/prometheus

# Health check
curl http://localhost:8083/metrics/health

# Recent failures
curl http://localhost:8083/metrics/failures
```

### Via Session Bridge

If running via the session bridge (port 8082):

```bash
curl http://localhost:8082/metrics/dashboard
curl http://localhost:8082/metrics/health
```

---

## Architecture

```
┌─────────────────────┐      ┌──────────────────────┐
│  webhook-server.py  │──────│   call_recording.py  │
│  (voice handling)   │      │   (call database)    │
└─────────────────────┘      └──────────┬───────────┘
                                        │
                             ┌──────────▼───────────┐
                             │   call_metrics.py    │
                             │   (aggregation)      │
                             └──────────┬───────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
    ┌─────────▼─────────┐     ┌─────────▼─────────┐     ┌─────────▼─────────┐
    │  metrics_server   │     │  session-bridge   │     │  CLI (direct)     │
    │  (port 8083)      │     │  (port 8082)      │     │                   │
    └───────────────────┘     └───────────────────┘     └───────────────────┘
```

---

## Endpoints

### `GET /metrics/prometheus`

Prometheus-compatible metrics for monitoring systems.

```
# HELP voice_calls_total Total number of calls
# TYPE voice_calls_total counter
voice_calls_total 142

# HELP voice_calls_success_rate Call success rate percentage
# TYPE voice_calls_success_rate gauge
voice_calls_success_rate 94.37

# HELP voice_calls_active Currently active calls
# TYPE voice_calls_active gauge
voice_calls_active 2

# HELP voice_call_duration_seconds Call duration statistics
# TYPE voice_call_duration_seconds summary
voice_call_duration_seconds{quantile="0.5"} 45.30
voice_call_duration_seconds{quantile="0.95"} 120.50
voice_call_duration_seconds{quantile="0.99"} 180.20
```

### `GET /metrics/dashboard`

Comprehensive dashboard data for visualization.

```json
{
  "generated_at": "2026-02-06T10:30:00.000Z",
  "period": {
    "start": "2026-02-05T10:30:00.000Z",
    "end": "2026-02-06T10:30:00.000Z"
  },
  "summary": {
    "total_calls": 142,
    "total_calls_delta": 15.2,
    "success_rate": 94.4,
    "success_rate_delta": 2.1,
    "avg_duration": 67.3,
    "avg_duration_delta": -5.2,
    "active_now": 2
  },
  "breakdown": {
    "by_status": {
      "completed": 134,
      "failed": 5,
      "timeout": 2,
      "cancelled": 1,
      "active": 0
    },
    "by_type": {
      "inbound": 45,
      "outbound": 97
    },
    "failure_reasons": {
      "unknown": 5
    }
  },
  "duration": {
    "avg": 67.3,
    "min": 12.1,
    "max": 245.8,
    "p50": 55.2,
    "p95": 145.3,
    "p99": 210.5,
    "total_seconds": 9018
  },
  "transcript": {
    "calls_with_transcript": 138,
    "transcript_rate": 97.2
  },
  "timeseries": {
    "hourly": [...]
  }
}
```

### `GET /metrics/health`

Health check for monitoring systems.

```json
{
  "status": "healthy",
  "timestamp": "2026-02-06T10:30:00.000Z",
  "indicators": {
    "calls_last_hour": 12,
    "success_rate": 100.0,
    "active_calls": 1,
    "avg_duration": 45.2
  },
  "warnings": []
}
```

**Status codes:**
- `200` - Healthy
- `503` - Degraded (check `warnings` array)

### `GET /metrics/failures?limit=10`

Recent failed calls for debugging.

```json
{
  "failures": [
    {
      "call_id": "abc123",
      "call_type": "outbound",
      "caller_number": "+14402915517",
      "callee_number": "+1234567890",
      "started_at": "2026-02-06T10:15:00",
      "ended_at": "2026-02-06T10:15:30",
      "duration_seconds": 30.5,
      "status": "failed",
      "failure_reason": "unknown"
    }
  ],
  "count": 1
}
```

### `GET /metrics/export?format=json&days=30`

Export call data for analytics.

**Parameters:**
- `format`: `json` (default) or `csv`
- `days`: Number of days to export (default: 30)

### `GET /metrics/hourly?hours=24`

Hourly aggregated metrics for time-series charts.

```json
{
  "timeseries": [
    {
      "hour": "2026-02-06T09:00:00Z",
      "total": 5,
      "completed": 5,
      "failed": 0,
      "avg_duration": 42.3
    }
  ],
  "hours": 24
}
```

### `GET /metrics/daily?days=30`

Daily aggregated metrics for trend analysis.

```json
{
  "timeseries": [
    {
      "date": "2026-02-05",
      "total": 45,
      "completed": 43,
      "failed": 2,
      "avg_duration": 58.7,
      "success_rate": 95.6
    }
  ],
  "days": 30
}
```

---

## CLI Usage

Direct access to metrics without HTTP server:

```bash
cd /path/to/openai-voice-skill/scripts

# Dashboard data
python call_metrics.py dashboard

# Prometheus format
python call_metrics.py prometheus

# Health check
python call_metrics.py health

# Recent failures
python call_metrics.py failures

# Export to CSV
python call_metrics.py export-csv --days 30 > calls.csv

# Export to JSON
python call_metrics.py export-json --days 30 > calls.json

# Hourly timeseries
python call_metrics.py hourly --hours 48

# Daily timeseries
python call_metrics.py daily --days 7
```

---

## Monitoring Integration

### Prometheus

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'voice-calls'
    static_configs:
      - targets: ['localhost:8083']
    metrics_path: '/metrics/prometheus'
    scrape_interval: 30s
```

### Grafana

Use the dashboard endpoint to populate Grafana panels:

```
# Data source query (JSON API)
GET http://localhost:8083/metrics/dashboard
```

### AlertManager

Example alert rules:

```yaml
groups:
  - name: voice-calls
    rules:
      - alert: VoiceCallSuccessRateLow
        expr: voice_calls_success_rate < 80
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Voice call success rate below 80%
      
      - alert: ZombieCallsDetected
        expr: voice_calls_active > 10
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: High number of active calls (possible zombies)
```

---

## Debugging Guide

### Identifying Issues

1. **Check health endpoint first:**
   ```bash
   curl http://localhost:8083/metrics/health
   ```

2. **If degraded, check recent failures:**
   ```bash
   curl http://localhost:8083/metrics/failures?limit=5
   ```

3. **Look for patterns in hourly data:**
   ```bash
   curl http://localhost:8083/metrics/hourly?hours=6
   ```

### Common Issues

| Issue | Indicator | Resolution |
|-------|-----------|------------|
| High failure rate | `success_rate < 80%` | Check `/metrics/failures` for patterns |
| Zombie calls | `active_calls > 10` | Run cleanup: `POST /cleanup-stale-calls` |
| Missing transcripts | `transcript_rate < 90%` | Check `call_recording.py` logs |
| Long durations | `p95 > 300s` | Review call types in `/metrics/export` |

### Structured Logging

Enable structured JSON logging for production debugging:

```python
from call_metrics import metrics_manager

# Emit call event
metrics_manager.log_call_event(
    "started",
    call_id="abc123",
    call_type="outbound",
    phone_number="+1234567890"
)

# Output (JSON):
# {"timestamp": "2026-02-06T10:30:00.000Z", "level": "INFO", 
#  "logger": "voice.metrics", "message": "call_started",
#  "call_id": "abc123", "call_type": "outbound", "phone_number": "+1234567890"}
```

---

## Performance Considerations

- **Metrics queries are read-only** - no impact on call processing
- **SQLite database** - suitable for moderate call volume (<1000 calls/day)
- **Timeseries queries** - aggregated in memory, cache for high-traffic dashboards
- **Export operations** - can be slow for large date ranges; use pagination

---

## Files

| File | Purpose |
|------|---------|
| `scripts/call_metrics.py` | Core metrics aggregation |
| `scripts/metrics_server.py` | HTTP server for metrics |
| `scripts/call_recording.py` | Call database and lifecycle |
| `channel-plugin/src/adapters/session-bridge.ts` | Metrics proxy via bridge |
| `docs/OBSERVABILITY.md` | This documentation |
