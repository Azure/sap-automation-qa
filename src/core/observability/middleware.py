# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
FastAPI middleware for observability.
"""

from __future__ import annotations
import time
import uuid
from typing import Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from src.core.observability.context import ObservabilityContext
from src.core.observability.events import (
    create_service_event,
    LogLevel,
)
from src.core.observability.logger import get_logger

CORRELATION_ID_HEADER = "X-Correlation-ID"
WORKSPACE_ID_HEADER = "X-Workspace-ID"
SKIP_PATHS = {"/healthz", "/favicon.ico", "/metrics"}


logger = get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for request observability.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request with observability context.

        :param request: Incoming request
        :type request: Request
        :param call_next: Next handler in chain
        :type call_next: RequestResponseEndpoint
        :returns: Response
        :rtype: Response
        """
        if request.url.path in SKIP_PATHS:
            return await call_next(request)
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        workspace_id = request.headers.get(WORKSPACE_ID_HEADER) or request.query_params.get(
            "workspace_id"
        )
        with ObservabilityContext(
            correlation_id=correlation_id,
            workspace_id=workspace_id,
        ):
            start_time = time.perf_counter()
            self._log_request_start(request, correlation_id)
            response: Response | None = None
            error: Exception | None = None
            try:
                response = await call_next(request)
            except Exception as exc:
                error = exc
                raise
            finally:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._log_request_end(
                    request=request,
                    response=response,
                    error=error,
                    duration_ms=duration_ms,
                )
            if response:
                response.headers[CORRELATION_ID_HEADER] = correlation_id
            assert response is not None
            return response

    def _log_request_start(
        self,
        request: Request,
        correlation_id: str,
    ) -> None:
        """Log request start event.

        :param request: Incoming request
        :param correlation_id: Correlation ID
        """
        event = create_service_event(
            event="request_start",
            level=LogLevel.INFO,
            http_method=request.method,
            http_path=str(request.url.path),
            client_ip=self._get_client_ip(request),
        )
        logger.event(event)

    def _log_request_end(
        self,
        request: Request,
        response: Optional[Response],
        error: Optional[Exception],
        duration_ms: int,
    ) -> None:
        """Log request end event.

        :param request: Incoming request
        :param response: Response (if successful)
        :param error: Error (if failed)
        :param duration_ms: Request duration in milliseconds
        """
        status_code = response.status_code if response else 500
        status = "success" if status_code < 400 else "error"
        level = LogLevel.INFO if status_code < 400 else LogLevel.ERROR

        event = create_service_event(
            event="request_end",
            level=level,
            status=status,
            http_method=request.method,
            http_path=str(request.url.path),
            http_status_code=status_code,
            duration_ms=duration_ms,
            error=str(error) if error else None,
        )
        logger.event(event)

    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request.

        :param request: Incoming request
        :returns: Client IP address
        :rtype: Optional[str]
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host

        return None


def add_observability_middleware(app: Any) -> None:
    """
    Add observability middleware to FastAPI app.

    :param app: FastAPI application instance
    :type app: FastAPI
    """
    app.add_middleware(ObservabilityMiddleware)
