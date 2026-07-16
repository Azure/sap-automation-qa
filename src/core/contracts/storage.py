# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Consumer-focused storage protocols (P1-WP-002D).

Each protocol captures *exactly* the methods that a specific consumer calls.
Concrete stores (``JobStore``, ``AzureTableJobStore``, etc.) keep their names
unchanged; protocols use distinct ``…Protocol`` suffixes to avoid collision.
"""

from __future__ import annotations
from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID
from src.core.models.job import Job, JobStatus
from src.core.models.schedule import Schedule


@runtime_checkable
class JobQueryProtocol(Protocol):
    """Job read operations consumed by jobs routes."""

    def get(self, job_id: UUID | str) -> Optional[Job]: ...

    def get_active(self, workspace_id: Optional[str] = None) -> List[Job]: ...

    def get_history(
        self,
        workspace_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        days: int = 7,
        limit: int = 100,
    ) -> List[Job]: ...

    def get_jobs_for_schedule(
        self,
        schedule_id: str,
        limit: int = 50,
    ) -> List[Job]: ...


@runtime_checkable
class JobLifecycleProtocol(Protocol):
    """Job persistence operations consumed by JobWorker."""

    def get(self, job_id: UUID | str) -> Optional[Job]: ...

    def get_active(self, workspace_id: Optional[str] = None) -> List[Job]: ...

    def get_active_for_workspace(self, workspace_id: str) -> Optional[Job]: ...

    def create(self, job: Job) -> Job: ...

    def update(self, job: Job) -> None: ...


@runtime_checkable
class JobStoreProtocol(JobQueryProtocol, JobLifecycleProtocol, Protocol):
    """Full job store protocol for StorageContext / backend composition.

    Satisfied by both SQLite ``JobStore`` and ``AzureTableJobStore``.
    """

    def close(self) -> None: ...


@runtime_checkable
class ScheduleCrudProtocol(Protocol):
    """Schedule operations consumed by schedules routes."""

    def get(self, schedule_id: str) -> Optional[Schedule]: ...

    def list(self, enabled_only: bool = False) -> List[Schedule]: ...

    def create(self, schedule: Schedule) -> Schedule: ...

    def update(self, schedule: Schedule) -> Schedule: ...

    def delete(self, schedule_id: str) -> bool: ...


@runtime_checkable
class ScheduleRuntimeProtocol(Protocol):
    """Schedule operations consumed by SchedulerService at runtime."""

    def get(self, schedule_id: str) -> Optional[Schedule]: ...

    def get_enabled(self) -> List[Schedule]: ...

    def update(self, schedule: Schedule) -> Schedule: ...


@runtime_checkable
class ScheduleStoreProtocol(ScheduleCrudProtocol, ScheduleRuntimeProtocol, Protocol):
    """Full schedule store protocol for StorageContext / backend composition.

    Satisfied by both SQLite ``ScheduleStore`` and ``AzureTableScheduleStore``.
    """

    def close(self) -> None: ...
