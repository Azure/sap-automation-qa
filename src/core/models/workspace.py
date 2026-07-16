# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workspace models."""

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
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
        """Deep-freeze a detached copy of execution variables."""
        object.__setattr__(self, "extra_vars", _freeze_value(self.extra_vars))


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
        """Deep-freeze a detached copy of execution variables."""
        object.__setattr__(self, "extra_vars", _freeze_value(self.extra_vars))


def _freeze_value(value: Any) -> Any:
    """Create an immutable, detached representation of a configuration value."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)
    return deepcopy(value)


def mutable_workspace_vars(values: Mapping[str, Any]) -> dict[str, Any]:
    """Convert frozen workspace variables to native mutable Ansible values.

    :param values: Deeply frozen workspace variables.
    :returns: A detached dictionary containing native dictionaries and lists.
    """

    def _thaw(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: _thaw(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [_thaw(item) for item in value]
        if isinstance(value, frozenset):
            return [_thaw(item) for item in value]
        return deepcopy(value)

    return {key: _thaw(value) for key, value in values.items()}
