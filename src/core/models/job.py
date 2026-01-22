# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Job execution models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class JobStatus(str, Enum):
    """Status of an execution job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobEventType(str, Enum):
    """Type of job event."""

    CREATED = "created"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobEvent(BaseModel):
    """Event emitted during job execution."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: JobEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = ""
    data: Optional[dict[str, Any]] = None


class Job(BaseModel):
    """Represents an async test execution job."""

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    schedule_id: Optional[str] = None
    test_group: Optional[str] = None
    test_ids: list[str] = Field(default_factory=list)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    events: list[JobEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def start(self) -> JobEvent:
        """Mark job as started.

        Sets the job status to RUNNING and records the start timestamp.

        :returns: JobEvent indicating the job has started.
        :rtype: JobEvent
        """
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()
        event = JobEvent(event_type=JobEventType.STARTED, message="Job started")
        self.events.append(event)
        return event

    def complete(self, result: dict[str, Any], message: str = "") -> JobEvent:
        """Mark job as completed successfully.

        Sets the job status to COMPLETED and stores the result.

        :param result: Dictionary containing execution results.
        :type result: dict[str, Any]
        :param message: Optional completion message.
        :type message: str
        :returns: JobEvent indicating completion.
        :rtype: JobEvent
        """
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result
        event = JobEvent(
            event_type=JobEventType.COMPLETED,
            message=message or "Job completed successfully",
            data=result,
        )
        self.events.append(event)
        return event

    def fail(self, error: str) -> JobEvent:
        """Mark job as failed.

        Sets the job status to FAILED and stores the error message.

        :param error: Error message describing why the job failed.
        :type error: str
        :returns: JobEvent indicating failure.
        :rtype: JobEvent
        """
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error
        event = JobEvent(event_type=JobEventType.FAILED, message=error)
        self.events.append(event)
        return event

    def cancel(self, reason: str = "Cancelled by user") -> JobEvent:
        """Mark job as cancelled.

        Sets the job status to CANCELLED with the given reason.

        :param reason: Reason for cancellation.
        :type reason: str
        :returns: JobEvent indicating cancellation.
        :rtype: JobEvent
        """
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.error = reason
        event = JobEvent(event_type=JobEventType.CANCELLED, message=reason)
        self.events.append(event)
        return event

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()


class JobListResponse(BaseModel):
    """Response containing list of jobs."""

    jobs: List[Job]
    total: int


class CreateJobRequest(BaseModel):
    """Request to create a new job."""

    workspace_id: str
    test_group: Optional[str] = None
    test_ids: List[str] = []


class CancelJobRequest(BaseModel):
    """Request to cancel a job."""

    reason: str = "Cancelled by user"
