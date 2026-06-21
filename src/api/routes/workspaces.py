# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workspaces API routes."""

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yaml
from fastapi import APIRouter, HTTPException
from src.core.observability import get_logger
from src.core.models.workspace import WorkspaceInfo, WorkspaceListResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])
_workspace_loader: Optional[Callable[[str], Dict[str, Any]]] = None

_WORKSPACE_BASE_DIR = "WORKSPACES/SYSTEM"
_VALID_WORKSPACE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _validate_workspace_id(workspace_id: str) -> Path:
    """Validate workspace_id to prevent path traversal attacks.

    :param workspace_id: The workspace identifier to validate.
    :type workspace_id: str
    :returns: Resolved safe path for the workspace directory.
    :rtype: Path
    :raises HTTPException: If the workspace_id is invalid (400 error).
    """
    if not workspace_id or "\x00" in workspace_id:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    if not _VALID_WORKSPACE_ID_PATTERN.match(workspace_id):
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    base_path = os.path.realpath(_WORKSPACE_BASE_DIR)
    fullpath = os.path.normpath(os.path.join(base_path, workspace_id))
    if not fullpath.startswith(base_path + os.sep):
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    return Path(fullpath)


def set_workspace_loader(loader: Callable[[str], Dict[str, Any]]) -> None:
    """Set the workspace loader function.

    :param loader: Callable that loads workspace config by ID.
    :type loader: Callable[[str], Dict[str, Any]]
    """
    global _workspace_loader
    _workspace_loader = loader


def _load_workspaces_from_directory(base_dir: str = "WORKSPACES/SYSTEM") -> List[WorkspaceInfo]:
    """Load workspaces from WORKSPACES/SYSTEM directory structure.

    :param base_dir: Base directory containing workspace subdirectories.
    :type base_dir: str
    :returns: List of discovered workspace information.
    :rtype: List[WorkspaceInfo]
    """
    workspaces = []
    base_path = Path(base_dir)

    if not base_path.exists():
        logger.warning(f"Workspaces directory not found: {base_dir}")
        return workspaces

    for workspace_dir in base_path.iterdir():
        if not workspace_dir.is_dir() or workspace_dir.name.startswith("."):
            continue
        hosts_file = workspace_dir / "hosts.yaml"
        params_file = workspace_dir / "sap-parameters.yaml"

        if not hosts_file.exists() and not params_file.exists():
            continue

        sap_sid = ""

        if params_file.exists():
            try:
                with open(params_file) as f:
                    params = yaml.safe_load(f) or {}
                sap_sid = params.get("sap_sid", "")
            except Exception as e:
                logger.warning(f"Failed to load sap-parameters for {workspace_dir.name}: {e}")

        workspaces.append(
            WorkspaceInfo(
                id=workspace_dir.name,
                name=sap_sid or workspace_dir.name,
                environment=workspace_dir.name.split("-")[0] if "-" in workspace_dir.name else "",
                path=str(workspace_dir),
            )
        )

    return workspaces


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces() -> WorkspaceListResponse:
    """List all available workspaces.

    :returns: Response containing list of workspaces and total count.
    :rtype: WorkspaceListResponse
    """
    workspaces = _load_workspaces_from_directory()
    return WorkspaceListResponse(workspaces=workspaces, total=len(workspaces))


@router.get("/{workspace_id}", response_model=WorkspaceInfo)
async def get_workspace(workspace_id: str) -> WorkspaceInfo:
    """Get a specific workspace.

    :param workspace_id: ID of the workspace to retrieve.
    :type workspace_id: str
    :returns: Workspace information.
    :rtype: WorkspaceInfo
    :raises HTTPException: If workspace not found (404) or invalid ID (400).
    """
    _validate_workspace_id(workspace_id)
    workspaces = _load_workspaces_from_directory()

    for ws in workspaces:
        if ws.id == workspace_id:
            return ws

    if _workspace_loader:
        result = _workspace_loader(workspace_id)
        if result:
            return WorkspaceInfo(
                id=workspace_id,
                name=result.get("name", workspace_id),
                environment=result.get("environment", ""),
                path=result.get("path", ""),
            )

    raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")


def default_workspace_loader(workspace_id: str) -> Dict[str, Any]:
    """Default workspace config loader.

    :param workspace_id: ID of the workspace to load.
    :type workspace_id: str
    :returns: Workspace configuration dictionary.
    :rtype: Dict[str, Any]
    :raises HTTPException: If the workspace_id is invalid (400 error).
    """
    workspace_dir = _validate_workspace_id(workspace_id)

    if not workspace_dir.exists():
        return {}

    hosts_file = workspace_dir / "hosts.yaml"
    params_file = workspace_dir / "sap-parameters.yaml"

    if not hosts_file.exists():
        return {}

    config: Dict[str, Any] = {
        "inventory_path": str(hosts_file),
    }

    if params_file.exists():
        try:
            with open(params_file) as f:
                params = yaml.safe_load(f) or {}
            config["sap_sid"] = params.get("sap_sid", "")
            config["db_sid"] = params.get("db_sid", "")
            config["database_high_availability"] = params.get("database_high_availability", False)
            config["scs_high_availability"] = params.get("scs_high_availability", False)
            config["extra_vars"] = params
        except Exception as e:
            logger.warning(f"Failed to load sap-parameters for {workspace_id}: {e}")

    return config
