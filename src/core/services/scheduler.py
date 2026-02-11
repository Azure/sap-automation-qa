# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Cron-based scheduler service for automated test execution."""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from apscheduler.triggers.cron import CronTrigger
from src.core.models.job import Job
from src.core.models.schedule import Schedule
from src.core.storage.schedule_store import ScheduleStore
from src.core.execution.worker import JobWorker
from src.core.observability import get_logger, create_service_event

logger = get_logger(__name__)


class SchedulerService:
    """Cron-based scheduler for automated test execution.

    Periodically checks schedules and triggers jobs for each configured workspace.
    """

    def __init__(
        self,
        schedule_store: ScheduleStore,
        job_worker: JobWorker,
        check_interval_seconds: int = 60,
    ) -> None:
        """Initialize the scheduler service.

        :param schedule_store: Store for loading schedules
        :param job_worker: Worker for submitting jobs
        :param check_interval_seconds: Interval between schedule checks
        """
        self._schedule_store = schedule_store
        self._job_worker = job_worker
        self._check_interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

        logger.info(f"SchedulerService initialized (check_interval={check_interval_seconds}s)")

    async def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            logger.warning("SchedulerService already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("SchedulerService started")

    async def stop(self) -> None:
        """Stop the scheduler background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("SchedulerService stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks schedules periodically.

        Runs continuously while the scheduler is active, checking for
        due schedules at the configured interval and triggering jobs.
        """
        logger.info("Scheduler loop started")

        while self._running:
            try:
                await self._check_and_trigger_schedules()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

            await asyncio.sleep(self._check_interval)

    async def _check_and_trigger_schedules(self) -> None:
        """Check all schedules and trigger due jobs.

        Iterates through enabled schedules and triggers any that have
        reached their next_run_time.
        """
        schedules = self._schedule_store.get_enabled()
        now = datetime.now(timezone.utc)

        for schedule in schedules:
            if schedule.next_run_time and schedule.next_run_time <= now:
                await self._trigger_schedule(schedule)

    async def _trigger_schedule(self, schedule: Schedule) -> None:
        """Trigger a schedule - creates one job per workspace.

        :param schedule: Schedule to trigger
        """
        try:
            current_schedule = self._schedule_store.get(schedule.id)
            if not current_schedule:
                logger.warning(f"Schedule '{schedule.name}' was deleted before trigger")
                return

            if not current_schedule.enabled:
                logger.info(f"Schedule '{schedule.name}' was disabled before trigger")
                return

            schedule = current_schedule

            logger.event(
                create_service_event(
                    "schedule_trigger",
                    schedule_id=schedule.id,
                    schedule_name=schedule.name,
                    workspace_count=len(schedule.workspace_ids),
                )
            )

            job_ids = []
            for workspace_id in schedule.workspace_ids:
                try:
                    job = Job(
                        workspace_id=workspace_id,
                        schedule_id=schedule.id,
                        test_group=schedule.test_group,
                        test_ids=schedule.test_ids,
                        metadata={
                            "scheduled": True,
                            "schedule_name": schedule.name,
                            "schedule_id": schedule.id,
                        },
                    )

                    submitted_job = await self._job_worker.submit_job(job)
                    job_ids.append(str(submitted_job.id))
                    logger.info(
                        f"Triggered job {submitted_job.id} for workspace {workspace_id} "
                        f"(schedule: {schedule.name})"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to trigger job for workspace {workspace_id} "
                        f"(schedule {schedule.id}): {e}",
                        exc_info=True,
                    )

            schedule.last_run_time = datetime.now(timezone.utc)
            schedule.last_run_job_ids = job_ids
            schedule.total_runs += 1
            if schedule.enabled:
                trigger = CronTrigger.from_crontab(schedule.cron_expression)
                next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
                schedule.next_run_time = next_run
            self._schedule_store.update(schedule)
            logger.info(
                f"Schedule '{schedule.name}' triggered {len(job_ids)} job(s). "
                f"Next run: {schedule.next_run_time}"
            )

        except Exception as e:
            logger.error(f"Failed to trigger schedule {schedule.id}: {e}", exc_info=True)

    async def trigger_now(self, schedule_id: str) -> list[str]:
        """Manually trigger a schedule immediately.

        :param schedule_id: Schedule ID to trigger
        :returns: List of created job IDs
        :raises ValueError: If schedule not found
        :raises PermissionError: If schedule is disabled
        """
        schedule = self._schedule_store.get(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        if not schedule.enabled:
            raise PermissionError(
                f"Schedule '{schedule.name}' is disabled. "
                f"Enable it before triggering."
            )
        await self._trigger_schedule(schedule)
        updated = self._schedule_store.get(schedule_id)
        return updated.last_run_job_ids if updated else []
