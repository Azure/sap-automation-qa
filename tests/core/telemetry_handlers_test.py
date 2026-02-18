# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for LogAnalyticsHandler and ADXHandler."""

import logging
from typing import Any

import pytest
from pytest_mock import MockerFixture
from src.core.models.telemetry import TelemetryConfig
from src.core.observability.telemetry_handlers import (
    ADXHandler,
    LogAnalyticsHandler,
)

_MOCK_SENDER = "src.core.observability.telemetry_handlers.TelemetryDataSender"


def _make_record(
    msg: str = "hello",
    level: int = logging.INFO,
    name: str = "test",
    lineno: int = 0,
    **extras: object,
) -> logging.LogRecord:
    """Build a lightweight LogRecord with optional extras."""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=lineno,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extras.items():
        setattr(record, k, v)
    return record


def _adx_config(**overrides: Any) -> TelemetryConfig:
    """Build a minimal ADX-enabled TelemetryConfig."""
    defaults: dict[str, Any] = {
        "adx_database_name": "TestDB",
        "adx_cluster_fqdn": "https://cluster.kusto.windows.net",
        "adx_client_id": "client-123",
        "telemetry_table_name": "TestTable",
        "batch_size": 100,
        "flush_interval_seconds": 60.0,
    }
    defaults.update(overrides)
    return TelemetryConfig(**defaults)


