# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for AzureTableJobStore and AzureTableScheduleStore."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import inspect

import pytest
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError

from src.core.models.job import Job, JobEvent, JobEventType, JobStatus
from src.core.models.schedule import Schedule
from src.core.exceptions import ConcurrencyConflictError, EntityTooLargeError
from src.core.storage.azure_table_store import (
    AzureTableJobStore,
    AzureTableScheduleStore,
    _validate_entity_size,
)


def _entity_with_etag(entity: dict, etag: str = 'W/"etag-1"') -> MagicMock:
    """Wrap a plain dict entity with a ``.metadata`` attribute like the SDK."""
    wrapped = MagicMock()
    wrapped.__getitem__.side_effect = entity.__getitem__
    wrapped.get.side_effect = entity.get
    wrapped.metadata = {"etag": etag}
    return wrapped


class TestValidateEntitySize:
    """Direct unit tests for the ``_validate_entity_size`` helper."""

    def test_string_property_over_64kib_is_rejected(self) -> None:
        """A single string property over 64 KiB is rejected, naming the field."""
        entity = {"PartitionKey": "staf", "RowKey": "id-1", "big": "x" * (64 * 1024 + 1)}

        with pytest.raises(EntityTooLargeError, match="big"):
            _validate_entity_size(entity, "job")

    def test_ascii_property_over_utf16_limit_is_rejected(self) -> None:
        """ASCII values are two bytes per character in Azure Table strings."""
        entity = {"PartitionKey": "staf", "RowKey": "id-1", "big": "x" * 40_000}

        with pytest.raises(EntityTooLargeError, match="big"):
            _validate_entity_size(entity, "job")

    def test_total_entity_over_1mib_is_rejected_without_any_single_field_over_64kib(
        self,
    ) -> None:
        """Many fields individually under 64 KiB can still sum past the 1 MiB entity limit."""
        entity = {"PartitionKey": "staf", "RowKey": "id-1"}
        # 40 fields of ~30 KiB each sum to ~1.2 MiB in UTF-16, comfortably over the 1 MiB
        # entity limit, while each individual field stays under 64 KiB.
        for i in range(40):
            entity[f"field_{i}"] = "y" * (30 * 1024)

        with pytest.raises(EntityTooLargeError, match="1 MiB"):
            _validate_entity_size(entity, "job")

    def test_boundary_safe_entity_passes(self) -> None:
        """A modestly-sized entity under both limits does not raise."""
        entity = {
            "PartitionKey": "staf",
            "RowKey": "id-1",
            "workspace_id": "WS-A",
            "notes": "n" * 1024,
        }

        _validate_entity_size(entity, "job")  # should not raise


