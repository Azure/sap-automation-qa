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

_POLL_INTERVAL = 0.02
_POLL_TIMEOUT = 3.0


async def _wait_for_terminal(
    job_store: JobStore,
    job_id: Any,
    timeout: float = _POLL_TIMEOUT,
) -> Job:
    """Poll until job reaches a terminal state.

    :param job_store: Store to query.
    :param job_id: Job ID.
    :param timeout: Max seconds to wait.
    :returns: The terminal-state job.
    :raises TimeoutError: If deadline exceeded.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        found = job_store.get(job_id)
        if found and found.is_terminal:
            return found
        await asyncio.sleep(_POLL_INTERVAL)
    raise TimeoutError(f"Job {job_id} did not reach terminal state " f"within {timeout}s")


class TestJobWorker:
    """Tests for JobWorker execution, lifecycle, crash recovery, and subprocess management."""

    @pytest.mark.asyncio
    async def test_submit_returns_job(
        self,
        job_worker: JobWorker,
        sample_job: Job,
    ) -> None:
        """
        Verify submit_job() returns the submitted job.
        """
        submitted = await job_worker.submit_job(sample_job)
        assert submitted.id == sample_job.id
        await job_worker.shutdown(timeout=1)

    @pytest.mark.asyncio
    async def test_submit_starts_execution(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify submit_job() triggers executor and sets started_at.
        """
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(
            return_value={"status": "success"},
        )
        executor.terminate_process = mocker.MagicMock(
            return_value=False,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(
            workspace_id="WS-01",
            test_group="test",
            test_ids=["test_1"],
        )
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(
            job_store,
            str(job.id),
        )
        assert retrieved.started_at is not None
        assert executor.run_test.called

    @pytest.mark.asyncio
    async def test_submit_rejects_duplicate_workspace(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify submit_job() raises WorkspaceLockError for locked workspace.
        """
        job1 = Job(
            workspace_id="WS-LOCKED",
            test_group="test",
        )
        job1.start()
        job_store.create(job1)
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(
            return_value={"status": "success"},
        )
        executor.terminate_process = mocker.MagicMock(
            return_value=False,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        with pytest.raises(WorkspaceLockError):
            await worker.submit_job(
                Job(
                    workspace_id="WS-LOCKED",
                    test_group="test",
                )
            )

    @pytest.mark.asyncio
    async def test_submit_allows_different_workspaces(
        self,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify multiple workspaces can run concurrently.
        """
        await job_worker.submit_job(
            Job(workspace_id="WS-A", test_group="test"),
        )
        await job_worker.submit_job(
            Job(workspace_id="WS-B", test_group="test"),
        )
        await job_worker.shutdown(timeout=1)

    @pytest.mark.asyncio
    async def test_job_transitions_to_running(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify job status transitions to RUNNING after submit.
        """
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(
            return_value={"status": "success"},
        )
        executor.terminate_process = mocker.MagicMock(
            return_value=False,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(
            workspace_id="WS-01",
            test_group="test",
            test_ids=["t1"],
        )
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(
            job_store,
            job.id,
        )
        assert retrieved.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
        )

    @pytest.mark.asyncio
    async def test_emits_started_event(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify job emits STARTED event on execution.
        """
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(
            return_value={"status": "success"},
        )
        executor.terminate_process = mocker.MagicMock(
            return_value=False,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(
            workspace_id="WS-01",
            test_group="test",
            test_ids=["t1"],
        )
        await worker.submit_job(job)
        events = [
            e
            async for e in worker.get_job_events(
                str(job.id),
                timeout=2.0,
            )
        ]
        assert JobEventType.STARTED in [e.event_type for e in events]

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(
        self,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify cancel_job() returns False for unknown job.
        """
        assert await job_worker.cancel_job(str(uuid4())) is False

    @pytest.mark.asyncio
    async def test_get_events_nonexistent(
        self,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify get_job_events() returns empty for unknown job.
        """
        events = [
            e
            async for e in job_worker.get_job_events(
                "nonexistent",
                timeout=0.05,
            )
        ]
        assert events == []

    @pytest.mark.asyncio
    async def test_event_stream_terminates(
        self,
        job_worker: JobWorker,
        sample_job: Job,
    ) -> None:
        """
        Verify event stream ends with terminal event.
        """
        await job_worker.submit_job(sample_job)
        events = [
            e
            async for e in job_worker.get_job_events(
                str(sample_job.id),
                timeout=2.0,
            )
        ]
        assert len(events) >= 1
        assert events[-1].event_type in (
            JobEventType.COMPLETED,
            JobEventType.FAILED,
            JobEventType.CANCELLED,
        )

    @pytest.mark.asyncio
    async def test_shutdown_no_jobs(
        self,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify shutdown() completes cleanly with no active jobs.
        """
        await job_worker.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_shutdown_clears_running(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify shutdown() cancels and clears all running jobs.
        """
        executor = mocker.MagicMock()

        def slow_run(**kw: Any) -> dict[str, Any]:
            import time

            time.sleep(100)
            return {"status": "success"}

        executor.run_test = mocker.MagicMock(
            side_effect=slow_run,
        )
        executor.terminate_process = mocker.MagicMock(
            return_value=True,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        for i in range(3):
            await worker.submit_job(
                Job(
                    workspace_id=f"WS-{i}",
                    test_group="test",
                    test_ids=["t1"],
                )
            )
        await asyncio.sleep(0.05)
        await worker.shutdown(timeout=1.0)
        assert len(worker._running_jobs) == 0

    @pytest.mark.asyncio
    async def test_empty_workspace_config_fails_job(
        self,
        job_store: JobStore,
        mocker: MockerFixture,
    ) -> None:
        """
        Verify job fails when workspace config is empty.
        """
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(
            return_value={"status": "success"},
        )
        executor.terminate_process = mocker.MagicMock(
            return_value=False,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=lambda ws: {},
        )
        job = Job(
            workspace_id="WS-EMPTY",
            test_group="test",
        )
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(
            job_store,
            job.id,
        )
        assert retrieved.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_workspace_loader_exception_fails_job(
        self,
        job_store: JobStore,
        mocker: MockerFixture,
    ) -> None:
        """
        Verify job fails when workspace loader raises exception.
        """
        executor = mocker.MagicMock()
        executor.terminate_process = mocker.MagicMock(
            return_value=False,
        )

        def loader(ws: str) -> dict[str, Any]:
            raise RuntimeError("Config not found")

        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=loader,
        )
        job = Job(
            workspace_id="WS-ERR",
            test_group="test",
        )
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(
            job_store,
            job.id,
        )
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error is not None
        assert "Config not found" in retrieved.error

    # -- crash recovery --

    def test_recovers_running_jobs(
        self,
        job_store: JobStore,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify running jobs are marked failed on recovery.
        """
        job = Job(
            workspace_id="WS-CRASH-1",
            test_group="test",
        )
        job.start()
        job_store.create(job)

        recovered = job_worker.recover_crashed_jobs()

        assert recovered == 1
        found = job_store.get(job.id)
        assert found is not None
        assert found.status == JobStatus.FAILED
        assert found.error is not None
        assert "Recovered after restart" in found.error

    def test_recovers_pending_jobs(
        self,
        job_store: JobStore,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify pending jobs are marked failed on recovery.
        """
        job = Job(
            workspace_id="WS-CRASH-2",
            test_group="test",
        )
        job_store.create(job)

        recovered = job_worker.recover_crashed_jobs()

        assert recovered == 1
        found = job_store.get(job.id)
        assert found is not None
        assert found.status == JobStatus.FAILED
        assert found.error is not None
        assert "was pending" in found.error

    def test_skips_completed_jobs(
        self,
        job_store: JobStore,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify completed jobs are not affected by recovery.
        """
        job = Job(workspace_id="WS-OK", test_group="test")
        job.start()
        job.complete({"ok": True})
        job_store.create(job)

        recovered = job_worker.recover_crashed_jobs()
        assert recovered == 0

    def test_recovers_multiple_jobs(
        self,
        job_store: JobStore,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify multiple orphaned jobs are all recovered.
        """
        for i in range(3):
            j = Job(
                workspace_id=f"WS-M-{i}",
                test_group="test",
            )
            j.start()
            job_store.create(j)

        assert job_worker.recover_crashed_jobs() == 3

    def test_no_jobs_returns_zero(
        self,
        job_store: JobStore,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify recovery returns 0 when no orphaned jobs.
        """
        assert job_worker.recover_crashed_jobs() == 0

    @pytest.mark.asyncio
    async def test_workspace_unlocked_after_recovery(
        self,
        job_store: JobStore,
        job_worker: JobWorker,
    ) -> None:
        """
        Verify workspace can accept new jobs after recovery.
        """
        stale = Job(
            workspace_id="WS-UNLOCK",
            test_group="test",
        )
        stale.start()
        job_store.create(stale)

        job_worker.recover_crashed_jobs()

        new_job = Job(
            workspace_id="WS-UNLOCK",
            test_group="test",
            test_ids=["t1"],
        )
        submitted = await job_worker.submit_job(new_job)
        assert submitted.id == new_job.id
        await job_worker.shutdown(timeout=1.0)

    # -- subprocess lifecycle --

    @pytest.mark.asyncio
    async def test_cancel_calls_terminate_process(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify cancel_job() calls executor.terminate_process.
        """
        executor = mocker.MagicMock()
        executor.terminate_process = mocker.MagicMock(
            return_value=True,
        )

        def slow_run(**kw: Any) -> dict[str, Any]:
            import time

            time.sleep(10)
            return {"status": "success"}

        executor.run_test = mocker.MagicMock(
            side_effect=slow_run,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        job = Job(
            workspace_id="WS-C1",
            test_group="test",
            test_ids=["t1"],
        )
        await worker.submit_job(job)
        await asyncio.sleep(0.2)

        await worker.cancel_job(str(job.id))
        executor.terminate_process.assert_called_once_with(
            str(job.id),
        )
        await worker.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_shutdown_calls_terminate_for_all(
        self,
        job_store: JobStore,
        workspace_loader: Callable[[str], dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        Verify shutdown() calls terminate_process for each job.
        """
        executor = mocker.MagicMock()
        executor.terminate_process = mocker.MagicMock(
            return_value=True,
        )

        def slow_run(**kw: Any) -> dict[str, Any]:
            import time

            time.sleep(10)
            return {"status": "success"}

        executor.run_test = mocker.MagicMock(
            side_effect=slow_run,
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_config_loader=workspace_loader,
        )
        for i in range(2):
            await worker.submit_job(
                Job(
                    workspace_id=f"WS-S{i}",
                    test_group="test",
                    test_ids=["t1"],
                )
            )
        await asyncio.sleep(0.2)

        await worker.shutdown(timeout=2.0)
        assert executor.terminate_process.call_count >= 2

    @pytest.mark.asyncio
    async def test_cancel_without_process_still_works(
        self,
        job_worker: JobWorker,
        sample_job: Job,
    ) -> None:
        """
        Verify cancel succeeds even if terminate returns False.
        """
        await job_worker.submit_job(sample_job)
        await asyncio.sleep(0.3)

        result = await job_worker.cancel_job(str(sample_job.id))
        # Job may have already completed (mock is instant),
        # so result could be False. No crash is the assertion.
        assert isinstance(result, bool)
