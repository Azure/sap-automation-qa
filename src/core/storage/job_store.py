# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""JSON-based storage for jobs."""

import json
import fcntl
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from src.core.models.job import Job, JobStatus
from src.core.observability import get_logger

logger = get_logger(__name__)


class JobStore:
    """JSON file-based storage for execution jobs.

    Stores active jobs in a single file and archives completed jobs
    to daily history files.
    """

    def __init__(
        self,
        data_dir: Path | str = "data/jobs",
    ) -> None:
        """Initialize the job store.

        :param data_dir: Directory for job storage
        """
        self.data_dir = Path(data_dir)
        self.active_file = self.data_dir / "active.json"
        self.history_dir = self.data_dir / "history"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        if not self.active_file.exists():
            self._write_active([])
            logger.info(f"Initialized job storage at {self.data_dir}")

    def _read_active(self) -> List[Job]:
        """Read active jobs from storage.

        Loads and deserializes all active jobs from the JSON file
        with shared file locking for concurrent read safety.

        :returns: List of active execution jobs.
        :rtype: List[Job]
        """
        try:
            with open(self.active_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            return [Job.model_validate(item) for item in data]
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to read active jobs: {e}")
            return []

    def _write_active(self, jobs: List[Job]) -> None:
        """Write active jobs to storage.

        Serializes and writes jobs to the JSON file with exclusive
        file locking to prevent concurrent write corruption.

        :param jobs: List of jobs to persist.
        :type jobs: List[Job]
        :raises Exception: If write operation fails.
        """
        try:
            with open(self.active_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    data = [job.model_dump(mode="json") for job in jobs]
                    json.dump(data, f, indent=2, default=str)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Failed to write active jobs: {e}")
            raise

    def _get_history_file(self, dt: date) -> Path:
        """Get history file path for a given date.

        :param dt: Date for which to get the history file.
        :type dt: date
        :returns: Path to the daily history JSON file.
        :rtype: Path
        """
        return self.history_dir / f"{dt.isoformat()}.json"

    def _append_to_history(self, job: Job) -> None:
        """Append completed job to daily history file.

        Archives a completed job to the appropriate daily history file.
        Creates the file if it doesn't exist.

        :param job: Completed job to archive.
        :type job: Job
        """
        history_file = self._get_history_file(date.today())

        jobs = []
        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        jobs = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                jobs = []

        jobs.append(job.model_dump(mode="json"))

        with open(history_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(jobs, f, indent=2, default=str)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        logger.debug(f"Archived job {job.id} to {history_file}")

    def create(self, job: Job) -> Job:
        """Create a new job.

        :param job: Job to create
        :returns: Created job
        """
        jobs = self._read_active()
        jobs.append(job)
        self._write_active(jobs)
        logger.info(f"Created job {job.id} for workspace {job.workspace_id}")
        return job

    def get(self, job_id: UUID | str) -> Optional[Job]:
        """Get a job by ID.

        :param job_id: Job ID
        :returns: Job if found, None otherwise
        """
        job_id_str = str(job_id)

        for job in self._read_active():
            if str(job.id) == job_id_str:
                return job

        for history_file in sorted(self.history_dir.glob("*.json"), reverse=True):
            try:
                with open(history_file, "r") as f:
                    for item in json.load(f):
                        if str(item.get("id")) == job_id_str:
                            return Job.model_validate(item)
            except Exception:
                continue

        return None

    def update(self, job: Job) -> None:
        """Update an existing job.

        :param job: Job to update
        """
        jobs = self._read_active()
        job_id_str = str(job.id)

        updated = False
        for i, existing in enumerate(jobs):
            if str(existing.id) == job_id_str:
                jobs[i] = job
                updated = True
                break

        if updated:
            if job.is_terminal:
                jobs = [j for j in jobs if str(j.id) != job_id_str]
                self._write_active(jobs)
                self._append_to_history(job)
            else:
                self._write_active(jobs)

            logger.debug(f"Updated job {job.id} (status={job.status})")

    def get_active(self, workspace_id: Optional[str] = None) -> List[Job]:
        """Get active (non-terminal) jobs.

        :param workspace_id: Optional filter by workspace
        :returns: List of active jobs
        """
        jobs = self._read_active()

        if workspace_id:
            jobs = [j for j in jobs if j.workspace_id == workspace_id]

        return jobs

    def get_active_for_workspace(self, workspace_id: str) -> Optional[Job]:
        """Get the active job for a workspace.

        :param workspace_id: Workspace ID
        :returns: Active job if exists
        """
        for job in self._read_active():
            if job.workspace_id == workspace_id and not job.is_terminal:
                return job
        return None

    def has_active_job(self, workspace_id: str) -> bool:
        """Check if workspace has an active job.

        :param workspace_id: Workspace ID
        :returns: True if active job exists
        """
        return self.get_active_for_workspace(workspace_id) is not None

    def get_history(
        self,
        workspace_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        days: int = 7,
        limit: int = 100,
    ) -> List[Job]:
        """Get job history.

        :param workspace_id: Optional filter by workspace
        :param schedule_id: Optional filter by schedule
        :param status: Optional filter by status
        :param days: Number of days to look back
        :param limit: Maximum number of jobs to return
        :returns: List of historical jobs
        """
        jobs = []
        today = date.today()

        for i in range(days):
            history_date = date.fromordinal(today.toordinal() - i)
            history_file = self._get_history_file(history_date)

            if not history_file.exists():
                continue

            try:
                with open(history_file, "r") as f:
                    for item in json.load(f):
                        job = Job.model_validate(item)

                        if workspace_id and job.workspace_id != workspace_id:
                            continue
                        if schedule_id and job.schedule_id != schedule_id:
                            continue
                        if status and job.status != status:
                            continue

                        jobs.append(job)

                        if len(jobs) >= limit:
                            return jobs
            except Exception as e:
                logger.warning(f"Failed to read history file {history_file}: {e}")

        return jobs

    def get_jobs_for_schedule(
        self,
        schedule_id: str,
        limit: int = 50,
    ) -> List[Job]:
        """Get jobs triggered by a specific schedule.

        :param schedule_id: Schedule ID
        :param limit: Maximum number of jobs
        :returns: List of jobs
        """
        return self.get_history(schedule_id=schedule_id, limit=limit)
