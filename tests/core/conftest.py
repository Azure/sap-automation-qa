# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Shared fixtures for core module tests."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Generator
from uuid import uuid4
import pytest
from pytest_mock import MockerFixture
from src.core.models.job import Job
from src.core.models.schedule import Schedule
from src.core.storage.job_store import JobStore
from src.core.storage.schedule_store import ScheduleStore
from src.core.execution.worker import JobWorker
from src.core.services.scheduler import SchedulerService


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_job() -> Job:
    return Job(
        id=uuid4(),
        workspace_id="TEST-WORKSPACE-01",
        test_group="ha_db_functional_tests",
        test_ids=["test_1", "test_2"],
        metadata={"source": "unit_test"},
    )


@pytest.fixture
def sample_running_job() -> Job:
    job = Job(id=uuid4(), workspace_id="TEST-WORKSPACE-02", test_group="ha_scs_functional_tests")
    job.start()
    return job


@pytest.fixture
def sample_completed_job() -> Job:
    job = Job(id=uuid4(), workspace_id="TEST-WORKSPACE-03", test_group="configuration_checks")
    job.start()
    job.complete({"passed": 5, "failed": 0})
    return job


@pytest.fixture
def sample_schedule() -> Schedule:
    return Schedule(
        id=str(uuid4()),
        name="Daily HA Tests",
        description="Run HA tests every day at midnight",
        cron_expression="0 0 * * *",
        timezone="UTC",
        workspace_ids=["WS-001", "WS-002"],
        test_group="ha_db_functional_tests",
        enabled=True,
    )


@pytest.fixture
def sample_disabled_schedule() -> Schedule:
    return Schedule(
        id=str(uuid4()),
        name="Disabled Schedule",
        cron_expression="0 12 * * *",
        workspace_ids=["WS-003"],
        enabled=False,
    )


@pytest.fixture
def due_schedule() -> Schedule:
    return Schedule(
        id=str(uuid4()),
        name="Due Schedule",
        cron_expression="* * * * *",
        workspace_ids=["WS-DUE"],
        enabled=True,
        next_run_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def job_store(temp_dir: Path) -> JobStore:
    return JobStore(db_path=temp_dir / "test.db")


@pytest.fixture
def schedule_store(temp_dir: Path) -> ScheduleStore:
    return ScheduleStore(db_path=temp_dir / "test.db")


@pytest.fixture
def mock_executor(mocker: MockerFixture) -> Any:
    executor = mocker.MagicMock()
    executor.execute = mocker.AsyncMock(
        return_value={"status": "success", "tests_passed": 3, "tests_failed": 0}
    )
    executor.terminate_process = mocker.MagicMock(
        return_value=False,
    )
    return executor


@pytest.fixture
def failing_executor(mocker: MockerFixture) -> Any:
    executor = mocker.MagicMock()
    executor.execute = mocker.AsyncMock(side_effect=RuntimeError("Executor failure"))
    executor.terminate_process = mocker.MagicMock(
        return_value=False,
    )
    return executor


@pytest.fixture
def workspace_loader() -> Callable[[str], dict[str, Any]]:
    def loader(workspace_id: str) -> dict[str, Any]:
        return {
            "inventory_path": f"WORKSPACES/SYSTEM/{workspace_id}/hosts.yaml",
            "sap_sid": "X00",
            "database_high_availability": True,
        }

    return loader


@pytest.fixture
def job_worker(
    job_store: JobStore, mock_executor: Any, workspace_loader: Any, temp_dir: Path
) -> JobWorker:
    return JobWorker(
        job_store=job_store,
        executor=mock_executor,
        workspace_config_loader=workspace_loader,
        log_dir=temp_dir / "logs",
    )


@pytest.fixture
def mock_job_worker(mocker: MockerFixture) -> Any:
    worker = mocker.MagicMock()

    async def mock_submit(job: Job) -> Job:
        job.start()
        return job

    worker.submit_job = mocker.AsyncMock(side_effect=mock_submit)
    return worker


@pytest.fixture
def scheduler_service(schedule_store: ScheduleStore, mock_job_worker: Any) -> SchedulerService:
    return SchedulerService(
        schedule_store=schedule_store,
        job_worker=mock_job_worker,
        check_interval_seconds=1,
    )
