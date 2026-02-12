# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])
_service_status: Dict[str, bool] = {}


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str
    services: Dict[str, bool] = {}


def set_service_status(name: str, running: bool) -> None:
    """Set a service's status for health check.

    :param name: Service name (e.g., "scheduler", "worker")
    :param running: Whether the service is running
    """
    _service_status[name] = running


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
