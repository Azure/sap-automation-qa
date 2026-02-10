# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for JobStore."""

from pathlib import Path
from src.core.models.job import Job, JobStatus
from src.core.storage.job_store import JobStore


class TestJobStore:
    """Unit tests for JobStore CRUD operations and history management."""

    def test_creates_directories(self, temp_dir: Path) -> None:
        """
        Verify JobStore creates parent directory and DB file on init.
        """
        store = JobStore(db_path=temp_dir / "sub" / "test.db")
        assert (temp_dir / "sub" / "test.db").exists()
        store.close()

    def test_create_and_get(self, job_store: JobStore, sample_job: Job) -> None:
        """
        Verify create() persists job and get() retrieves it.
        """
        created = job_store.create(sample_job)
        assert created.id == sample_job.id
        retrieved = job_store.get(sample_job.id)
        assert retrieved is not None
        assert retrieved.workspace_id == sample_job.workspace_id

    def test_get_nonexistent(self, job_store: JobStore) -> None:
        """
        Verify get() returns None for unknown job ID.
        """
        assert job_store.get("00000000-0000-0000-0000-000000000000") is None

    def test_create_multiple(self, job_store: JobStore) -> None:
        """
        Verify multiple jobs can be created and retrieved.
        """
        for i in range(5):
            job_store.create(Job(workspace_id=f"WS-{i}"))
        assert len(job_store.get_active()) == 5

    def test_update_state(self, job_store: JobStore, sample_job: Job) -> None:
        """
        Verify update() persists job state changes.
        """
        job_store.create(sample_job)
        sample_job.start()
        job_store.update(sample_job)
        retrieved = job_store.get(sample_job.id)
        assert retrieved is not None
        assert retrieved.status == JobStatus.RUNNING

    def test_update_to_terminal_archives(self, job_store: JobStore, sample_job: Job) -> None:
        """
        Verify terminal jobs are archived and removed from active.
        """
        job_store.create(sample_job)
        sample_job.start()
        sample_job.complete({})
        job_store.update(sample_job)
        assert not any(str(j.id) == str(sample_job.id) for j in job_store.get_active())
        retrieved = job_store.get(sample_job.id)
        assert retrieved is not None
        assert retrieved.status == JobStatus.COMPLETED

    def test_get_active_returns_non_terminal(self, job_store: JobStore) -> None:
        """
        Verify get_active() excludes terminal jobs.
        """
        pending = Job(workspace_id="WS-1")
        completed = Job(workspace_id="WS-2")
        job_store.create(pending)
        completed.start()
        completed.complete({})
        job_store.create(completed)
        job_store.update(completed)
        assert len(job_store.get_active()) == 1

    def test_get_active_filter_by_workspace(self, job_store: JobStore) -> None:
        """
        Verify get_active() filters by workspace_id.
        """
        job_store.create(Job(workspace_id="WS-A"))
        job_store.create(Job(workspace_id="WS-B"))
        job_store.create(Job(workspace_id="WS-A"))
        assert len(job_store.get_active(workspace_id="WS-A")) == 2
        assert len(job_store.get_active(workspace_id="WS-B")) == 1

    def test_get_active_for_workspace(self, job_store: JobStore, sample_running_job: Job) -> None:
        """
        Verify get_active_for_workspace() returns first active job.
        """
        job_store.create(sample_running_job)
        active = job_store.get_active_for_workspace(sample_running_job.workspace_id)
        assert active is not None
        assert active.id == sample_running_job.id

    def test_get_active_for_workspace_none(self, job_store: JobStore) -> None:
        """
        Verify get_active_for_workspace() returns None when no active job.
        """
        assert job_store.get_active_for_workspace("NONEXISTENT") is None

    def test_has_active_job(self, job_store: JobStore, sample_running_job: Job) -> None:
        """
        Verify has_active_job() returns correct boolean.
        """
        job_store.create(sample_running_job)
        assert job_store.has_active_job(sample_running_job.workspace_id)
        assert not job_store.has_active_job("OTHER")

    def test_get_history_empty(self, job_store: JobStore) -> None:
        """
        Verify get_history() returns empty list when no history.
        """
        assert job_store.get_history() == []

    def test_get_history_with_completed(self, job_store: JobStore) -> None:
        """
        Verify get_history() includes completed jobs.
        """
        job = Job(workspace_id="WS")
        job_store.create(job)
        job.start()
        job.complete({})
        job_store.update(job)
        assert len(job_store.get_history()) == 1

    def test_get_history_filter_by_workspace(self, job_store: JobStore) -> None:
        """
        Verify get_history() filters by workspace_id.
        """
        for ws in ["WS-A", "WS-B", "WS-A"]:
            job = Job(workspace_id=ws)
            job_store.create(job)
            job.start()
            job.complete({})
            job_store.update(job)
        assert len(job_store.get_history(workspace_id="WS-A")) == 2

    def test_get_history_filter_by_schedule(self, job_store: JobStore) -> None:
        """
        Verify get_history() filters by schedule_id.
        """
        for sched in ["S1", "S2"]:
            job = Job(workspace_id="WS", schedule_id=sched)
            job_store.create(job)
            job.start()
            job.complete({})
            job_store.update(job)
        assert len(job_store.get_history(schedule_id="S1")) == 1

    def test_get_history_limit(self, job_store: JobStore) -> None:
        """
        Verify get_history() respects limit parameter.
        """
        for i in range(10):
            job = Job(workspace_id=f"WS-{i}")
            job_store.create(job)
            job.start()
            job.complete({})
            job_store.update(job)
        assert len(job_store.get_history(limit=3)) == 3

    def test_completed_job_in_history(self, job_store: JobStore) -> None:
        """
        Verify completed job is queryable via get_history.
        """
        job = Job(workspace_id="WS-HIST")
        job_store.create(job)
        job.start()
        job.complete({"ok": True})
        job_store.update(job)
        found = job_store.get(job.id)
        assert found is not None
        assert found.status == JobStatus.COMPLETED

    def test_update_nonexistent_noop(self, job_store: JobStore, sample_job: Job) -> None:
        """
        Verify update() on nonexistent job is a no-op.
        """
        job_store.update(sample_job)
        assert job_store.get(sample_job.id) is None

    def test_concurrent_creates(self, job_store: JobStore) -> None:
        """
        Verify concurrent creates don't cause data loss.
        """
        for i in range(20):
            job_store.create(Job(workspace_id=f"WS-{i}"))
        assert len(job_store.get_active()) == 20

    def test_log_file_persisted(self, job_store: JobStore) -> None:
        """
        Verify log_file field is persisted and retrieved.
        """
        job = Job(workspace_id="WS-LOG")
        job.log_file = "/data/logs/test-job.log"
        job_store.create(job)
        retrieved = job_store.get(job.id)
        assert retrieved is not None
        assert retrieved.log_file == "/data/logs/test-job.log"

    def test_log_file_none_by_default(self, job_store: JobStore) -> None:
        """
        Verify log_file is None when not set.
        """
        job = Job(workspace_id="WS-NOLOG")
        job_store.create(job)
        retrieved = job_store.get(job.id)
        assert retrieved is not None
        assert retrieved.log_file is None
