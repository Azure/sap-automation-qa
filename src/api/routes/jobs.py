# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Jobs API routes
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from src.api.routes.workspaces import _load_workspaces_from_directory
from src.core.models.job import Job, JobStatus, CreateJobRequest, CancelJobRequest, JobListResponse
from src.core.storage.job_store import JobStore
from src.core.execution.worker import JobWorker
from src.core.execution.executor import TEST_GROUP_PLAYBOOKS
from src.core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])
_job_store: Optional[JobStore] = None
_job_worker: Optional[JobWorker] = None


def set_job_store(store: JobStore) -> None:
    """Set the job store instance.

    :param store: JobStore instance for persistence.
    :type store: JobStore
    """
    global _job_store
    _job_store = store


def set_job_worker(worker: JobWorker) -> None:
    """Set the job worker instance.

    :param worker: JobWorker instance for executing jobs.
    :type worker: JobWorker
    """
    global _job_worker
    _job_worker = worker


def get_job_store() -> JobStore:
    """Get the job store instance.

    :returns: The configured JobStore instance.
    :rtype: JobStore
    :raises HTTPException: If store not initialized (503 error).
    """
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized")
    return _job_store


def get_job_worker() -> JobWorker:
    """Get the job worker instance.

    :returns: The configured JobWorker instance.
    :rtype: JobWorker
    :raises HTTPException: If worker not initialized (503 error).
    """
    if _job_worker is None:
        raise HTTPException(status_code=503, detail="Job worker not initialized")
    return _job_worker


@router.get("", response_model=JobListResponse)
async def list_jobs(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace"),
    status: Optional[str] = Query(None, description="Filter by status"),
    active_only: bool = Query(False, description="Only show active jobs"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> JobListResponse:
    """List execution jobs.

    :param workspace_id: Filter jobs by workspace ID.
    :type workspace_id: Optional[str]
    :param status: Filter jobs by status.
    :type status: Optional[str]
    :param active_only: If True, only return active (non-terminal) jobs.
    :type active_only: bool
    :param limit: Maximum number of jobs to return.
    :type limit: int
    :returns: Response containing list of jobs and total count.
    :rtype: JobListResponse
    """
    store = get_job_store()

    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {[s.value for s in JobStatus]}",
            )

    if active_only:
        jobs = store.get_active(workspace_id=workspace_id)
    else:
        jobs = store.get_history(
            workspace_id=workspace_id,
            status=status_filter,
            limit=limit,
        )
        jobs = store.get_active(workspace_id=workspace_id) + jobs

    if limit:
        jobs = jobs[:limit]

    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    """Get a specific job by ID.

    :param job_id: Unique identifier of the job.
    :type job_id: str
    :returns: The requested job.
    :rtype: Job
    :raises HTTPException: If job not found (404 error).
    """
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job


@router.post("", response_model=Job, status_code=201)
async def create_job(request: CreateJobRequest) -> Job:
    """Create and submit a new job.

    :param request: Job creation request with workspace and test details.
    :type request: CreateJobRequest
    :returns: The created and submitted job.
    :rtype: Job
    :raises HTTPException: 404 if workspace not found, 400 on invalid test_group.
    """
    if request.workspace_id not in {ws.id for ws in _load_workspaces_from_directory()}:
        raise HTTPException(
            status_code=404,
            detail=f"Workspace '{request.workspace_id}' not found",
        )

    if request.test_group and request.test_group not in TEST_GROUP_PLAYBOOKS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown test_group '{request.test_group}'. "
                f"Valid values: {sorted(TEST_GROUP_PLAYBOOKS)}"
            ),
        )

    try:
        submitted = await get_job_worker().submit_job(
            Job(
                workspace_id=request.workspace_id,
                test_group=request.test_group,
                test_ids=request.test_ids,
            )
        )
        logger.info(f"Created job {submitted.id} for workspace {request.workspace_id}")
        return submitted
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, request: CancelJobRequest) -> dict:
    """Cancel a running job.

    :param job_id: ID of the job to cancel.
    :type job_id: str
    :param request: Cancellation request with optional reason.
    :type request: CancelJobRequest
    :returns: Status dict with cancellation confirmation.
    :rtype: dict
    :raises HTTPException: If job not found or not running (404 error).
    """

    success = await get_job_worker().cancel_job(job_id, request.reason)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or not running")

    return {"status": "cancelled", "job_id": job_id}


@router.get("/{job_id}/events")
async def get_job_events(job_id: str) -> dict:
    """Get events for a job."""
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": job_id,
        "events": [e.model_dump(mode="json") for e in job.events],
    }


@router.get("/{job_id}/log")
async def get_job_log(
    job_id: str,
    tail: Optional[int] = Query(
        None,
        ge=1,
        description="Return only the last N lines",
    ),
) -> PlainTextResponse:
    """Return the Ansible process log for a job.

    :param job_id: ID of the job.
    :param tail: Optional: return only the last N lines.
    :returns: Plain-text log content.
    :raises HTTPException: 404 if job or log file not found.
    """
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    if not job.log_file:
        raise HTTPException(
            status_code=404,
            detail=f"No log file recorded for job {job_id}",
        )

    log_path = Path(job.log_file)
    if not log_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file not found on disk: {log_path}",
        )

    try:
        content = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read log: {exc}",
        )

    if tail is not None:
        lines = content.splitlines()
        content = "\n".join(lines[-tail:])

    return PlainTextResponse(content)
