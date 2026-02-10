# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for LogAnalyticsHandler."""

import logging
import queue
import time
import pytest
from pytest_mock import MockerFixture
from src.core.observability.log_analytics import (
    LogAnalyticsHandler,
    add_log_analytics_handler,
)


class TestLogAnalyticsHandler:
    """
    Tests for the LogAnalyticsHandler class.
    """

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
        Handler with credentials starts the background sender thread.
        """
        handler = LogAnalyticsHandler(
            workspace_id="ws-123",
            shared_key="key-abc",
        )
        assert handler._thread is not None
        assert handler._thread.is_alive()
        handler.close()

    def test_init_reads_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Handler reads defaults from environment variables.
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
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
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
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=42,
            msg="something happened",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
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
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="msg",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "corr-123"
        record.duration_ms = 42
        record.complex_obj = {"nested": True}
        entry = handler._format_record(record)
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

    def test_send_batch_returns_false_without_credentials(self) -> None:
        """
        Send batch returns False when credentials missing.
        """
        handler = LogAnalyticsHandler()
        assert handler._send_batch([{"msg": "test"}]) is False
        handler.close()

    def test_send_batch_success(self, mocker: MockerFixture) -> None:
        """
        Send batch returns True on 200 response.
        """
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_instance = mocker.MagicMock()
        mock_instance.send_telemetry_data_to_azureloganalytics.return_value = mock_response
        mock_sender_cls = mocker.patch(
            "src.core.observability.log_analytics.TelemetryDataSender",
            return_value=mock_instance,
        )

        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
        )
        result = handler._send_batch([{"msg": "test"}])
        assert result is True
        mock_sender_cls.assert_called_once()
        handler.close()

    def test_send_batch_failure(self, mocker: MockerFixture) -> None:
        """
        Send batch returns False on non-200 response.
        """
        mock_response = mocker.MagicMock()
        mock_response.status_code = 500
        mock_instance = mocker.MagicMock()
        mock_instance.send_telemetry_data_to_azureloganalytics.return_value = mock_response
        mocker.patch(
            "src.core.observability.log_analytics.TelemetryDataSender",
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
            "src.core.observability.log_analytics.TelemetryDataSender",
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
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_instance = mocker.MagicMock()
        mock_instance.send_telemetry_data_to_azureloganalytics.return_value = mock_response
        mocker.patch(
            "src.core.observability.log_analytics.TelemetryDataSender",
            return_value=mock_instance,
        )

        handler = LogAnalyticsHandler(
            workspace_id="ws",
            shared_key="key",
            batch_size=1000,
            flush_interval=100.0,
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="flush me",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
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


class TestAddLogAnalyticsHandler:
    """
    Tests for the add_log_analytics_handler helper.
    """

    def test_returns_none_without_credentials(self) -> None:
        """
        Returns None when no credentials provided.
        """
        result = add_log_analytics_handler()
        assert result is None

    def test_returns_handler_with_credentials(self) -> None:
        """
        Returns handler and attaches it to logger.
        """
        test_logger = logging.getLogger("test.la.handler")
        handler = add_log_analytics_handler(
            logger=test_logger,
            workspace_id="ws-test",
            shared_key="key-test",
            table_name="TestTable",
        )
        assert handler is not None
        assert isinstance(handler, LogAnalyticsHandler)
        assert handler in test_logger.handlers
        handler.close()
        test_logger.removeHandler(handler)

    def test_uses_env_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Falls back to environment variables for credentials.
        """
        monkeypatch.setenv("LOG_ANALYTICS_WORKSPACE_ID", "env-ws")
        monkeypatch.setenv("LOG_ANALYTICS_SHARED_KEY", "env-key")
        test_logger = logging.getLogger("test.la.env")
        handler = add_log_analytics_handler(logger=test_logger)
        assert handler is not None
        handler.close()
        test_logger.removeHandler(handler)

    def test_adds_to_root_logger_when_none(self) -> None:
        """
        Adds handler to root logger when no logger specified.
        """
        root = logging.getLogger()
        handler = add_log_analytics_handler(
            workspace_id="ws",
            shared_key="key",
        )
        assert handler is not None
        assert handler in root.handlers
        handler.close()
        root.removeHandler(handler)
