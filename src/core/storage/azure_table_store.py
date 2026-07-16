# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure Table Storage-backed stores for jobs and schedules.
"""

from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from azure.core import MatchConditions
from azure.core.credentials import TokenCredential
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient, TableServiceClient, UpdateMode
from src.core.exceptions import ConcurrencyConflictError, EntityTooLargeError
from src.core.models.job import Job, JobStatus
from src.core.models.schedule import Schedule
from src.core.observability import get_logger

logger = get_logger(__name__)

_PARTITION_KEY = "staf"
_WORKSPACE_LOCK_PARTITION_KEY = "workspace-lock"
_JOB_TERMINAL_STATUSES = (
    JobStatus.COMPLETED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
)


_MAX_STRING_PROPERTY_BYTES = 64 * 1024
_MAX_ENTITY_BYTES = 1024 * 1024


def _validate_entity_size(entity: Dict[str, Any], entity_kind: str) -> None:
    """Reject a table entity that violates Azure Table Storage size limits.

    This is a client-side safety net, not a byte-exact reimplementation of
    the service's internal accounting. Azure Table string properties are
    UTF-16, so string limits and the approximate entity total use UTF-16 bytes.

    :param entity: Entity that would be written.
    :param entity_kind: Human-readable entity kind, used in error messages.
    :raises EntityTooLargeError: If any string property exceeds 64 KiB, or
        the entity's total approximate size exceeds 1 MiB.
    """
    row_key = entity.get("RowKey", "<unknown>")
    total = 0
    for key, value in entity.items():
        total += len(key.encode("utf-16-le"))
        if isinstance(value, str):
            size = len(value.encode("utf-16-le"))
            if size > _MAX_STRING_PROPERTY_BYTES:
                raise EntityTooLargeError(
                    f"{entity_kind} {row_key}: property '{key}' is {size} bytes, "
                    f"exceeding the Azure Table Storage 64 KiB string property limit"
                )
            total += size
        elif value is not None:
            total += len(str(value).encode("utf-16-le"))
    if total > _MAX_ENTITY_BYTES:
        raise EntityTooLargeError(
            f"{entity_kind} {row_key}: entity is approximately {total} bytes, "
            f"exceeding the Azure Table Storage 1 MiB entity size limit"
        )


def _dt_to_str(dt: Optional[datetime]) -> str:
    """Convert a datetime to an ISO-8601 string for table storage.

    :param dt: Datetime to convert.
    :returns: ISO string, or ``""`` when ``dt`` is None.
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _str_to_dt(value: Optional[str]) -> Optional[datetime]:
    """Convert an ISO-8601 string back to a datetime.

    :param value: ISO string, possibly empty or None.
    :returns: Parsed datetime, or None when ``value`` is empty/None.
    """
    return datetime.fromisoformat(value) if value else None


def _require(entity: Dict[str, Any], field: str, entity_kind: str) -> Any:
    """Fetch a required field from a table entity, rejecting malformed entities.

    :param entity: Raw table entity.
    :param field: Required field name.
    :param entity_kind: Human-readable entity kind, used in the error message.
    :returns: The field's value.
    :raises ValueError: If the field is missing, rather than silently
        defaulting to success-shaped data.
    """
    if field not in entity:
        row_key = entity.get("RowKey", "<unknown>")
        raise ValueError(
            f"Malformed {entity_kind} entity {row_key}: missing required field '{field}'"
        )
    return entity[field]


def _close_quietly(obj: Any) -> None:
    """Call ``close()`` on ``obj`` if it exists and is callable.

    :param obj: Object to close, or None.
    """
    if obj is None:
        return
    close = getattr(obj, "close", None)
    if callable(close):
        close()


def _extract_etag(value: Any) -> Optional[str]:
    """Extract a concrete ETag from an Azure response or table entity."""
    metadata = getattr(value, "metadata", None)
    etag = metadata.get("etag") if metadata is not None else None
    if not isinstance(etag, str) and hasattr(value, "get"):
        candidate = value.get("etag")
        etag = candidate if isinstance(candidate, str) else None
    return etag


