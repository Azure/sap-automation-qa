# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Execution exceptions.
"""


class ExecutionError(Exception):
    """
    Base exception for execution errors.
    """

    pass


class WorkspaceLockError(ExecutionError):
    """
    Raised when workspace already has an active job.
    """

    def __init__(self, workspace_id: str, active_job_id: str) -> None:
        self.workspace_id = workspace_id
        self.active_job_id = active_job_id
        super().__init__(f"Workspace {workspace_id} already has active job {active_job_id}")


class JobNotFoundError(ExecutionError):
    """
    Raised when job is not found.
    """

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job {job_id} not found")


class JobCancellationError(ExecutionError):
    """
    Raised when job cancellation fails.
    """

    def __init__(self, job_id: str, reason: str) -> None:
        self.job_id = job_id
        self.reason = reason
        super().__init__(f"Failed to cancel job {job_id}: {reason}")


class CredentialProvisionError(ExecutionError):
    """Raised when SSH credential provisioning fails."""
