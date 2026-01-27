# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Fixtures for API tests."""

import tempfile
from pathlib import Path
from typing import Any, Generator
import pytest
from pytest_mock import MockerFixture
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routes import jobs, schedules
from src.core.storage.job_store import JobStore
from src.core.storage.schedule_store import ScheduleStore
from src.core.execution.worker import JobWorker
from src.core.models.job import Job
from src.core.models.schedule import Schedule


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app for testing."""
    from src.api.routes import (
        health_router,
        jobs_router,
        schedules_router,
        workspaces_router,
    )

    app = FastAPI(title="Test API")
    app.include_router(health_router)
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(schedules_router, prefix="/api/v1")
    app.include_router(workspaces_router, prefix="/api/v1")
    return app


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def job_store(temp_dir: Path) -> JobStore:
    """Provide a JobStore instance."""
    return JobStore(data_dir=temp_dir / "jobs")


@pytest.fixture
def schedule_store(temp_dir: Path) -> ScheduleStore:
    """Provide a ScheduleStore instance."""
    return ScheduleStore(storage_path=temp_dir / "schedules.json")


@pytest.fixture
def mock_workspace_loader(mocker: MockerFixture) -> Any:
    """Provide a mock workspace config loader."""
    loader = mocker.MagicMock()
    loader.side_effect = lambda ws_id: {
        "workspace_id": ws_id,
        "inventory_path": f"/path/to/{ws_id}/inventory",
        "extra_vars": {},
    }
    return loader


@pytest.fixture
def mock_executor(mocker: MockerFixture) -> Any:
    """Provide a mock test executor."""
    executor = mocker.MagicMock()
    executor.run_test = mocker.MagicMock(return_value={"status": "success"})
    return executor


@pytest.fixture
def job_worker(
    job_store: JobStore,
    mock_executor: Any,
    mock_workspace_loader: Any,
) -> JobWorker:
    """Provide a JobWorker instance."""
    return JobWorker(
        job_store=job_store,
        executor=mock_executor,
        workspace_config_loader=mock_workspace_loader,
    )


@pytest.fixture
def client(
    job_store: JobStore,
    schedule_store: ScheduleStore,
    job_worker: JobWorker,
    mock_workspace_loader: Any,
) -> Generator[TestClient, None, None]:
    """Provide a test client with all dependencies configured."""
    app = create_test_app()
    app.state.job_store = job_store
    app.state.schedule_store = schedule_store
    app.state.job_worker = job_worker
    app.state.workspace_loader = mock_workspace_loader
    jobs.set_job_store(job_store)
    jobs.set_job_worker(job_worker)
    schedules.set_schedule_store(schedule_store)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_job(job_store: JobStore) -> Job:
    """Provide a sample job in the store."""
    job = Job(
        workspace_id="TEST-WORKSPACE-01",
        test_group="CONFIG_CHECKS",
        test_ids=["test1", "test2"],
    )
    job_store.create(job)
    return job


@pytest.fixture
def sample_running_job(job_store: JobStore) -> Job:
    """Provide a sample running job in the store."""
    job = Job(
        workspace_id="TEST-WORKSPACE-02",
        test_group="HA_DB_HANA",
    )
    job.start()
    job_store.create(job)
    return job


@pytest.fixture
def sample_schedule(schedule_store: ScheduleStore) -> Schedule:
    """Provide a sample schedule in the store."""
    schedule = Schedule(
        name="Nightly Config Checks",
        cron_expression="0 0 * * *",
        workspace_ids=["WS-01", "WS-02"],
        test_group="CONFIG_CHECKS",
    )
    schedule_store.create(schedule)
    return schedule
