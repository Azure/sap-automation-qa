# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for ObservabilityMiddleware."""

import pytest
from pytest_mock import MockerFixture
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.observability.middleware import (
    ObservabilityMiddleware,
    add_observability_middleware,
    CORRELATION_ID_HEADER,
    WORKSPACE_ID_HEADER,
    SKIP_PATHS,
)


def _create_app_with_middleware() -> FastAPI:
    """Create a minimal FastAPI app with observability middleware."""
    app = FastAPI()
    add_observability_middleware(app)

    @app.get("/test")
    async def test_endpoint() -> dict:
        return {"ok": True}

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "healthy"}

    @app.get("/error")
    async def error_endpoint() -> dict:
        raise ValueError("test error")

    return app


class TestObservabilityMiddleware:
    """
    Tests for ObservabilityMiddleware.
    """

    @pytest.fixture
    def app(self) -> FastAPI:
        """
        Provide an app with middleware.
        """
        return _create_app_with_middleware()

    @pytest.fixture
    def test_client(self, app: FastAPI) -> TestClient:
        """
        Provide a test client.
        """
        return TestClient(app, raise_server_exceptions=False)

    def test_adds_correlation_id_to_response(self, test_client: TestClient) -> None:
        """
        Middleware injects correlation ID header into response.
        """
        response = test_client.get("/test")
        assert response.status_code == 200
        assert CORRELATION_ID_HEADER in response.headers

    def test_preserves_provided_correlation_id(self, test_client: TestClient) -> None:
        """
        Middleware uses client-provided correlation ID.
        """
        cid = "my-custom-correlation-id"
        response = test_client.get(
            "/test",
            headers={CORRELATION_ID_HEADER: cid},
        )
        assert response.status_code == 200
        assert response.headers[CORRELATION_ID_HEADER] == cid

    def test_skips_healthz(self, test_client: TestClient) -> None:
        """
        Middleware skips skip paths without adding headers.
        """
        response = test_client.get("/healthz")
        assert response.status_code == 200
        assert CORRELATION_ID_HEADER not in response.headers

    def test_workspace_id_from_header(self, test_client: TestClient) -> None:
        """
        Middleware extracts workspace ID from header.
        """
        response = test_client.get(
            "/test",
            headers={WORKSPACE_ID_HEADER: "WS-123"},
        )
        assert response.status_code == 200

    def test_workspace_id_from_query_param(self, test_client: TestClient) -> None:
        """
        Middleware extracts workspace ID from query parameter.
        """
        response = test_client.get("/test?workspace_id=WS-456")
        assert response.status_code == 200

    def test_error_response_logged(self, test_client: TestClient) -> None:
        """
        Middleware logs error responses with correct status code.
        """
        response = test_client.get("/error")
        assert response.status_code == 500

    def test_forwarded_for_header(self, test_client: TestClient) -> None:
        """
        Middleware extracts client IP from X-Forwarded-For.
        """
        response = test_client.get(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"},
        )
        assert response.status_code == 200

    def test_get_client_ip_no_forwarded(self, mocker: MockerFixture) -> None:
        """
        Returns client host when no X-Forwarded-For header.
        """
        request = mocker.MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"
        ip = ObservabilityMiddleware._get_client_ip(request)
        assert ip == "127.0.0.1"

    def test_get_client_ip_no_client(self, mocker: MockerFixture) -> None:
        """
        Returns None when no client info available.
        """
        request = mocker.MagicMock()
        request.headers = {}
        request.client = None
        ip = ObservabilityMiddleware._get_client_ip(request)
        assert ip is None

    def test_get_client_ip_forwarded_for(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        Returns first IP from X-Forwarded-For header.
        """
        request = mocker.MagicMock()
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        ip = ObservabilityMiddleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_add_observability_middleware(self) -> None:
        """
        add_observability_middleware registers the middleware.
        """
        app = FastAPI()
        initial_count = len(app.user_middleware)
        add_observability_middleware(app)
        assert len(app.user_middleware) == initial_count + 1

    def test_skip_paths_constant(self) -> None:
        """
        SKIP_PATHS contains expected paths.
        """
        assert "/healthz" in SKIP_PATHS
        assert "/favicon.ico" in SKIP_PATHS
        assert "/metrics" in SKIP_PATHS
