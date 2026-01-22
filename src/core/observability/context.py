# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Request context management using ContextVars.
Thread-safe, async-compatible context propagation for observability.
"""

from __future__ import annotations
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class ContextData:
    """
    Immutable value object containing observability context fields.
    """

    correlation_id: Optional[str] = None
    workspace_id: Optional[str] = None
    execution_id: Optional[str] = None

    def with_updates(self, **kwargs: Any) -> "ContextData":
        """
        Create new ContextData with updated fields.
        """
        current = {
            "correlation_id": self.correlation_id,
            "workspace_id": self.workspace_id,
            "execution_id": self.execution_id,
        }
        current.update(kwargs)
        return ContextData(**current)

    def to_dict(self) -> dict[str, Optional[str]]:
        """
        Convert to dictionary for logging (non-None values only).
        """
        return {
            k: v
            for k, v in {
                "correlation_id": self.correlation_id,
                "workspace_id": self.workspace_id,
                "execution_id": self.execution_id,
            }.items()
            if v is not None
        }


class IContextProvider(Protocol):
    """Protocol for context providers - enables testing and alternative implementations."""

    def get_context(self) -> ContextData:
        """Get current context data."""
        ...

    def set_context(self, data: ContextData) -> Token:
        """Set context data, returning token for restoration."""
        ...

    def reset(self, token: Token) -> None:
        """Reset context to previous state using token."""
        ...


class ContextVarProvider:
    """
    Thread-safe context provider using Python's ContextVar.
    """

    def __init__(self) -> None:
        """Initialize with empty context."""
        self._var: ContextVar[ContextData] = ContextVar(
            "observability_context",
            default=ContextData(),
        )

    def get_context(self) -> ContextData:
        """Get current context data.

        :returns: Current ContextData
        :rtype: ContextData
        """
        return self._var.get()

    def set_context(self, data: ContextData) -> Token:
        """Set context data, returning token for restoration.

        :param data: ContextData to set
        :type data: ContextData
        :returns: Token for resetting to previous state
        :rtype: Token
        """
        return self._var.set(data)

    def reset(self, token: Token) -> None:
        """Reset context to previous state using token.

        :param token: Token from previous set_context call
        :type token: Token
        """
        self._var.reset(token)


class ObservabilityContextManager:
    """
    Singleton manager for observability context.
    Provides high-level API for context operations while encapsulating
    the underlying ContextVar implementation.
    """

    _instance: Optional["ObservabilityContextManager"] = None
    _provider: Optional[ContextVarProvider] = None

    def __new__(cls) -> "ObservabilityContextManager":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._provider = ContextVarProvider()
        return cls._instance

    @classmethod
    def instance(cls) -> "ObservabilityContextManager":
        """Get singleton instance.

        :returns: Singleton ObservabilityContextManager
        :rtype: ObservabilityContextManager
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing only)."""
        cls._instance = None
        cls._provider = None

    @property
    def _ctx_provider(self) -> ContextVarProvider:
        """Get provider with type safety.

        :returns: The context provider
        :rtype: ContextVarProvider
        """
        assert self._provider is not None, "ObservabilityContextManager not initialized"
        return self._provider

    @property
    def correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return self._ctx_provider.get_context().correlation_id

    @property
    def workspace_id(self) -> Optional[str]:
        """Get current workspace ID."""
        return self._ctx_provider.get_context().workspace_id

    @property
    def execution_id(self) -> Optional[str]:
        """Get current execution ID."""
        return self._ctx_provider.get_context().execution_id

    def set_correlation_id(self, value: Optional[str] = None) -> str:
        """Set correlation ID (generates UUID if None)."""
        cid = value or str(uuid.uuid4())
        current = self._ctx_provider.get_context()
        self._ctx_provider.set_context(current.with_updates(correlation_id=cid))
        return cid

    def set_workspace_id(self, value: Optional[str]) -> None:
        """Set current workspace ID.

        :param value: Workspace ID
        :type value: Optional[str]
        """
        current = self._ctx_provider.get_context()
        self._ctx_provider.set_context(current.with_updates(workspace_id=value))

    def set_execution_id(self, value: Optional[str] = None) -> str:
        """Set execution ID (generates UUID if None).

        :param value: Execution ID or None to generate
        :type value: Optional[str]
        :returns: The execution ID that was set
        :rtype: str
        """
        eid = value or str(uuid.uuid4())
        current = self._ctx_provider.get_context()
        self._ctx_provider.set_context(current.with_updates(execution_id=eid))
        return eid

    def get_all(self) -> dict[str, Optional[str]]:
        """Get all context values as dictionary.

        :returns: Dictionary with all context values
        :rtype: dict[str, Optional[str]]
        """
        return self._ctx_provider.get_context().to_dict()

    def clear(self) -> None:
        """Clear all context values."""
        self._ctx_provider.set_context(ContextData())


class ObservabilityScope:
    """
    Context manager for scoped observability context.
    """

    def __init__(
        self,
        correlation_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        auto_correlation_id: bool = False,
        auto_execution_id: bool = False,
    ) -> None:
        """Initialize scope with context values.

        :param correlation_id: Correlation ID to set
        :param workspace_id: Workspace ID to set
        :param execution_id: Execution ID to set
        :param auto_correlation_id: Generate correlation_id if not provided
        :param auto_execution_id: Generate execution_id if not provided
        """
        self._correlation_id = correlation_id
        self._workspace_id = workspace_id
        self._execution_id = execution_id
        self._auto_correlation_id = auto_correlation_id
        self._auto_execution_id = auto_execution_id
        self._token: Optional[Token] = None
        self._manager = ObservabilityContextManager.instance()

    def __enter__(self) -> "ObservabilityScope":
        """Enter scope and set context values."""
        provider = self._manager._ctx_provider
        current = provider.get_context()

        updates: dict[str, str] = {}

        if self._correlation_id is not None:
            updates["correlation_id"] = self._correlation_id
        elif self._auto_correlation_id:
            updates["correlation_id"] = str(uuid.uuid4())

        if self._workspace_id is not None:
            updates["workspace_id"] = self._workspace_id

        if self._execution_id is not None:
            updates["execution_id"] = self._execution_id
        elif self._auto_execution_id:
            updates["execution_id"] = str(uuid.uuid4())

        if updates:
            new_context = current.with_updates(**updates)
            self._token = provider.set_context(new_context)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit scope and restore previous context."""
        if self._token is not None:
            self._manager._ctx_provider.reset(self._token)
            self._token = None




class ExecutionScope(ObservabilityScope):
    """
    Specialized scope for test/Ansible execution.
    """

    def __init__(
        self,
        workspace_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Initialize execution scope.

        :param workspace_id: Workspace ID
        :param kwargs: Additional scope parameters
        """
        super().__init__(
            workspace_id=workspace_id,
            auto_execution_id=True,
            **kwargs,
        )


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return ObservabilityContextManager.instance().correlation_id


def set_correlation_id(value: Optional[str] = None) -> str:
    """Set correlation ID."""
    return ObservabilityContextManager.instance().set_correlation_id(value)


def get_workspace_id() -> Optional[str]:
    """Get current workspace ID."""
    return ObservabilityContextManager.instance().workspace_id


def set_workspace_id(value: Optional[str]) -> None:
    """Set workspace ID."""
    ObservabilityContextManager.instance().set_workspace_id(value)


def get_execution_id() -> Optional[str]:
    """Get current execution ID."""
    return ObservabilityContextManager.instance().execution_id


def clear_context() -> None:
    """Clear all context."""
    ObservabilityContextManager.instance().clear()


ObservabilityContext = ObservabilityScope
ExecutionContext = ExecutionScope
