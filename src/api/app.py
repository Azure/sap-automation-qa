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
import uvicorn

from src.core.observability import initialize_logging, get_logger, ObservabilityMiddleware
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


log_format = os.environ.get("LOG_FORMAT", "console")
initialize_logging(level=logging.INFO, log_format=log_format)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown."""
    logger.info("Initializing SAP QA Scheduler...")

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    job_store = JobStore(data_dir=data_dir / "jobs")
    schedule_store = ScheduleStore(storage_path=data_dir / "schedules.json")

    executor = AnsibleExecutor(playbook_dir=Path("src"))

    workspace_loader = default_workspace_loader
    set_workspace_loader(workspace_loader)

    job_worker = JobWorker(
        job_store=job_store,
        executor=executor,
        workspace_config_loader=workspace_loader,
    )

    scheduler_service = SchedulerService(
        schedule_store=schedule_store,
        job_worker=job_worker,
        check_interval_seconds=int(os.environ.get("SCHEDULER_CHECK_INTERVAL", "60")),
    )

    set_job_store(job_store)
    set_job_worker(job_worker)
    set_schedule_store(schedule_store)
    set_scheduler_service(scheduler_service)

    await scheduler_service.start()
    set_service_status("scheduler", True)

    logger.info("SAP QA Scheduler initialized successfully")

    yield

    logger.info("Shutting down SAP QA Scheduler...")

    set_service_status("scheduler", False)
    await scheduler_service.stop()

    logger.info("SAP QA Scheduler shutdown complete")


app = FastAPI(
    title="SAP QA Scheduler API",
    description="REST API for SAP Testing Automation Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ObservabilityMiddleware)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(schedules_router)
app.include_router(workspaces_router)


if __name__ == "__main__":
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
