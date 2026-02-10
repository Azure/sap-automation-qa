# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""SQLite-based storage for schedules."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.core.models.schedule import Schedule
from src.core.observability import get_logger

logger = get_logger(__name__)

_SCHEDULES_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    cron_expression  TEXT NOT NULL,
    timezone         TEXT NOT NULL DEFAULT 'UTC',
    workspace_ids    TEXT NOT NULL DEFAULT '[]',
    test_group       TEXT,
    test_ids         TEXT NOT NULL DEFAULT '[]',
    enabled          INTEGER NOT NULL DEFAULT 1,
    next_run_time    TEXT,
    last_run_time    TEXT,
    last_run_job_ids TEXT NOT NULL DEFAULT '[]',
    total_runs       INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
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


class ScheduleStore:
    """SQLite-backed storage for schedules.

    Uses WAL journal mode for crash safety. All writes are
    wrapped in transactions.
    """

    def __init__(
        self,
        db_path: Path | str = "data/scheduler.db",
    ) -> None:
        """Initialize the schedule store.

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
        self._conn.executescript(_SCHEDULES_SCHEMA)

        logger.info(f"Initialized schedule storage at {self.db_path}")

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    @staticmethod
    def _schedule_to_row(schedule: Schedule) -> dict:
        """Convert a Schedule model to a flat dict for SQLite."""
        return {
            "id": schedule.id,
            "name": schedule.name,
            "description": schedule.description,
            "cron_expression": schedule.cron_expression,
            "timezone": schedule.timezone,
            "workspace_ids": json.dumps(schedule.workspace_ids),
            "test_group": schedule.test_group,
            "test_ids": json.dumps(schedule.test_ids),
            "enabled": 1 if schedule.enabled else 0,
            "next_run_time": _dt_to_iso(schedule.next_run_time),
            "last_run_time": _dt_to_iso(schedule.last_run_time),
            "last_run_job_ids": json.dumps(schedule.last_run_job_ids),
            "total_runs": schedule.total_runs,
            "created_at": _dt_to_iso(schedule.created_at),
            "updated_at": _dt_to_iso(schedule.updated_at),
        }

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> Schedule:
        """Reconstruct a Schedule model from a database row."""
        data = dict(row)
        data["workspace_ids"] = json.loads(data["workspace_ids"])
        data["test_ids"] = json.loads(data["test_ids"])
        data["last_run_job_ids"] = json.loads(data["last_run_job_ids"])
        data["enabled"] = bool(data["enabled"])
        for dt_field in (
            "next_run_time",
            "last_run_time",
            "created_at",
            "updated_at",
        ):
            if data.get(dt_field):
                data[dt_field] = datetime.fromisoformat(data[dt_field])
        return Schedule(**data)

    def create(self, schedule: Schedule) -> Schedule:
        """Create a new schedule.

        :param schedule: Schedule to create.
        :returns: Created schedule.
        :raises ValueError: If schedule with same ID exists.
        """
        row = self._schedule_to_row(schedule)
        try:
            with self._conn:
                self._conn.execute(
                    """INSERT INTO schedules
                       (id, name, description, cron_expression,
                        timezone, workspace_ids, test_group,
                        test_ids, enabled, next_run_time,
                        last_run_time, last_run_job_ids,
                        total_runs, created_at, updated_at)
                       VALUES
                       (:id, :name, :description,
                        :cron_expression, :timezone,
                        :workspace_ids, :test_group, :test_ids,
                        :enabled, :next_run_time, :last_run_time,
                        :last_run_job_ids, :total_runs,
                        :created_at, :updated_at)
                    """,
                    row,
                )
        except sqlite3.IntegrityError:
            raise ValueError(f"Schedule with ID {schedule.id} already exists")

        logger.info(f"Created schedule '{schedule.name}' " f"(ID: {schedule.id})")
        return schedule

    def get(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID.

        :param schedule_id: Schedule ID.
        :returns: Schedule if found.
        """
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.execute(
            "SELECT * FROM schedules WHERE id = ?",
            (schedule_id,),
        )
        row = cur.fetchone()
        return self._row_to_schedule(row) if row else None

    def list(self, enabled_only: bool = False) -> List[Schedule]:
        """List all schedules.

        :param enabled_only: If True, only return enabled schedules.
        :returns: List of schedules.
        """
        self._conn.row_factory = sqlite3.Row
        if enabled_only:
            cur = self._conn.execute("SELECT * FROM schedules WHERE enabled = 1")
        else:
            cur = self._conn.execute("SELECT * FROM schedules")
        return [self._row_to_schedule(r) for r in cur.fetchall()]

    def update(self, schedule: Schedule) -> Schedule:
        """Update an existing schedule.

        :param schedule: Schedule to update.
        :returns: Updated schedule.
        :raises ValueError: If schedule not found.
        """
        schedule.updated_at = datetime.utcnow()
        row = self._schedule_to_row(schedule)
        with self._conn:
            cur = self._conn.execute(
                """UPDATE schedules SET
                       name             = :name,
                       description      = :description,
                       cron_expression  = :cron_expression,
                       timezone         = :timezone,
                       workspace_ids    = :workspace_ids,
                       test_group       = :test_group,
                       test_ids         = :test_ids,
                       enabled          = :enabled,
                       next_run_time    = :next_run_time,
                       last_run_time    = :last_run_time,
                       last_run_job_ids = :last_run_job_ids,
                       total_runs       = :total_runs,
                       updated_at       = :updated_at
                   WHERE id = :id
                """,
                row,
            )
        if cur.rowcount == 0:
            raise ValueError(f"Schedule {schedule.id} not found")
        logger.info(f"Updated schedule '{schedule.name}' " f"(ID: {schedule.id})")
        return schedule

    def delete(self, schedule_id: str) -> bool:
        """Delete a schedule.

        :param schedule_id: Schedule ID.
        :returns: True if deleted.
        """
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM schedules WHERE id = ?",
                (schedule_id,),
            )
        if cur.rowcount > 0:
            logger.info(f"Deleted schedule {schedule_id}")
            return True
        return False

    def get_enabled(self) -> List[Schedule]:
        """Get all enabled schedules.

        :returns: List of enabled schedules.
        """
        return self.list(enabled_only=True)
