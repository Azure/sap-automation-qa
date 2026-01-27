# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for ScheduleStore."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from src.core.models.schedule import Schedule
from src.core.storage.schedule_store import ScheduleStore


class TestScheduleStore:
    """Unit tests for ScheduleStore CRUD operations."""

    def test_creates_storage_file(self, temp_dir: Path) -> None:
        """Verify ScheduleStore creates storage file on init."""
        ScheduleStore(storage_path=temp_dir / "schedules.json")
        assert (temp_dir / "schedules.json").exists()

    def test_creates_parent_dirs(self, temp_dir: Path) -> None:
        """Verify ScheduleStore creates nested parent directories."""
        ScheduleStore(storage_path=temp_dir / "nested" / "dir" / "s.json")
        assert (temp_dir / "nested" / "dir" / "s.json").exists()

    def test_create_and_get(self, schedule_store: ScheduleStore, sample_schedule: Schedule) -> None:
        """Verify create() persists schedule and get() retrieves it."""
        created = schedule_store.create(sample_schedule)
        assert created.id == sample_schedule.id
        assert schedule_store.get(sample_schedule.id) is not None

    def test_create_duplicate_raises(
        self, schedule_store: ScheduleStore, sample_schedule: Schedule
    ) -> None:
        """Verify create() raises ValueError for duplicate ID."""
        schedule_store.create(sample_schedule)
        with pytest.raises(ValueError, match="already exists"):
            schedule_store.create(
                Schedule(
                    id=sample_schedule.id,
                    name="X",
                    cron_expression="* * * * *",
                    workspace_ids=[],
                )
            )

    def test_get_nonexistent(self, schedule_store: ScheduleStore) -> None:
        """Verify get() returns None for unknown schedule ID."""
        assert schedule_store.get("nonexistent") is None

    def test_list_all(
        self,
        schedule_store: ScheduleStore,
        sample_schedule: Schedule,
        sample_disabled_schedule: Schedule,
    ) -> None:
        """Verify list() returns all schedules."""
        schedule_store.create(sample_schedule)
        schedule_store.create(sample_disabled_schedule)
        assert len(schedule_store.list()) == 2

    def test_list_enabled_only(
        self,
        schedule_store: ScheduleStore,
        sample_schedule: Schedule,
        sample_disabled_schedule: Schedule,
    ) -> None:
        """Verify list(enabled_only=True) filters disabled schedules."""
        schedule_store.create(sample_schedule)
        schedule_store.create(sample_disabled_schedule)
        enabled = schedule_store.list(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].enabled is True

    def test_list_empty(self, schedule_store: ScheduleStore) -> None:
        """Verify list() returns empty list when no schedules exist."""
        assert schedule_store.list() == []

    def test_update_name(self, schedule_store: ScheduleStore, sample_schedule: Schedule) -> None:
        """Verify update() persists schedule changes."""
        schedule_store.create(sample_schedule)
        sample_schedule.name = "Updated"
        updated = schedule_store.update(sample_schedule)
        assert updated.name == "Updated"
        retrieved = schedule_store.get(sample_schedule.id)
        assert retrieved is not None
        assert retrieved.name == "Updated"

    def test_update_sets_updated_at(
        self, schedule_store: ScheduleStore, sample_schedule: Schedule
    ) -> None:
        """Verify update() bumps updated_at timestamp."""
        schedule_store.create(sample_schedule)
        original = sample_schedule.updated_at
        sample_schedule.enabled = False
        updated = schedule_store.update(sample_schedule)
        assert updated.updated_at > original

    def test_update_nonexistent_raises(
        self, schedule_store: ScheduleStore, sample_schedule: Schedule
    ) -> None:
        """Verify update() raises ValueError for unknown schedule."""
        with pytest.raises(ValueError, match="not found"):
            schedule_store.update(sample_schedule)

    def test_delete_existing(
        self, schedule_store: ScheduleStore, sample_schedule: Schedule
    ) -> None:
        """Verify delete() removes schedule and returns True."""
        schedule_store.create(sample_schedule)
        assert schedule_store.delete(sample_schedule.id) is True
        assert schedule_store.get(sample_schedule.id) is None

    def test_delete_nonexistent(self, schedule_store: ScheduleStore) -> None:
        """Verify delete() returns False for unknown schedule."""
        assert schedule_store.delete("nonexistent") is False

    def test_delete_does_not_affect_others(
        self,
        schedule_store: ScheduleStore,
        sample_schedule: Schedule,
        sample_disabled_schedule: Schedule,
    ) -> None:
        """Verify delete() only removes target schedule."""
        schedule_store.create(sample_schedule)
        schedule_store.create(sample_disabled_schedule)
        schedule_store.delete(sample_schedule.id)
        remaining = schedule_store.list()
        assert len(remaining) == 1
        assert remaining[0].id == sample_disabled_schedule.id

    def test_get_enabled(
        self,
        schedule_store: ScheduleStore,
        sample_schedule: Schedule,
        sample_disabled_schedule: Schedule,
    ) -> None:
        """Verify get_enabled() returns only enabled schedules."""
        schedule_store.create(sample_schedule)
        schedule_store.create(sample_disabled_schedule)
        enabled = schedule_store.get_enabled()
        assert len(enabled) == 1
        assert all(s.enabled for s in enabled)

    def test_datetime_persistence(self, schedule_store: ScheduleStore) -> None:
        """Verify datetime fields persist correctly through JSON."""
        now = datetime.now(timezone.utc)
        sched = Schedule(
            name="DT",
            cron_expression="0 0 * * *",
            workspace_ids=["WS"],
            next_run_time=now,
            last_run_time=now,
        )
        schedule_store.create(sched)
        retrieved = schedule_store.get(sched.id)
        assert retrieved is not None
        assert retrieved.next_run_time is not None
        assert retrieved.last_run_time is not None

    def test_empty_workspace_ids_allowed(self, schedule_store: ScheduleStore) -> None:
        """Verify schedule can be created with empty workspace_ids list."""
        sched = Schedule(name="Empty", cron_expression="0 0 * * *", workspace_ids=[])
        created = schedule_store.create(sched)
        assert created.workspace_ids == []

    def test_many_workspaces(self, schedule_store: ScheduleStore) -> None:
        """Verify schedule handles large workspace_ids list."""
        sched = Schedule(
            name="Many",
            cron_expression="0 0 * * *",
            workspace_ids=[f"WS-{i}" for i in range(100)],
        )
        schedule_store.create(sched)
        retrieved = schedule_store.get(sched.id)
        assert retrieved is not None
        assert len(retrieved.workspace_ids) == 100

    def test_corrupted_file(self, temp_dir: Path) -> None:
        """Verify corrupted storage file returns empty list gracefully."""
        path = temp_dir / "corrupted.json"
        path.write_text("{ invalid }")
        assert ScheduleStore(storage_path=path).list() == []