class TestAzureTableJobStoreConstruction:
    """Constructor behavior: DI vs. endpoint-based production construction."""

    def test_requires_endpoint_or_table_client(self) -> None:
        """Requires endpoint or table client."""
        with pytest.raises(ValueError, match="endpoint is required"):
            AzureTableJobStore()

    def test_constructs_from_endpoint_with_default_credential(self) -> None:
        """Constructs from endpoint with injected credential."""
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_client = MagicMock()
            mock_svc.get_table_client.return_value = mock_client
            mock_svc_cls.return_value = mock_svc
            mock_cred = MagicMock()

            store = AzureTableJobStore(
                endpoint="https://acct.table.core.windows.net",
                table_name="CustomJobs",
                credential=mock_cred,
            )

            mock_svc_cls.assert_called_once_with(
                endpoint="https://acct.table.core.windows.net",
                credential=mock_cred,
            )
            mock_svc.create_table_if_not_exists.assert_called_once_with("CustomJobs")
            mock_svc.get_table_client.assert_called_once_with("CustomJobs")
            assert store.table_name == "CustomJobs"

    def test_no_connection_string_or_account_key_used(self) -> None:
        """Only endpoint + DefaultAzureCredential is accepted; no key-based auth path exists."""
        sig = inspect.signature(AzureTableJobStore.__init__)
        assert "account_key" not in sig.parameters
        assert "connection_string" not in sig.parameters

    def test_close_closes_owned_service_and_credential_exactly_once(self) -> None:
        """Production construction owns the service; close() releases it once.

        The derived ``TableClient``'s own ``close()`` is a no-op transport
        wrapper in the real SDK, so releasing resources depends on closing
        the owning service client -- verified here directly since ``close()``
        is idempotent. The credential is caller-owned and NOT closed by the store.
        """
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_client = MagicMock()
            mock_svc.get_table_client.return_value = mock_client
            mock_svc_cls.return_value = mock_svc
            mock_cred = MagicMock()

            store = AzureTableJobStore(
                endpoint="https://acct.table.core.windows.net", credential=mock_cred
            )
            store.close()
            store.close()

            mock_svc.close.assert_called_once()
            # Credential is NOT owned by the store — not closed here
            mock_cred.close.assert_not_called()

    def test_injected_client_close_does_not_own_service_or_credential(self) -> None:
        """DI construction owns no service; injected client is non-owning."""
        mock_client = MagicMock()
        store = AzureTableJobStore(table_client=mock_client, table_name="Jobs")

        assert store._service is None

        store.close()
        # Non-owning: the store does NOT close the injected shared client
        mock_client.close.assert_not_called()

    def test_get_table_client_failure_closes_service(self) -> None:
        """A failure after table creation still closes the owning service."""
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_service = MagicMock()
            mock_service.get_table_client.side_effect = RuntimeError("client failure")
            mock_svc_cls.return_value = mock_service

            with pytest.raises(RuntimeError, match="client failure"):
                AzureTableJobStore(
                    endpoint="https://acct.table.core.windows.net",
                    credential=MagicMock(),
                )

            mock_service.close.assert_called_once()


