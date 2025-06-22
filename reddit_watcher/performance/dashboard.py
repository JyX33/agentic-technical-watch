# ABOUTME: Performance monitoring dashboard for real-time system metrics and alerting
# ABOUTME: Provides web-based dashboard, REST API endpoints, and automated performance alerts

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .ml_model_cache import get_model_cache
from .resource_monitor import get_resource_monitor

logger = logging.getLogger(__name__)


class PerformanceDashboard:
    """
    Real-time performance monitoring dashboard.

    Features:
    - REST API for performance metrics
    - WebSocket for real-time updates
    - Web-based dashboard interface
    - Automated alerting system
    - Historical data visualization
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.resource_monitor = get_resource_monitor()
        self.model_cache = get_model_cache()
        self.websocket_clients = set()

        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not available - dashboard will not be accessible")
            self.app = None
            return

        # Create FastAPI app
        self.app = FastAPI(
            title="Reddit Technical Watcher - Performance Dashboard",
            description="Real-time performance monitoring and metrics",
            version="1.0.0",
        )

        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""
        if not self.app:
            return

        @self.app.get("/")
        async def dashboard():
            """Serve the main dashboard page."""
            return HTMLResponse(self._get_dashboard_html())

        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}

        @self.app.get("/api/metrics/current")
        async def get_current_metrics():
            """Get current system metrics."""
            current = self.resource_monitor.get_current_metrics()
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "metrics": current.__dict__ if current else None,
            }

        @self.app.get("/api/metrics/performance")
        async def get_performance_metrics():
            """Get performance summary."""
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "performance": self.resource_monitor.get_performance_summary(),
                "agents": self.resource_monitor.get_agent_performance_summary(),
            }

        @self.app.get("/api/metrics/resources")
        async def get_resource_metrics():
            """Get resource usage averages."""
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "averages": self.resource_monitor.get_resource_averages(last_n=100),
                "cache_info": self.model_cache.get_cache_info(),
                "model_metrics": self.model_cache.get_performance_metrics(),
            }

        @self.app.websocket("/ws/metrics")
        async def websocket_metrics(websocket: WebSocket):
            """WebSocket endpoint for real-time metrics."""
            await websocket.accept()
            self.websocket_clients.add(websocket)

            try:
                while True:
                    # Send current metrics every 5 seconds
                    current = self.resource_monitor.get_current_metrics()
                    if current:
                        data = {
                            "type": "metrics_update",
                            "timestamp": datetime.now(UTC).isoformat(),
                            "data": current.__dict__,
                        }
                        await websocket.send_text(json.dumps(data))

                    await asyncio.sleep(5)

            except WebSocketDisconnect:
                self.websocket_clients.remove(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if websocket in self.websocket_clients:
                    self.websocket_clients.remove(websocket)

    def _get_dashboard_html(self) -> str:
        """Generate the dashboard HTML."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Reddit Technical Watcher - Performance Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .metric-title {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label {
            font-size: 14px;
            color: #666;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-healthy { background-color: #10b981; }
        .status-warning { background-color: #f59e0b; }
        .status-error { background-color: #ef4444; }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }
        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
        }
        .progress-fill.low { background-color: #10b981; }
        .progress-fill.medium { background-color: #f59e0b; }
        .progress-fill.high { background-color: #ef4444; }
        .log-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-height: 300px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 5px 0;
            border-bottom: 1px solid #e5e7eb;
            font-size: 14px;
        }
        .timestamp {
            color: #666;
            font-family: monospace;
        }
        .connection-status {
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .connected {
            background-color: #d1fae5;
            color: #065f46;
        }
        .disconnected {
            background-color: #fee2e2;
            color: #991b1b;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Reddit Technical Watcher</h1>
            <p>Performance Monitoring Dashboard</p>
        </div>

        <div id="connection-status" class="connection-status disconnected">
            <span class="status-indicator status-error"></span>
            Connecting to metrics stream...
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">CPU Usage</div>
                <div class="metric-value" id="cpu-value">--</div>
                <div class="metric-label">Percent</div>
                <div class="progress-bar">
                    <div class="progress-fill low" id="cpu-progress" style="width: 0%"></div>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Memory Usage</div>
                <div class="metric-value" id="memory-value">--</div>
                <div class="metric-label">Percent</div>
                <div class="progress-bar">
                    <div class="progress-fill low" id="memory-progress" style="width: 0%"></div>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Disk Usage</div>
                <div class="metric-value" id="disk-value">--</div>
                <div class="metric-label">Percent</div>
                <div class="progress-bar">
                    <div class="progress-fill low" id="disk-progress" style="width: 0%"></div>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Active Connections</div>
                <div class="metric-value" id="connections-value">--</div>
                <div class="metric-label">Database + HTTP</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Open Files</div>
                <div class="metric-value" id="files-value">--</div>
                <div class="metric-label">File Descriptors</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Process Count</div>
                <div class="metric-value" id="processes-value">--</div>
                <div class="metric-label">System Processes</div>
            </div>
        </div>

        <div class="metric-card">
            <div class="metric-title">📊 Performance Log</div>
            <div id="performance-log" class="log-container">
                <div class="log-entry">
                    <span class="timestamp">--:--:--</span> Waiting for metrics...
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let reconnectInterval = 5000;

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/metrics`;

            ws = new WebSocket(wsUrl);

            ws.onopen = function() {
                console.log('WebSocket connected');
                updateConnectionStatus(true);
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'metrics_update') {
                    updateMetrics(data.data);
                    logPerformanceEvent('Metrics updated', 'info');
                }
            };

            ws.onclose = function() {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                setTimeout(connectWebSocket, reconnectInterval);
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                updateConnectionStatus(false);
            };
        }

        function updateConnectionStatus(connected) {
            const statusElement = document.getElementById('connection-status');
            const indicator = statusElement.querySelector('.status-indicator');

            if (connected) {
                statusElement.className = 'connection-status connected';
                statusElement.innerHTML = '<span class="status-indicator status-healthy"></span>Connected to metrics stream';
            } else {
                statusElement.className = 'connection-status disconnected';
                statusElement.innerHTML = '<span class="status-indicator status-error"></span>Disconnected - Reconnecting...';
            }
        }

        function updateMetrics(metrics) {
            // Update CPU
            updateMetric('cpu', metrics.cpu_percent);

            // Update Memory
            updateMetric('memory', metrics.memory_percent);

            // Update Disk
            updateMetric('disk', metrics.disk_usage_percent);

            // Update simple metrics
            document.getElementById('connections-value').textContent = metrics.active_connections || '--';
            document.getElementById('files-value').textContent = metrics.open_files || '--';
            document.getElementById('processes-value').textContent = metrics.process_count || '--';
        }

        function updateMetric(type, value) {
            const valueElement = document.getElementById(`${type}-value`);
            const progressElement = document.getElementById(`${type}-progress`);

            if (value !== undefined && value !== null) {
                valueElement.textContent = `${value.toFixed(1)}%`;
                progressElement.style.width = `${Math.min(value, 100)}%`;

                // Update color based on value
                progressElement.className = 'progress-fill';
                if (value < 60) {
                    progressElement.classList.add('low');
                } else if (value < 80) {
                    progressElement.classList.add('medium');
                } else {
                    progressElement.classList.add('high');
                }
            } else {
                valueElement.textContent = '--';
                progressElement.style.width = '0%';
            }
        }

        function logPerformanceEvent(message, level = 'info') {
            const logContainer = document.getElementById('performance-log');
            const timestamp = new Date().toLocaleTimeString();

            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            logEntry.innerHTML = `<span class="timestamp">${timestamp}</span> ${message}`;

            logContainer.insertBefore(logEntry, logContainer.firstChild);

            // Keep only last 50 entries
            while (logContainer.children.length > 50) {
                logContainer.removeChild(logContainer.lastChild);
            }
        }

        // Start WebSocket connection
        connectWebSocket();

        // Load initial data
        fetch('/api/metrics/current')
            .then(response => response.json())
            .then(data => {
                if (data.metrics) {
                    updateMetrics(data.metrics);
                    logPerformanceEvent('Initial metrics loaded', 'success');
                }
            })
            .catch(error => {
                console.error('Failed to load initial metrics:', error);
                logPerformanceEvent('Failed to load initial metrics', 'error');
            });
    </script>
</body>
</html>
        """

    async def start_server(self):
        """Start the dashboard server."""
        if not FASTAPI_AVAILABLE:
            logger.error("FastAPI not available - cannot start dashboard server")
            return

        logger.info(f"Starting performance dashboard on http://{self.host}:{self.port}")

        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def broadcast_metrics(self, metrics: dict[str, Any]):
        """Broadcast metrics to all connected WebSocket clients."""
        if not self.websocket_clients:
            return

        message = json.dumps(
            {
                "type": "metrics_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": metrics,
            }
        )

        # Send to all clients, remove disconnected ones
        disconnected = set()
        for client in self.websocket_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.add(client)

        # Remove disconnected clients
        self.websocket_clients -= disconnected


# Global dashboard instance
_dashboard: PerformanceDashboard | None = None


def get_dashboard(host: str = "0.0.0.0", port: int = 8080) -> PerformanceDashboard:
    """Get the global dashboard instance."""
    global _dashboard
    if _dashboard is None:
        _dashboard = PerformanceDashboard(host, port)
    return _dashboard


async def start_dashboard_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the performance dashboard server."""
    dashboard = get_dashboard(host, port)
    await dashboard.start_server()


if __name__ == "__main__":
    import sys

    # Simple CLI for starting the dashboard
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    asyncio.run(start_dashboard_server(host, port))
