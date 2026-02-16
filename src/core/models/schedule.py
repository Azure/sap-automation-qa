# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Schedule configuration models."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class Schedule(BaseModel):
    """Schedule configuration for automated test execution."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    cron_expression: str
    timezone: str = "UTC"
    workspace_ids: List[str] = Field(default_factory=list)
    test_group: Optional[str] = None
    test_ids: List[str] = Field(default_factory=list)
    enabled: bool = True
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    last_run_job_ids: List[str] = Field(default_factory=list)
    total_runs: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class CreateScheduleRequest(BaseModel):
    """Request to create a new schedule."""

    name: str
    description: str = ""
    cron_expression: str
    timezone: str = "UTC"
    workspace_ids: List[str]
    test_group: Optional[str] = None
    test_ids: List[str] = Field(default_factory=list)
    enabled: bool = True


class UpdateScheduleRequest(BaseModel):
    """Request to update an existing schedule."""

    name: Optional[str] = None
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    workspace_ids: Optional[List[str]] = None
    test_group: Optional[str] = None
    test_ids: Optional[List[str]] = None
    enabled: Optional[bool] = None


class ScheduleListResponse(BaseModel):
    """Response containing list of schedules."""

    schedules: List[Schedule]
    total: int
