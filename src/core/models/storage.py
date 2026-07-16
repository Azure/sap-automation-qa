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

        if self.db is not None:
            self.db.close()
            self._closed = True
            return

        job_error: Exception | None = None
        try:
            self.job_store.close()
        except Exception as exc:
            job_error = exc

        try:
            self.schedule_store.close()
        except Exception as schedule_error:
            if job_error is not None:
                raise RuntimeError("Both job and schedule stores failed to close") from job_error
            raise schedule_error

        if job_error is not None:
            raise job_error
        self._closed = True
