# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""SQLite-based storage for jobs."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from src.core.models.job import Job, JobStatus
from src.core.observability import get_logger

logger = get_logger(__name__)

_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    schedule_id  TEXT,
    test_group   TEXT,
    test_ids     TEXT NOT NULL DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    error        TEXT,
    result       TEXT,
    log_file     TEXT,
    events       TEXT NOT NULL DEFAULT '[]',
    metadata     TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_jobs_workspace
    ON jobs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status
    ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_schedule
    ON jobs(schedule_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created
    ON jobs(created_at);
"""


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO-8601 string for SQLite storage.

    :param dt: Datetime to convert.
    :returns: ISO string or None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class JobStore:
    """SQLite-backed storage for execution jobs.

    Uses WAL journal mode for crash safety and concurrent
    read performance. All writes are wrapped in transactions.
    """

    def __init__(
        self,
        db_path: Path | str = "data/scheduler.db",
    ) -> None:
        """Initialize the job store.

        :param db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self.db_path),
            isolation_level="DEFERRED",
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_JOBS_SCHEMA)

        logger.info(f"Initialized job storage at {self.db_path}")

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    @staticmethod
    def _job_to_row(job: Job) -> dict:
        """Convert a Job model to a flat dict for SQLite storage."""
        return {
            "id": str(job.id),
            "workspace_id": job.workspace_id,
            "schedule_id": job.schedule_id,
            "test_group": job.test_group,
            "test_ids": json.dumps(job.test_ids),
            "status": job.status if isinstance(job.status, str) else job.status.value,
            "created_at": _dt_to_iso(job.created_at),
            "started_at": _dt_to_iso(job.started_at),
            "completed_at": _dt_to_iso(job.completed_at),
            "error": job.error,
            "result": json.dumps(job.result, default=str) if job.result else None,
            "log_file": job.log_file,
            "events": json.dumps(
                [e.model_dump(mode="json") for e in job.events],
                default=str,
            ),
            "metadata": json.dumps(job.metadata, default=str),
        }

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        """Reconstruct a Job model from a database row."""
        data = dict(row)
        data["test_ids"] = json.loads(data["test_ids"])
        data["events"] = json.loads(data["events"])
        data["metadata"] = json.loads(data["metadata"])
        data["result"] = json.loads(data["result"]) if data["result"] else None
        for dt_field in ("created_at", "started_at", "completed_at"):
            if data.get(dt_field):
                data[dt_field] = datetime.fromisoformat(data[dt_field])
        return Job.model_validate(data)

    def create(self, job: Job) -> Job:
        """Create a new job.

        :param job: Job to create.
        :returns: Created job.
        """
        row = self._job_to_row(job)
        with self._conn:
            self._conn.execute(
                """INSERT INTO jobs
                   (id, workspace_id, schedule_id, test_group,
                    test_ids, status, created_at, started_at,
                    completed_at, error, result, log_file,
                    events, metadata)
                   VALUES
                   (:id, :workspace_id, :schedule_id, :test_group,
                    :test_ids, :status, :created_at, :started_at,
                    :completed_at, :error, :result, :log_file,
                    :events, :metadata)
                """,
                row,
            )
        logger.info(f"Created job {job.id} for workspace {job.workspace_id}")
        return job

    def get(self, job_id: UUID | str) -> Optional[Job]:
        """Get a job by ID.

        :param job_id: Job ID.
        :returns: Job if found, None otherwise.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (str(job_id),)).fetchone()
        return self._row_to_job(row) if row else None

    def update(self, job: Job) -> None:
        """Update an existing job.

        :param job: Job with updated fields.
        """
        row = self._job_to_row(job)
        with self._conn:
            cur = self._conn.execute(
                """UPDATE jobs SET
                       workspace_id  = :workspace_id,
                       schedule_id   = :schedule_id,
                       test_group    = :test_group,
                       test_ids      = :test_ids,
                       status        = :status,
                       created_at    = :created_at,
                       started_at    = :started_at,
                       completed_at  = :completed_at,
                       error         = :error,
                       result        = :result,
                       log_file      = :log_file,
                       events        = :events,
                       metadata      = :metadata
                   WHERE id = :id
                """,
                row,
            )
        if cur.rowcount:
            logger.debug(f"Updated job {job.id} (status={job.status})")

    def get_active(self, workspace_id: Optional[str] = None) -> List[Job]:
        """Get active (non-terminal) jobs.

        :param workspace_id: Optional filter by workspace.
        :returns: List of active jobs.
        """
        self._conn.row_factory = sqlite3.Row
        terminal = (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        )
        if workspace_id:
            cur = self._conn.execute(
                "SELECT * FROM jobs " "WHERE status NOT IN (?, ?, ?) " "AND workspace_id = ?",
                (*terminal, workspace_id),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM jobs " "WHERE status NOT IN (?, ?, ?)",
                terminal,
            )
        return [self._row_to_job(r) for r in cur.fetchall()]

    def get_active_for_workspace(self, workspace_id: str) -> Optional[Job]:
        """Get the active job for a workspace.

        :param workspace_id: Workspace ID.
        :returns: Active job if one exists.
        """
        self._conn.row_factory = sqlite3.Row
        terminal = (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        )
        cur = self._conn.execute(
            "SELECT * FROM jobs "
            "WHERE workspace_id = ? "
            "AND status NOT IN (?, ?, ?) "
            "LIMIT 1",
            (workspace_id, *terminal),
        )
        row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def has_active_job(self, workspace_id: str) -> bool:
        """Check if workspace has an active job.

        :param workspace_id: Workspace ID.
        :returns: True if active job exists.
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

        :param workspace_id: Optional filter by workspace.
        :param schedule_id: Optional filter by schedule.
        :param status: Optional filter by status.
        :param days: Number of days to look back.
        :param limit: Maximum number of jobs to return.
        :returns: List of historical jobs.
        """
        self._conn.row_factory = sqlite3.Row
        terminal = (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        )

        clauses = [
            "status IN (?, ?, ?)",
            "created_at >= ?",
        ]
        params: list = [*terminal, _dt_to_iso(datetime.now(timezone.utc) - timedelta(days=days))]

        if workspace_id:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        if schedule_id:
            clauses.append("schedule_id = ?")
            params.append(schedule_id)
        if status:
            status_val = status if isinstance(status, str) else status.value
            clauses.append("status = ?")
            params.append(status_val)

        where = " AND ".join(clauses)
        params.append(limit)

        cur = self._conn.execute(
            f"SELECT * FROM jobs WHERE {where} " "ORDER BY created_at DESC LIMIT ?",
            params,
        )
        return [self._row_to_job(r) for r in cur.fetchall()]

    def get_jobs_for_schedule(
        self,
        schedule_id: str,
        limit: int = 50,
    ) -> List[Job]:
        """Get jobs triggered by a specific schedule.

        :param schedule_id: Schedule ID.
        :param limit: Maximum number of jobs.
        :returns: List of jobs.
        """
        return self.get_history(schedule_id=schedule_id, limit=limit)
