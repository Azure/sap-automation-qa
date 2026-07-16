# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Storage factory: local SQLite by default, Azure Table Storage opt-in."""

import os
from pathlib import Path
from typing import Mapping
from src.core.models.storage import StorageContext
from src.core.storage.azure_context import AzureStorageContext
from src.core.storage.azure_table_store import AzureTableJobStore, AzureTableScheduleStore
from src.core.storage.job_store import JobStore
from src.core.storage.schedule_store import ScheduleStore
from src.core.storage.staf_store import StafStore

DEFAULT_AZURE_JOBS_TABLE = "Jobs"
DEFAULT_AZURE_SCHEDULES_TABLE = "Schedules"


def _get_env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    """Resolve the environment mapping to read configuration from."""
    return env if env is not None else os.environ


def create_storage_context(
    db_path: Path | str = "data/scheduler.db",
    *,
    env: Mapping[str, str] | None = None,
    azure_context: AzureStorageContext | None = None,
) -> StorageContext:
    """Create the storage context for the configured backend."""
    resolved_env = _get_env(env)
    endpoint = (resolved_env.get("AZURE_TABLE_ENDPOINT") or "").strip()

    if not endpoint:
        db = StafStore(db_path)
        return StorageContext(
            backend="sqlite",
            db=db,
            job_store=JobStore(db=db),
            schedule_store=ScheduleStore(db=db),
            owned_resources=(db,),
        )

    if azure_context is None or not azure_context.has_table:
        raise RuntimeError(
            "AZURE_TABLE_ENDPOINT is set but no AzureStorageContext with Table Storage is available"
        )

    jobs_table = (resolved_env.get("AZURE_TABLE_JOBS") or "").strip() or DEFAULT_AZURE_JOBS_TABLE
    schedules_table = (
        resolved_env.get("AZURE_TABLE_SCHEDULES") or ""
    ).strip() or DEFAULT_AZURE_SCHEDULES_TABLE

    job_store = AzureTableJobStore(table_client=azure_context.get_table_client(jobs_table))
    schedule_store = AzureTableScheduleStore(
        table_client=azure_context.get_table_client(schedules_table)
    )
    return StorageContext(
        backend="azure_table",
        db=None,
        job_store=job_store,
        schedule_store=schedule_store,
        owned_resources=(job_store, schedule_store),
    )
