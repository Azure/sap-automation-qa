# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for SchedulerService."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
from pytest_mock import MockerFixture
from src.core.models.schedule import Schedule
from src.core.services.scheduler import SchedulerService
from src.core.storage.schedule_store import ScheduleStore


class TestSchedulerService:
    """Unit tests for SchedulerService cron-based job triggering."""

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler_service: SchedulerService) -> None:
        """
        Verify start() and stop() lifecycle methods.
        """
        await scheduler_service.start()
        assert scheduler_service._running
        await scheduler_service.stop()
        assert not scheduler_service._running

    @pytest.mark.asyncio
    async def test_multiple_start(self, scheduler_service: SchedulerService) -> None:
        """
        Verify multiple start() calls are idempotent.
        """
        await scheduler_service.start()
        await scheduler_service.start()
        assert scheduler_service._running
        await scheduler_service.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self, scheduler_service: SchedulerService) -> None:
        """
        Verify stop() is safe when not started.
        """
        await scheduler_service.stop()
        assert not scheduler_service._running

    @pytest.mark.asyncio
    async def test_triggers_due_schedule(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify scheduler triggers jobs for due schedules.
        """
        schedule_store.create(
            Schedule(
                name="Trigger Test",
                workspace_ids=["WS-TRIGGER"],
                test_group="test",
                cron_expression="* * * * *",
                enabled=True,
                next_run_time=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
        )
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=1,
        )
        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()
        mock_job_worker.submit_job.assert_called()

    @pytest.mark.asyncio
    async def test_skips_disabled_schedule(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify scheduler skips disabled schedules.
        """
        schedule_store.create(
            Schedule(
                name="Disabled Test",
                workspace_ids=["WS-DISABLED"],
                test_group="test",
                cron_expression="* * * * *",
                enabled=False,
                next_run_time=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
        )
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=1,
        )
        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()
        mock_job_worker.submit_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_future_schedule(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify scheduler skips schedules with future next_run_time.
        """
        schedule_store.create(
            Schedule(
                name="Future Test",
                workspace_ids=["WS-FUTURE"],
                test_group="test",
                cron_expression="* * * * *",
                enabled=True,
                next_run_time=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=1,
        )
        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()
        mock_job_worker.submit_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_next_run(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify scheduler updates next_run_time after trigger.
        """
        schedule = Schedule(
            name="Update Test",
            workspace_ids=["WS-UPDATE"],
            test_group="test",
            cron_expression="*/5 * * * *",
            enabled=True,
            next_run_time=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        schedule_store.create(schedule)
        old_next = schedule.next_run_time
        assert old_next is not None
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=1,
        )
        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()
        updated = schedule_store.get(schedule.id)
        assert updated is not None
        assert updated.next_run_time is not None
        assert updated.next_run_time > old_next

    @pytest.mark.asyncio
    async def test_handles_submit_failure(
        self, schedule_store: ScheduleStore, mocker: MockerFixture
    ) -> None:
        """
        Verify scheduler handles job submission failures gracefully.
        """
        schedule_store.create(
            Schedule(
                name="Fail Test",
                workspace_ids=["WS-FAIL"],
                test_group="test",
                cron_expression="* * * * *",
                enabled=True,
                next_run_time=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
        )
        worker = mocker.MagicMock()
        worker.submit_job = mocker.AsyncMock(side_effect=Exception("Submit failed"))
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=worker,
            check_interval_seconds=1,
        )
        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()

    @pytest.mark.asyncio
    async def test_empty_schedules(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify scheduler handles empty schedule store.
        """
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=1,
        )
        await service.start()
        await asyncio.sleep(0.2)
        await service.stop()
        mock_job_worker.submit_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_interval_stored(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify check_interval_seconds is stored correctly.
        """
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=10,
        )
        assert service._check_interval == 10

    @pytest.mark.asyncio
    async def test_trigger_now(self, schedule_store: ScheduleStore, mock_job_worker: Any) -> None:
        """
        Verify trigger_now() immediately triggers schedule.
        """
        schedule = Schedule(
            name="Trigger Now Test",
            workspace_ids=["WS-NOW"],
            test_group="test",
            cron_expression="0 0 * * *",
            enabled=True,
        )
        schedule_store.create(schedule)
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=60,
        )
        job_ids = await service.trigger_now(schedule.id)
        mock_job_worker.submit_job.assert_called()
        assert isinstance(job_ids, list)

    @pytest.mark.asyncio
    async def test_trigger_now_not_found(
        self, schedule_store: ScheduleStore, mock_job_worker: Any
    ) -> None:
        """
        Verify trigger_now() raises ValueError for unknown schedule.
        """
        service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=mock_job_worker,
            check_interval_seconds=60,
        )
        with pytest.raises(ValueError, match="not found"):
            await service.trigger_now("nonexistent-id")
