# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for Workspaces API routes."""

import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from src.api.routes import workspaces
from src.api.routes.workspaces import (
    _load_workspaces_from_directory,
    default_workspace_loader,
    set_workspace_loader,
)


@pytest.fixture
def workspace_dir() -> Generator[Path, None, None]:
    """
    Provide a temp directory with workspace structure.
    """
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "WORKSPACES" / "SYSTEM"
        base.mkdir(parents=True)
        yield base


def _create_workspace(
    base: Path,
    name: str,
    *,
    sap_sid: str = "HDB",
    ha_db: bool = False,
    ha_scs: bool = False,
    hosts: bool = True,
    params: bool = True,
) -> Path:
    """Helper to create a workspace directory with config files."""
    ws_dir = base / name
    ws_dir.mkdir(parents=True, exist_ok=True)
    if hosts:
        (ws_dir / "hosts.yaml").write_text("all:\n  hosts:\n    node1:\n")
    if params:
        (ws_dir / "sap-parameters.yaml").write_text(
            f"sap_sid: {sap_sid}\n"
            f"database_high_availability: {str(ha_db).lower()}\n"
            f"scs_high_availability: {str(ha_scs).lower()}\n"
        )
    return ws_dir


class TestWorkspacesApi:
    """
    Tests for the Workspaces API routes.
    """

    def test_load_empty_directory(self, workspace_dir: Path) -> None:
        """
        Returns empty list when no workspaces exist.
        """
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert result == []

    def test_load_nonexistent_directory(self) -> None:
        """
        Returns empty list when base directory doesn't exist.
        """
        result = _load_workspaces_from_directory("/nonexistent/path")
        assert result == []

    def test_load_skips_hidden_directories(self, workspace_dir: Path) -> None:
        """
        Skips directories starting with dot.
        """
        hidden = workspace_dir / ".hidden"
        hidden.mkdir()
        (hidden / "hosts.yaml").write_text("all:\n")
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert result == []

    def test_load_skips_dir_without_config_files(self, workspace_dir: Path) -> None:
        """
        Skips directories without hosts.yaml or sap-parameters.yaml.
        """
        (workspace_dir / "EMPTY-WS").mkdir()
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert result == []

    def test_load_workspace_with_params(self, workspace_dir: Path) -> None:
        """
        Loads workspace with sap-parameters.yaml.
        """
        _create_workspace(workspace_dir, "DEV-EUS2-SAP01", sap_sid="HDB")
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert len(result) == 1
        assert result[0].id == "DEV-EUS2-SAP01"
        assert result[0].name == "HDB"
        assert result[0].environment == "DEV"

    def test_load_workspace_without_params(self, workspace_dir: Path) -> None:
        """
        Loads workspace with only hosts.yaml (no params).
        """
        _create_workspace(workspace_dir, "NOPARAM-WS", params=False)
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert len(result) == 1
        assert result[0].id == "NOPARAM-WS"
        assert result[0].name == "NOPARAM-WS"

    def test_load_workspace_no_hyphen_in_name(self, workspace_dir: Path) -> None:
        """
        Environment is empty string when no hyphen in workspace name.
        """
        _create_workspace(workspace_dir, "STANDALONE", sap_sid="S4H")
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert len(result) == 1
        assert result[0].environment == ""

    def test_load_workspace_invalid_yaml(self, workspace_dir: Path) -> None:
        """
        Handles invalid YAML in sap-parameters gracefully.
        """
        ws = workspace_dir / "BAD-YAML"
        ws.mkdir()
        (ws / "hosts.yaml").write_text("all:\n")
        (ws / "sap-parameters.yaml").write_text(": invalid: yaml: [[[")
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert len(result) == 1
        assert result[0].id == "BAD-YAML"

    def test_load_multiple_workspaces(self, workspace_dir: Path) -> None:
        """
        Loads multiple workspaces from directory.
        """
        _create_workspace(workspace_dir, "PRD-WS-01", sap_sid="HDB")
        _create_workspace(workspace_dir, "DEV-WS-02", sap_sid="S4H")
        result = _load_workspaces_from_directory(str(workspace_dir))
        assert len(result) == 2
        ids = {ws.id for ws in result}
        assert "PRD-WS-01" in ids
        assert "DEV-WS-02" in ids

    def test_list_workspaces_endpoint(self, client: TestClient) -> None:
        """
        GET /workspaces returns list response.
        """
        response = client.get("/api/v1/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert "workspaces" in data
        assert "total" in data

    def test_get_workspace_not_found(self, client: TestClient) -> None:
        """
        GET /workspaces/{id} returns 404 for nonexistent workspace.
        """
        response = client.get("/api/v1/workspaces/NONEXISTENT")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_default_workspace_loader_nonexistent(self) -> None:
        """
        Default loader returns empty dict for nonexistent workspace.
        """
        assert default_workspace_loader("DOES-NOT-EXIST") == {}

    def test_default_workspace_loader_no_hosts(
        self,
        workspace_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Default loader returns empty dict when hosts.yaml missing.
        """
        ws = workspace_dir / "NO-HOSTS"
        ws.mkdir()
        (ws / "sap-parameters.yaml").write_text("sap_sid: X\n")
        monkeypatch.chdir(workspace_dir.parent.parent)
        assert default_workspace_loader("NO-HOSTS") == {}

    def test_default_workspace_loader_with_config(
        self,
        workspace_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Default loader returns full config dict.
        """
        _create_workspace(
            workspace_dir,
            "FULL-WS",
            sap_sid="HDB",
            ha_db=True,
            ha_scs=False,
        )
        monkeypatch.chdir(workspace_dir.parent.parent)
        result = default_workspace_loader("FULL-WS")
        assert result["sap_sid"] == "HDB"
        assert result["database_high_availability"] is True
        assert result["scs_high_availability"] is False
        assert "inventory_path" in result
        assert "extra_vars" in result

    def test_default_workspace_loader_invalid_params(
        self,
        workspace_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Default loader handles invalid YAML in params gracefully.
        """
        ws = workspace_dir / "BAD-PARAMS"
        ws.mkdir()
        (ws / "hosts.yaml").write_text("all:\n")
        (ws / "sap-parameters.yaml").write_text(": [[[bad yaml")
        monkeypatch.chdir(workspace_dir.parent.parent)
        result = default_workspace_loader("BAD-PARAMS")
        assert "inventory_path" in result
        assert "sap_sid" not in result

    def test_set_workspace_loader(self) -> None:
        """
        set_workspace_loader sets the global loader.
        """
        original = workspaces._workspace_loader
        try:
            mock_loader = lambda ws_id: {"id": ws_id}
            set_workspace_loader(mock_loader)
            assert workspaces._workspace_loader is mock_loader
        finally:
            workspaces._workspace_loader = original
