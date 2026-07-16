# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Job model."""

import pytest
from src.core.models.job import Job, JobStatus, JobEventType


class TestJobModel:
    """Unit tests for the Job model state machine and event tracking."""

    def test_defaults(self) -> None:
        """
        Verify a new job has correct default values.
        """
        job = Job(workspace_id="WS-001")
        assert job.status == JobStatus.PENDING
        assert job.id is not None
        assert job.started_at is None
        assert job.events == []
        assert not job.is_terminal

    def test_start(self, sample_job: Job) -> None:
        """
        Verify start() transitions job to RUNNING and emits STARTED event.
        """
        event = sample_job.start()
        assert event.event_type == JobEventType.STARTED
        assert sample_job.status == JobStatus.RUNNING
        assert sample_job.started_at is not None
        assert not sample_job.is_terminal

    def test_complete(self, sample_running_job: Job) -> None:
        """
        Verify complete() transitions job to COMPLETED with result.
        """
        event = sample_running_job.complete({"passed": 10})
        assert event.event_type == JobEventType.COMPLETED
        assert sample_running_job.status == JobStatus.COMPLETED
        assert sample_running_job.result == {"passed": 10}
        assert sample_running_job.is_terminal

    def test_fail(self, sample_running_job: Job) -> None:
        """
        Verify fail() transitions job to FAILED with error message.
        """
        event = sample_running_job.fail("timeout")
        assert event.event_type == JobEventType.FAILED
        assert sample_running_job.status == JobStatus.FAILED
        assert sample_running_job.error == "timeout"
        assert sample_running_job.is_terminal

    def test_cancel_pending(self, sample_job: Job) -> None:
        """
        Verify cancel() works on pending jobs with reason.
        """
        event = sample_job.cancel("user request")
        assert event.event_type == JobEventType.CANCELLED
        assert sample_job.status == JobStatus.CANCELLED
        assert sample_job.is_terminal

    def test_cancel_running(self, sample_running_job: Job) -> None:
        """
        Verify cancel() works on running jobs.
        """
        event = sample_running_job.cancel()
        assert event.event_type == JobEventType.CANCELLED
        assert sample_running_job.status == JobStatus.CANCELLED

    @pytest.mark.parametrize(
        "status,terminal",
        [
            (JobStatus.PENDING, False),
            (JobStatus.RUNNING, False),
            (JobStatus.COMPLETED, True),
            (JobStatus.FAILED, True),
            (JobStatus.CANCELLED, True),
        ],
    )
    def test_is_terminal(self, status: JobStatus, terminal: bool) -> None:
        """
        Verify is_terminal property for each status.
        """
        assert Job(workspace_id="WS", status=status).is_terminal == terminal

    def test_duration_none_when_not_started(self, sample_job: Job) -> None:
        """
        Verify duration_seconds is None for unstarted jobs.
        """
        assert sample_job.duration_seconds is None

    def test_duration_calculated(self, sample_completed_job: Job) -> None:
        """
        Verify duration_seconds is calculated for completed jobs.
        """
        duration = sample_completed_job.duration_seconds
        assert duration is not None
        assert duration >= 0

    def test_events_accumulate(self) -> None:
        """
        Verify events list accumulates through state transitions.
        """
        job = Job(workspace_id="WS")
        job.start()
        job.complete({})
        assert len(job.events) == 2
        assert job.events[0].event_type == JobEventType.STARTED
        assert job.events[1].event_type == JobEventType.COMPLETED

    def test_empty_workspace_allowed(self) -> None:
        """
        Verify empty workspace_id is allowed.
        """
        assert Job(workspace_id="").workspace_id == ""

    def test_complete_with_empty_result(self) -> None:
        """
        Verify complete() accepts empty result dict.
        """
        job = Job(workspace_id="WS")
        job.start()
        job.complete({})
        assert job.result == {}

    def test_fail_with_empty_error(self) -> None:
        """
        Verify fail() accepts empty error string.
        """
        job = Job(workspace_id="WS")
        job.start()
        job.fail("")
        assert job.error == ""


class TestJobModelP1WP003:
    """P1-WP-003: actor, approval_ref, incident_ticket, offline fields."""

    def test_new_fields_default_values(self) -> None:
        """New fields have correct defaults (None/False)."""
        job = Job(workspace_id="WS")
        assert job.actor is None
        assert job.approval_ref is None
        assert job.incident_ticket is None
        assert job.offline is False

    def test_new_fields_set_explicitly(self) -> None:
        """New fields are settable at construction."""
        job = Job(
            workspace_id="WS",
            actor="user@example.com",
            approval_ref="CHG-123",
            incident_ticket="INC-456",
            offline=True,
        )
        assert job.actor == "user@example.com"
        assert job.approval_ref == "CHG-123"
        assert job.incident_ticket == "INC-456"
        assert job.offline is True

    def test_offline_false_by_default(self) -> None:
        """offline defaults to False, not None."""
        job = Job(workspace_id="WS")
        assert job.offline is False
        assert isinstance(job.offline, bool)

    def test_model_round_trip_json(self) -> None:
        """New fields survive JSON serialization/deserialization."""
        job = Job(
            workspace_id="WS",
            actor="bot",
            approval_ref="REF-1",
            incident_ticket="TKT-9",
            offline=True,
        )
        data = job.model_dump(mode="json")
        restored = Job.model_validate(data)
        assert restored.actor == "bot"
        assert restored.approval_ref == "REF-1"
        assert restored.incident_ticket == "TKT-9"
        assert restored.offline is True

    def test_existing_fields_unchanged(self) -> None:
        """Existing model semantics are not broken by new fields."""
        job = Job(workspace_id="WS", test_group="ConfigurationChecks")
        assert job.status == JobStatus.PENDING
        assert job.test_ids == []
        job.start()
        assert job.status == JobStatus.RUNNING
