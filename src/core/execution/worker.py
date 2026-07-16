# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Background job worker for async test execution."""

import asyncio
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from src.core.contracts.workspace import WorkspaceMaterializer
from src.core.execution.exceptions import CredentialProvisionError, WorkspaceLockError
from src.core.execution.executor import ExecutorProtocol
from src.core.execution.ssh_provider import SshCredentialProvider
from src.core.models.job import Job, JobEvent, JobEventType, JobStatus
from src.core.models.workspace import MaterializedWorkspace, mutable_workspace_vars
from src.core.observability import ExecutionScope, create_execution_event, get_logger
from src.core.contracts.storage import JobLifecycleProtocol

logger = get_logger(__name__)


class JobWorker:
    """Background worker for async test execution."""

    def __init__(
        self,
        job_store: JobLifecycleProtocol,
        executor: ExecutorProtocol,
        workspace_backend: WorkspaceMaterializer,
        log_dir: Path,
        ssh_provider: SshCredentialProvider | None = None,
    ) -> None:
        """Initialize the job worker."""
        self.job_store = job_store
        self.executor = executor
        self.workspace_backend = workspace_backend
        self._log_dir = log_dir
        self.ssh_provider = ssh_provider or SshCredentialProvider()
        self._running_jobs: dict[str, asyncio.Task] = {}
        self._event_queues: dict[str, asyncio.Queue[JobEvent]] = {}
        logger.info("JobWorker initialized")

    def recover_crashed_jobs(self) -> int:
        """Recover jobs left in non-terminal state after a crash."""
        recovered = 0
        for job in self.job_store.get_active():
            if job.status in (JobStatus.RUNNING, JobStatus.PENDING):
                previous_status = job.status
                job.fail(f"Recovered after restart (was {previous_status})")
                self.job_store.update(job)
                recovered += 1

        if recovered:
            logger.info("Startup recovery: %s orphaned job(s) marked as failed", recovered)
        return recovered

    async def submit_job(self, job: Job) -> Job:
        """Submit a job for async execution."""
        active_job = self.job_store.get_active_for_workspace(job.workspace_id)
        if active_job and active_job.id != job.id:
            logger.warning(
                "Workspace %s already has active job %s", job.workspace_id, active_job.id
            )
            raise WorkspaceLockError(
                workspace_id=job.workspace_id, active_job_id=str(active_job.id)
            )

        self.job_store.create(job)
        self._event_queues[str(job.id)] = asyncio.Queue()
        task = asyncio.create_task(self._execute_job(job))
        self._running_jobs[str(job.id)] = task
        logger.info("Submitted job %s for workspace %s", job.id, job.workspace_id)
        return job

    async def get_job_events(
        self,
        job_id: str,
        timeout: float = 60.0,
    ) -> AsyncGenerator[JobEvent, None]:
        """Stream job events."""
        queue = self._event_queues.get(job_id)
        if not queue:
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                yield event
                if event.event_type in (
                    JobEventType.COMPLETED,
                    JobEventType.FAILED,
                    JobEventType.CANCELLED,
                ):
                    break
            except asyncio.TimeoutError:
                break

    async def cancel_job(self, job_id: str, reason: str = "Cancelled by user") -> bool:
        """Cancel a running job."""
        task = self._running_jobs.get(job_id)
        if not task:
            return False

        self.executor.terminate_process(job_id)
        task.cancel()

        job = self.job_store.get(job_id)
        if job and not job.is_terminal:
            job.cancel(reason)
            self.job_store.update(job)

        logger.info("Cancelled job %s: %s", job_id, reason)
        return True

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the worker, cancelling all running jobs."""
        if not self._running_jobs:
            logger.info("JobWorker shutdown: no running jobs")
            return

        logger.info("JobWorker shutdown: cancelling %s running jobs", len(self._running_jobs))
        for job_id, task in self._running_jobs.items():
            if not task.done():
                self.executor.terminate_process(job_id)
                task.cancel()
                logger.info("Cancelled running job %s", job_id)

        tasks = list(self._running_jobs.values())
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("JobWorker shutdown: timed out after %ss", timeout)

        self._running_jobs.clear()
        self._event_queues.clear()
        logger.info("JobWorker shutdown complete")

    async def _emit_event(self, job_id: str, event: JobEvent) -> None:
        """Emit an event to the job's queue."""
        queue = self._event_queues.get(job_id)
        if queue:
            await queue.put(event)

    async def _execute_job(self, job: Job) -> None:
        """Execute a job in the background."""
        start_time = time.perf_counter()
        ssh_credential = None
        materialized: MaterializedWorkspace | None = None

        with ExecutionScope(execution_id=str(job.id), workspace_id=job.workspace_id):
            try:
                event = job.start()
                self.job_store.update(job)
                await self._emit_event(str(job.id), event)

                logger.event(
                    create_execution_event(
                        "job_start",
                        job_id=str(job.id),
                        workspace_id=job.workspace_id,
                        test_group=job.test_group,
                    )
                )

                materialized = await asyncio.to_thread(
                    self.workspace_backend.materialize,
                    job.workspace_id,
                    str(job.id),
                )
                inventory_path = materialized.inventory_path
                if not inventory_path:
                    raise ValueError(f"No inventory path for workspace {job.workspace_id}")

                workspace_dir = materialized.local_path
                extra_vars = mutable_workspace_vars(materialized.extra_vars)
                extra_vars["_workspace_directory"] = str(workspace_dir)

                private_key_path = None
                ssh_password = None
                if not job.offline:
                    ssh_credential = await asyncio.to_thread(
                        self._provision_ssh_credential,
                        workspace_id=job.workspace_id,
                        extra_vars=extra_vars,
                    )
                    if ssh_credential:
                        private_key_path = ssh_credential.private_key_path
                        ssh_password = ssh_credential.ssh_password
                        logger.info(
                            "SSH credential provisioned for workspace %s (type=%s)",
                            job.workspace_id,
                            ssh_credential.auth_type.value,
                        )

                results = []
                test_ids = job.test_ids or []
                if not job.test_group and not test_ids:
                    raise ValueError("No tests specified for execution")
                if not test_ids:
                    test_ids = [""]

                self._log_dir.mkdir(parents=True, exist_ok=True)
                log_path = self._log_dir / f"{job.id}.log"
                log_path.write_text("", encoding="utf-8")
                job.log_file = str(log_path)
                self.job_store.update(job)

                for test_id in test_ids:
                    if job.status == JobStatus.CANCELLED:
                        break
                    try:
                        result = await asyncio.to_thread(
                            self.executor.run_test,
                            workspace_id=job.workspace_id,
                            test_id=test_id,
                            test_group=job.test_group or "ConfigurationChecks",
                            inventory_path=inventory_path,
                            extra_vars=extra_vars,
                            log_file=log_path,
                            job_id=str(job.id),
                            private_key_path=private_key_path,
                            ssh_password=ssh_password,
                            offline=job.offline,
                        )
                        if result.get("status") == "failed":
                            results.append(
                                {
                                    "test_id": test_id,
                                    "status": "failed",
                                    "error": result.get("error"),
                                }
                            )
                        else:
                            results.append(
                                {"test_id": test_id, "status": "success", "result": result}
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        results.append({"test_id": test_id, "status": "failed", "error": str(exc)})

                if job.status != JobStatus.CANCELLED:
                    all_success = all(result.get("status") == "success" for result in results)
                    summary = {
                        "results": results,
                        "status": "success" if all_success else "partial",
                        "tests_run": len(results),
                        "tests_passed": sum(
                            1 for result in results if result.get("status") == "success"
                        ),
                        "tests_failed": sum(
                            1 for result in results if result.get("status") == "failed"
                        ),
                    }
                    if all_success:
                        event = job.complete(summary, f"All {len(results)} tests completed")
                    else:
                        event = job.complete(
                            summary,
                            (
                                f"Completed: {summary['tests_passed']} passed, "
                                f"{summary['tests_failed']} failed"
                            ),
                        )

                    self.job_store.update(job)
                    await self._emit_event(str(job.id), event)
                    logger.event(
                        create_execution_event(
                            "job_complete",
                            job_id=str(job.id),
                            workspace_id=job.workspace_id,
                            test_group=job.test_group,
                            tests_passed=summary["tests_passed"],
                            tests_failed=summary["tests_failed"],
                            duration_ms=(time.perf_counter() - start_time) * 1000,
                        )
                    )
            except asyncio.CancelledError:
                logger.event(
                    create_execution_event(
                        "job_cancel",
                        job_id=str(job.id),
                        workspace_id=job.workspace_id,
                        reason="User cancelled",
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                    )
                )
                event = job.cancel("Job cancelled")
                self.job_store.update(job)
                await self._emit_event(str(job.id), event)
            except Exception as exc:
                logger.event(
                    create_execution_event(
                        "job_fail",
                        job_id=str(job.id),
                        workspace_id=job.workspace_id,
                        error=str(exc),
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                    )
                )
                event = job.fail(str(exc))
                self.job_store.update(job)
                await self._emit_event(str(job.id), event)
            finally:
                if materialized is not None:
                    try:
                        await asyncio.to_thread(self.workspace_backend.cleanup, materialized)
                    except Exception as cleanup_err:
                        logger.warning(
                            "Workspace cleanup failed for job %s workspace %s: %s",
                            job.id,
                            materialized.workspace_id,
                            cleanup_err,
                            exc_info=True,
                        )
                if ssh_credential:
                    ssh_credential.cleanup()
                self._running_jobs.pop(str(job.id), None)
                self._event_queues.pop(str(job.id), None)

    def _provision_ssh_credential(self, workspace_id: str, extra_vars: dict[str, Any]) -> Any:
        """Provision SSH credentials for a workspace."""
        try:
            return self.ssh_provider.provision(workspace_id=workspace_id, extra_vars=extra_vars)
        except CredentialProvisionError:
            logger.warning(
                "SSH credential provisioning failed for workspace %s — "
                "Ansible will attempt default SSH auth",
                workspace_id,
                exc_info=True,
            )
            return None

    def get_running_job_ids(self) -> list[str]:
        """Get IDs of currently running jobs."""
        return list(self._running_jobs.keys())