class TestAzureTableJobStoreCrud:
    """CRUD and query round trips for AzureTableJobStore."""

    @pytest.fixture
    def mock_table_client(self) -> MagicMock:
        """Provide a mocked ``TableClient``.

        :returns: A mocked ``TableClient``.
        """
        return MagicMock()

    @pytest.fixture
    def job_store(self, mock_table_client: MagicMock) -> AzureTableJobStore:
        """Provide an ``AzureTableJobStore`` wired to the mocked client.

        :param mock_table_client: Mocked table client to inject.
        :returns: An ``AzureTableJobStore`` using the mocked client.
        """
        return AzureTableJobStore(table_client=mock_table_client, table_name="Jobs")

    def test_create_calls_create_entity_with_partition_and_row_key(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Create calls create entity with partition and row key."""
        job = Job(workspace_id="WS-A", test_group="DatabaseHighAvailability")
        result = job_store.create(job)
        assert mock_table_client.create_entity.call_count == 2
        entity = mock_table_client.create_entity.call_args_list[1].args[0]
        assert entity["PartitionKey"] == "staf"
        assert entity["RowKey"] == str(job.id)
        assert result is job

    def test_create_duplicate_propagates_unwrapped(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Parity with local JobStore: duplicate create is not wrapped into ValueError."""
        mock_table_client.create_entity.side_effect = ResourceExistsError("duplicate")
        with pytest.raises(ResourceExistsError):
            job_store.create(Job(workspace_id="WS-A"))

    def test_get_returns_none_when_missing(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get returns none when missing."""
        mock_table_client.get_entity.side_effect = ResourceNotFoundError("missing")
        assert job_store.get(uuid4()) is None

    def test_get_roundtrips_full_job(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get roundtrips full job."""
        job = Job(
            workspace_id="WS-A",
            test_group="DatabaseHighAvailability",
            test_ids=["ha-config", "azure-lb"],
            metadata={"foo": "bar", "n": 3},
            actor="mcp-agent",
            approval_ref="CHG-42",
            incident_ticket="INC-42",
            offline=True,
        )
        job.start()
        job.complete({"passed": 5, "failed": 0})
        entity = job_store._to_entity(job)
        mock_table_client.get_entity.return_value = entity

        restored = job_store.get(job.id)

        assert restored is not None
        assert str(restored.id) == str(job.id)
        assert restored.workspace_id == "WS-A"
        assert restored.test_group == "DatabaseHighAvailability"
        assert restored.test_ids == ["ha-config", "azure-lb"]
        assert restored.metadata == {"foo": "bar", "n": 3}
        assert restored.actor == "mcp-agent"
        assert restored.approval_ref == "CHG-42"
        assert restored.incident_ticket == "INC-42"
        assert restored.offline is True
        assert restored.status == JobStatus.COMPLETED.value
        assert restored.result == {"passed": 5, "failed": 0}
        assert restored.started_at is not None
        assert restored.completed_at is not None
        assert len(restored.events) == 2

    def test_optional_datetimes_roundtrip_as_none(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Optional datetimes roundtrip as none."""
        job = Job(workspace_id="WS-A")
        entity = job_store._to_entity(job)
        mock_table_client.get_entity.return_value = entity

        restored = job_store.get(job.id)

        assert restored is not None
        assert restored.started_at is None
        assert restored.completed_at is None

    def test_empty_result_and_error_roundtrip_without_becoming_none(
        self, job_store: AzureTableJobStore
    ) -> None:
        """Valid empty values remain distinct from absent values."""
        completed = Job(workspace_id="WS-A")
        completed.start()
        completed.complete({})
        failed = Job(workspace_id="WS-B")
        failed.start()
        failed.fail("")

        restored_completed = job_store._to_job(job_store._to_entity(completed))
        restored_failed = job_store._to_job(job_store._to_entity(failed))

        assert restored_completed.result == {}
        assert restored_failed.error == ""

    def test_all_statuses_roundtrip(self, job_store: AzureTableJobStore) -> None:
        """All statuses roundtrip."""
        for status in JobStatus:
            job = Job(workspace_id="WS-A")
            job.status = status
            entity = job_store._to_entity(job)
            assert entity["status"] == status.value
            restored = job_store._to_job(entity)
            assert restored.status == status.value

    def test_get_malformed_entity_missing_required_field_raises(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get malformed entity missing required field raises."""
        entity = {"RowKey": str(uuid4()), "status": "pending"}  # missing workspace_id
        mock_table_client.get_entity.return_value = entity
        with pytest.raises(ValueError, match="workspace_id"):
            job_store.get(entity["RowKey"])

    def test_get_malformed_entity_invalid_json_raises(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get malformed entity invalid json raises."""
        job = Job(workspace_id="WS-A")
        entity = job_store._to_entity(job)
        entity["metadata"] = "{not-json"
        mock_table_client.get_entity.return_value = entity
        with pytest.raises(ValueError, match="Malformed job entity"):
            job_store.get(job.id)

    def test_update_missing_job_is_noop(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Update missing job is noop."""
        mock_table_client.get_entity.side_effect = ResourceNotFoundError("missing")
        job_store.update(Job(workspace_id="WS-A"))
        mock_table_client.update_entity.assert_not_called()

    def test_update_existing_uses_etag_optimistic_concurrency(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Update existing uses etag optimistic concurrency."""
        job = Job(workspace_id="WS-A")
        job._storage_etag = 'W/"etag-123"'

        job.start()
        job_store.update(job)

        mock_table_client.update_entity.assert_called_once()
        _, kwargs = mock_table_client.update_entity.call_args
        assert kwargs["etag"] == 'W/"etag-123"'
        assert kwargs["match_condition"].name == "IfNotModified"

    def test_update_conflict_raises_concurrency_error(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Update conflict raises concurrency error."""
        job = Job(workspace_id="WS-A")
        job._storage_etag = 'W/"etag-1"'
        conflict = HttpResponseError(message="Precondition Failed")
        conflict.status_code = 412
        mock_table_client.update_entity.side_effect = conflict

        with pytest.raises(ConcurrencyConflictError):
            job_store.update(job)

    def test_update_non_conflict_http_error_propagates(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Update non conflict http error propagates."""
        job = Job(workspace_id="WS-A")
        job._storage_etag = 'W/"etag-1"'
        server_error = HttpResponseError(message="Server error")
        server_error.status_code = 500
        mock_table_client.update_entity.side_effect = server_error

        with pytest.raises(HttpResponseError):
            job_store.update(job)

    def test_get_active_filters_terminal_statuses(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Non-terminal jobs are kept; terminal ones are excluded client-side."""
        running = Job(workspace_id="WS-A")
        running.start()
        completed = Job(workspace_id="WS-A")
        completed.start()
        completed.complete({})

        # The (mocked) server-side query already returns only WS-A entities.
        mock_table_client.query_entities.return_value = [
            job_store._to_entity(running),
            job_store._to_entity(completed),
        ]

        active = job_store.get_active(workspace_id="WS-A")
        assert len(active) == 1
        assert str(active[0].id) == str(running.id)

    def test_get_active_passes_workspace_filter_to_query(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get active passes workspace filter to query."""
        mock_table_client.query_entities.return_value = []
        job_store.get_active(workspace_id="WS-A")
        args, kwargs = mock_table_client.query_entities.call_args
        assert "workspace_id eq @ws" in args[0]
        assert kwargs["parameters"]["ws"] == "WS-A"
        assert args[0].count("status ne") == len(JobStatus) - 2

    def test_get_active_for_workspace_and_has_active_job(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get active for workspace and has active job."""
        mock_table_client.query_entities.return_value = []
        assert job_store.get_active_for_workspace("WS-A") is None
        assert job_store.has_active_job("WS-A") is False

        running = Job(workspace_id="WS-A")
        running.start()
        mock_table_client.query_entities.return_value = [job_store._to_entity(running)]
        assert job_store.get_active_for_workspace("WS-A") is not None
        assert job_store.has_active_job("WS-A") is True

    def test_get_history_filters_sorts_and_limits(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get history filters sorts and limits."""
        entities = []
        for i in range(5):
            job = Job(workspace_id="WS-A")
            job.start()
            job.complete({})
            job.created_at = datetime.now(timezone.utc) - timedelta(hours=i)
            entities.append(job_store._to_entity(job))
        mock_table_client.query_entities.return_value = entities

        result = job_store.get_history(workspace_id="WS-A", limit=3)
        assert len(result) == 3
        assert result[0].created_at >= result[1].created_at >= result[2].created_at

    def test_get_history_excludes_jobs_outside_window(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get history excludes jobs outside window."""
        # The store passes a `created_at ge cutoff` filter to the (mocked)
        # query; assert the filter/parameters reflect the requested window.
        job_store.get_history(days=3)
        _, kwargs = mock_table_client.query_entities.call_args
        assert "cutoff" in kwargs["parameters"]

    def test_get_history_status_filter(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get history status filter."""
        failed = Job(workspace_id="WS-A")
        failed.start()
        failed.fail("boom")
        completed = Job(workspace_id="WS-A")
        completed.start()
        completed.complete({})
        mock_table_client.query_entities.return_value = [
            job_store._to_entity(failed),
            job_store._to_entity(completed),
        ]

        result = job_store.get_history(status=JobStatus.FAILED)
        assert len(result) == 1
        assert result[0].status == JobStatus.FAILED.value

    def test_get_jobs_for_schedule_delegates_to_history(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Get jobs for schedule delegates to history."""
        job = Job(workspace_id="WS-A", schedule_id="SCH-1")
        job.start()
        job.complete({})
        mock_table_client.query_entities.return_value = [job_store._to_entity(job)]

        result = job_store.get_jobs_for_schedule("SCH-1", limit=10)
        assert len(result) == 1
        assert result[0].schedule_id == "SCH-1"
        _, kwargs = mock_table_client.query_entities.call_args
        assert kwargs["parameters"]["sid"] == "SCH-1"

    def test_close_is_idempotent(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Close is idempotent."""
        job_store.close()
        job_store.close()
        # Non-owning injected client: store does NOT close it
        mock_table_client.close.assert_not_called()


class TestAzureTableJobStoreSizeValidation:
    """Explicit pre-write size validation against Azure Table Storage limits."""

    @pytest.fixture
    def mock_table_client(self) -> MagicMock:
        """Provide a mocked ``TableClient``.

        :returns: A mocked ``TableClient``.
        """
        return MagicMock()

    @pytest.fixture
    def job_store(self, mock_table_client: MagicMock) -> AzureTableJobStore:
        """Provide an ``AzureTableJobStore`` wired to the mocked client.

        :param mock_table_client: Mocked table client to inject.
        :returns: An ``AzureTableJobStore`` using the mocked client.
        """
        return AzureTableJobStore(table_client=mock_table_client, table_name="Jobs")

    def test_create_rejects_oversized_events(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """A job whose serialized ``events`` exceeds 64 KiB is rejected, naming the field."""
        job = Job(workspace_id="WS-A")
        job.events.append(
            JobEvent(
                event_type=JobEventType.CREATED,
                message="oversized",
                data={"payload": "e" * (65 * 1024)},
            )
        )

        with pytest.raises(EntityTooLargeError, match="events"):
            job_store.create(job)
        mock_table_client.create_entity.assert_not_called()

    def test_create_rejects_oversized_result(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """A job whose serialized ``result`` exceeds 64 KiB is rejected before create."""
        job = Job(workspace_id="WS-A")
        job.start()
        job.complete({"payload": "r" * (65 * 1024)})

        with pytest.raises(EntityTooLargeError, match="result"):
            job_store.create(job)
        mock_table_client.create_entity.assert_not_called()

    def test_create_rejects_oversized_metadata(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """A job whose serialized ``metadata`` exceeds 64 KiB is rejected before create."""
        job = Job(workspace_id="WS-A")
        job.metadata["blob"] = "m" * (65 * 1024)

        with pytest.raises(EntityTooLargeError, match="metadata"):
            job_store.create(job)
        mock_table_client.create_entity.assert_not_called()

    def test_update_rejects_oversized_entity_before_writing(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """Update also validates size before calling ``update_entity``."""
        job = Job(workspace_id="WS-A")
        job._storage_etag = 'W/"etag-1"'
        job.metadata["blob"] = "m" * (65 * 1024)

        with pytest.raises(EntityTooLargeError):
            job_store.update(job)
        mock_table_client.update_entity.assert_not_called()

    def test_create_succeeds_for_boundary_safe_normal_entity(
        self, job_store: AzureTableJobStore, mock_table_client: MagicMock
    ) -> None:
        """A normally-sized job (well under both limits) is not rejected."""
        job = Job(workspace_id="WS-A", test_group="DatabaseHighAvailability")
        job.start()
        job.complete({"ok": True, "details": "n" * 1024})

        result = job_store.create(job)

        mock_table_client.create_entity.assert_called_once()
        assert result is job


class TestAzureTableScheduleStoreConstruction:
    """Constructor behavior: DI vs. endpoint-based production construction."""

    def test_requires_endpoint_or_table_client(self) -> None:
        """Requires endpoint or table client."""
        with pytest.raises(ValueError, match="endpoint is required"):
            AzureTableScheduleStore()

    def test_constructs_from_endpoint_with_custom_table_name(self) -> None:
        """Constructs from endpoint with custom table name."""
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_client = MagicMock()
            mock_svc.get_table_client.return_value = mock_client
            mock_svc_cls.return_value = mock_svc
            mock_cred = MagicMock()

            store = AzureTableScheduleStore(
                endpoint="https://acct.table.core.windows.net",
                table_name="CustomSchedules",
                credential=mock_cred,
            )

            mock_svc.create_table_if_not_exists.assert_called_once_with("CustomSchedules")
            mock_svc.get_table_client.assert_called_once_with("CustomSchedules")
            assert store.table_name == "CustomSchedules"

    def test_close_closes_owned_service_and_credential_exactly_once(self) -> None:
        """Production construction owns the service; close() releases it once.

        The derived ``TableClient``'s own ``close()`` is a no-op transport
        wrapper in the real SDK, so releasing resources depends on closing
        the owning service client -- verified here directly since ``close()``
        is idempotent. The credential is caller-owned and NOT closed by the store.
        """
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_client = MagicMock()
            mock_svc.get_table_client.return_value = mock_client
            mock_svc_cls.return_value = mock_svc
            mock_cred = MagicMock()

            store = AzureTableScheduleStore(
                endpoint="https://acct.table.core.windows.net", credential=mock_cred
            )
            store.close()
            store.close()

            mock_svc.close.assert_called_once()
            # Credential is NOT owned by the store — not closed here
            mock_cred.close.assert_not_called()

    def test_injected_client_close_does_not_own_service_or_credential(self) -> None:
        """DI construction owns no service; only the injected client is closed."""
        mock_client = MagicMock()
        store = AzureTableScheduleStore(table_client=mock_client, table_name="Schedules")

        assert store._service is None

        store.close()
        # Non-owning: injected client is NOT closed by the store
        mock_client.close.assert_not_called()


class TestAzureTableScheduleStoreCrud:
    """CRUD and query round trips for AzureTableScheduleStore."""

    @pytest.fixture
    def mock_table_client(self) -> MagicMock:
        """Provide a mocked ``TableClient``.

        :returns: A mocked ``TableClient``.
        """
        return MagicMock()

    @pytest.fixture
    def schedule_store(self, mock_table_client: MagicMock) -> AzureTableScheduleStore:
        """Provide an ``AzureTableScheduleStore`` wired to the mocked client.

        :param mock_table_client: Mocked table client to inject.
        :returns: An ``AzureTableScheduleStore`` using the mocked client.
        """
        return AzureTableScheduleStore(table_client=mock_table_client, table_name="Schedules")

    def test_create_calls_create_entity(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Create calls create entity."""
        schedule = Schedule(name="daily", cron_expression="0 0 * * *", workspace_ids=["WS-A"])
        result = schedule_store.create(schedule)
        mock_table_client.create_entity.assert_called_once()
        entity = mock_table_client.create_entity.call_args[0][0]
        assert entity["PartitionKey"] == "staf"
        assert entity["RowKey"] == schedule.id
        assert result is schedule

    def test_create_duplicate_raises_value_error(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Create duplicate raises value error."""
        mock_table_client.create_entity.side_effect = ResourceExistsError("duplicate")
        with pytest.raises(ValueError, match="already exists"):
            schedule_store.create(Schedule(name="daily", cron_expression="0 0 * * *"))

    def test_get_returns_none_when_missing(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Get returns none when missing."""
        mock_table_client.get_entity.side_effect = ResourceNotFoundError("missing")
        assert schedule_store.get("missing-id") is None

    def test_get_roundtrips_full_schedule(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Get roundtrips full schedule."""
        now = datetime.now(timezone.utc)
        schedule = Schedule(
            name="nightly",
            description="desc",
            cron_expression="0 2 * * *",
            workspace_ids=["WS-A", "WS-B"],
            test_group="ConfigurationChecks",
            test_ids=["c1", "c2"],
            enabled=True,
            next_run_time=now,
            last_run_time=now,
            last_run_job_ids=["J1", "J2"],
            total_runs=7,
        )
        entity = schedule_store._to_entity(schedule)
        mock_table_client.get_entity.return_value = entity

        restored = schedule_store.get(schedule.id)

        assert restored is not None
        assert restored.id == schedule.id
        assert restored.name == "nightly"
        assert restored.cron_expression == "0 2 * * *"
        assert restored.workspace_ids == ["WS-A", "WS-B"]
        assert restored.test_group == "ConfigurationChecks"
        assert restored.test_ids == ["c1", "c2"]
        assert restored.enabled is True
        assert restored.next_run_time is not None
        assert restored.last_run_time is not None
        assert restored.last_run_job_ids == ["J1", "J2"]
        assert restored.total_runs == 7

    def test_get_malformed_entity_missing_required_field_raises(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Get malformed entity missing required field raises."""
        entity = {"RowKey": "SCH-1", "name": "x"}  # missing cron_expression
        mock_table_client.get_entity.return_value = entity
        with pytest.raises(ValueError, match="cron_expression"):
            schedule_store.get("SCH-1")

    def test_get_malformed_entity_invalid_json_raises(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Get malformed entity invalid json raises."""
        schedule = Schedule(name="x", cron_expression="* * * * *")
        entity = schedule_store._to_entity(schedule)
        entity["workspace_ids"] = "[not-json"
        mock_table_client.get_entity.return_value = entity
        with pytest.raises(ValueError, match="Malformed schedule entity"):
            schedule_store.get(schedule.id)

    def test_list_all(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """List all."""
        enabled = Schedule(name="a", cron_expression="* * * * *", enabled=True)
        disabled = Schedule(name="b", cron_expression="* * * * *", enabled=False)
        mock_table_client.query_entities.return_value = [
            schedule_store._to_entity(enabled),
            schedule_store._to_entity(disabled),
        ]
        assert len(schedule_store.list()) == 2

    def test_list_enabled_only_filters(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """List enabled only filters."""
        enabled = Schedule(name="a", cron_expression="* * * * *", enabled=True)
        mock_table_client.query_entities.return_value = [schedule_store._to_entity(enabled)]

        result = schedule_store.list(enabled_only=True)

        assert len(result) == 1
        args, _ = mock_table_client.query_entities.call_args
        assert "enabled eq true" in args[0]

    def test_get_enabled_delegates_to_list(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Get enabled delegates to list."""
        mock_table_client.query_entities.return_value = []
        assert schedule_store.get_enabled() == []
        args, _ = mock_table_client.query_entities.call_args
        assert "enabled eq true" in args[0]

    def test_update_missing_raises_value_error(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Update missing raises value error."""
        mock_table_client.get_entity.side_effect = ResourceNotFoundError("missing")
        with pytest.raises(ValueError, match="not found"):
            schedule_store.update(Schedule(name="x", cron_expression="* * * * *"))
        mock_table_client.update_entity.assert_not_called()

    def test_update_existing_uses_etag_and_bumps_updated_at(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Update existing uses etag and bumps updated at."""
        schedule = Schedule(name="x", cron_expression="* * * * *")
        schedule.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
        original_updated_at = schedule.updated_at
        schedule._storage_etag = 'W/"sched-etag"'

        updated = schedule_store.update(schedule)

        mock_table_client.update_entity.assert_called_once()
        _, kwargs = mock_table_client.update_entity.call_args
        assert kwargs["etag"] == 'W/"sched-etag"'
        assert kwargs["match_condition"].name == "IfNotModified"
        assert updated.updated_at > original_updated_at

    def test_update_conflict_raises_concurrency_error(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Update conflict raises concurrency error."""
        schedule = Schedule(name="x", cron_expression="* * * * *")
        schedule._storage_etag = 'W/"etag-1"'
        conflict = HttpResponseError(message="Precondition Failed")
        conflict.status_code = 412
        mock_table_client.update_entity.side_effect = conflict

        with pytest.raises(ConcurrencyConflictError):
            schedule_store.update(schedule)

    def test_delete_existing_returns_true(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Delete existing returns true."""
        assert schedule_store.delete("SCH-1") is True
        mock_table_client.delete_entity.assert_called_once_with("staf", "SCH-1")

    def test_delete_missing_returns_false(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Delete missing returns false."""
        mock_table_client.delete_entity.side_effect = ResourceNotFoundError("missing")
        assert schedule_store.delete("missing") is False

    def test_close_is_idempotent(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Close is idempotent."""
        schedule_store.close()
        schedule_store.close()
        # Non-owning injected client: store does NOT close it
        mock_table_client.close.assert_not_called()


class TestAzureTableScheduleStoreSizeValidation:
    """Explicit pre-write size validation against Azure Table Storage limits."""

    @pytest.fixture
    def mock_table_client(self) -> MagicMock:
        """Provide a mocked ``TableClient``.

        :returns: A mocked ``TableClient``.
        """
        return MagicMock()

    @pytest.fixture
    def schedule_store(self, mock_table_client: MagicMock) -> AzureTableScheduleStore:
        """Provide an ``AzureTableScheduleStore`` wired to the mocked client.

        :param mock_table_client: Mocked table client to inject.
        :returns: An ``AzureTableScheduleStore`` using the mocked client.
        """
        return AzureTableScheduleStore(table_client=mock_table_client, table_name="Schedules")

    def test_create_rejects_oversized_description(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """A schedule whose ``description`` exceeds 64 KiB is rejected, naming the field."""
        schedule = Schedule(
            name="daily",
            cron_expression="0 0 * * *",
            workspace_ids=["WS-A"],
            description="d" * (65 * 1024),
        )

        with pytest.raises(EntityTooLargeError, match="description"):
            schedule_store.create(schedule)
        mock_table_client.create_entity.assert_not_called()

    def test_create_rejects_oversized_test_ids(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """A schedule whose serialized ``test_ids`` exceeds 64 KiB is rejected."""
        schedule = Schedule(
            name="daily",
            cron_expression="0 0 * * *",
            workspace_ids=["WS-A"],
            test_ids=[f"test-{i:06d}" for i in range(10_000)],
        )

        with pytest.raises(EntityTooLargeError, match="test_ids"):
            schedule_store.create(schedule)
        mock_table_client.create_entity.assert_not_called()

    def test_update_rejects_oversized_entity_before_writing(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """Update also validates size before calling ``update_entity``."""
        schedule = Schedule(name="daily", cron_expression="0 0 * * *", workspace_ids=["WS-A"])
        mock_table_client.get_entity.return_value = _entity_with_etag(
            schedule_store._to_entity(schedule)
        )
        schedule.description = "d" * (65 * 1024)

        with pytest.raises(EntityTooLargeError):
            schedule_store.update(schedule)
        mock_table_client.update_entity.assert_not_called()

    def test_create_succeeds_for_boundary_safe_normal_entity(
        self, schedule_store: AzureTableScheduleStore, mock_table_client: MagicMock
    ) -> None:
        """A normally-sized schedule (well under both limits) is not rejected."""
        schedule = Schedule(
            name="daily",
            cron_expression="0 0 * * *",
            workspace_ids=["WS-A", "WS-B"],
            description="Runs the nightly regression suite" * 10,
        )

        result = schedule_store.create(schedule)

        mock_table_client.create_entity.assert_called_once()
        assert result is schedule


# ---------------------------------------------------------------------------
# _new_table_resources: service leak on initialization failure
# ---------------------------------------------------------------------------


class TestNewTableResourcesServiceLeak:
    """Prove TableServiceClient is closed if create_table_if_not_exists raises."""

    def test_service_closed_on_create_table_failure(self) -> None:
        """If table creation fails, the TableServiceClient is closed before re-raising."""
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.create_table_if_not_exists.side_effect = HttpResponseError(
                message="403 Forbidden"
            )
            mock_svc_cls.return_value = mock_svc
            mock_cred = MagicMock()

            from src.core.storage.azure_table_store import _new_table_resources

            with pytest.raises(HttpResponseError, match="403 Forbidden"):
                _new_table_resources(
                    endpoint="https://acct.table.core.windows.net",
                    table_name="TestTable",
                    credential=mock_cred,
                )

            mock_svc.close.assert_called_once()

    def test_credential_not_closed_on_create_table_failure(self) -> None:
        """Credential remains caller-owned even when service init fails."""
        with patch("src.core.storage.azure_table_store.TableServiceClient") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.create_table_if_not_exists.side_effect = RuntimeError("boom")
            mock_svc_cls.return_value = mock_svc
            mock_cred = MagicMock()

            from src.core.storage.azure_table_store import _new_table_resources

            with pytest.raises(RuntimeError, match="boom"):
                _new_table_resources(
                    endpoint="https://acct.table.core.windows.net",
                    table_name="TestTable",
                    credential=mock_cred,
                )

            mock_cred.close.assert_not_called()
