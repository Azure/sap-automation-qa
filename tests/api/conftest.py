# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Fixtures for API tests."""

import tempfile
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import jobs, schedules
from src.api.routes.workspaces import set_workspace_backend
from src.core.execution.worker import JobWorker
from src.core.models.job import Job
from src.core.models.schedule import Schedule
from src.core.models.workspace import MaterializedWorkspace, WorkspaceConfig, WorkspaceSummary
from src.core.storage.job_store import JobStore
from src.core.storage.schedule_store import ScheduleStore


class ApiWorkspaceBackend:
    """Simple backend used by API tests."""

    backend_name = "filesystem"

    def __init__(self, root: Path) -> None:
        self.root = root

    def list_workspaces(self) -> list[WorkspaceSummary]:
        return [
            WorkspaceSummary(
                workspace_id=ws_id, name=ws_id, environment="test", path=str(self.root / ws_id)
            )
            for ws_id in (
                "NEW-WORKSPACE",
                "EXEC-TEST",
                "WS",
                "WS-A",
                "WS-B",
                "TEST-WORKSPACE-01",
                "TEST-WORKSPACE-02",
            )
        ]

    def get_workspace_config(self, workspace_id: str) -> WorkspaceConfig:
        if workspace_id not in {summary.workspace_id for summary in self.list_workspaces()}:
            from src.core.exceptions import WorkspaceNotFoundError

            raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")
        workspace_dir = self.root / workspace_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        inventory = workspace_dir / "hosts.yaml"
        inventory.write_text("all:\n  hosts:\n    node1:\n", encoding="utf-8")
        return WorkspaceConfig(
            workspace_id=workspace_id,
            inventory_path=str(inventory),
            sap_sid=workspace_id,
            extra_vars={"sap_sid": workspace_id},
            path=str(workspace_dir),
        )

    def materialize(self, workspace_id: str, job_id: str) -> MaterializedWorkspace:
        config = self.get_workspace_config(workspace_id)
        return MaterializedWorkspace(
            workspace_id=workspace_id,
            job_id=job_id,
            local_path=Path(config.path),
            inventory_path=config.inventory_path,
            extra_vars=config.extra_vars,
            owned=False,
        )

    def cleanup(self, materialized: MaterializedWorkspace) -> None:
        return None

    def close(self) -> None:
        return None


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app for testing."""
    from src.api.routes.health import router as health_router
    from src.api.routes.jobs import router as jobs_router
    from src.api.routes.schedules import router as schedules_router
    from src.api.routes.workspaces import router as workspaces_router

    app = FastAPI(title="Test API")
    app.include_router(health_router)
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(schedules_router, prefix="/api/v1")
    app.include_router(workspaces_router, prefix="/api/v1")
    return app


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


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
def workspace_backend(temp_dir: Path) -> ApiWorkspaceBackend:
    return ApiWorkspaceBackend(temp_dir / "api-workspaces")


@pytest.fixture
def mock_executor(mocker: Any) -> Any:
    executor = mocker.MagicMock()
    executor.run_test = mocker.MagicMock(return_value={"status": "success"})
    executor.terminate_process = mocker.MagicMock(return_value=False)
    return executor


@pytest.fixture
def job_worker(
    job_store: JobStore,
    workspace_backend: ApiWorkspaceBackend,
    mock_executor: Any,
    temp_dir: Path,
) -> JobWorker:
    return JobWorker(
        job_store=job_store,
        executor=mock_executor,
        workspace_backend=workspace_backend,
        log_dir=temp_dir / "job-logs",
    )


@pytest.fixture
def client(
    job_store: JobStore,
    schedule_store: ScheduleStore,
    job_worker: JobWorker,
    workspace_backend: ApiWorkspaceBackend,
) -> Generator[TestClient, None, None]:
    app = create_test_app()
    app.state.job_store = job_store
    app.state.schedule_store = schedule_store
    app.state.job_worker = job_worker
    jobs.set_job_store(job_store)
    jobs.set_job_worker(job_worker)
    schedules.set_schedule_store(schedule_store)
    set_workspace_backend(workspace_backend)
    with TestClient(app) as test_client:
        yield test_client
    set_workspace_backend(None)


@pytest.fixture
def sample_job(job_store: JobStore) -> Job:
    job = Job(
        id=uuid4(),
        workspace_id="TEST-WORKSPACE-01",
        test_group="ConfigurationChecks",
        test_ids=["test1", "test2"],
    )
    job_store.create(job)
    return job


@pytest.fixture
def sample_running_job(job_store: JobStore) -> Job:
    job = Job(id=uuid4(), workspace_id="TEST-WORKSPACE-02", test_group="DatabaseHighAvailability")
    job.start()
    job_store.create(job)
    return job


@pytest.fixture
def sample_schedule(schedule_store: ScheduleStore) -> Schedule:
    schedule = Schedule(
        name="Nightly Config Checks",
        cron_expression="0 0 * * *",
        workspace_ids=["WS-01", "WS-02"],
        test_group="ConfigurationChecks",
    )
    schedule_store.create(schedule)
    return schedule
