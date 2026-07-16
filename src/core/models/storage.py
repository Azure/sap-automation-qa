# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Storage context model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.core.contracts.storage import JobStoreProtocol, ScheduleStoreProtocol

if TYPE_CHECKING:
    from src.core.storage.staf_store import StafStore


@dataclass
class StorageContext:
    """
    Bundles the storage backend with the job and schedule stores.
    """

    backend: str
    db: StafStore | None
    job_store: JobStoreProtocol
    schedule_store: ScheduleStoreProtocol
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Close exactly the resources owned by this storage context."""
        if self._closed:
            return
        self._closed = True

        if self.db is not None:
            self.db.close()
            return

        self.job_store.close()
        self.schedule_store.close()
