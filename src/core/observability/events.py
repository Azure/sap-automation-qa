# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Typed event definitions for structured logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from src.core.observability.context import (
    get_correlation_id,
    get_execution_id,
    get_workspace_id,
)


class LogStream(str, Enum):
    """
    Log stream identifiers (indexed labels in Loki).
    """

    SERVICE = "service_logs"
    EXECUTION = "execution_logs"


class LogLevel(str, Enum):
    """Standard log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


ServiceEventType = Literal[
    "request_start",
    "request_end",
    "schedule_trigger",
    "health_check",
    "error",
]


class ServiceEvent(BaseModel):
    """Service-level log event for HTTP/API operations."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stream: Literal[LogStream.SERVICE] = LogStream.SERVICE
    correlation_id: Optional[str] = None
    level: LogLevel = LogLevel.INFO
    event: ServiceEventType
    duration_ms: Optional[int] = None
    status: Optional[Literal["success", "failed", "error"]] = None
    error: Optional[str] = None
    http_method: Optional[str] = None
    http_path: Optional[str] = None
    http_status_code: Optional[int] = None
    client_ip: Optional[str] = None
    schedule_id: Optional[str] = None
    schedule_name: Optional[str] = None
    workspace_count: Optional[int] = None

    workspace_id: Optional[str] = None

    class Config:
        use_enum_values = True


ExecutionEventType = Literal[
    "job_start",
    "job_complete",
    "job_fail",
    "job_cancel",
    "execution_start",
    "execution_end",
    "test_start",
    "test_end",
    "config_check",
    "command_exec",
    "error",
]


class ExecutionEvent(BaseModel):
    """Execution-level log event for job and test operations."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stream: Literal[LogStream.EXECUTION] = LogStream.EXECUTION
    correlation_id: Optional[str] = None
    level: LogLevel = LogLevel.INFO
    event: ExecutionEventType
    duration_ms: Optional[float] = None
    status: Optional[Literal["success", "failed", "skipped", "error"]] = None
    error: Optional[str] = None
    job_id: Optional[str] = None
    execution_id: Optional[str] = None
    workspace_id: Optional[str] = None
    test_id: Optional[str] = None
    test_name: Optional[str] = None
    test_group: Optional[str] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None

    class Config:
        use_enum_values = True


def truncate(text: Optional[str], max_length: int = 200) -> Optional[str]:
    """Truncate text to max length with ellipsis.

    :param text: Text to truncate
    :type text: Optional[str]
    :param max_length: Maximum length
    :type max_length: int
    :returns: Truncated text or None
    :rtype: Optional[str]
    """
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def create_service_event(
    event: ServiceEventType,
    level: LogLevel = LogLevel.INFO,
    **kwargs: Any,
) -> ServiceEvent:
    """Create a service event with context auto-populated.

    :param event: Event type
    :type event: ServiceEventType
    :param level: Log level
    :type level: LogLevel
    :param kwargs: Additional event fields
    :returns: ServiceEvent instance
    :rtype: ServiceEvent
    """

    return ServiceEvent(
        event=event,
        level=level,
        correlation_id=kwargs.pop("correlation_id", get_correlation_id()),
        workspace_id=kwargs.pop("workspace_id", get_workspace_id()),
        **kwargs,
    )


def create_execution_event(
    event: ExecutionEventType,
    level: LogLevel = LogLevel.INFO,
    **kwargs: Any,
) -> ExecutionEvent:
    """Create an execution event with context auto-populated."""

    return ExecutionEvent(
        event=event,
        level=level,
        correlation_id=kwargs.pop("correlation_id", get_correlation_id()),
        execution_id=kwargs.pop("execution_id", get_execution_id()),
        workspace_id=kwargs.pop("workspace_id", get_workspace_id()),
        **kwargs,
    )
