# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
FastAPI application for SAP QA Scheduler.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.observability import (
    initialize_logging,
    get_logger,
    ObservabilityMiddleware,
)
from src.core.storage.job_store import JobStore
from src.core.storage.schedule_store import ScheduleStore
from src.core.execution.executor import AnsibleExecutor
from src.core.execution.worker import JobWorker
from src.core.services.scheduler import SchedulerService
from src.api.routes import (
    health_router,
    jobs_router,
    schedules_router,
    workspaces_router,
    set_job_store,
    set_job_worker,
    set_schedule_store,
    set_scheduler_service,
    set_workspace_loader,
)
from src.api.routes.health import set_service_status
from src.api.routes.workspaces import default_workspace_loader

API_V1_PREFIX = "/api/v1"
LOG_FORMAT = os.environ.get("LOG_FORMAT", "console")
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
WORKSPACES_BASE = Path(os.environ.get("WORKSPACES_BASE", "WORKSPACES/SYSTEM"))
PLAYBOOK_DIR = Path(os.environ.get("PLAYBOOK_DIR", "src"))
SCHEDULER_CHECK_INTERVAL = int(os.environ.get("SCHEDULER_CHECK_INTERVAL", "60"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(
    ","
)

initialize_logging(level=logging.INFO, log_format=LOG_FORMAT)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown.

    Initializes all services on startup and ensures graceful shutdown.
    Services are stored in app.state for dependency injection.

    :param app: FastAPI application instance.
    :type app: FastAPI
    :yields: None
    """
    scheduler_service = None
    job_worker = None
    job_store = None
    schedule_store = None

    try:
        logger.info("Initializing SAP QA Scheduler...")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        db_path = DATA_DIR / "scheduler.db"
        job_store = JobStore(db_path=db_path)
        schedule_store = ScheduleStore(db_path=db_path)
        workspace_loader = default_workspace_loader
        set_workspace_loader(workspace_loader)
        job_worker = JobWorker(
            job_store=job_store,
            executor=AnsibleExecutor(playbook_dir=PLAYBOOK_DIR),
            workspace_config_loader=workspace_loader,
            workspaces_base=WORKSPACES_BASE,
        )
        job_worker.recover_crashed_jobs()
        scheduler_service = SchedulerService(
            schedule_store=schedule_store,
            job_worker=job_worker,
            check_interval_seconds=SCHEDULER_CHECK_INTERVAL,
        )
        app.state.job_store = job_store
        app.state.schedule_store = schedule_store
        app.state.job_worker = job_worker
        app.state.scheduler_service = scheduler_service
        set_job_store(job_store)
        set_job_worker(job_worker)
        set_schedule_store(schedule_store)
        set_scheduler_service(scheduler_service)
        await scheduler_service.start()
        set_service_status("scheduler", True)
        logger.info("SAP QA Scheduler initialized successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to initialize SAP QA Scheduler: {e}", exc_info=True)
        raise

    finally:
        logger.info("Shutting down SAP QA Scheduler...")
        set_service_status("scheduler", False)
        if scheduler_service:
            await scheduler_service.stop()
        if job_worker:
            await job_worker.shutdown()
        if job_store:
            job_store.close()
        if schedule_store:
            schedule_store.close()
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
