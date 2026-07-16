# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workspace models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel


class WorkspaceInfo(BaseModel):
    """Workspace information."""

    id: str
    name: str
    environment: str = ""
    path: str = ""


class WorkspaceListResponse(BaseModel):
    """Response containing list of workspaces."""

    workspaces: list[WorkspaceInfo]
    total: int


@dataclass(frozen=True)
class WorkspaceManifest:
    """Commit marker for a workspace blob revision."""

    schema_version: int
    revision: str
    hosts_yaml_etag: str
    sap_parameters_yaml_etag: str


@dataclass(frozen=True)
class WorkspaceConfig:
    """Parsed workspace configuration from hosts.yaml and sap-parameters.yaml."""

    workspace_id: str
    inventory_path: str
    sap_sid: str = ""
    db_sid: str = ""
    database_high_availability: bool = False
    scs_high_availability: bool = False
    extra_vars: Mapping[str, Any] = field(default_factory=dict)
    path: str = ""

    def __post_init__(self) -> None:
        """Store a defensive copy of extra_vars."""
        object.__setattr__(self, "extra_vars", dict(self.extra_vars))


@dataclass(frozen=True)
class WorkspaceSummary:
    """Summary info for listing workspaces."""

    workspace_id: str
    name: str
    environment: str = ""
    path: str = ""


@dataclass(frozen=True)
class MaterializedWorkspace:
    """Result of materializing a workspace for job execution."""

    workspace_id: str
    job_id: str
    local_path: Path
    inventory_path: str
    extra_vars: Mapping[str, Any] = field(default_factory=dict)
    owned: bool = False

    def __post_init__(self) -> None:
        """Store a defensive copy of extra_vars."""
        object.__setattr__(self, "extra_vars", dict(self.extra_vars))
