# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Remote telemetry log handlers with async background batching.
"""

from __future__ import annotations
import json
import logging
import os
import queue
import threading
import time
from abc import abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from src.core.models.telemetry import TelemetryConfig
from src.modules.send_telemetry_data import TelemetryDataSender

_logger = logging.getLogger(__name__)

_DEFAULT_VARS_PATHS = (
    Path("vars.yaml"),
    Path("/app/vars.yaml"),
)


def _coalesce(*values: Optional[str]) -> Optional[str]:
    """
    Return first non-empty, non-``null`` string value.
    """
    for v in values:
        if v and str(v).strip() and str(v).strip().lower() != "null":
            return str(v).strip()
    return None


def load_telemetry_config(
    vars_path: Optional[Path] = None,
) -> TelemetryConfig:
    """
    Load telemetry config by merging vars.yaml with env overrides.

    :param vars_path: Explicit path to vars.yaml
    :returns: Frozen TelemetryConfig
    """
    yaml_data: dict[str, Any] = {}

    search: list[Path] = []
    if vars_path:
        search.append(vars_path)
    search.extend(_DEFAULT_VARS_PATHS)

    for candidate in search:
        if candidate.is_file():
            try:
                with open(candidate, "r", encoding="utf-8") as fh:
                    yaml_data = yaml.safe_load(fh) or {}
                _logger.info(
                    "Loaded telemetry config from %s",
                    candidate,
                )
                break
            except Exception as exc:
                _logger.warning(
                    "Failed to read %s: %s",
                    candidate,
                    exc,
                )

    def _get(
        yaml_key: str,
        env_key: Optional[str] = None,
    ) -> Optional[str]:
        env_key = env_key or yaml_key.upper()
        return _coalesce(
            os.environ.get(env_key),
            yaml_data.get(yaml_key),
        )

    return TelemetryConfig(
        telemetry_data_destination=_get(
            "telemetry_data_destination",
            "TELEMETRY_DATA_DESTINATION",
        ),
        laws_workspace_id=_get("laws_workspace_id", "LAWS_WORKSPACE_ID"),
        laws_shared_key=_get("laws_shared_key", "LAWS_SHARED_KEY"),
        laws_subscription_id=_get("laws_subscription_id", "LAWS_SUBSCRIPTION_ID"),
        laws_resource_group=_get("laws_resource_group", "LAWS_RESOURCE_GROUP"),
        laws_workspace_name=_get("laws_workspace_name", "LAWS_WORKSPACE_NAME"),
        adx_database_name=_get("adx_database_name", "ADX_DATABASE_NAME"),
        adx_cluster_fqdn=_get("adx_cluster_fqdn", "ADX_CLUSTER_FQDN"),
        adx_client_id=_get("adx_client_id", "ADX_CLIENT_ID"),
        telemetry_table_name=_get("telemetry_table_name", "TELEMETRY_TABLE_NAME"),
        service_log_table_name=_get("service_log_table_name", "SERVICE_LOG_TABLE_NAME"),
        user_assigned_identity_client_id=_get(
            "user_assigned_identity_client_id",
            "USER_ASSIGNED_IDENTITY_CLIENT_ID",
        ),
        batch_size=int(os.environ.get("TELEMETRY_BATCH_SIZE", "100")),
        flush_interval_seconds=float(os.environ.get("TELEMETRY_FLUSH_INTERVAL", "60.0")),
    )


_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(
    {
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
        "taskName",
    }
)


class _BaseRemoteLogHandler(logging.Handler):
    """
    Abstract base for remote telemetry log handlers.
    """

    def __init__(
        self,
        *,
        table_name: str,
        batch_size: int = 100,
        flush_interval: float = 60.0,
        enabled: bool = True,
    ) -> None:
        super().__init__()
        self.table_name = table_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._shutdown = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if enabled:
            self._start_background_thread()

    def _start_background_thread(self) -> None:
        """
        Start the background sender thread.
        """
        self._thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._thread.start()

    def _sender_loop(self) -> None:
        """
        Background loop that batches and sends logs.
        """
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
            except Exception as exc:
                _logger.debug("sender_loop error: %s", exc)

        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._send_batch(batch)

    def flush(self) -> None:
        """
        Flush remaining logs (blocks until complete).
        """
        start = time.time()
        while not self._queue.empty() and time.time() - start < 10.0:
            time.sleep(0.1)

    def close(self) -> None:
        """
        Shutdown the handler gracefully.
        """
        self._shutdown.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        super().close()

    @staticmethod
    def _format_record(
        record: logging.LogRecord,
    ) -> Dict[str, Any]:
        """
        Format a log record for remote ingestion.

        :param record: Log record to format
        :returns: Dictionary with standard + extra fields
        """
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or key.startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool, type(None))):
                entry[key] = value
            else:
                try:
                    entry[key] = str(value)
                except Exception:
                    pass
        return entry

    @abstractmethod
    def _send_batch(self, batch: List[Dict[str, Any]]) -> bool:
        """
        Send a batch of formatted log entries to the remote destination.

        :param batch: Non-empty list of log dicts
        :returns: True on success
        """
        raise NotImplementedError


class LogAnalyticsHandler(_BaseRemoteLogHandler):
    """
    Async handler that batches logs to Azure Log Analytics.
    """

    def __init__(
        self,
        workspace_id: Optional[str] = None,
        shared_key: Optional[str] = None,
        table_name: Optional[str] = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        config: Optional["TelemetryConfig"] = None,
    ) -> None:
        self._config = config
        if config is not None:
            self.workspace_id = workspace_id or config.laws_workspace_id or ""
            self.shared_key = shared_key or config.laws_shared_key or ""
            self._subscription_id = config.laws_subscription_id or ""
            self._resource_group = config.laws_resource_group or ""
            self._workspace_name = config.laws_workspace_name or ""
            self._user_mi_client_id = config.user_assigned_identity_client_id or ""
            _table = table_name or config.service_table()
            _batch = config.batch_size
            _flush = config.flush_interval_seconds
            _enabled = config.has_log_analytics
        else:
            self.workspace_id = workspace_id or os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "")
            self.shared_key = shared_key or os.environ.get("LOG_ANALYTICS_SHARED_KEY", "")
            self._subscription_id = ""
            self._resource_group = ""
            self._workspace_name = ""
            self._user_mi_client_id = ""
            _table = table_name or os.environ.get("LOG_ANALYTICS_TABLE", "SAPQALogs")
            _batch = int(os.environ.get("LOG_ANALYTICS_BATCH_SIZE", batch_size))
            _flush = float(os.environ.get("LOG_ANALYTICS_FLUSH_INTERVAL", flush_interval))
            _enabled = bool(self.workspace_id and self.shared_key)

        super().__init__(
            table_name=_table,
            batch_size=_batch,
            flush_interval=_flush,
            enabled=_enabled,
        )

    @property
    def _has_credentials(self) -> bool:
        """True when handler can send (direct key or Azure lookup)."""
        if self.workspace_id and self.shared_key:
            return True
        if self._config is not None:
            return self._config.has_log_analytics
        return False

    def emit(self, record: logging.LogRecord) -> None:
        """
        Enqueue a log record for async sending.
        """
        if not self._has_credentials:
            return
        try:
            self._queue.put_nowait(self._format_record(record))
        except queue.Full:
            pass

    def _send_batch(self, batch: List[Dict[str, Any]]) -> bool:
        """
        Send a batch to Log Analytics via TelemetryDataSender.

        When shared_key is absent but Azure lookup fields are
        present, TelemetryDataSender.validate_params() resolves
        the key via managed identity automatically.
        """
        if not batch or not self._has_credentials:
            return False
        try:
            params: Dict[str, Any] = {
                "test_group_json_data": {},
                "telemetry_data_destination": "azureloganalytics",
                "laws_workspace_id": self.workspace_id,
                "telemetry_table_name": self.table_name,
                "workspace_directory": os.environ.get("LOG_DIR", "data/logs"),
            }
            if self.shared_key:
                params["laws_shared_key"] = self.shared_key
            else:
                params["laws_subscription_id"] = self._subscription_id
                params["laws_resource_group"] = self._resource_group
                params["laws_workspace_name"] = self._workspace_name
                if self._user_mi_client_id:
                    params["user_assigned_identity_client_id"] = self._user_mi_client_id
            sender = TelemetryDataSender(module_params=params)
            if not sender.validate_params():
                _logger.warning(
                    "LA validate_params failed for %s",
                    self.table_name,
                )
                return False
            response = sender.send_telemetry_data_to_azureloganalytics(json.dumps(batch))
            _logger.info(
                "LA send_batch: %d records → %s (status %s)",
                len(batch),
                self.table_name,
                response.status_code,
            )
            return response.status_code in (200, 202)
        except Exception as exc:
            _logger.warning("LA send_batch error: %s", exc)
            return False


class ADXHandler(_BaseRemoteLogHandler):
    """
    Async handler that batches logs to Azure Data Explorer.
    """

    def __init__(
        self,
        config: "TelemetryConfig",
        table_name: Optional[str] = None,
        batch_size: Optional[int] = None,
        flush_interval: Optional[float] = None,
    ) -> None:
        self._config = config
        super().__init__(
            table_name=table_name or config.service_table(),
            batch_size=batch_size or config.batch_size,
            flush_interval=(
                flush_interval if flush_interval is not None else config.flush_interval_seconds
            ),
            enabled=config.has_adx,
        )

    def emit(self, record: logging.LogRecord) -> None:
        if not self._config.has_adx:
            return
        try:
            self._queue.put_nowait(self._format_record(record))
        except queue.Full:
            pass

    def _send_batch(self, batch: List[Dict[str, Any]]) -> bool:
        if not batch or not self._config.has_adx:
            return False
        try:
            sender = TelemetryDataSender(
                module_params={
                    "test_group_json_data": {},
                    "telemetry_data_destination": ("azuredataexplorer"),
                    "adx_database_name": (self._config.adx_database_name),
                    "adx_cluster_fqdn": (self._config.adx_cluster_fqdn),
                    "adx_client_id": self._config.adx_client_id,
                    "telemetry_table_name": self.table_name,
                    "workspace_directory": "data/logs",
                }
            )
            sender.send_telemetry_data_to_azuredataexplorer(json.dumps(batch))
            _logger.info(
                "ADX send_batch: %d records → %s",
                len(batch),
                self.table_name,
            )
            return True
        except Exception as exc:
            _logger.warning("ADX send_batch error: %s", exc)
            return False
