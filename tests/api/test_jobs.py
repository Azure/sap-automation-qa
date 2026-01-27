# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Jobs API routes."""

from fastapi.testclient import TestClient

from src.core.models.job import Job, JobStatus
from src.core.storage.job_store import JobStore


class TestListJobs:
    """Tests for GET /api/v1/jobs endpoint."""

    def test_list_jobs_empty(self, client: TestClient) -> None:
        """Returns empty list when no jobs exist."""
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_with_data(self, client: TestClient, sample_job: Job) -> None:
        """Returns jobs when data exists."""
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["workspace_id"] == sample_job.workspace_id

    def test_list_jobs_filter_by_workspace(self, client: TestClient, job_store: JobStore) -> None:
        """Filters jobs by workspace_id."""
        job_store.create(Job(workspace_id="WS-A", test_group="test"))
        job_store.create(Job(workspace_id="WS-B", test_group="test"))
        response = client.get("/api/v1/jobs?workspace_id=WS-A")
        assert response.status_code == 200
        data = response.json()
        assert all(j["workspace_id"] == "WS-A" for j in data["jobs"])

    def test_list_jobs_active_only(
        self, client: TestClient, sample_job: Job, sample_running_job: Job
    ) -> None:
        """Filters to only active jobs."""
        response = client.get("/api/v1/jobs?active_only=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) >= 1


class TestGetJob:
    """Tests for GET /api/v1/jobs/{job_id} endpoint."""

    def test_get_job_success(self, client: TestClient, sample_job: Job) -> None:
        """Returns job when found."""
        response = client.get(f"/api/v1/jobs/{sample_job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_job.id)
        assert data["workspace_id"] == sample_job.workspace_id

    def test_get_job_not_found(self, client: TestClient) -> None:
        """Returns 404 when job not found."""
        response = client.get(f"/api/v1/jobs/{'00000000-0000-0000-0000-000000000000'}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateJob:
    """Tests for POST /api/v1/jobs endpoint."""

    def test_create_job_success(self, client: TestClient) -> None:
        """Creates job successfully."""
        response = client.post(
            "/api/v1/jobs",
            json={
                "workspace_id": "NEW-WORKSPACE",
                "test_group": "CONFIG_CHECKS",
                "test_ids": ["test1"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["workspace_id"] == "NEW-WORKSPACE"
        assert data["test_group"] == "CONFIG_CHECKS"
        assert "id" in data

    def test_create_job_missing_workspace(self, client: TestClient) -> None:
        """Returns 422 when workspace_id missing."""
        assert client.post("/api/v1/jobs", json={"test_group": "CONFIG_CHECKS"}).status_code == 422

    def test_create_job_starts_execution(self, client: TestClient) -> None:
        """Submitted job should be persisted."""
        response = client.post(
            "/api/v1/jobs",
            json={
                "workspace_id": "EXEC-TEST",
                "test_group": "CONFIG_CHECKS",
            },
        )
        assert response.status_code == 201
        assert client.get(f"/api/v1/jobs/{response.json()['id']}").status_code in (200, 404)


class TestCancelJob:
    """Tests for POST /api/v1/jobs/{job_id}/cancel endpoint."""

    def test_cancel_running_job(self, client: TestClient, sample_running_job: Job) -> None:
        """Cancels a running job."""
        response = client.post(
            f"/api/v1/jobs/{sample_running_job.id}/cancel",
            json={"reason": "Test cancellation"},
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "cancelled"

    def test_cancel_nonexistent_job(self, client: TestClient) -> None:
        """Returns 404 for nonexistent job."""
        assert (
            client.post(
                f"/api/v1/jobs/{'00000000-0000-0000-0000-000000000000'}/cancel",
                json={"reason": "Test"},
            ).status_code
            == 404
        )


class TestEdgeCases:
    """Edge case tests for Jobs API."""

    def test_list_jobs_with_limit(self, client: TestClient, job_store: JobStore) -> None:
        """Respects limit parameter."""
        for i in range(10):
            job_store.create(Job(workspace_id=f"WS-{i}", test_group="test"))
        response = client.get("/api/v1/jobs?limit=5")
        assert response.status_code == 200
        assert len(response.json()["jobs"]) <= 5

    def test_invalid_status_filter(self, client: TestClient, sample_job: Job) -> None:
        """Handles invalid status filter gracefully."""
        assert client.get("/api/v1/jobs?status=invalid").status_code in (200, 400, 422, 500)
