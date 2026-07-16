# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Canonical core domain exceptions."""


class WorkspaceBackendError(Exception):
    """Base error for workspace backend operations."""


class WorkspaceNotFoundError(WorkspaceBackendError):
    """Raised when a workspace does not exist."""


class WorkspaceValidationError(WorkspaceBackendError):
    """Raised for invalid workspace IDs or path traversal attempts."""


class WorkspaceConfigError(WorkspaceBackendError):
    """Raised for malformed, oversized, or missing config files."""


class ETagMismatchError(WorkspaceBackendError):
    """Raised when workspace files have inconsistent ETags (revision mismatch)."""


class ConcurrencyConflictError(RuntimeError):
    """Raised when an Azure Table optimistic-concurrency update loses."""


class EntityTooLargeError(ValueError):
    """Raised when an entity exceeds Azure Table Storage size limits."""


class KnowledgeExtractionError(ValueError):
    """Base error for invalid authoritative knowledge sources."""


class ConfigurationCheckExtractionError(KnowledgeExtractionError):
    """Raised when configuration-check knowledge cannot be normalized."""


class HAExtractionError(KnowledgeExtractionError):
    """Raised when HA or backup knowledge cannot be normalized."""


class KnowledgeIndexError(Exception):
    """Base error for generated knowledge-index operations."""


class IndexMissingError(KnowledgeIndexError):
    """Raised when the generated knowledge index does not exist."""


class IndexCorruptError(KnowledgeIndexError):
    """Raised when the generated knowledge index is not valid SQLite."""


class IndexIncompatibleError(KnowledgeIndexError):
    """Raised when the generated index schema is incompatible."""


class InvalidQueryError(KnowledgeIndexError):
    """Raised when a knowledge search query is invalid."""


class InvalidFilterError(KnowledgeIndexError):
    """Raised when a knowledge search filter is invalid."""


class InvalidLimitError(KnowledgeIndexError):
    """Raised when a knowledge search limit is invalid."""


class BuildValidationError(KnowledgeIndexError):
    """Raised when generated-index validation fails."""
