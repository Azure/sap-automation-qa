# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Schedules API routes."""

from fastapi.testclient import TestClient
from src.core.models.schedule import Schedule


class TestSchedulesApi:
    """Tests for the Schedules API routes."""

    def test_list_schedules_empty(self, client: TestClient) -> None:
        """
        Returns empty list when no schedules exist.
        """
        response = client.get("/api/v1/schedules")
        assert response.status_code == 200
        data = response.json()
        assert data["schedules"] == []
        assert data["total"] == 0

    def test_list_schedules_with_data(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Returns schedules when data exists.
        """
        response = client.get("/api/v1/schedules")
        assert response.status_code == 200
        data = response.json()
        assert len(data["schedules"]) == 1
        assert data["schedules"][0]["name"] == sample_schedule.name

    def test_get_schedule_success(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Returns schedule when found.
        """
        response = client.get(f"/api/v1/schedules/{sample_schedule.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_schedule.id
        assert data["name"] == sample_schedule.name

    def test_get_schedule_not_found(self, client: TestClient) -> None:
        """
        Returns 404 when schedule not found.
        """
        assert client.get("/api/v1/schedules/nonexistent-id").status_code == 404

    def test_create_schedule_success(self, client: TestClient) -> None:
        """
        Creates schedule successfully.
        """
        response = client.post(
            "/api/v1/schedules",
            json={
                "name": "Weekly HA Tests",
                "cron_expression": "0 0 * * 0",
                "workspace_ids": ["WS-01"],
                "test_group": "HA_DB_HANA",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Weekly HA Tests"
        assert data["enabled"] is True
        assert "id" in data

    def test_create_schedule_missing_name(self, client: TestClient) -> None:
        """
        Returns 422 when name missing.
        """
        assert (
            client.post(
                "/api/v1/schedules",
                json={
                    "cron_expression": "0 0 * * *",
                    "workspace_ids": ["WS-01"],
                },
            ).status_code
            == 422
        )

    def test_create_schedule_missing_cron(self, client: TestClient) -> None:
        """
        Returns 422 when cron_expression missing.
        """
        assert (
            client.post(
                "/api/v1/schedules",
                json={
                    "name": "Test Schedule",
                    "workspace_ids": ["WS-01"],
                },
            ).status_code
            == 422
        )

    def test_update_schedule_success(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Updates schedule successfully.
        """
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"name": "Updated Name", "enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["enabled"] is False

    def test_update_schedule_not_found(self, client: TestClient) -> None:
        """
        Returns 404 when schedule not found.
        """
        assert (
            client.patch(
                "/api/v1/schedules/nonexistent-id",
                json={"name": "New Name"},
            ).status_code
            == 404
        )

    def test_update_schedule_partial(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Partial updates preserve other fields.
        """
        original_cron = sample_schedule.cron_expression
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cron_expression"] == original_cron
        assert data["description"] == "Updated description"

    def test_delete_schedule_success(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Deletes schedule successfully.
        """
        response = client.delete(f"/api/v1/schedules/{sample_schedule.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert client.get(f"/api/v1/schedules/{sample_schedule.id}").status_code == 404

    def test_delete_schedule_not_found(self, client: TestClient) -> None:
        """
        Returns 404 when schedule not found.
        """
        assert client.delete("/api/v1/schedules/nonexistent-id").status_code == 404

    def test_create_schedule_with_defaults(self, client: TestClient) -> None:
        """
        Creates schedule with default values.
        """
        response = client.post(
            "/api/v1/schedules",
            json={
                "name": "Minimal Schedule",
                "cron_expression": "0 12 * * *",
                "workspace_ids": ["WS-01"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["timezone"] == "UTC"
        assert data["enabled"] is True
        assert data["total_runs"] == 0

    def test_update_schedule_empty_payload(
        self, client: TestClient, sample_schedule: Schedule
    ) -> None:
        """
        Empty update payload preserves all fields.
        """
        response = client.patch(f"/api/v1/schedules/{sample_schedule.id}", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_schedule.name

    def test_cron_change_recalculates_next_run(
        self, client: TestClient, sample_schedule: Schedule
    ) -> None:
        """
        Changing cron_expression recalculates next_run_time.
        """
        original_next = client.get(f"/api/v1/schedules/{sample_schedule.id}").json()[
            "next_run_time"
        ]
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"cron_expression": "30 6 * * *"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["next_run_time"] is not None
        assert data["next_run_time"] != original_next
        assert data["cron_expression"] == "30 6 * * *"

    def test_disable_clears_next_run(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Disabling a schedule clears next_run_time.
        """
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["next_run_time"] is None

    def test_reenable_sets_next_run(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Re-enabling a schedule recalculates next_run_time.
        """
        client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"enabled": False},
        )
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"enabled": True},
        )
        assert response.status_code == 200
        assert response.json()["next_run_time"] is not None

    def test_description_change_preserves_next_run(
        self, client: TestClient, sample_schedule: Schedule
    ) -> None:
        """
        Non-scheduling fields don't recalculate next_run_time.
        """
        original = client.get(f"/api/v1/schedules/{sample_schedule.id}").json()
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"description": "new description"},
        )
        assert response.status_code == 200
        assert response.json()["next_run_time"] == original["next_run_time"]

    def test_timezone_change_recalculates(
        self, client: TestClient, sample_schedule: Schedule
    ) -> None:
        """
        Changing timezone recalculates next_run_time.
        """
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"timezone": "US/Pacific"},
        )
        assert response.status_code == 200
        assert response.json()["next_run_time"] is not None

    def test_update_sets_updated_at(self, client: TestClient, sample_schedule: Schedule) -> None:
        """
        Any update sets updated_at to current time.
        """
        original = client.get(f"/api/v1/schedules/{sample_schedule.id}").json()
        response = client.patch(
            f"/api/v1/schedules/{sample_schedule.id}",
            json={"name": "Renamed"},
        )
        assert response.status_code == 200
        assert response.json()["updated_at"] >= original["updated_at"]

    def test_create_enabled_schedule_has_next_run(self, client: TestClient) -> None:
        """
        Creating an enabled schedule sets next_run_time.
        """
        response = client.post(
            "/api/v1/schedules",
            json={
                "name": "Enabled Schedule",
                "cron_expression": "0 12 * * *",
                "workspace_ids": ["WS-01"],
            },
        )
        assert response.status_code == 201
        assert response.json()["next_run_time"] is not None

    def test_create_disabled_schedule_no_next_run(self, client: TestClient) -> None:
        """
        Creating a disabled schedule has no next_run_time.
        """
        response = client.post(
            "/api/v1/schedules",
            json={
                "name": "Disabled Schedule",
                "cron_expression": "0 12 * * *",
                "workspace_ids": ["WS-01"],
                "enabled": False,
            },
        )
        assert response.status_code == 201
        assert response.json()["next_run_time"] is None