class TestLogAnalyticsHandler:
    """Tests for the LogAnalyticsHandler class."""

    def test_init_without_credentials_no_thread(self) -> None:
        """
        Handler without credentials does not start background thread.
        """
        handler = LogAnalyticsHandler()
        assert handler._thread is None
        assert handler.workspace_id == ""
        assert handler.shared_key == ""
        handler.close()

    def test_init_with_credentials_starts_thread(self) -> None:
        """
        Handler with valid credentials starts the background sender thread.
        """
        handler = LogAnalyticsHandler(
            workspace_id="ws-123",
            shared_key="key-abc",
        )
        assert handler._thread is not None
        assert handler._thread.is_alive()
        handler.close()

    def test_init_reads_env_defaults(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Handler reads default values from environment variables.
        """
        monkeypatch.setenv("LOG_ANALYTICS_WORKSPACE_ID", "env-ws")
        monkeypatch.setenv("LOG_ANALYTICS_SHARED_KEY", "env-key")
        monkeypatch.setenv("LOG_ANALYTICS_TABLE", "CustomTable")
        monkeypatch.setenv("LOG_ANALYTICS_BATCH_SIZE", "50")
        monkeypatch.setenv("LOG_ANALYTICS_FLUSH_INTERVAL", "10.0")
        handler = LogAnalyticsHandler()
        assert handler.workspace_id == "env-ws"
        assert handler.shared_key == "env-key"
        assert handler.table_name == "CustomTable"
        assert handler.batch_size == 50
        assert handler.flush_interval == 10.0
        handler.close()

    def test_emit_without_credentials_is_noop(self) -> None:
        """
        Emit does nothing when credentials are missing.
        """
        handler = LogAnalyticsHandler()
        handler.emit(_make_record())
        assert handler._queue.empty()
        handler.close()

    def test_emit_enqueues_record(self) -> None:
        """
        Emit queues a formatted record when credentials exist.
        """
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        handler.emit(
            _make_record(
                msg="something happened",
                level=logging.WARNING,
                name="test.logger",
                lineno=42,
            )
        )
        assert not handler._queue.empty()
        entry = handler._queue.get_nowait()
        assert entry["level"] == "WARNING"
        assert entry["message"] == "something happened"
        assert entry["logger"] == "test.logger"
        assert "timestamp" in entry
        handler.close()

    def test_format_record_includes_custom_extras(self) -> None:
        """
        Format record extracts extra fields from log record.
        """
        handler = LogAnalyticsHandler()
        entry = handler._format_record(
            _make_record(
                correlation_id="corr-123",
                duration_ms=42,
                complex_obj={"nested": True},
            )
        )
        assert entry["correlation_id"] == "corr-123"
        assert entry["duration_ms"] == 42
        assert "nested" in str(entry["complex_obj"])
        handler.close()

    def test_send_batch_returns_false_on_empty(self) -> None:
        """
        Send batch returns False for empty batch.
        """
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        assert handler._send_batch([]) is False
        handler.close()

    def test_send_batch_returns_false_without_credentials(
        self,
    ) -> None:
        """
        Send batch returns False when credentials missing.
        """
        handler = LogAnalyticsHandler()
        assert handler._send_batch([{"msg": "test"}]) is False
        handler.close()

    def test_send_batch_success(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Send batch returns True on 200 response.
        """
        mock_response = mocker.MagicMock(status_code=200)
        mock_instance = mocker.MagicMock()
        mock_instance.send_telemetry_data_to_azureloganalytics.return_value = mock_response
        mocker.patch(
            _MOCK_SENDER,
            return_value=mock_instance,
        )
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        assert handler._send_batch([{"msg": "test"}]) is True
        handler.close()

    def test_send_batch_failure(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Send batch returns False on non-200 response.
        """
        mock_response = mocker.MagicMock(status_code=500)
        mock_instance = mocker.MagicMock()
        mock_instance.send_telemetry_data_to_azureloganalytics.return_value = mock_response
        mocker.patch(
            _MOCK_SENDER,
            return_value=mock_instance,
        )
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        assert handler._send_batch([{"msg": "test"}]) is False
        handler.close()

    def test_send_batch_exception_returns_false(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Send batch returns False when exception occurs.
        """
        mocker.patch(
            _MOCK_SENDER,
            side_effect=RuntimeError("connection failed"),
        )
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        assert handler._send_batch([{"msg": "test"}]) is False
        handler.close()

    def test_sender_loop_flushes_on_shutdown(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Background loop drains queue on shutdown.
        """
        mock_instance = mocker.MagicMock()
        mock_instance.send_telemetry_data_to_azureloganalytics.return_value = mocker.MagicMock(
            status_code=200
        )
        mocker.patch(
            _MOCK_SENDER,
            return_value=mock_instance,
        )
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
            batch_size=1000,
            flush_interval=100.0,
        )
        handler.emit(_make_record(msg="flush me"))
        handler.close()
        assert mock_instance.send_telemetry_data_to_azureloganalytics.called

    def test_flush_waits_for_empty_queue(self) -> None:
        """
        Flush blocks until queue is empty or timeout.
        """
        handler = LogAnalyticsHandler()
        handler.flush()
        handler.close()

    def test_close_sets_shutdown_flag(self) -> None:
        """
        Close sets the shutdown event.
        """
        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        assert not handler._shutdown.is_set()
        handler.close()
        assert handler._shutdown.is_set()


class TestADXHandler:
    """Tests for the ADXHandler class."""

    def test_init_without_adx_no_thread(self) -> None:
        """
        Handler without ADX credentials does not start thread.
        """
        handler = ADXHandler(config=TelemetryConfig())
        assert handler._thread is None
        handler.close()

    def test_init_with_adx_starts_thread(self) -> None:
        """
        Handler with ADX credentials starts background thread.
        """
        handler = ADXHandler(config=_adx_config())
        assert handler._thread is not None
        assert handler._thread.is_alive()
        handler.close()

    def test_table_name_from_config(self) -> None:
        """
        Table name defaults to config.service_table().
        """
        cfg = _adx_config()
        handler = ADXHandler(config=cfg)
        assert handler.table_name == cfg.service_table()
        handler.close()

    def test_table_name_override(self) -> None:
        """
        Explicit table_name overrides config.
        """
        handler = ADXHandler(
            config=_adx_config(),
            table_name="OverrideTable",
        )
        assert handler.table_name == "OverrideTable"
        handler.close()

    def test_emit_without_adx_is_noop(self) -> None:
        """
        Emit on handler without ADX credentials is a no-op.
        """
        handler = ADXHandler(config=TelemetryConfig())
        handler.emit(_make_record())
        assert handler._queue.empty()
        handler.close()

    def test_emit_enqueues_record(self) -> None:
        """
        Emit with valid config enqueues formatted record.
        """
        handler = ADXHandler(config=_adx_config())
        handler.emit(
            _make_record(
                msg="test warning",
                level=logging.WARNING,
                name="test.logger",
                lineno=42,
            )
        )
        assert not handler._queue.empty()
        entry = handler._queue.get_nowait()
        assert entry["level"] == "WARNING"
        assert entry["logger"] == "test.logger"
        assert entry["message"] == "test warning"
        assert "timestamp" in entry
        handler.close()

    def test_format_record_includes_extras(self) -> None:
        """
        Custom record attributes are included in format.
        """
        handler = ADXHandler(config=_adx_config())
        entry = handler._format_record(_make_record(correlation_id="test-corr-id"))
        assert entry["correlation_id"] == "test-corr-id"
        handler.close()

    def test_send_batch_returns_false_on_empty(self) -> None:
        """
        Empty batch returns False.
        """
        handler = ADXHandler(config=_adx_config())
        assert handler._send_batch([]) is False
        handler.close()

    def test_send_batch_returns_false_without_adx(self) -> None:
        """
        Batch without ADX credentials returns False.
        """
        handler = ADXHandler(config=TelemetryConfig())
        assert handler._send_batch([{"msg": "test"}]) is False
        handler.close()

    def test_send_batch_success(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Successful batch send returns True.
        """
        mock_sender = mocker.MagicMock()
        mocker.patch(
            _MOCK_SENDER,
            return_value=mock_sender,
        )
        handler = ADXHandler(config=_adx_config())
        assert handler._send_batch([{"msg": "test"}]) is True
        mock_sender.send_telemetry_data_to_azuredataexplorer.assert_called_once()
        handler.close()

    def test_send_batch_exception_returns_false(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Exception during send returns False.
        """
        mocker.patch(
            _MOCK_SENDER,
            side_effect=Exception("boom"),
        )
        handler = ADXHandler(config=_adx_config())
        assert handler._send_batch([{"msg": "test"}]) is False
        handler.close()

    def test_close_sets_shutdown_flag(self) -> None:
        """
        Close sets the shutdown event.
        """
        handler = ADXHandler(config=_adx_config())
        assert not handler._shutdown.is_set()
        handler.close()
        assert handler._shutdown.is_set()
