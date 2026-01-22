# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Jobs API routes
"""

import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from src.core.models.job import Job, JobStatus, CreateJobRequest, CancelJobRequest, JobListResponse
from src.core.storage.job_store import JobStore
from src.core.execution.worker import JobWorker
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

    if active_only:
        jobs = store.get_active(workspace_id=workspace_id)
    else:
        jobs = store.get_history(
            workspace_id=workspace_id,
            status=JobStatus(status) if status else None,
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
    :raises HTTPException: If job creation fails (400 error).
    """

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


@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str, request: Request) -> StreamingResponse:
    """Stream job events via Server-Sent Events (SSE).

    :param job_id: ID of the job to stream events for.
    :type job_id: str
    :param request: FastAPI request object for disconnect detection.
    :type request: Request
    :returns: SSE stream of job events.
    :rtype: StreamingResponse
    :raises HTTPException: If job not found (404 error).
    """
    store = get_job_store()
    job = store.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    async def event_generator():
        """Generate SSE events for job status updates."""
        last_event_count = 0

        while True:
            if await request.is_disconnected():
                break

            current_job = store.get(job_id)
            if not current_job:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            if len(current_job.events) > last_event_count:
                for event in current_job.events[last_event_count:]:
                    event_data = {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                        "message": event.message,
                        "data": event.data,
                    }
                    yield f"event: {event.event_type}\ndata: {json.dumps(event_data)}\n\n"
                last_event_count = len(current_job.events)

            status_data = {
                "job_id": current_job.id,
                "status": (
                    current_job.status.value
                    if hasattr(current_job.status, "value")
                    else current_job.status
                ),
            }
            yield f"event: status\ndata: {json.dumps(status_data)}\n\n"
            if current_job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                result_data = {
                    "job_id": current_job.id,
                    "status": (
                        current_job.status.value
                        if hasattr(current_job.status, "value")
                        else current_job.status
                    ),
                    "error": current_job.error,
                    "completed_at": (
                        current_job.completed_at.isoformat() if current_job.completed_at else None
                    ),
                }
                yield f"event: complete\ndata: {json.dumps(result_data)}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
