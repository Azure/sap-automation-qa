# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Storage context model."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

from src.core.contracts.storage import JobStoreProtocol, ScheduleStoreProtocol


class Closeable(Protocol):
    """Resource that can be closed by a storage context."""

    def close(self) -> None:
        """Release the owned resource."""
        ...


@dataclass
class StorageContext:
    """
    Bundles the storage backend with the job and schedule stores.
    """

    backend: str
    db: Closeable | None
    job_store: JobStoreProtocol
    schedule_store: ScheduleStoreProtocol
    owned_resources: tuple[Closeable, ...]
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Close exactly the resources owned by this storage context."""
        if self._closed:
            return

        errors: list[Exception] = []
        for resource in self.owned_resources:
            try:
                resource.close()
            except Exception as exc:
                errors.append(exc)
        if errors:
            if len(errors) > 1:
                raise RuntimeError("Multiple storage resources failed to close") from errors[0]
            raise errors[0]
        self._closed = True
