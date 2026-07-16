# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workspace backend protocols (P1-WP-004)."""

from __future__ import annotations
from typing import Protocol, runtime_checkable
from src.core.models.workspace import MaterializedWorkspace, WorkspaceConfig, WorkspaceSummary


@runtime_checkable
class WorkspaceReader(Protocol):
    """Protocol for reading workspace configuration (API routes)."""

    def list_workspaces(self) -> list[WorkspaceSummary]:
        """List all available workspaces."""
        ...

    def get_workspace_config(self, workspace_id: str) -> WorkspaceConfig:
        """Read workspace configuration by ID."""
        ...

    @property
    def backend_name(self) -> str:
        """Return backend type identifier for health reporting."""
        ...


@runtime_checkable
class WorkspaceMaterializer(Protocol):
    """Protocol for materializing workspace config for job execution."""

    def materialize(self, workspace_id: str, job_id: str) -> MaterializedWorkspace:
        """Materialize workspace config into a local execution directory."""
        ...

    def cleanup(self, materialized: MaterializedWorkspace) -> None:
        """Clean up a materialized workspace after job completion."""
        ...

    @property
    def backend_name(self) -> str:
        """Return backend type identifier."""
        ...
