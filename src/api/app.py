# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""FastAPI application for SAP QA Scheduler."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.health import (
    router as health_router,
    set_service_status,
    set_storage_backend,
    set_workspace_backend,
)
from src.api.routes.jobs import (
    router as jobs_router,
    set_job_store,
    set_job_worker,
    set_workspace_reader as set_job_workspace_reader,
)
from src.api.routes.schedules import (
    router as schedules_router,
    set_schedule_store,
    set_scheduler_service,
)
from src.api.routes.workspaces import (
    router as workspaces_router,
    set_workspace_backend as set_workspace_reader,
)
from src.core.execution.executor import AnsibleExecutor
from src.core.execution.worker import JobWorker
from src.core.models.storage import StorageContext
from src.core.observability import (
    ObservabilityMiddleware,
    get_logger,
    initialize_logging,
    load_telemetry_config,
)
from src.core.services.scheduler import SchedulerService
from src.core.storage.azure_context import AzureStorageContext, create_azure_storage_context
from src.core.storage.factory import create_storage_context
from src.core.storage.workspace import create_workspace_backend

API_V1_PREFIX = "/api/v1"
LOG_FORMAT = os.environ.get("LOG_FORMAT", "console")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
WORKSPACES_BASE = Path(os.environ.get("WORKSPACES_BASE", "WORKSPACES/SYSTEM"))
PLAYBOOK_DIR = Path(os.environ.get("PLAYBOOK_DIR", "src"))
SCHEDULER_CHECK_INTERVAL = int(os.environ.get("SCHEDULER_CHECK_INTERVAL", "60"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(
    ","
)

telemetry_config = load_telemetry_config()
initialize_logging(level=logging.INFO, log_format=LOG_FORMAT, telemetry_config=telemetry_config)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown."""
    scheduler_service = None
    job_worker = None
    storage_ctx: StorageContext | None = None
    azure_ctx: AzureStorageContext | None = None
    workspace_backend = None

    try:
        logger.info("Initializing SAP QA Scheduler...")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        db_path = DATA_DIR / "scheduler.db"

        azure_ctx = create_azure_storage_context()
        storage_ctx = create_storage_context(db_path=db_path, azure_context=azure_ctx)
        set_storage_backend(storage_ctx.backend)

        job_store = storage_ctx.job_store
        schedule_store = storage_ctx.schedule_store
        workspace_backend = create_workspace_backend(
            azure_context=azure_ctx,
            workspaces_base=WORKSPACES_BASE,
            data_dir=DATA_DIR,
        )
        set_workspace_reader(workspace_backend)
        set_job_workspace_reader(workspace_backend)
        set_workspace_backend(workspace_backend.backend_name)

        job_worker = JobWorker(
            job_store=job_store,
            executor=AnsibleExecutor(playbook_dir=PLAYBOOK_DIR, telemetry_config=telemetry_config),
            workspace_backend=workspace_backend,
            log_dir=DATA_DIR / "job-logs",
        )
        job_worker.recover_crashed_jobs()
        scheduler_service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=job_worker,
            check_interval_seconds=SCHEDULER_CHECK_INTERVAL,
        )

        application.state.job_store = job_store
        application.state.schedule_store = schedule_store
        application.state.job_worker = job_worker
        application.state.scheduler_service = scheduler_service
        set_job_store(job_store)
        set_job_worker(job_worker)
        set_schedule_store(schedule_store)
        set_scheduler_service(scheduler_service)

        await scheduler_service.start()
        set_service_status("scheduler", True)
        logger.info("SAP QA Scheduler initialized successfully")
        yield
    except Exception as exc:
        logger.error("Failed to initialize SAP QA Scheduler: %s", exc, exc_info=True)
        raise
    finally:
        logger.info("Shutting down SAP QA Scheduler...")
        set_service_status("scheduler", False)
        try:
            if scheduler_service is not None:
                await scheduler_service.stop()
        except Exception as exc:
            logger.warning("Error stopping scheduler: %s", exc, exc_info=True)
        try:
            if job_worker is not None:
                await job_worker.shutdown()
        except Exception as exc:
            logger.warning("Error shutting down worker: %s", exc, exc_info=True)
        try:
            if workspace_backend is not None:
                workspace_backend.close()
        except Exception as exc:
            logger.warning("Error closing workspace backend: %s", exc, exc_info=True)
        try:
            if storage_ctx is not None:
                storage_ctx.close()
        except Exception as exc:
            logger.warning("Error closing storage context: %s", exc, exc_info=True)
        try:
            if azure_ctx is not None:
                azure_ctx.close()
        except Exception as exc:
            logger.warning("Error closing Azure context: %s", exc, exc_info=True)

        logger.info("SAP QA Scheduler shutdown complete")


app = FastAPI(
    title="SAP QA Scheduler API",
    description="REST API for SAP Testing Automation Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(jobs_router, prefix=API_V1_PREFIX)
app.include_router(schedules_router, prefix=API_V1_PREFIX)
app.include_router(workspaces_router, prefix=API_V1_PREFIX)
