# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Shared fixtures for core module tests."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from src.core.execution.worker import JobWorker
from src.core.models.job import Job
from src.core.models.schedule import Schedule
from src.core.models.workspace import MaterializedWorkspace
from src.core.services.scheduler import SchedulerService
from src.core.storage.job_store import JobStore
from src.core.storage.schedule_store import ScheduleStore


class FakeWorkspaceBackend:
    """Simple workspace backend for worker tests."""

    backend_name = "filesystem"

    def __init__(self, root: Path) -> None:
        self.root = root

    def materialize(self, workspace_id: str, job_id: str) -> MaterializedWorkspace:
        workspace_dir = self.root / workspace_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        inventory = workspace_dir / "hosts.yaml"
        inventory.write_text("all:\n  hosts:\n    node1:\n", encoding="utf-8")
        return MaterializedWorkspace(
            workspace_id=workspace_id,
            job_id=job_id,
            local_path=workspace_dir,
            inventory_path=str(inventory),
            extra_vars={"sap_sid": "X00"},
            owned=False,
        )

    def cleanup(self, materialized: MaterializedWorkspace) -> None:
        return None


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
def job_store(temp_dir: Path):
    store = JobStore(db_path=temp_dir / "test.db")
    yield store
    store.close()


@pytest.fixture
def schedule_store(temp_dir: Path):
    store = ScheduleStore(db_path=temp_dir / "test.db")
    yield store
    store.close()


@pytest.fixture
def mock_executor(mocker: MockerFixture) -> Any:
    executor = mocker.MagicMock()
    executor.run_test = mocker.MagicMock(return_value={"status": "success"})
    executor.terminate_process = mocker.MagicMock(return_value=False)
    return executor


@pytest.fixture
def failing_executor(mocker: MockerFixture) -> Any:
    executor = mocker.MagicMock()
    executor.run_test = mocker.MagicMock(side_effect=RuntimeError("Executor failure"))
    executor.terminate_process = mocker.MagicMock(return_value=False)
    return executor


@pytest.fixture
def workspace_backend(temp_dir: Path) -> FakeWorkspaceBackend:
    return FakeWorkspaceBackend(temp_dir / "workspaces")


@pytest.fixture
def job_worker(
    job_store: JobStore, mock_executor: Any, workspace_backend: Any, temp_dir: Path
) -> JobWorker:
    return JobWorker(
        job_store=job_store,
        executor=mock_executor,
        workspace_backend=workspace_backend,
        log_dir=temp_dir / "job-logs",
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
