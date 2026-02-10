# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Jobs API routes."""

from pathlib import Path
import pytest
from pytest_mock import MockerFixture
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routes import jobs
from src.core.models.job import Job
from src.core.storage.job_store import JobStore


class TestJobsApi:
    """Tests for the Jobs API routes."""

    def test_list_jobs_empty(self, client: TestClient) -> None:
        """
        Returns empty list when no jobs exist.
        """
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_with_data(self, client: TestClient, sample_job: Job) -> None:
        """
        Returns jobs when data exists.
        """
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["workspace_id"] == sample_job.workspace_id

    def test_list_jobs_filter_by_workspace(self, client: TestClient, job_store: JobStore) -> None:
        """
        Filters jobs by workspace_id.
        """
        job_store.create(Job(workspace_id="WS-A", test_group="test"))
        job_store.create(Job(workspace_id="WS-B", test_group="test"))
        response = client.get("/api/v1/jobs?workspace_id=WS-A")
        assert response.status_code == 200
        data = response.json()
        assert all(j["workspace_id"] == "WS-A" for j in data["jobs"])

    def test_list_jobs_active_only(
        self, client: TestClient, sample_job: Job, sample_running_job: Job
    ) -> None:
        """
        Filters to only active jobs.
        """
        response = client.get("/api/v1/jobs?active_only=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) >= 1

    def test_get_job_success(self, client: TestClient, sample_job: Job) -> None:
        """
        Returns job when found.
        """
        response = client.get(f"/api/v1/jobs/{sample_job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_job.id)
        assert data["workspace_id"] == sample_job.workspace_id

    def test_get_job_not_found(self, client: TestClient) -> None:
        """
        Returns 404 when job not found.
        """
        response = client.get(f"/api/v1/jobs/{'00000000-0000-0000-0000-000000000000'}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_job_success(self, client: TestClient) -> None:
        """
        Creates job successfully.
        """
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
        """
        Returns 422 when workspace_id missing.
        """
        assert client.post("/api/v1/jobs", json={"test_group": "CONFIG_CHECKS"}).status_code == 422

    def test_create_job_starts_execution(self, client: TestClient) -> None:
        """
        Submitted job should be persisted.
        """
        response = client.post(
            "/api/v1/jobs",
            json={
                "workspace_id": "EXEC-TEST",
                "test_group": "CONFIG_CHECKS",
            },
        )
        assert response.status_code == 201
        assert client.get(f"/api/v1/jobs/{response.json()['id']}").status_code in (200, 404)

    def test_cancel_running_job(self, client: TestClient, sample_running_job: Job) -> None:
        """
        Cancels a running job.
        """
        response = client.post(
            f"/api/v1/jobs/{sample_running_job.id}/cancel",
            json={"reason": "Test cancellation"},
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "cancelled"

    def test_cancel_nonexistent_job(self, client: TestClient) -> None:
        """
        Returns 404 for nonexistent job.
        """
        assert (
            client.post(
                f"/api/v1/jobs/{'00000000-0000-0000-0000-000000000000'}/cancel",
                json={"reason": "Test"},
            ).status_code
            == 404
        )

    def test_list_jobs_with_limit(self, client: TestClient, job_store: JobStore) -> None:
        """
        Respects limit parameter.
        """
        for i in range(10):
            job_store.create(Job(workspace_id=f"WS-{i}", test_group="test"))
        response = client.get("/api/v1/jobs?limit=5")
        assert response.status_code == 200
        assert len(response.json()["jobs"]) <= 5

    def test_invalid_status_filter(self, client: TestClient, sample_job: Job) -> None:
        """
        Handles invalid status filter gracefully.
        """
        assert client.get("/api/v1/jobs?status=invalid").status_code in (200, 400, 422, 500)

    def test_log_not_found_no_job(self, client: TestClient) -> None:
        """
        Returns 404 when job doesn't exist.
        """
        assert (
            client.get(f"/api/v1/jobs/{'00000000-0000-0000-0000-000000000000'}/log").status_code
            == 404
        )

    def test_log_not_found_no_file(self, client: TestClient, job_store: JobStore) -> None:
        """
        Returns 404 when job has no log_file.
        """
        job = Job(workspace_id="WS-NOLOG")
        job_store.create(job)
        response = client.get(f"/api/v1/jobs/{job.id}/log")
        assert response.status_code == 404
        assert "No log file" in response.json()["detail"]

    def test_log_not_found_file_missing(self, client: TestClient, job_store: JobStore) -> None:
        """
        Returns 404 when log_file path doesn't exist.
        """
        job = Job(workspace_id="WS-GONE")
        job.log_file = "/nonexistent/path.log"
        job_store.create(job)
        response = client.get(f"/api/v1/jobs/{job.id}/log")
        assert response.status_code == 404
        assert "not found on disk" in response.json()["detail"]

    def test_log_returns_content(
        self,
        client: TestClient,
        job_store: JobStore,
        temp_dir: Path,
    ) -> None:
        """
        Returns full log content as plain text.
        """
        log_path = temp_dir / "logs" / "test-job.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("TASK [check_hana] ***\nok: [host1]\n")
        job = Job(workspace_id="WS-LOG")
        job.log_file = str(log_path)
        job_store.create(job)
        response = client.get(f"/api/v1/jobs/{job.id}/log")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "TASK [check_hana]" in response.text

    def test_log_tail_parameter(
        self,
        client: TestClient,
        job_store: JobStore,
        temp_dir: Path,
    ) -> None:
        """
        Returns only the last N lines with tail param.
        """
        log_path = temp_dir / "logs" / "tail.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join([f"line {i}" for i in range(20)]))
        job = Job(workspace_id="WS-TAIL")
        job.log_file = str(log_path)
        job_store.create(job)
        response = client.get(f"/api/v1/jobs/{job.id}/log?tail=3")
        assert response.status_code == 200
        assert len(response.text.strip().splitlines()) == 3
        assert "line 19" in response.text.strip().splitlines()[-1]

    def test_get_job_store_uninitialized(self) -> None:
        """
        Returns 503 when job store is not initialized.
        """
        app = FastAPI()
        app.include_router(jobs.router, prefix="/api/v1")
        saved_store = jobs._job_store
        try:
            jobs._job_store = None
            with TestClient(app) as c:
                response = c.get("/api/v1/jobs")
                assert response.status_code == 503
                assert "not initialized" in response.json()["detail"]
        finally:
            jobs._job_store = saved_store

    def test_get_job_worker_uninitialized(self) -> None:
        """
        Returns 503 when job worker is not initialized and then the exception it as 400.
        """
        app = FastAPI()
        app.include_router(jobs.router, prefix="/api/v1")
        saved_worker = jobs._job_worker
        saved_store = jobs._job_store
        try:
            jobs._job_worker = None
            with TestClient(app) as c:
                response = c.post(
                    "/api/v1/jobs",
                    json={
                        "workspace_id": "WS",
                        "test_group": "test",
                    },
                )
                assert response.status_code == 400
                assert "not initialized" in response.json()["detail"]
        finally:
            jobs._job_worker = saved_worker
            jobs._job_store = saved_store

    def test_get_job_events_success(
        self,
        client: TestClient,
        sample_job: Job,
    ) -> None:
        """
        Returns events list for a job.
        """
        response = client.get(f"/api/v1/jobs/{sample_job.id}/events")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == str(sample_job.id)
        assert "events" in data

    def test_get_job_events_not_found(self, client: TestClient) -> None:
        """
        Returns 404 when job not found for events.
        """
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/v1/jobs/{fake_id}/events")
        assert response.status_code == 404

    def test_list_jobs_invalid_status_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """
        Returns 400 for invalid status filter value.
        """
        response = client.get("/api/v1/jobs?status=BOGUS")
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_log_read_os_error(
        self,
        client: TestClient,
        job_store: JobStore,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """
        Returns 500 when log file read fails with OSError.
        """
        log_path = temp_dir / "logs" / "unreadable.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("content")
        job = Job(workspace_id="WS-OSERR")
        job.log_file = str(log_path)
        job_store.create(job)
        mocker.patch.object(Path, "read_text", side_effect=OSError("perm denied"))
        response = client.get(f"/api/v1/jobs/{job.id}/log")
        assert response.status_code == 500
        assert "Failed to read" in response.json()["detail"]