def _new_table_resources(
    endpoint: str, table_name: str, credential: TokenCredential
) -> tuple[TableServiceClient, TableClient]:
    """
    Build owning service resources and a table client.

    :param endpoint: Azure Table Storage endpoint URL.
    :param table_name: Table to create (if missing) and connect to.
    :param credential: Azure ``TokenCredential`` provided by the identity
        provider. The caller retains ownership.
    :returns: The owning ``TableServiceClient`` and a ``TableClient`` for
        ``table_name``.
    """
    service = TableServiceClient(endpoint=endpoint, credential=credential)
    try:
        service.create_table_if_not_exists(table_name)
        client = service.get_table_client(table_name)
    except Exception:
        _close_quietly(service)
        raise
    return service, client


class AzureTableJobStore:
    """Job storage backed by Azure Table Storage.

    Uses ``PartitionKey="staf"``/``RowKey=<job id>``.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        table_name: str = "Jobs",
        *,
        table_client: Optional[TableClient] = None,
        credential: Optional[TokenCredential] = None,
    ) -> None:
        """Initialize the job store.

        :param endpoint: Azure Table Storage endpoint URL. Required unless
            ``table_client`` is supplied.
        :param table_name: Table name for jobs.
        :param table_client: Pre-built client (e.g. a mock) for dependency
            injection. The client is treated as non-owning shared infrastructure.
            ``close()`` will not close it. No credential or service is created
            when this is given.
        :param credential: Azure ``TokenCredential`` to use for authentication.
            Required when ``endpoint`` is given and ``table_client`` is not.
            The credential is caller-owned and NOT closed by this store.
        :raises ValueError: If neither ``endpoint`` nor ``table_client`` is given,
            or if ``endpoint`` is given without ``credential``.
        """
        if table_client is not None:
            self._client = table_client
            self._service = None
            self._owns_client = False
        else:
            if not endpoint:
                raise ValueError("endpoint is required when table_client is not provided")
            if credential is None:
                raise ValueError("credential is required when table_client is not provided")
            self._service, self._client = _new_table_resources(endpoint, table_name, credential)
            self._owns_client = True
        self.table_name = table_name
        self._closed = False
        logger.info(f"Initialized Azure Table job storage: table={table_name}")

    def close(self) -> None:
        """
        Close owned resources.
        """
        if self._closed:
            return
        if self._owns_client:
            _close_quietly(self._client)
        _close_quietly(self._service)
        self._closed = True

    @staticmethod
    def _to_entity(job: Job) -> Dict[str, Any]:
        """Serialize a Job to a table entity.

        :raises EntityTooLargeError: If the resulting entity violates Azure
            Table Storage's 64 KiB string-property or 1 MiB entity size
            limits (see :func:`_validate_entity_size`).
        """
        entity = {
            "PartitionKey": _PARTITION_KEY,
            "RowKey": str(job.id),
            "workspace_id": job.workspace_id,
            "schedule_id": job.schedule_id or "",
            "test_group": job.test_group or "",
            "test_ids": json.dumps(job.test_ids),
            "status": job.status if isinstance(job.status, str) else job.status.value,
            "created_at": _dt_to_str(job.created_at),
            "started_at": _dt_to_str(job.started_at),
            "completed_at": _dt_to_str(job.completed_at),
            "error_present": job.error is not None,
            "error": job.error if job.error is not None else "",
            "result_present": job.result is not None,
            "result": json.dumps(job.result, default=str) if job.result is not None else "",
            "log_file": job.log_file or "",
            "events": json.dumps(
                [e.model_dump(mode="json") for e in job.events],
                default=str,
            ),
            "metadata": json.dumps(job.metadata, default=str),
            "actor": job.actor or "",
            "approval_ref": job.approval_ref or "",
            "incident_ticket": job.incident_ticket or "",
            "offline": job.offline,
        }
        _validate_entity_size(entity, "job")
        return entity

    @staticmethod
    def _to_job(entity: Dict[str, Any]) -> Job:
        """Deserialize a table entity to a Job.

        :raises ValueError: If the entity is missing a required field or
            contains unparsable JSON (malformed entity).
        """
        try:
            data: Dict[str, Any] = {
                "id": _require(entity, "RowKey", "job"),
                "workspace_id": _require(entity, "workspace_id", "job"),
                "schedule_id": entity.get("schedule_id") or None,
                "test_group": entity.get("test_group") or None,
                "test_ids": json.loads(entity.get("test_ids") or "[]"),
                "status": _require(entity, "status", "job"),
                "started_at": _str_to_dt(entity.get("started_at")),
                "completed_at": _str_to_dt(entity.get("completed_at")),
                "error": (
                    entity.get("error", "")
                    if entity.get("error_present", bool(entity.get("error")))
                    else None
                ),
                "result": (
                    json.loads(entity.get("result", ""))
                    if entity.get("result_present", bool(entity.get("result")))
                    else None
                ),
                "log_file": entity.get("log_file") or None,
                "events": json.loads(entity.get("events") or "[]"),
                "metadata": json.loads(entity.get("metadata") or "{}"),
                "actor": entity.get("actor") or None,
                "approval_ref": entity.get("approval_ref") or None,
                "incident_ticket": entity.get("incident_ticket") or None,
                "offline": bool(entity.get("offline", False)),
            }
        except (json.JSONDecodeError, TypeError) as exc:
            row_key = entity.get("RowKey", "<unknown>")
            raise ValueError(f"Malformed job entity {row_key}: {exc}") from exc
        created_at = _str_to_dt(entity.get("created_at"))
        if created_at is not None:
            data["created_at"] = created_at
        job = Job.model_validate(data)
        job._storage_etag = _extract_etag(entity)
        return job

    def create(self, job: Job) -> Job:
        """Create a new job.

        :param job: Job to create.
        :returns: Created job.
        :raises azure.core.exceptions.ResourceExistsError: If a job with the
            same ID already exists. Left unwrapped, mirroring the local
            store's unwrapped ``sqlite3.IntegrityError`` on duplicate insert.
        """
        entity = self._to_entity(job)
        lock_acquired = not job.is_terminal
        if lock_acquired:
            lock_entity = {
                "PartitionKey": _WORKSPACE_LOCK_PARTITION_KEY,
                "RowKey": job.workspace_id,
                "job_id": str(job.id),
                "created_at": _dt_to_str(job.created_at),
            }
            self._client.create_entity(lock_entity)
        try:
            response = self._client.create_entity(entity)
        except Exception:
            if lock_acquired:
                self._release_workspace_lock(job)
            raise
        job._storage_etag = _extract_etag(response)
        logger.info(f"Created job {job.id} for workspace {job.workspace_id}")
        return job

    def _release_workspace_lock(self, job: Job) -> None:
        """Release the lock owned by a job after rollback or terminal update."""
        try:
            lock = self._client.get_entity(_WORKSPACE_LOCK_PARTITION_KEY, job.workspace_id)
        except ResourceNotFoundError:
            return
        if lock.get("job_id") != str(job.id):
            return
        self._client.delete_entity(_WORKSPACE_LOCK_PARTITION_KEY, job.workspace_id)

    def get(self, job_id: UUID | str) -> Optional[Job]:
        """Get a job by ID.

        :param job_id: Job ID.
        :returns: Job if found, None otherwise.
        """
        try:
            entity = self._client.get_entity(_PARTITION_KEY, str(job_id))
        except ResourceNotFoundError:
            return None
        return self._to_job(entity)

    def update(self, job: Job) -> None:
        """
        Update an existing job using ETag optimistic concurrency.

        :param job: Job with updated fields.
        :raises ConcurrencyConflictError: If the job was modified by another
            writer between the existence check and this update.
        """
        entity = self._to_entity(job)
        etag = job._storage_etag
        if etag is None:
            try:
                self._client.get_entity(_PARTITION_KEY, str(job.id))
            except ResourceNotFoundError:
                return
            raise ConcurrencyConflictError(f"Job {job.id} has no expected storage version")
        try:
            response = self._client.update_entity(
                entity,
                mode=UpdateMode.REPLACE,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
        except HttpResponseError as exc:
            if exc.status_code == 412:
                raise ConcurrencyConflictError(f"Job {job.id} was modified concurrently") from exc
            raise
        updated_etag = _extract_etag(response)
        job._storage_etag = updated_etag
        if job.is_terminal:
            self._release_workspace_lock(job)
        logger.debug(f"Updated job {job.id} (status={job.status})")

    def get_active(self, workspace_id: Optional[str] = None) -> List[Job]:
        """Get active (non-terminal) jobs.

        :param workspace_id: Optional filter by workspace.
        :returns: List of active jobs.
        """
        query_filter = "PartitionKey eq @pk"
        parameters: Dict[str, Any] = {"pk": _PARTITION_KEY}
        for index, terminal_status in enumerate(_JOB_TERMINAL_STATUSES):
            parameter = f"terminal{index}"
            query_filter += f" and status ne @{parameter}"
            parameters[parameter] = terminal_status
        if workspace_id:
            query_filter += " and workspace_id eq @ws"
            parameters["ws"] = workspace_id
        jobs = [
            self._to_job(e)
            for e in self._client.query_entities(query_filter, parameters=parameters)
        ]
        return [j for j in jobs if j.status not in _JOB_TERMINAL_STATUSES]

    def get_active_for_workspace(self, workspace_id: str) -> Optional[Job]:
        """Get the active job for a workspace.

        :param workspace_id: Workspace ID.
        :returns: Active job if one exists.
        """
        active = self.get_active(workspace_id)
        return active[0] if active else None

    def has_active_job(self, workspace_id: str) -> bool:
        """Check if workspace has an active job.

        :param workspace_id: Workspace ID.
        :returns: True if active job exists.
        """
        return self.get_active_for_workspace(workspace_id) is not None

    def get_history(
        self,
        workspace_id: Optional[str] = None,
        schedule_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        days: int = 7,
        limit: int = 100,
    ) -> List[Job]:
        """Get job history.

        :param workspace_id: Optional filter by workspace.
        :param schedule_id: Optional filter by schedule.
        :param status: Optional filter by status.
        :param days: Number of days to look back.
        :param limit: Maximum number of jobs to return.
        :returns: List of historical jobs, most recent first.
        """
        cutoff = _dt_to_str(datetime.now(timezone.utc) - timedelta(days=days))
        terminal_clause = " or ".join(
            f"status eq @t{i}" for i in range(len(_JOB_TERMINAL_STATUSES))
        )
        parameters: Dict[str, Any] = {
            f"t{i}": value for i, value in enumerate(_JOB_TERMINAL_STATUSES)
        }
        parameters["pk"] = _PARTITION_KEY
        parameters["cutoff"] = cutoff
        query_filter = f"PartitionKey eq @pk and ({terminal_clause}) and created_at ge @cutoff"
        if workspace_id:
            query_filter += " and workspace_id eq @ws"
            parameters["ws"] = workspace_id
        if schedule_id:
            query_filter += " and schedule_id eq @sid"
            parameters["sid"] = schedule_id

        jobs = [
            self._to_job(e)
            for e in self._client.query_entities(query_filter, parameters=parameters)
        ]
        if status is not None:
            status_val = status.value if hasattr(status, "value") else status
            jobs = [j for j in jobs if j.status == status_val]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def get_jobs_for_schedule(
        self,
        schedule_id: str,
        limit: int = 50,
    ) -> List[Job]:
        """Get jobs triggered by a specific schedule.

        Delegates to :meth:`get_history`, matching the local store's
        behavior of returning only terminal jobs within its default
        lookback window.

        :param schedule_id: Schedule ID.
        :param limit: Maximum number of jobs.
        :returns: List of jobs.
        """
        return self.get_history(schedule_id=schedule_id, limit=limit)


class AzureTableScheduleStore:
    """Schedule storage backed by Azure Table Storage.

    Uses ``PartitionKey="staf"``/``RowKey=<schedule id>``.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        table_name: str = "Schedules",
        *,
        table_client: Optional[TableClient] = None,
        credential: Optional[TokenCredential] = None,
    ) -> None:
        """Initialize the schedule store.

        :param endpoint: Azure Table Storage endpoint URL. Required unless
            ``table_client`` is supplied.
        :param table_name: Table name for schedules.
        :param table_client: Pre-built client (e.g. a mock) for dependency
            injection. The client is treated as non-owning shared infrastructure.
            ``close()`` will not close it. No credential or service is created
            when this is given.
        :param credential: Azure ``TokenCredential`` to use for authentication.
            Required when ``endpoint`` is given and ``table_client`` is not.
            The credential is caller-owned and NOT closed by this store.
        :raises ValueError: If neither ``endpoint`` nor ``table_client`` is given,
            or if ``endpoint`` is given without ``credential``.
        """
        if table_client is not None:
            self._client = table_client
            self._service = None
            self._owns_client = False
        else:
            if not endpoint:
                raise ValueError("endpoint is required when table_client is not provided")
            if credential is None:
                raise ValueError("credential is required when table_client is not provided")
            self._service, self._client = _new_table_resources(endpoint, table_name, credential)
            self._owns_client = True
        self.table_name = table_name
        self._closed = False
        logger.info(f"Initialized Azure Table schedule storage: table={table_name}")

    def close(self) -> None:
        """Close owned resources.

        Idempotent: safe to call multiple times. When constructed from an
        ``endpoint``, closes the owning service transport and derived table
        client. When constructed via injected ``table_client``, the client is
        treated as non-owning shared infrastructure and is not closed here.
        The credential is always caller-owned and never closed here.
        """
        if self._closed:
            return
        if self._owns_client:
            _close_quietly(self._client)
        _close_quietly(self._service)
        self._closed = True

    @staticmethod
    def _to_entity(schedule: Schedule) -> Dict[str, Any]:
        """Serialize a Schedule to a table entity.

        :raises EntityTooLargeError: If the resulting entity violates Azure
            Table Storage's 64 KiB string-property or 1 MiB entity size
            limits (see :func:`_validate_entity_size`).
        """
        entity = {
            "PartitionKey": _PARTITION_KEY,
            "RowKey": schedule.id,
            "name": schedule.name,
            "description": schedule.description,
            "cron_expression": schedule.cron_expression,
            "timezone": schedule.timezone,
            "workspace_ids": json.dumps(schedule.workspace_ids),
            "test_group": schedule.test_group or "",
            "test_ids": json.dumps(schedule.test_ids),
            "enabled": bool(schedule.enabled),
            "next_run_time": _dt_to_str(schedule.next_run_time),
            "last_run_time": _dt_to_str(schedule.last_run_time),
            "last_run_job_ids": json.dumps(schedule.last_run_job_ids),
            "total_runs": schedule.total_runs,
            "created_at": _dt_to_str(schedule.created_at),
            "updated_at": _dt_to_str(schedule.updated_at),
        }
        _validate_entity_size(entity, "schedule")
        return entity

    @staticmethod
    def _to_schedule(entity: Dict[str, Any]) -> Schedule:
        """Deserialize a table entity to a Schedule.

        :raises ValueError: If the entity is missing a required field or
            contains unparsable JSON (malformed entity).
        """
        try:
            data: Dict[str, Any] = {
                "id": _require(entity, "RowKey", "schedule"),
                "name": _require(entity, "name", "schedule"),
                "description": entity.get("description", ""),
                "cron_expression": _require(entity, "cron_expression", "schedule"),
                "timezone": entity.get("timezone", "UTC"),
                "workspace_ids": json.loads(entity.get("workspace_ids") or "[]"),
                "test_group": entity.get("test_group") or None,
                "test_ids": json.loads(entity.get("test_ids") or "[]"),
                "enabled": bool(entity.get("enabled", True)),
                "last_run_job_ids": json.loads(entity.get("last_run_job_ids") or "[]"),
                "total_runs": entity.get("total_runs", 0),
            }
        except (json.JSONDecodeError, TypeError) as exc:
            row_key = entity.get("RowKey", "<unknown>")
            raise ValueError(f"Malformed schedule entity {row_key}: {exc}") from exc
        for dt_field in ("next_run_time", "last_run_time", "created_at", "updated_at"):
            value = _str_to_dt(entity.get(dt_field))
            if value is not None:
                data[dt_field] = value
        schedule = Schedule.model_validate(data)
        schedule._storage_etag = _extract_etag(entity)
        return schedule

    def create(self, schedule: Schedule) -> Schedule:
        """Create a new schedule.

        :param schedule: Schedule to create.
        :returns: Created schedule.
        :raises ValueError: If a schedule with the same ID already exists.
        """
        try:
            response = self._client.create_entity(self._to_entity(schedule))
        except ResourceExistsError as exc:
            raise ValueError(f"Schedule with ID {schedule.id} already exists") from exc
        schedule._storage_etag = _extract_etag(response)
        logger.info(f"Created schedule '{schedule.name}' (ID: {schedule.id})")
        return schedule

    def get(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID.

        :param schedule_id: Schedule ID.
        :returns: Schedule if found.
        """
        try:
            entity = self._client.get_entity(_PARTITION_KEY, schedule_id)
        except ResourceNotFoundError:
            return None
        return self._to_schedule(entity)

    def list(self, enabled_only: bool = False) -> List[Schedule]:
        """List all schedules.

        :param enabled_only: If True, only return enabled schedules.
        :returns: List of schedules.
        """
        query_filter = "PartitionKey eq @pk"
        parameters: Dict[str, Any] = {"pk": _PARTITION_KEY}
        if enabled_only:
            query_filter += " and enabled eq true"
        return [
            self._to_schedule(e)
            for e in self._client.query_entities(query_filter, parameters=parameters)
        ]

    def update(self, schedule: Schedule) -> Schedule:
        """Update an existing schedule using ETag optimistic concurrency.

        :param schedule: Schedule to update.
        :returns: Updated schedule.
        :raises ValueError: If schedule not found.
        :raises ConcurrencyConflictError: If the schedule was modified by
            another writer between the existence check and this update.
        """
        entity = self._to_entity(schedule)
        etag = schedule._storage_etag
        if etag is None:
            try:
                self._client.get_entity(_PARTITION_KEY, schedule.id)
            except ResourceNotFoundError as exc:
                raise ValueError(f"Schedule {schedule.id} not found") from exc
            raise ConcurrencyConflictError(
                f"Schedule {schedule.id} has no expected storage version"
            )
        schedule.updated_at = datetime.now(timezone.utc)
        try:
            response = self._client.update_entity(
                entity,
                mode=UpdateMode.REPLACE,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
        except HttpResponseError as exc:
            if exc.status_code == 412:
                raise ConcurrencyConflictError(
                    f"Schedule {schedule.id} was modified concurrently"
                ) from exc
            raise
        updated_etag = _extract_etag(response)
        schedule._storage_etag = updated_etag
        logger.info(f"Updated schedule '{schedule.name}' (ID: {schedule.id})")
        return schedule

    def delete(self, schedule_id: str) -> bool:
        """Delete a schedule.

        :param schedule_id: Schedule ID.
        :returns: True if deleted.
        """
        try:
            self._client.delete_entity(_PARTITION_KEY, schedule_id)
        except ResourceNotFoundError:
            return False
        logger.info(f"Deleted schedule {schedule_id}")
        return True

    def get_enabled(self) -> List[Schedule]:
        """Get all enabled schedules.

        :returns: List of enabled schedules.
        """
        return self.list(enabled_only=True)
