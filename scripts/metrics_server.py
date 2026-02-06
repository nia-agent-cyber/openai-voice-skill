#!/usr/bin/env python3
"""
Metrics HTTP Server

Exposes call_metrics.py functionality via HTTP endpoints.
Runs alongside webhook-server.py on a separate port.

Endpoints:
- GET /metrics/prometheus - Prometheus-format metrics
- GET /metrics/dashboard - Dashboard JSON data
- GET /metrics/export - CSV/JSON export
- GET /metrics/health - Health check
- GET /metrics/failures - Recent failures
- GET /metrics/hourly - Hourly timeseries
- GET /metrics/daily - Daily timeseries

Usage:
    python metrics_server.py [--port 8083]
"""

import argparse
import json
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dataclasses import asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metrics-server")

# Import metrics manager (handle both direct run and module import)
try:
    from call_metrics import metrics_manager
except ImportError:
    from scripts.call_metrics import metrics_manager

class MetricsRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for metrics endpoints."""
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(f"{self.address_string()} - {format % args}")
    
    def send_json_response(self, data, status_code=200):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))
    
    def send_text_response(self, data, content_type="text/plain", status_code=200):
        """Send plain text response."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data.encode("utf-8"))
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        try:
            # Prometheus metrics
            if path == "/metrics/prometheus" or path == "/metrics":
                metrics = metrics_manager.get_prometheus_metrics()
                self.send_text_response(metrics, "text/plain; charset=utf-8")
                return
            
            # Dashboard data
            if path == "/metrics/dashboard":
                dashboard = metrics_manager.get_dashboard_data()
                self.send_json_response(dashboard)
                return
            
            # Export data
            if path == "/metrics/export":
                format_type = query.get("format", ["json"])[0]
                days = int(query.get("days", [30])[0])
                
                if format_type == "csv":
                    data = metrics_manager.export_csv(days=days)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", 
                                   f'attachment; filename="calls-export.csv"')
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data.encode("utf-8"))
                else:
                    data = metrics_manager.export_json(days=days)
                    self.send_text_response(data, "application/json")
                return
            
            # Health check
            if path == "/metrics/health":
                health = metrics_manager.health_check()
                status_code = 200 if health["status"] == "healthy" else 503
                self.send_json_response(health, status_code)
                return
            
            # Recent failures
            if path == "/metrics/failures":
                limit = int(query.get("limit", [10])[0])
                failures = metrics_manager.get_recent_failures(limit=limit)
                self.send_json_response({"failures": failures, "count": len(failures)})
                return
            
            # Hourly timeseries
            if path == "/metrics/hourly":
                hours = int(query.get("hours", [24])[0])
                timeseries = metrics_manager.get_hourly_timeseries(hours=hours)
                data = [asdict(b) for b in timeseries]
                self.send_json_response({"timeseries": data, "hours": hours})
                return
            
            # Daily timeseries
            if path == "/metrics/daily":
                days = int(query.get("days", [30])[0])
                timeseries = metrics_manager.get_daily_timeseries(days=days)
                data = [asdict(b) for b in timeseries]
                self.send_json_response({"timeseries": data, "days": days})
                return
            
            # Root - show available endpoints
            if path == "/" or path == "":
                endpoints = {
                    "name": "Voice Call Metrics Server",
                    "version": "1.0.0",
                    "endpoints": {
                        "/metrics/prometheus": "Prometheus-format metrics",
                        "/metrics/dashboard": "Dashboard JSON data",
                        "/metrics/export?format=json&days=30": "Export data",
                        "/metrics/health": "Health check",
                        "/metrics/failures?limit=10": "Recent failures",
                        "/metrics/hourly?hours=24": "Hourly timeseries",
                        "/metrics/daily?days=30": "Daily timeseries",
                    }
                }
                self.send_json_response(endpoints)
                return
            
            # 404
            self.send_json_response({"error": "Not found"}, 404)
            
        except Exception as e:
            logger.exception(f"Error handling request: {e}")
            self.send_json_response({"error": str(e)}, 500)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port: int = 8083):
    """Run the metrics HTTP server."""
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, MetricsRequestHandler)
    
    logger.info(f"Starting metrics server on port {port}")
    logger.info("Endpoints:")
    logger.info(f"  GET http://localhost:{port}/metrics/prometheus")
    logger.info(f"  GET http://localhost:{port}/metrics/dashboard")
    logger.info(f"  GET http://localhost:{port}/metrics/export")
    logger.info(f"  GET http://localhost:{port}/metrics/health")
    logger.info(f"  GET http://localhost:{port}/metrics/failures")
    logger.info(f"  GET http://localhost:{port}/metrics/hourly")
    logger.info(f"  GET http://localhost:{port}/metrics/daily")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down metrics server")
        httpd.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Call Metrics Server")
    parser.add_argument("--port", type=int, default=8083, 
                       help="Port to listen on (default: 8083)")
    
    args = parser.parse_args()
    run_server(port=args.port)
