# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])
_service_status: Dict[str, bool] = {}
_storage_backend: Optional[str] = None
_workspace_backend: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str
    services: Dict[str, bool] = {}
    storage_backend: Optional[str] = None
    workspace_backend: Optional[str] = None


def set_service_status(name: str, running: bool) -> None:
    """Set a service's status for health check.

    :param name: Service name (e.g., "scheduler", "worker")
    :param running: Whether the service is running
    """
    _service_status[name] = running


def set_storage_backend(backend: str) -> None:
    """Set the active storage backend name for health reporting.

    :param backend: Backend identifier (e.g., "sqlite", "azure_table").
        No credentials, endpoints, or table names are stored.
    """
    global _storage_backend
    _storage_backend = backend


def set_workspace_backend(backend: str) -> None:
    """Set the active workspace backend name for health reporting.

    :param backend: Backend identifier: ``"filesystem"`` or ``"blob"``.
        No credentials, endpoints, or container names are stored.
    """
    global _workspace_backend
    _workspace_backend = backend


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status.

    :returns: Health status including all service states.
    :rtype: HealthResponse
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        services=_service_status.copy(),
        storage_backend=_storage_backend,
        workspace_backend=_workspace_backend,
    )


@router.get("/")
async def root() -> dict:
    """Root endpoint.

    :returns: Service information and documentation link.
    :rtype: dict
    """
    return {
        "service": "SAP QA Scheduler API",
        "version": "1.0.0",
        "docs": "/docs",
    }
