# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for JobWorker."""

import asyncio
from typing import Any, Callable
from uuid import uuid4
import pytest
from pytest_mock import MockerFixture
from src.core.models.job import Job, JobStatus, JobEventType
from src.core.execution.worker import JobWorker
from src.core.execution.exceptions import WorkspaceLockError
from src.core.storage.job_store import JobStore


class TestJobWorker:
    """Unit tests for JobWorker job execution and lifecycle management."""

    @pytest.mark.asyncio
    async def test_submit_returns_job(self, job_worker: JobWorker, sample_job: Job) -> None:
        """Verify submit_job() returns the submitted job."""
        submitted = await job_worker.submit_job(sample_job)
        assert submitted.id == sample_job.id
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_submit_starts_execution(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify submit_job() triggers executor and sets started_at."""
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(workspace_id="WS-01", test_group="test", test_ids=["test_1"])
        await worker.submit_job(job)
        await asyncio.sleep(0.5)
        retrieved = job_store.get(str(job.id))
        assert retrieved is not None
        assert retrieved.started_at is not None
        assert executor.run_test.called

    @pytest.mark.asyncio
    async def test_submit_rejects_duplicate_workspace(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify submit_job() raises WorkspaceLockError for locked workspace."""
        job1 = Job(workspace_id="WS-LOCKED", test_group="test")
        job1.start()
        job_store.create(job1)
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        with pytest.raises(WorkspaceLockError):
            await worker.submit_job(Job(workspace_id="WS-LOCKED", test_group="test"))

    @pytest.mark.asyncio
    async def test_submit_allows_different_workspaces(self, job_worker: JobWorker) -> None:
        """Verify multiple workspaces can run concurrently."""
        await job_worker.submit_job(Job(workspace_id="WS-A", test_group="test"))
        await job_worker.submit_job(Job(workspace_id="WS-B", test_group="test"))
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_job_transitions_to_running(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify job status transitions to RUNNING after submit."""
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(workspace_id="WS-01", test_group="test", test_ids=["t1"])
        await worker.submit_job(job)
        await asyncio.sleep(0.1)
        retrieved = job_store.get(job.id)
        assert retrieved is not None
        assert retrieved.status in (
            JobStatus.RUNNING,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
        )
        await worker.shutdown(timeout=1)

    @pytest.mark.asyncio
    async def test_emits_started_event(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify job emits STARTED event on execution."""
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(workspace_id="WS-01", test_group="test", test_ids=["t1"])
        await worker.submit_job(job)
        events = [e async for e in worker.get_job_events(str(job.id), timeout=2.0)]
        assert JobEventType.STARTED in [e.event_type for e in events]

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self, job_worker: JobWorker) -> None:
        """Verify cancel_job() returns False for unknown job."""
        assert await job_worker.cancel_job(str(uuid4())) is False

    @pytest.mark.asyncio
    async def test_get_events_nonexistent(self, job_worker: JobWorker) -> None:
        """Verify get_job_events() returns empty for unknown job."""
        events = [e async for e in job_worker.get_job_events("nonexistent", timeout=0.1)]
        assert events == []

    @pytest.mark.asyncio
    async def test_event_stream_terminates(self, job_worker: JobWorker, sample_job: Job) -> None:
        """Verify event stream ends with terminal event."""
        await job_worker.submit_job(sample_job)
        events = [e async for e in job_worker.get_job_events(str(sample_job.id), timeout=2.0)]
        assert len(events) >= 1
        assert events[-1].event_type in (
            JobEventType.COMPLETED,
            JobEventType.FAILED,
            JobEventType.CANCELLED,
        )

    @pytest.mark.asyncio
    async def test_shutdown_no_jobs(self, job_worker: JobWorker) -> None:
        """Verify shutdown() completes cleanly with no active jobs."""
        await job_worker.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_shutdown_clears_running(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """Verify shutdown() cancels and clears all running jobs."""
        executor = mocker.MagicMock()
        executor.execute = mocker.AsyncMock(side_effect=lambda j, c: asyncio.sleep(100))
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        for i in range(3):
            await worker.submit_job(Job(workspace_id=f"WS-{i}", test_group="test"))
        await asyncio.sleep(0.1)
        await worker.shutdown(timeout=1.0)
        assert len(worker._running_jobs) == 0

    @pytest.mark.asyncio
    async def test_empty_workspace_config_fails_job(
        self, job_store: JobStore, mocker: MockerFixture
    ) -> None:
        """Verify job fails when workspace config is empty."""
        executor = mocker.MagicMock()
        executor.execute = mocker.AsyncMock(return_value={"status": "success"})
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=lambda ws: {},
        )
        job = Job(workspace_id="WS-EMPTY", test_group="test")
        await worker.submit_job(job)
        await asyncio.sleep(0.3)
        retrieved = job_store.get(job.id)
        assert retrieved is not None
        assert retrieved.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_workspace_loader_exception_fails_job(
        self, job_store: JobStore, mocker: MockerFixture
    ) -> None:
        """Verify job fails when workspace loader raises exception."""
        executor = mocker.MagicMock()

        def loader(ws: str) -> dict[str, Any]:
            raise RuntimeError("Config not found")

        worker = JobWorker(job_store=job_store, executor=executor, workspace_config_loader=loader)
        job = Job(workspace_id="WS-ERR", test_group="test")
        await worker.submit_job(job)
        await asyncio.sleep(0.3)
        retrieved = job_store.get(job.id)
        assert retrieved is not None
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error is not None
        assert "Config not found" in retrieved.error
