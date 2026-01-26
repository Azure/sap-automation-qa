# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""JSON-based storage for schedules."""

import json
import fcntl
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.core.models.schedule import Schedule
from src.core.observability import get_logger

logger = get_logger(__name__)


class ScheduleStore:
    """JSON file-based storage for schedules."""

    def __init__(self, storage_path: Path | str = "data/schedules.json") -> None:
        """Initialize the schedule store.

        :param storage_path: Path to JSON storage file
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.storage_path.exists():
            self._write_schedules([])
            logger.info(f"Initialized schedule storage at {self.storage_path}")

    def _read_schedules(self) -> List[Schedule]:
        """Read all schedules from storage.

        Loads and deserializes all schedules from the JSON file
        with shared file locking for concurrent read safety.

        :returns: List of schedule configurations.
        :rtype: List[Schedule]
        """
        try:
            with open(self.storage_path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            schedules = []
            for item in data:
                for dt_field in ["next_run_time", "last_run_time", "created_at", "updated_at"]:
                    if item.get(dt_field):
                        dt_str = item[dt_field].replace("Z", "+00:00")
                        item[dt_field] = datetime.fromisoformat(dt_str)

                schedules.append(Schedule(**item))

            return schedules
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to read schedules: {e}")
            return []

    def _write_schedules(self, schedules: List[Schedule]) -> None:
        """Write schedules to storage.

        Serializes and writes schedules to the JSON file with exclusive
        file locking to prevent concurrent write corruption.

        :param schedules: List of schedules to persist.
        :type schedules: List[Schedule]
        :raises Exception: If write operation fails.
        """
        try:
            data = [s.model_dump(mode="json") for s in schedules]

            with open(self.storage_path, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, default=str)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            logger.debug(f"Wrote {len(schedules)} schedules to storage")
        except Exception as e:
            logger.error(f"Failed to write schedules: {e}")
            raise

    def create(self, schedule: Schedule) -> Schedule:
        """Create a new schedule.

        :param schedule: Schedule to create
        :returns: Created schedule
        :raises ValueError: If schedule with same ID exists
        """
        schedules = self._read_schedules()

        if any(s.id == schedule.id for s in schedules):
            raise ValueError(f"Schedule with ID {schedule.id} already exists")

        schedules.append(schedule)
        self._write_schedules(schedules)

        logger.info(f"Created schedule '{schedule.name}' (ID: {schedule.id})")
        return schedule

    def get(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID.

        :param schedule_id: Schedule ID
        :returns: Schedule if found
        """
        for schedule in self._read_schedules():
            if schedule.id == schedule_id:
                return schedule
        return None

    def list(self, enabled_only: bool = False) -> List[Schedule]:
        """List all schedules.

        :param enabled_only: If True, only return enabled schedules
        :returns: List of schedules
        """
        schedules = self._read_schedules()
        if enabled_only:
            schedules = [s for s in schedules if s.enabled]
        return schedules

    def update(self, schedule: Schedule) -> Schedule:
        """Update an existing schedule.

        :param schedule: Schedule to update
        :returns: Updated schedule
        :raises ValueError: If schedule not found
        """
        schedules = self._read_schedules()

        for i, existing in enumerate(schedules):
            if existing.id == schedule.id:
                schedule.updated_at = datetime.utcnow()
                schedules[i] = schedule
                self._write_schedules(schedules)
                logger.info(f"Updated schedule '{schedule.name}' (ID: {schedule.id})")
                return schedule

        raise ValueError(f"Schedule {schedule.id} not found")

    def delete(self, schedule_id: str) -> bool:
        """Delete a schedule.

        :param schedule_id: Schedule ID
        :returns: True if deleted
        """
        schedules = self._read_schedules()
        original_count = len(schedules)

        schedules = [s for s in schedules if s.id != schedule_id]

        if len(schedules) < original_count:
            self._write_schedules(schedules)
            logger.info(f"Deleted schedule {schedule_id}")
            return True

        return False

    def get_enabled(self) -> List[Schedule]:
        """Get all enabled schedules.

        :returns: List of enabled schedules
        """
        return self.list(enabled_only=True)
