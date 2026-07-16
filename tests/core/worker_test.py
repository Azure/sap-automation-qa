# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for JobWorker."""

import asyncio
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from src.core.execution.exceptions import WorkspaceLockError
from src.core.execution.worker import JobWorker
from src.core.models.job import Job, JobEventType, JobStatus
from src.core.models.workspace import MaterializedWorkspace
from src.core.storage.job_store import JobStore

_POLL_INTERVAL = 0.02
_POLL_TIMEOUT = 3.0


async def _wait_for_terminal(
    job_store: JobStore, job_id: Any, timeout: float = _POLL_TIMEOUT
) -> Job:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        found = job_store.get(job_id)
        if found and found.is_terminal:
            return found
        await asyncio.sleep(_POLL_INTERVAL)
    raise TimeoutError(f"Job {job_id} did not reach terminal state within {timeout}s")


def _materialized(temp_dir: Path, workspace_id: str, job_id: str) -> MaterializedWorkspace:
    workspace_dir = temp_dir / workspace_id
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


class TestJobWorker:
    """Tests for JobWorker execution and lifecycle."""

    @pytest.mark.asyncio
    async def test_submit_returns_job(self, job_worker: JobWorker, sample_job: Job) -> None:
        submitted = await job_worker.submit_job(sample_job)
        assert submitted.id == sample_job.id
        await job_worker.shutdown(timeout=1)

    @pytest.mark.asyncio
    async def test_submit_starts_execution(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        executor.terminate_process = mocker.MagicMock(return_value=False)
        backend = mocker.MagicMock()
        backend.materialize.side_effect = lambda workspace_id, job_id: _materialized(
            temp_dir, workspace_id, job_id
        )
        backend.cleanup = mocker.MagicMock()
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        job = Job(workspace_id="WS-01", test_group="test", test_ids=["test_1"])
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(job_store, str(job.id))
        assert retrieved.started_at is not None
        assert executor.run_test.called
        backend.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_offline_job_skips_ssh_and_forwards_offline(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()
        executor.run_test.return_value = {"status": "success"}
        executor.terminate_process.return_value = False
        backend = mocker.MagicMock()
        backend.materialize.side_effect = lambda workspace_id, job_id: _materialized(
            temp_dir, workspace_id, job_id
        )
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        provision = mocker.patch.object(worker, "_provision_ssh_credential")
        job = Job(
            workspace_id="WS-OFFLINE",
            test_group="DatabaseHighAvailability",
            test_ids=["ha-config-offline"],
            offline=True,
        )

        await worker.submit_job(job)
        await _wait_for_terminal(job_store, job.id)

        provision.assert_not_called()
        call = executor.run_test.call_args.kwargs
        assert call["offline"] is True
        assert call["private_key_path"] is None
        assert call["ssh_password"] is None

    @pytest.mark.asyncio
    async def test_submit_rejects_duplicate_workspace(
        self, job_store: JobStore, workspace_backend: Any, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        job1 = Job(workspace_id="WS-LOCKED", test_group="test")
        job1.start()
        job_store.create(job1)
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        executor.terminate_process = mocker.MagicMock(return_value=False)
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=workspace_backend,
            log_dir=temp_dir / "job-logs",
        )
        with pytest.raises(WorkspaceLockError):
            await worker.submit_job(Job(workspace_id="WS-LOCKED", test_group="test"))

    @pytest.mark.asyncio
    async def test_emits_started_event(
        self, job_store: JobStore, workspace_backend: Any, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        executor.terminate_process = mocker.MagicMock(return_value=False)
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=workspace_backend,
            log_dir=temp_dir / "job-logs",
        )
        job = Job(workspace_id="WS-01", test_group="test", test_ids=["t1"])
        await worker.submit_job(job)
        events = [event async for event in worker.get_job_events(str(job.id), timeout=2.0)]
        assert JobEventType.STARTED in [event.event_type for event in events]

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self, job_worker: JobWorker) -> None:
        assert await job_worker.cancel_job(str(uuid4())) is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_running(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()

        def slow_run(**kw: Any) -> dict[str, Any]:
            import time

            time.sleep(10)
            return {"status": "success"}

        executor.run_test = mocker.MagicMock(side_effect=slow_run)
        executor.terminate_process = mocker.MagicMock(return_value=True)
        backend = mocker.MagicMock()
        backend.materialize.side_effect = lambda workspace_id, job_id: _materialized(
            temp_dir, workspace_id, job_id
        )
        backend.cleanup = mocker.MagicMock()
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        for index in range(2):
            await worker.submit_job(
                Job(workspace_id=f"WS-{index}", test_group="test", test_ids=["t1"])
            )
        await asyncio.sleep(0.05)
        await worker.shutdown(timeout=1.0)
        assert len(worker._running_jobs) == 0
        assert executor.terminate_process.call_count >= 2

    @pytest.mark.asyncio
    async def test_materialize_exception_fails_job(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()
        executor.terminate_process = mocker.MagicMock(return_value=False)
        backend = mocker.MagicMock()
        backend.materialize.side_effect = RuntimeError("Config not found")
        backend.cleanup = mocker.MagicMock()
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        job = Job(workspace_id="WS-ERR", test_group="test")
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(job_store, job.id)
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error is not None
        assert "Config not found" in retrieved.error
        backend.cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_exception_is_logged(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()
        executor.run_test = mocker.MagicMock(return_value={"status": "success"})
        executor.terminate_process = mocker.MagicMock(return_value=False)
        backend = mocker.MagicMock()
        backend.materialize.side_effect = lambda workspace_id, job_id: MaterializedWorkspace(
            workspace_id=workspace_id,
            job_id=job_id,
            local_path=temp_dir / workspace_id,
            inventory_path=str((temp_dir / workspace_id / "hosts.yaml")),
            extra_vars={},
            owned=True,
        )
        (temp_dir / "WS-CLEAN").mkdir(parents=True, exist_ok=True)
        (temp_dir / "WS-CLEAN" / "hosts.yaml").write_text("all:\n", encoding="utf-8")
        backend.cleanup.side_effect = RuntimeError("cleanup failed")
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        job = Job(workspace_id="WS-CLEAN", test_group="test", test_ids=["t1"])
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(job_store, job.id)
        assert retrieved.status == JobStatus.COMPLETED
        backend.cleanup.assert_called_once()

    def test_recovers_running_jobs(self, job_store: JobStore, job_worker: JobWorker) -> None:
        job = Job(workspace_id="WS-CRASH-1", test_group="test")
        job.start()
        job_store.create(job)
        recovered = job_worker.recover_crashed_jobs()
        assert recovered == 1
        found = job_store.get(job.id)
        assert found is not None
        assert found.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_cancel_calls_terminate_process(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()
        executor.terminate_process = mocker.MagicMock(return_value=True)

        def slow_run(**kw: Any) -> dict[str, Any]:
            import time

            time.sleep(10)
            return {"status": "success"}

        executor.run_test = mocker.MagicMock(side_effect=slow_run)
        backend = mocker.MagicMock()
        backend.materialize.side_effect = lambda workspace_id, job_id: _materialized(
            temp_dir, workspace_id, job_id
        )
        backend.cleanup = mocker.MagicMock()
        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        job = Job(workspace_id="WS-C1", test_group="test", test_ids=["t1"])
        await worker.submit_job(job)
        await asyncio.sleep(0.2)
        await worker.cancel_job(str(job.id))
        executor.terminate_process.assert_called_once_with(str(job.id))
        await worker.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_log_file_survives_owned_workspace_cleanup(
        self, job_store: JobStore, temp_dir: Path, mocker: MockerFixture
    ) -> None:
        executor = mocker.MagicMock()

        def run_test(**kwargs: Any) -> dict[str, Any]:
            log_file = kwargs["log_file"]
            log_file.write_text("job ran\n", encoding="utf-8")
            return {"status": "success"}

        executor.run_test = mocker.MagicMock(side_effect=run_test)
        executor.terminate_process = mocker.MagicMock(return_value=False)

        workspace_dir = temp_dir / "owned-workspaces" / "WS-LOG"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = workspace_dir / "hosts.yaml"
        inventory_path.write_text("all:\n  hosts:\n    node1:\n", encoding="utf-8")
        materialized = MaterializedWorkspace(
            workspace_id="WS-LOG",
            job_id=str(uuid4()),
            local_path=workspace_dir,
            inventory_path=str(inventory_path),
            extra_vars={},
            owned=True,
        )

        backend = mocker.MagicMock()
        backend.materialize.side_effect = lambda workspace_id, job_id: materialized
        backend.cleanup.side_effect = lambda workspace: shutil.rmtree(workspace.local_path)

        worker = JobWorker(
            job_store=job_store,
            executor=executor,
            workspace_backend=backend,
            log_dir=temp_dir / "job-logs",
        )
        job = Job(workspace_id="WS-LOG", test_group="test", test_ids=["t1"])
        await worker.submit_job(job)
        retrieved = await _wait_for_terminal(job_store, job.id)

        assert retrieved.log_file is not None
        log_path = Path(retrieved.log_file)
        assert log_path.exists()
        assert log_path.read_text(encoding="utf-8") == "job ran\n"
        assert not materialized.local_path.exists()
