# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Observability module for SAP QA Framework.

This module provides production-grade observability with OOP design:

Classes:
- ObservabilityContextManager: Singleton for context management
- StructuredLogger: Logger with context injection
- LoggerFactory: Factory for creating loggers
- JSONFormatter/ConsoleFormatter: Log formatters

Events:
- ServiceEvent: HTTP/API layer events
- ExecutionEvent: Ansible/test events

Usage:
    from src.core.observability import (
        LoggerFactory,
        get_logger,
    )

    # Initialize once at startup
    LoggerFactory.initialize(level=logging.INFO, log_format="json")

    # Get logger
    logger = get_logger(__name__)

"""

# Context management
from src.core.observability.context import (
    ContextData,
    ObservabilityContextManager,
    ContextVarProvider,
    IContextProvider,
    ObservabilityScope,
    ExecutionScope,
    ObservabilityContext,
    ExecutionContext,
    get_correlation_id,
    set_correlation_id,
    get_workspace_id,
    set_workspace_id,
    get_execution_id,
    clear_context,
)

from src.core.observability.events import (
    LogStream,
    LogLevel,
    ServiceEvent,
    ExecutionEvent,
    create_service_event,
    create_execution_event,
)

from src.core.observability.logger import (
    LogFormatter,
    JSONFormatter,
    ConsoleFormatter,
    StructuredLogger,
    LoggerFactory,
    initialize_logging,
    get_logger,
    clear_correlation_id,
)

from src.core.observability.log_analytics import (
    LogAnalyticsHandler,
    add_log_analytics_handler,
)

from src.core.observability.middleware import (
    ObservabilityMiddleware,
    add_observability_middleware,
    CORRELATION_ID_HEADER,
    WORKSPACE_ID_HEADER,
)


__all__ = [
    "ContextData",
    "ObservabilityContextManager",
    "ContextVarProvider",
    "IContextProvider",
    "ObservabilityScope",
    "ExecutionScope",
    "get_correlation_id",
    "set_correlation_id",
    "clear_context",
    "clear_correlation_id",
    "LogStream",
    "LogLevel",
    "ServiceEvent",
    "ExecutionEvent",
    "create_service_event",
    "create_execution_event",
    "LogFormatter",
    "JSONFormatter",
    "ConsoleFormatter",
    "StructuredLogger",
    "LoggerFactory",
    "initialize_logging",
    "get_logger",
    "LogAnalyticsHandler",
    "add_log_analytics_handler",
    "ObservabilityMiddleware",
    "add_observability_middleware",
    "CORRELATION_ID_HEADER",
    "WORKSPACE_ID_HEADER",
]
