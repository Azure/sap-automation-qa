# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Workspace models."""
from typing import List
from pydantic import BaseModel


class WorkspaceInfo(BaseModel):
    """Workspace information."""

    id: str
    name: str
    environment: str = ""
    path: str = ""


class WorkspaceListResponse(BaseModel):
    """Response containing list of workspaces."""

    workspaces: List[WorkspaceInfo]
    total: int
