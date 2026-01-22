# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure Log Analytics log handler with async background batching.

Buffers logs in memory and sends to Log Analytics Data Collector API
in batches using a background thread. Uses the existing TelemetryDataSender
from send_telemetry_data module.
"""

import json
import logging
import os
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.modules.send_telemetry_data import TelemetryDataSender


class LogAnalyticsHandler(logging.Handler):
    """
    Async logging handler that batches and sends logs to Azure Log Analytics.

    Features:
    - Buffers logs in memory queue
    - Background thread sends batches to Log Analytics
    - Configurable batch size and flush interval
    - Graceful shutdown with final flush

    """

    def __init__(
        self,
        workspace_id: Optional[str] = None,
        shared_key: Optional[str] = None,
        table_name: Optional[str] = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        """Initialize the Log Analytics handler.

        :param workspace_id: Log Analytics workspace ID
        :param shared_key: Log Analytics shared key
        :param table_name: Log Analytics table name
        :param batch_size: Number of logs to batch before sending
        :param flush_interval: Seconds between flush attempts
        """
        super().__init__()

        self.workspace_id = workspace_id or os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "")
        self.shared_key = shared_key or os.environ.get("LOG_ANALYTICS_SHARED_KEY", "")
        self.table_name = table_name or os.environ.get("LOG_ANALYTICS_TABLE", "SAPQALogs")
        self.batch_size = int(os.environ.get("LOG_ANALYTICS_BATCH_SIZE", batch_size))
        self.flush_interval = float(os.environ.get("LOG_ANALYTICS_FLUSH_INTERVAL", flush_interval))

        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._shutdown = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if self.workspace_id and self.shared_key:
            self._start_background_thread()

    def _start_background_thread(self) -> None:
        """Start the background sender thread."""
        self._thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._thread.start()

    def _sender_loop(self) -> None:
        """Background loop that batches and sends logs."""
        batch: List[Dict[str, Any]] = []
        last_flush = time.time()

        while not self._shutdown.is_set():
            try:
                try:
                    batch.append(self._queue.get(timeout=0.5))
                except queue.Empty:
                    pass
                should_flush = len(batch) >= self.batch_size or (
                    batch and time.time() - last_flush >= self.flush_interval
                )

                if should_flush and batch:
                    self._send_batch(batch)
                    batch = []
                    last_flush = time.time()

            except Exception:
                pass
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]) -> bool:
        """Send a batch of logs to Log Analytics using TelemetryDataSender.

        :param batch: List of log entries to send
        :returns: True if successful, False otherwise
        """
        if not batch or not self.workspace_id or not self.shared_key:
            return False

        try:
            response = TelemetryDataSender(
                module_params={
                    "test_group_json_data": {},
                    "telemetry_data_destination": "azureloganalytics",
                    "laws_workspace_id": self.workspace_id,
                    "laws_shared_key": self.shared_key,
                    "telemetry_table_name": self.table_name,
                    "workspace_directory": os.environ.get("LOG_DIR", "data/logs"),
                }
            ).send_telemetry_data_to_azureloganalytics(json.dumps(batch))
            return response.status_code in (200, 202)

        except Exception:
            return False

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the queue.

        :param record: Log record to emit
        """
        if not self.workspace_id or not self.shared_key:
            return

        try:
            self._queue.put_nowait(self._format_record(record))
        except queue.Full:
            pass

    def _format_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Format a log record for Log Analytics.

        :param record: Log record to format
        :returns: Dictionary suitable for Log Analytics
        """
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "message",
                    "asctime",
                ):
                    if isinstance(value, (str, int, float, bool, type(None))):
                        entry[key] = value
                    else:
                        try:
                            entry[key] = str(value)
                        except Exception:
                            pass

        return entry

    def flush(self) -> None:
        """Flush remaining logs (blocks until complete)."""
        start = time.time()
        while not self._queue.empty() and time.time() - start < 10.0:
            time.sleep(0.1)

    def close(self) -> None:
        """Shutdown the handler gracefully."""
        self._shutdown.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        super().close()


def add_log_analytics_handler(
    logger: Optional[logging.Logger] = None,
    workspace_id: Optional[str] = None,
    shared_key: Optional[str] = None,
    table_name: Optional[str] = None,
) -> Optional[LogAnalyticsHandler]:
    """Add a Log Analytics handler to a logger.

    If workspace_id and shared_key are not provided, reads from environment.
    Returns None if credentials are not available.

    :param logger: Logger to add handler to (default: root logger)
    :param workspace_id: Log Analytics workspace ID
    :param shared_key: Log Analytics shared key
    :param table_name: Log Analytics table name
    :returns: The handler if added, None if credentials missing
    """
    ws_id = workspace_id or os.environ.get("LOG_ANALYTICS_WORKSPACE_ID")
    key = shared_key or os.environ.get("LOG_ANALYTICS_SHARED_KEY")

    if not ws_id or not key:
        return None

    handler = LogAnalyticsHandler(
        workspace_id=ws_id,
        shared_key=key,
        table_name=table_name,
    )

    target_logger = logger or logging.getLogger()
    target_logger.addHandler(handler)

    return handler
