# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Background job worker for async test execution."""

import asyncio
import time
from typing import Any, AsyncGenerator, Callable
from src.core.models.job import Job, JobEvent, JobEventType, JobStatus
from src.core.storage.job_store import JobStore
from src.core.execution.executor import TestExecutor
from src.core.execution.exceptions import WorkspaceLockError
from src.core.observability import (
    get_logger,
    ExecutionScope,
    create_execution_event,
)

logger = get_logger(__name__)


class JobWorker:
    """Background worker for async test execution."""

    def __init__(
        self,
        job_store: JobStore,
        executor: TestExecutor,
        workspace_config_loader: Callable[[str], dict[str, Any]],
    ) -> None:
        """Initialize the job worker.

        :param job_store: Job store for persistence
        :param executor: Test executor implementation
        :param workspace_config_loader: Function to load workspace config by ID
        """
        self.job_store = job_store
        self.executor = executor
        self.workspace_config_loader = workspace_config_loader
        self._running_jobs: dict[str, asyncio.Task] = {}
        self._event_queues: dict[str, asyncio.Queue[JobEvent]] = {}

        logger.info("JobWorker initialized")

    async def submit_job(self, job: Job) -> Job:
        """Submit a job for async execution.

        :param job: Job to execute
        :returns: The submitted job
        :raises WorkspaceLockError: If workspace already has an active job
        """
        active_job = self.job_store.get_active_for_workspace(job.workspace_id)
        if active_job and active_job.id != job.id:
            logger.warning(f"Workspace {job.workspace_id} already has active job {active_job.id}")
            raise WorkspaceLockError(
                workspace_id=job.workspace_id,
                active_job_id=str(active_job.id),
            )

        self.job_store.create(job)

        self._event_queues[str(job.id)] = asyncio.Queue()
        task = asyncio.create_task(self._execute_job(job))
        self._running_jobs[str(job.id)] = task

        logger.info(f"Submitted job {job.id} for workspace {job.workspace_id}")
        return job

    async def get_job_events(
        self,
        job_id: str,
        timeout: float = 60.0,
    ) -> AsyncGenerator[JobEvent, None]:
        """Stream job events.

        :param job_id: Job ID to stream events for
        :param timeout: Timeout for waiting on events
        :yields: Job events
        """
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
        """Cancel a running job.

        :param job_id: Job ID to cancel
        :param reason: Cancellation reason
        :returns: True if cancelled successfully
        """
        task = self._running_jobs.get(job_id)
        if not task:
            return False

        task.cancel()

        job = self.job_store.get(job_id)
        if job and not job.is_terminal:
            job.cancel(reason)
            self.job_store.update(job)

        logger.info(f"Cancelled job {job_id}: {reason}")
        return True

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the worker, cancelling all running jobs.

        :param timeout: Maximum time to wait for jobs to complete.
        :type timeout: float
        """
        if not self._running_jobs:
            logger.info("JobWorker shutdown: no running jobs")
            return

        logger.info(f"JobWorker shutdown: cancelling {len(self._running_jobs)} running jobs")

        # Cancel all running tasks
        for job_id, task in self._running_jobs.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled running job {job_id}")

        # Wait for all tasks to complete with timeout
        if self._running_jobs:
            tasks = list(self._running_jobs.values())
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"JobWorker shutdown: timed out after {timeout}s")

        self._running_jobs.clear()
        self._event_queues.clear()
        logger.info("JobWorker shutdown complete")

    async def _emit_event(self, job_id: str, event: JobEvent) -> None:
        """Emit an event to the job's queue.

        Adds an event to the async queue for streaming to subscribers.

        :param job_id: ID of the job to emit event for.
        :type job_id: str
        :param event: Event to emit.
        :type event: JobEvent
        """
        queue = self._event_queues.get(job_id)
        if queue:
            await queue.put(event)

    async def _execute_job(self, job: Job) -> None:
        """Execute a job in the background.

        :param job: Job to execute
        """
        start_time = time.perf_counter()

        with ExecutionScope(
            execution_id=str(job.id),
            workspace_id=job.workspace_id,
        ):
            try:
                event = job.start()
                self.job_store.update(job)
                await self._emit_event(str(job.id), event)

                logger.event(create_execution_event(
                    "job_start",
                    job_id=str(job.id),
                    workspace_id=job.workspace_id,
                    test_group=job.test_group,
                ))

                workspace_config = self.workspace_config_loader(job.workspace_id)
                if not workspace_config:
                    raise ValueError(f"Workspace {job.workspace_id} not found")

                inventory_path = workspace_config.get("inventory_path", "")
                if not inventory_path:
                    raise ValueError(f"No inventory path for workspace {job.workspace_id}")

                results = []
                test_ids = job.test_ids or ([""] if job.test_group else [])

                if not test_ids:
                    raise ValueError("No tests specified for execution")

                job.total_steps = len(test_ids)

                for idx, test_id in enumerate(test_ids):
                    if job.status == JobStatus.CANCELLED:
                        break

                    step_name = f"Test: {test_id}" if test_id else f"Group: {job.test_group}"
                    event = job.step_started(idx, step_name, f"Starting {step_name}...")
                    self.job_store.update(job)
                    await self._emit_event(str(job.id), event)

                    logger.event(create_execution_event(
                        "step_start",
                        job_id=str(job.id),
                        step_index=idx,
                        step_name=step_name,
                        test_id=test_id,
                    ))
                    step_start = time.perf_counter()

                    try:
                        result = await asyncio.to_thread(
                            self.executor.run_test,
                            workspace_id=job.workspace_id,
                            test_id=test_id,
                            test_group=job.test_group or "CONFIG_CHECKS",
                            inventory_path=inventory_path,
                            extra_vars=workspace_config.get("extra_vars"),
                        )
                        step_duration_ms = (time.perf_counter() - step_start) * 1000

                        if result.get("status") == "failed":
                            event = job.step_failed(
                                idx, step_name, result.get("error", "Unknown error")
                            )
                            await self._emit_event(str(job.id), event)
                            logger.event(create_execution_event(
                                "step_fail",
                                job_id=str(job.id),
                                step_index=idx,
                                step_name=step_name,
                                test_id=test_id,
                                error=result.get("error", "Unknown error"),
                                duration_ms=step_duration_ms,
                            ))
                            results.append(
                                {
                                    "test_id": test_id,
                                    "status": "failed",
                                    "error": result.get("error"),
                                }
                            )
                        else:
                            event = job.step_completed(idx, step_name, f"{step_name} completed")
                            await self._emit_event(str(job.id), event)
                            logger.event(create_execution_event(
                                "step_complete",
                                job_id=str(job.id),
                                step_index=idx,
                                step_name=step_name,
                                test_id=test_id,
                                duration_ms=step_duration_ms,
                            ))
                            results.append(
                                {
                                    "test_id": test_id,
                                    "status": "success",
                                    "result": result,
                                }
                            )

                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        event = job.step_failed(idx, step_name, str(e))
                        await self._emit_event(str(job.id), event)
                        logger.event(create_execution_event(
                            "step_fail",
                            job_id=str(job.id),
                            step_index=idx,
                            step_name=step_name,
                            error=str(e),
                        ))
                        results.append({"test_id": test_id, "status": "failed", "error": str(e)})

                    self.job_store.update(job)

                if job.status != JobStatus.CANCELLED:
                    all_success = all(r.get("status") == "success" for r in results)
                    summary = {
                        "results": results,
                        "status": "success" if all_success else "partial",
                        "tests_run": len(results),
                        "tests_passed": sum(1 for r in results if r.get("status") == "success"),
                        "tests_failed": sum(1 for r in results if r.get("status") == "failed"),
                    }

                    if all_success:
                        event = job.complete(summary, f"All {len(results)} tests completed")
                    else:
                        passed = summary["tests_passed"]
                        failed = summary["tests_failed"]
                        event = job.complete(summary, f"Completed: {passed} passed, {failed} failed")

                    self.job_store.update(job)
                    await self._emit_event(str(job.id), event)

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.event(create_execution_event(
                        "job_complete",
                        job_id=str(job.id),
                        workspace_id=job.workspace_id,
                        test_group=job.test_group,
                        tests_passed=summary["tests_passed"],
                        tests_failed=summary["tests_failed"],
                        duration_ms=duration_ms,
                    ))

            except asyncio.CancelledError:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.event(create_execution_event(
                    "job_cancel",
                    job_id=str(job.id),
                    workspace_id=job.workspace_id,
                    reason="User cancelled",
                    duration_ms=duration_ms,
                ))
                event = job.cancel("Job cancelled")
                self.job_store.update(job)
                await self._emit_event(str(job.id), event)

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.event(create_execution_event(
                    "job_fail",
                    job_id=str(job.id),
                    workspace_id=job.workspace_id,
                    error=str(e),
                    duration_ms=duration_ms,
                ))
                event = job.fail(str(e))
                self.job_store.update(job)
                await self._emit_event(str(job.id), event)

            finally:
                if str(job.id) in self._running_jobs:
                    del self._running_jobs[str(job.id)]
                if str(job.id) in self._event_queues:
                    del self._event_queues[str(job.id)]

    def get_running_job_ids(self) -> list[str]:
        """Get IDs of currently running jobs."""
        return list(self._running_jobs.keys())
