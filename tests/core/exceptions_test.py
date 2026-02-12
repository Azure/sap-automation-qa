# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for execution exceptions."""

from src.core.execution.exceptions import (
    ExecutionError,
    WorkspaceLockError,
    JobNotFoundError,
    JobCancellationError,
)


class TestExecutionExceptions:
    """
    Tests for the execution exception hierarchy.
    """

    def test_execution_error_is_exception(self) -> None:
        """
        ExecutionError inherits from Exception.
        """
        err = ExecutionError("base error")
        assert isinstance(err, Exception)
        assert str(err) == "base error"

    def test_workspace_lock_error_attributes(self) -> None:
        """
        WorkspaceLockError stores workspace_id and active_job_id.
        """
        err = WorkspaceLockError(
            workspace_id="WS-01",
            active_job_id="job-abc",
        )
        assert err.workspace_id == "WS-01"
        assert err.active_job_id == "job-abc"
        assert "WS-01" in str(err)
        assert "job-abc" in str(err)
        assert isinstance(err, ExecutionError)

    def test_job_not_found_error_attributes(self) -> None:
        """
        JobNotFoundError stores job_id.
        """
        err = JobNotFoundError(job_id="job-xyz")
        assert err.job_id == "job-xyz"
        assert "job-xyz" in str(err)
        assert isinstance(err, ExecutionError)

    def test_job_cancellation_error_attributes(self) -> None:
        """
        JobCancellationError stores job_id and reason.
        """
        err = JobCancellationError(
            job_id="job-999",
            reason="timeout exceeded",
        )
        assert err.job_id == "job-999"
        assert err.reason == "timeout exceeded"
        assert "job-999" in str(err)
        assert "timeout exceeded" in str(err)
        assert isinstance(err, ExecutionError)

    def test_exceptions_are_catchable_as_base(self) -> None:
        """
        All subclasses are catchable as ExecutionError.
        """
        for exc in [
            WorkspaceLockError("ws", "job"),
            JobNotFoundError("job"),
            JobCancellationError("job", "reason"),
        ]:
            try:
                raise exc
            except ExecutionError as caught:
                assert caught is exc
