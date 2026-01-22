# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Schedules API routes."""

from datetime import datetime
from typing import Optional
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException, Query
from src.core.models.schedule import (
    Schedule,
    CreateScheduleRequest,
    UpdateScheduleRequest,
    ScheduleListResponse,
)
from src.core.storage.schedule_store import ScheduleStore
from src.core.services.scheduler import SchedulerService
from src.core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/schedules", tags=["schedules"])
_schedule_store: Optional[ScheduleStore] = None
_scheduler_service: Optional[SchedulerService] = None


def set_schedule_store(store: ScheduleStore) -> None:
    """Set the schedule store instance.

    :param store: ScheduleStore instance for persistence.
    :type store: ScheduleStore
    """
    global _schedule_store
    _schedule_store = store


def set_scheduler_service(service: SchedulerService) -> None:
    """Set the scheduler service instance.

    :param service: SchedulerService instance for scheduling.
    :type service: SchedulerService
    """
    global _scheduler_service
    _scheduler_service = service


def get_schedule_store() -> ScheduleStore:
    """Get the schedule store instance.

    :returns: The configured ScheduleStore instance.
    :rtype: ScheduleStore
    :raises HTTPException: If store not initialized (503 error).
    """
    if _schedule_store is None:
        raise HTTPException(status_code=503, detail="Schedule store not initialized")
    return _schedule_store


@router.post("", response_model=Schedule, status_code=201)
async def create_schedule(request: CreateScheduleRequest) -> Schedule:
    """Create a new schedule."""
    store = get_schedule_store()

    try:
        CronTrigger.from_crontab(request.cron_expression)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cron expression '{request.cron_expression}': {str(e)}",
        )

    if not request.workspace_ids:
        raise HTTPException(status_code=400, detail="At least one workspace_id is required")

    schedule = Schedule(
        name=request.name,
        description=request.description,
        cron_expression=request.cron_expression,
        timezone=request.timezone,
        workspace_ids=request.workspace_ids,
        test_group=request.test_group,
        test_ids=request.test_ids,
        enabled=request.enabled,
    )

    if schedule.enabled:
        trigger = CronTrigger.from_crontab(schedule.cron_expression)
        next_run = trigger.get_next_fire_time(None, datetime.utcnow())
        schedule.next_run_time = next_run

    created = store.create(schedule)
    logger.info(f"Created schedule '{created.name}' (ID: {created.id})")

    return created


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    enabled_only: bool = Query(False, description="Only show enabled schedules"),
) -> ScheduleListResponse:
    """List all schedules."""
    store = get_schedule_store()
    schedules = store.list(enabled_only=enabled_only)

    return ScheduleListResponse(schedules=schedules, total=len(schedules))


@router.get("/{schedule_id}", response_model=Schedule)
async def get_schedule(schedule_id: str) -> Schedule:
    """Get a specific schedule."""
    store = get_schedule_store()
    schedule = store.get(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    return schedule


@router.patch("/{schedule_id}", response_model=Schedule)
async def update_schedule(schedule_id: str, request: UpdateScheduleRequest) -> Schedule:
    """Update an existing schedule."""
    store = get_schedule_store()
    schedule = store.get(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    update_data = request.model_dump(exclude_unset=True)

    if "cron_expression" in update_data:
        try:
            CronTrigger.from_crontab(update_data["cron_expression"])
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cron expression: {str(e)}",
            )

    for field, value in update_data.items():
        setattr(schedule, field, value)

    if schedule.enabled:
        trigger = CronTrigger.from_crontab(schedule.cron_expression)
        next_run = trigger.get_next_fire_time(None, datetime.utcnow())
        schedule.next_run_time = next_run

    updated = store.update(schedule)
    logger.info(f"Updated schedule '{updated.name}' (ID: {updated.id})")

    return updated


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str) -> dict:
    """Delete a schedule.

    :param schedule_id: ID of the schedule to delete.
    :type schedule_id: str
    :returns: Status dict with deletion confirmation.
    :rtype: dict
    :raises HTTPException: If schedule not found (404 error).
    """
    store = get_schedule_store()

    if not store.delete(schedule_id):
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    logger.info(f"Deleted schedule {schedule_id}")
    return {"status": "deleted", "schedule_id": schedule_id}


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(schedule_id: str) -> dict:
    """Manually trigger a schedule immediately.

    :param schedule_id: ID of the schedule to trigger.
    :type schedule_id: str
    :returns: Status dict with triggered job IDs.
    :rtype: dict
    :raises HTTPException: If schedule not found (404) or service unavailable (503).
    """
    if not _scheduler_service:
        raise HTTPException(status_code=503, detail="Scheduler service not available")

    try:
        job_ids = await _scheduler_service.trigger_now(schedule_id)
        return {
            "status": "triggered",
            "schedule_id": schedule_id,
            "job_ids": job_ids,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to trigger schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{schedule_id}/jobs")
async def get_schedule_jobs(
    schedule_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Get jobs triggered by a schedule.

    :param schedule_id: ID of the schedule.
    :type schedule_id: str
    :param limit: Maximum number of jobs to return.
    :type limit: int
    :returns: Dict containing list of jobs and total count.
    :rtype: dict
    :raises HTTPException: If schedule not found (404 error).
    """
    from src.api.routes.jobs import get_job_store

    store = get_schedule_store()
    schedule = store.get(schedule_id)

    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    job_store = get_job_store()
    jobs = job_store.get_jobs_for_schedule(schedule_id, limit=limit)

    return {
        "schedule_id": schedule_id,
        "jobs": [j.model_dump(mode="json") for j in jobs],
        "total": len(jobs),
    }
