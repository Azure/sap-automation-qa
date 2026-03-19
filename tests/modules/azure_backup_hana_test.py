# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Unit tests for the azure_backup_hana module.
"""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
import pytest
import yaml
from src.modules.azure_backup_hana import (
    AzureBackupHana,
    run_module,
)
from src.module_utils.enums import TestStatus
from src.module_utils.backup_discovery import (
    BackupDiscovery,
)
from src.module_utils.backup_parameters import (
    BackupParameterBuilder,
)
from src.module_utils.backup_restore import (
    BackupRestoreHelper,
)
from azure.mgmt.recoveryservicesbackup.models import (
    AzureWorkloadJob,
    AzureWorkloadSAPHanaRestoreRequest,
    AzureVmWorkloadSAPHanaDatabaseProtectedItem,
    ProtectedItemResource,
    RecoveryType,
)


def _make_protected_item(
    friendly_name: str = "SYSTEMDB",
    server_name: str = "hanavm01",
    parent_name: str = "H05",
    protected_item_health_status: str | None = "Healthy",
    protection_status: str = "Protected",
    last_backup_time: datetime | None = None,
    policy_name: str = "daily-policy",
    policy_id: str = "/subscriptions/sub/resourceGroups/rg/providers/"
    "Microsoft.RecoveryServices/vaults/vault/backupPolicies/daily-policy",
    container_name: str = "VMAppContainer;Compute;rg;hanavm01",
    item_name: str = "saphanadatabase;h05;systemdb",
) -> SimpleNamespace:
    """Build a fake ``ProtectedItemResource`` for testing."""
    return SimpleNamespace(
        name=item_name,
        container_name=container_name,
        properties=SimpleNamespace(
            friendly_name=friendly_name,
            server_name=server_name,
            parent_name=parent_name,
            protected_item_health_status=protected_item_health_status,
            protection_status=protection_status,
            last_backup_time=last_backup_time or datetime(2026, 3, 1, 12, 0),
            policy_name=policy_name,
            policy_id=policy_id,
            container_name=container_name,
        ),
    )


def _make_recovery_point(
    rp_id: str = "/subscriptions/sub/resourceGroups/rg/"
    "providers/Microsoft.RecoveryServices/"
    "vaults/vault/backupFabrics/Azure/"
    "protectionContainers/ctr/"
    "protectedItems/item/recoveryPoints/rp123",
    rp_time: datetime | None = None,
    rp_type: str = "Full",
) -> SimpleNamespace:
    """Build a fake ``RecoveryPointResource`` for testing."""
    return SimpleNamespace(
        id=rp_id,
        properties=SimpleNamespace(
            recovery_point_time_in_utc=(rp_time or datetime(2026, 3, 1, 10, 0)),
            type=rp_type,
        ),
    )


def _make_job(status: str = "Completed") -> SimpleNamespace:
    """Build a fake ``JobResource`` for testing."""
    return SimpleNamespace(
        properties=SimpleNamespace(status=status, error_details=None),
    )


def _make_poller(
    job_id: str = "job-abc-123",
    header_key: str = "azure-asyncoperation",
) -> SimpleNamespace:
    """Build a fake LRO poller with headers containing a job ID."""
    url = (
        f"https://management.azure.com/subscriptions/sub/"
        f"resourceGroups/rg/providers/Microsoft.RecoveryServices/"
        f"operationResults/{job_id}?api-version=2024-01-01"
    )
    return SimpleNamespace(
        initial_response=lambda: SimpleNamespace(
            http_response=SimpleNamespace(headers={header_key: url}),
        ),
    )


_PARAM_YAML = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "roles"
    / "backup_db_hana"
    / "vars"
    / "backup-parameters.yml"
)
with open(_PARAM_YAML, encoding="utf-8") as _fh:
    PARAM_DEFS: list[dict[str, str]] = yaml.safe_load(
        _fh,
    )["backup_parameters"]


@pytest.fixture
def mock_client(mocker):
    """Return a ``mocker.MagicMock`` standing in for ``RecoveryServicesBackupClient``."""
    return mocker.MagicMock()


@pytest.fixture
def backup(mock_client, mocker):
    """Create an ``AzureBackupHana`` instance with the SDK client pre-injected."""
    mocker.patch(
        "src.modules.azure_backup_hana.ManagedIdentityCredential",
    )
    instance = AzureBackupHana(
        vault_resource_id=(
            "/subscriptions/sub-123"
            "/resourceGroups/test-rg"
            "/providers/Microsoft.RecoveryServices"
            "/vaults/test-vault"
        ),
        subscription_id="sub-123",
        msi_client_id="msi-abc",
        database_sid="H05",
        poll_interval=0,
        poll_timeout=5,
        parameter_definitions=PARAM_DEFS,
    )
    instance._client = mock_client
    return instance


class TestAzureBackupHanaInit:
    """Tests for ``AzureBackupHana`` initialisation."""

    def test_default_result_keys(self, backup):
        """Result dict contains required keys after init."""
        for key in (
            "protected_items",
            "restore_points",
            "restore_job",
            "start",
            "end",
        ):
            assert key in backup.result

    def test_initial_values(self, backup):
        """Attributes correctly stored from constructor."""
        assert backup.vault_name == "test-vault"
        assert backup.vault_resource_group == "test-rg"
        assert backup.subscription_id == "sub-123"
        assert backup.database_sid == "H05"
        assert backup.poll_interval == 0
        assert backup.poll_timeout == 5

    def test_vault_resource_id_stored(self, backup):
        """Full resource ID is stored on the instance."""
        assert "Microsoft.RecoveryServices/vaults/test-vault" in (backup.vault_resource_id)

    def test_result_start_is_iso_timestamp(self, backup):
        """The start timestamp must be a valid ISO-8601 string."""
        datetime.fromisoformat(backup.result["start"])

    def test_returns_cached_client(self, backup, mock_client):
        """When ``_client`` is set, the property should return it directly."""
        assert backup.client is mock_client

    def test_creates_client_when_none(self, mocker):
        """Client is created via SDK when ``_client`` is ``None``."""
        mock_cred = mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        mock_cls = mocker.patch(
            "src.modules.azure_backup_hana.RecoveryServicesBackupClient",
        )
        instance = AzureBackupHana(
            vault_resource_id=(
                "/subscriptions/sub"
                "/resourceGroups/rg"
                "/providers/Microsoft.RecoveryServices"
                "/vaults/v"
            ),
            subscription_id="sub",
            msi_client_id="msi",
        )
        instance._client = None
        _ = instance.client
        mock_cred.assert_called_once_with(client_id="msi")
        mock_cls.assert_called_once_with(
            credential=mock_cred.return_value,
            subscription_id="sub",
        )

    def test_creates_system_mi_when_no_client_id(self, mocker):
        """System-assigned MI used when ``msi_client_id`` is empty."""
        mock_cred = mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        mocker.patch(
            "src.modules.azure_backup_hana.RecoveryServicesBackupClient",
        )
        instance = AzureBackupHana(
            vault_resource_id=(
                "/subscriptions/sub"
                "/resourceGroups/rg"
                "/providers/Microsoft.RecoveryServices"
                "/vaults/v"
            ),
            subscription_id="sub",
            msi_client_id="",
        )
        instance._client = None
        _ = instance.client
        mock_cred.assert_called_once_with()

    def test_raises_runtime_error_on_auth_failure(self, mocker):
        """``RuntimeError`` raised when credential creation fails."""
        mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
            side_effect=Exception("auth boom"),
        )
        instance = AzureBackupHana(
            vault_resource_id=(
                "/subscriptions/sub"
                "/resourceGroups/rg"
                "/providers/Microsoft.RecoveryServices"
                "/vaults/v"
            ),
            subscription_id="sub",
        )
        instance._client = None
        with pytest.raises(RuntimeError, match="auth boom"):
            _ = instance.client


class TestStaticHelpers:
    """Tests for static / private utility methods."""

    @pytest.mark.parametrize(
        "rp_id, expected",
        [
            ("/subs/rg/rp123", "rp123"),
            ("single", "single"),
            ("", ""),
        ],
    )
    def test_rp_name_from_id(self, rp_id, expected):
        """Last ARM path segment extracted correctly."""
        assert BackupRestoreHelper.rp_name_from_id(rp_id) == expected

    def test_build_container_id(self, backup):
        """ARM resource ID built with correct format."""
        cid = BackupRestoreHelper.build_container_id(
            "sub-123",
            "myvm",
            "myrg",
        )
        assert cid == (
            "/subscriptions/sub-123"
            "/resourceGroups/myrg"
            "/providers/Microsoft.Compute"
            "/virtualMachines/myvm"
        )

    def test_vm_id_to_container_id(self, backup):
        """VM Compute ID converted to protection container ID."""
        vm_id = (
            "/subscriptions/sub-x/resourceGroups/my-rg"
            "/providers/Microsoft.Compute"
            "/virtualMachines/my-vm"
        )
        result = backup.restore_helper._vm_id_to_container_id(
            vm_id,
        )
        assert "/protectionContainers/" in result
        assert "VMAppContainer;Compute;my-rg;my-vm" in result
        assert "Microsoft.RecoveryServices" in result
        assert "Microsoft.Compute" not in result

    def test_get_props(self):
        """SDK properties returned with typed dot access."""
        item = _make_protected_item(friendly_name="DB01")
        props = AzureBackupHana._get_props(cast(ProtectedItemResource, item))
        assert props.friendly_name == "DB01"
        assert props.protected_item_health_status == "Healthy"

    def test_get_props_none_health(self):
        """None protected_item_health_status is passthrough (caller handles)."""
        item = _make_protected_item(protected_item_health_status=None)
        props = AzureBackupHana._get_props(cast(ProtectedItemResource, item))
        assert props.protected_item_health_status is None

    @pytest.mark.parametrize(
        "container, expected",
        [
            ("HanaHSRContainer;Compute;rg;vm", True),
            ("hanahsrcontainer;x;y;z", True),
            ("VMAppContainer;Compute;rg;vm", False),
            ("", False),
            (None, False),
        ],
    )
    def test_is_hsr_container(self, container, expected):
        """HSR container detection by name substring."""
        assert BackupDiscovery.is_hsr_container(container) == expected

    @pytest.mark.parametrize(
        "source_vm, container, server_name, expected",
        [
            ("", "HanaHSRContainer;hsrtestxn02", "n02dhdb00a5678", True),
            ("", "VMAppContainer;Compute;rg;vm", "hanavm01", True),
            (
                "testx-eus2-sap99-n01_n01dhdb_z1_00a1234",
                "VMAppContainer;compute;testx-eus2-sap99-n01;"
                "testx-eus2-sap99-n01_n01dhdb_z1_00a1234",
                "n01dhdb00a1234",
                True,
            ),
            (
                "testx-eus2-sap99-n01_n01dhdb_z1_00a1234",
                "VMAppContainer;compute;other-rg;some-other-vm",
                "othervm01",
                False,
            ),
            (
                "testx-eus2-sap99-n01_n01dhdb_z1_00a1234",
                "HanaHSRContainer;hsrtestxn01",
                "n01dhdb00a1234",
                True,
            ),
            (
                "testx-eus2-sap99-n01_n01dhdb_z1_00a1234",
                "HanaHSRContainer;hsrtestxn02",
                "n02dhdb00a5678",
                False,
            ),
            (
                "testx-eus2-sap99-n01_n01dhdb_z1_00a1234",
                "HanaHSRContainer;hsrtestxn01",
                "",
                False,
            ),
        ],
    )
    def test_matches_source_vm(self, source_vm, container, server_name, expected, mocker):
        """_matches_source_vm filters HSR by server_name overlap."""
        disc = BackupDiscovery(
            client=mocker.MagicMock(),
            vault_name="v",
            vault_resource_group="rg",
            source_vm_name=source_vm,
        )
        assert disc._matches_source_vm(container, server_name) == expected

    @pytest.mark.parametrize(
        "health, protection, has_rp, is_hsr, last_job_status, expected",
        [
            ("Healthy", "Healthy", True, False, None, "PASSED"),
            ("Healthy", "Protected", True, False, None, "PASSED"),
            ("Healthy", "Protecting", True, False, None, "PASSED"),
            ("Unknown", "Healthy", True, True, None, "PASSED"),
            ("Unknown", "Healthy", True, False, None, "WARNING"),
            ("Unhealthy", "Healthy", True, False, None, "WARNING"),
            ("Healthy", "NotProtected", True, False, None, "FAILED"),
            ("Healthy", "ProtectionFailed", True, False, None, "FAILED"),
            ("Healthy", "Invalid", True, False, None, "FAILED"),
            ("Healthy", "Healthy", False, False, None, "FAILED"),
            (None, "Healthy", True, False, None, "WARNING"),
            ("Unhealthy", "Unhealthy", True, False, "InProgress", "WARNING"),
            ("Unhealthy", "Unhealthy", True, False, None, "WARNING"),
            ("Unhealthy", "Unhealthy", False, False, "InProgress", "FAILED"),
        ],
    )
    def test_evaluate_db_status(
        self,
        health,
        protection,
        has_rp,
        is_hsr,
        last_job_status,
        expected,
    ):
        """Per-DB status derived from health/protection/RP/HSR."""
        props = SimpleNamespace(
            protected_item_health_status=health,
            protection_status=protection,
        )
        last_job = (
            cast(AzureWorkloadJob, SimpleNamespace(status=last_job_status))
            if last_job_status
            else None
        )
        assert (
            BackupDiscovery.evaluate_db_status(
                cast(AzureVmWorkloadSAPHanaDatabaseProtectedItem, props),
                has_rp,
                is_hsr,
                last_job,
            )
            == expected
        )

    def test_all_healthy(self, backup, mock_client):
        """SUCCESS when every item is healthy with restore points."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(friendly_name="DB1"),
            _make_protected_item(friendly_name="DB2"),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.SUCCESS.value
        assert len(result["protected_items"]) == 2
        assert "2 PASSED" in result["message"]
        assert result["end"] is not None
        for item in result["protected_items"]:
            assert item["backup_status"] == TestStatus.SUCCESS.value
            assert "hana_system" in item
            assert "latest_restore_point" in item

    def test_unhealthy_items_give_warning(self, backup, mock_client):
        """WARNING when at least one item has non-Healthy status."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(protected_item_health_status="Healthy"),
            _make_protected_item(protected_item_health_status="Unhealthy"),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.WARNING.value
        assert "1 WARNING" in result["message"]

    def test_empty_vault(self, backup, mock_client):
        """FAILED with zero items when vault is empty."""
        mock_client.backup_protected_items.list.return_value = []
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.ERROR.value
        assert result["protected_items"] == []

    def test_last_backup_time_none(self, backup, mock_client):
        """Empty string when last_backup_time is ``None``."""
        item = _make_protected_item()
        item.properties.last_backup_time = None
        mock_client.backup_protected_items.list.return_value = [item]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()
        assert result["protected_items"][0]["last_backup_time"] == ""

    def test_hsr_container_unknown_health_is_passed(
        self,
        backup,
        mock_client,
    ):
        """PASSED for HSR container with Unknown health_status."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(
                protected_item_health_status=None,
                container_name=("HanaHSRContainer;Compute;rg;hsrvm01"),
            ),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.SUCCESS.value
        item = result["protected_items"][0]
        assert item["backup_status"] == TestStatus.SUCCESS.value
        assert item["server_type"] == "HSR"

    def test_non_hsr_unknown_health_is_warning(
        self,
        backup,
        mock_client,
    ):
        """WARNING for non-HSR container with Unknown health."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(protected_item_health_status=None),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.WARNING.value
        item = result["protected_items"][0]
        assert item["backup_status"] == TestStatus.WARNING.value
        assert item["server_type"] == "Standalone Instance"

    def test_no_restore_points_gives_failed(
        self,
        backup,
        mock_client,
    ):
        """FAILED when an item has no recovery points."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = []
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.ERROR.value
        assert result["protected_items"][0]["backup_status"] == (TestStatus.ERROR.value)

    def test_cumulative_status_worst_wins(
        self,
        backup,
        mock_client,
    ):
        """Cumulative status reflects worst per-DB status."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(
                friendly_name="healthy_db",
                protected_item_health_status="Healthy",
            ),
            _make_protected_item(
                friendly_name="no_rp_db",
                protected_item_health_status="Healthy",
            ),
        ]
        mock_client.recovery_points.list.side_effect = [
            [_make_recovery_point()],
            [],
        ]
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.ERROR.value
        statuses = [i["backup_status"] for i in result["protected_items"]]
        assert TestStatus.SUCCESS.value in statuses
        assert TestStatus.ERROR.value in statuses

    def test_discover_includes_restore_points_list(
        self,
        backup,
        mock_client,
    ):
        """Result includes legacy restore_points list."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        assert len(result["restore_points"]) == 1
        rp = result["restore_points"][0]
        assert rp["recovery_point_count"] == 1
        assert rp["latest_recovery_point_type"] == "Full"

    def test_details_contains_parameters_list(
        self,
        backup,
        mock_client,
    ):
        """Result includes details dict with parameters for table rendering."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        assert "details" in result
        assert "parameters" in result["details"]
        params = result["details"]["parameters"]
        assert isinstance(params, list)
        assert len(params) > 0
        for p in params:
            assert set(p.keys()) == {
                "category",
                "id",
                "name",
                "value",
                "expected_value",
                "status",
            }

    def test_details_parameters_per_db_rows(
        self,
        backup,
        mock_client,
    ):
        """Each DB produces 9 parameter rows for the table."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(friendly_name="SYSTEMDB"),
            _make_protected_item(friendly_name="HDB"),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = []
        result = backup.discover_protected_items()

        params = result["details"]["parameters"]
        assert len(params) == 18

    def test_details_parameters_names(
        self,
        backup,
        mock_client,
    ):
        """Parameter rows cover expected validation aspects."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        param_names = [p["name"] for p in result["details"]["parameters"]]
        assert "Backup Status" in param_names
        assert "Health Status" in param_names
        assert "Protection Status" in param_names
        assert "Last Backup Time" in param_names
        assert "Latest Restore Point" in param_names
        assert "Backup Type" in param_names
        assert "Policy Name" in param_names
        assert "Last Job" in param_names
        assert "Last Full Backup" in param_names

    def test_details_parameters_status_coloring(
        self,
        backup,
        mock_client,
    ):
        """Parameter status reflects per-DB backup_status."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(protected_item_health_status="Healthy"),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.discover_protected_items()

        for p in result["details"]["parameters"]:
            if p["name"] == "Backup Status":
                assert p["status"] == TestStatus.SUCCESS.value
                assert p["value"] == TestStatus.SUCCESS.value

    def test_details_empty_vault_no_parameters(
        self,
        backup,
        mock_client,
    ):
        """Empty vault produces empty parameters list."""
        mock_client.backup_protected_items.list.return_value = []
        result = backup.discover_protected_items()

        assert result["details"]["parameters"] == []

    def test_hsr_health_expected_value(
        self,
        backup,
        mock_client,
    ):
        """HSR containers show 'Healthy or Unknown (HSR)' as expected."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(
                container_name=("HanaHSRContainer;Compute;rg;vm01"),
            ),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = []
        result = backup.discover_protected_items()

        health_rows = [p for p in result["details"]["parameters"] if p["name"] == "Health Status"]
        assert len(health_rows) == 1
        assert health_rows[0]["expected_value"] == ("Healthy or Unknown (HSR)")

    def test_non_hsr_health_expected_value(
        self,
        backup,
        mock_client,
    ):
        """Non-HSR containers show 'Healthy' as expected."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(
                container_name=("VMAppContainer;Compute;rg;vm01"),
            ),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = []
        result = backup.discover_protected_items()

        health_rows = [p for p in result["details"]["parameters"] if p["name"] == "Health Status"]
        assert len(health_rows) == 1
        assert health_rows[0]["expected_value"] == "Healthy"

    def test_custom_param_defs_subset(
        self,
        mock_client,
        mocker,
    ):
        """Custom parameter_definitions produce only those rows."""
        mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        custom_defs = [
            {
                "key": "backup_status",
                "name": "Backup Status",
                "expected_value": "PASSED",
                "id_source": "server_type",
            },
            {
                "key": "policy_name",
                "name": "Policy Name",
                "expected_value": "",
                "id_source": "db_name",
            },
        ]
        instance = AzureBackupHana(
            vault_resource_id=(
                "/subscriptions/sub-123"
                "/resourceGroups/test-rg"
                "/providers/Microsoft.RecoveryServices"
                "/vaults/test-vault"
            ),
            subscription_id="sub-123",
            msi_client_id="msi-abc",
            database_sid="H05",
            parameter_definitions=custom_defs,
        )
        instance._client = mock_client
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = []
        result = instance.discover_protected_items()

        params = result["details"]["parameters"]
        assert len(params) == 2
        assert params[0]["name"] == "Backup Status"
        assert params[1]["name"] == "Policy Name"

    def test_custom_param_defs_hsr_expected(
        self,
        mock_client,
        mocker,
    ):
        """YAML expected_value_hsr overrides expected_value for HSR."""
        mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        custom_defs = [
            {
                "key": "health_status",
                "name": "Health Status",
                "expected_value": "Healthy",
                "expected_value_hsr": "Healthy or Unknown (HSR)",
                "id_source": "db_name",
            },
        ]
        instance = AzureBackupHana(
            vault_resource_id=(
                "/subscriptions/sub-123"
                "/resourceGroups/test-rg"
                "/providers/Microsoft.RecoveryServices"
                "/vaults/test-vault"
            ),
            subscription_id="sub-123",
            msi_client_id="msi-abc",
            database_sid="H05",
            parameter_definitions=custom_defs,
        )
        instance._client = mock_client
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(
                container_name="HanaHSRContainer;Compute;rg;vm01",
            ),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = []
        result = instance.discover_protected_items()

        params = result["details"]["parameters"]
        assert len(params) == 1
        assert params[0]["expected_value"] == "Healthy or Unknown (HSR)"

    def test_compute_param_values_keys(self):
        """_compute_param_values returns all nine expected keys."""
        props = SimpleNamespace(
            protected_item_health_status="Healthy",
            protection_status="Healthy",
            last_backup_time=datetime(2026, 3, 1, 12, 0),
            policy_name="daily-policy",
            policy_id="/subscriptions/sub/resourceGroups/rg/providers/"
            "Microsoft.RecoveryServices/vaults/vault/backupPolicies/daily-policy",
            container_name="VMAppContainer;Compute;rg;vm01",
        )
        computed = BackupParameterBuilder.compute_param_values(
            props,
            "2026-03-01T10:00:00",
            "Full",
            None,
            None,
            TestStatus.SUCCESS.value,
        )
        expected_keys = {
            "backup_status",
            "health_status",
            "protection_status",
            "last_backup_time",
            "latest_restore_point",
            "backup_type",
            "policy_name",
            "last_job",
            "last_full_backup",
        }
        assert set(computed.keys()) == expected_keys
        for vals in computed.values():
            assert "value" in vals
            assert "status" in vals

    def test_discover_includes_job_info(
        self,
        backup,
        mock_client,
    ):
        """Job info populated from backup_jobs.list."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(friendly_name="SYSTEMDB"),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = [
            SimpleNamespace(
                properties=AzureWorkloadJob(
                    entity_friendly_name="hsrdjwp2r10:SYSTEMDB",
                    operation="Backup",
                    status="Completed",
                    start_time=datetime(2026, 3, 5, 15, 29),
                ),
            ),
            SimpleNamespace(
                properties=AzureWorkloadJob(
                    entity_friendly_name="hsrdjwp2r10:SYSTEMDB",
                    operation="ConfigureBackup",
                    status="Completed",
                    start_time=datetime(2026, 3, 5, 15, 12),
                ),
            ),
        ]
        result = backup.discover_protected_items()

        db = result["protected_items"][0]
        assert db["last_job_operation"] == "Backup"
        assert db["last_job_status"] == "Completed"
        assert db["last_full_backup_status"] == "Completed"
        assert "2026-03-05" in db["last_full_backup_time"]

        param_names = [p["name"] for p in result["details"]["parameters"]]
        assert "Last Job" in param_names
        assert "Last Full Backup" in param_names

        last_job_row = [p for p in result["details"]["parameters"] if p["name"] == "Last Job"][0]
        assert "Backup" in last_job_row["value"]
        assert last_job_row["status"] == TestStatus.SUCCESS.value

    def test_discover_job_bracket_name_stripped(
        self,
        backup,
        mock_client,
    ):
        """Backup jobs with [vm_name] suffix still match the DB."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(friendly_name="SYSTEMDB"),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.return_value = [
            SimpleNamespace(
                properties=AzureWorkloadJob(
                    entity_friendly_name="hsrdjwp2r10:SYSTEMDB [hanavm01]",
                    operation="Backup (Full)",
                    status="Completed",
                    start_time=datetime(2026, 3, 5, 15, 29),
                ),
            ),
            SimpleNamespace(
                properties=AzureWorkloadJob(
                    entity_friendly_name="hsrdjwp2r10:SYSTEMDB",
                    operation="ConfigureBackup",
                    status="Completed",
                    start_time=datetime(2026, 3, 5, 15, 12),
                ),
            ),
        ]
        result = backup.discover_protected_items()

        db = result["protected_items"][0]
        assert db["last_job_operation"] == "Backup (Full)"
        assert db["last_full_backup_status"] == "Completed"
        assert "2026-03-05" in db["last_full_backup_time"]

    def test_discover_jobs_api_failure_graceful(
        self,
        backup,
        mock_client,
    ):
        """Discover still works when backup_jobs API fails."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.backup_jobs.list.side_effect = RuntimeError("jobs API down")
        result = backup.discover_protected_items()

        assert result["status"] == TestStatus.SUCCESS.value
        db = result["protected_items"][0]
        assert db["last_job_operation"] == "N/A"
        assert db["last_full_backup_status"] == "N/A"

    def test_all_items_have_restore_points(self, backup, mock_client):
        """SUCCESS when every item has at least one RP."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        result = backup.check_restore_points()

        assert result["status"] == TestStatus.SUCCESS.value
        assert len(result["restore_points"]) == 1
        assert result["restore_points"][0]["recovery_point_count"] == 1

    def test_missing_restore_points_give_warning(
        self,
        backup,
        mock_client,
    ):
        """WARNING when an item has no recovery points."""
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = []

        result = backup.check_restore_points()

        assert result["status"] == TestStatus.WARNING.value
        assert "no recovery points" in result["message"]

    def test_original_workload_restore(self, backup, mock_client, mocker):
        """SUCCESS for in-place (original workload) restore."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.restores.begin_trigger.return_value = _make_poller(
            job_id="job-111",
        )
        mocker.patch("src.module_utils.backup_restore.time.sleep")
        mocker.patch.object(
            backup.restore_helper,
            "find_latest_restore_job_id",
            return_value="job-111",
        )

        result = backup.restore_to_database(
            container_name="ctr",
            item_name="item",
        )

        assert result["status"] == TestStatus.SUCCESS.value
        assert result["restore_job"]["job_id"] == "job-111"
        assert result["restore_job"]["recovery_type"] == (RecoveryType.ORIGINAL_LOCATION)

    def test_alternate_workload_restore(self, backup, mock_client, mocker):
        """SUCCESS for cross-VM (alternate workload) restore."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.restores.begin_trigger.return_value = _make_poller(
            job_id="job-222",
        )
        mocker.patch("src.module_utils.backup_restore.time.sleep")
        mocker.patch.object(
            backup.restore_helper,
            "find_latest_restore_job_id",
            return_value="job-222",
        )

        result = backup.restore_to_database(
            container_name="ctr",
            item_name="item",
            target_container_name="target-ctr",
            target_database_name="target-db",
        )

        assert result["status"] == TestStatus.SUCCESS.value
        assert result["restore_job"]["recovery_type"] == (RecoveryType.ALTERNATE_LOCATION)

    def test_explicit_restore_mode_override(self, backup, mock_client, mocker):
        """Alternate restore auto-detected from target_container_name (HSR scenario)."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.restores.begin_trigger.return_value = _make_poller(
            job_id="job-hsr-1",
        )
        mocker.patch("src.module_utils.backup_restore.time.sleep")
        mocker.patch.object(
            backup.restore_helper,
            "find_latest_restore_job_id",
            return_value="job-hsr-1",
        )
        vm_arm = (
            "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"
        )

        result = backup.restore_to_database(
            container_name="VMAppContainer;Compute;rg;vm;hanahsr",
            item_name="item",
            target_container_name="VMAppContainer;Compute;rg;vm;hanahsr",
            target_database_name="item",
            source_resource_id=vm_arm,
        )

        assert result["status"] == TestStatus.SUCCESS.value
        assert result["restore_job"]["recovery_type"] == (RecoveryType.ALTERNATE_LOCATION)
        assert result["restore_job"]["job_id"] == "job-hsr-1"
        call_kwargs = mock_client.restores.begin_trigger.call_args
        req = call_kwargs.kwargs["parameters"]
        assert req.properties.source_resource_id == vm_arm

    def test_explicit_restore_mode_olr(self, backup, mock_client, mocker):
        """OriginalLocation used when no target_container_name."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.restores.begin_trigger.return_value = _make_poller(
            job_id="job-olr-1",
        )
        mocker.patch("src.module_utils.backup_restore.time.sleep")
        mocker.patch.object(
            backup.restore_helper,
            "find_latest_restore_job_id",
            return_value="job-olr-1",
        )

        result = backup.restore_to_database(
            container_name="ctr",
            item_name="item",
        )

        assert result["status"] == TestStatus.SUCCESS.value
        assert result["restore_job"]["recovery_type"] == (RecoveryType.ORIGINAL_LOCATION)

    def test_no_recovery_point_returns_error_no_recovery(
        self,
        backup,
        mock_client,
    ):
        """ERROR when no recovery point exists."""
        mock_client.recovery_points.list.return_value = []

        result = backup.restore_to_database(
            container_name="ctr",
            item_name="item",
        )

        assert result["status"] == TestStatus.ERROR.value
        assert "recovery point" in result["message"].lower()

    def test_sdk_exception_handled_sdk_ex_1(self, backup, mock_client):
        """handle_error called on SDK exception."""
        mock_client.recovery_points.list.side_effect = RuntimeError("restore fail")

        result = backup.restore_to_database(
            container_name="ctr",
            item_name="item",
        )

        assert result["status"] == TestStatus.ERROR.value

    def test_restore_as_files_success(self, backup, mock_client, mocker):
        """SUCCESS when restore-as-files triggers correctly."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.restores.begin_trigger.return_value = _make_poller(
            job_id="job-fs-1",
        )
        mocker.patch("src.module_utils.backup_restore.time.sleep")
        mocker.patch.object(
            backup.restore_helper,
            "find_latest_restore_job_id",
            return_value="job-fs-1",
        )

        result = backup.restore_to_filesystem(
            container_name="ctr",
            item_name="item",
            target_filesystem_path="/backup/restore",
        )

        assert result["status"] == TestStatus.SUCCESS.value
        assert result["restore_job"]["restore_mode"] == "RestoreAsFiles"
        assert result["restore_job"]["target_path"] == "/backup/restore"

    def test_cross_vm_filesystem_restore(self, backup, mock_client, mocker):
        """SUCCESS with target VM parameters set."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mock_client.restores.begin_trigger.return_value = _make_poller(
            job_id="job-fs-2",
        )
        mocker.patch("src.module_utils.backup_restore.time.sleep")
        mocker.patch.object(
            backup.restore_helper,
            "find_latest_restore_job_id",
            return_value="job-fs-2",
        )

        result = backup.restore_to_filesystem(
            container_name="ctr",
            item_name="item",
            target_filesystem_path="/backup/restore",
            target_vm_name="targetvm",
            target_vm_resource_group="targetrg",
        )

        assert result["status"] == TestStatus.SUCCESS.value

    def test_no_recovery_point_returns_error(
        self,
        backup,
        mock_client,
    ):
        """ERROR when no recovery point exists."""
        mock_client.recovery_points.list.return_value = []

        result = backup.restore_to_filesystem(
            container_name="ctr",
            item_name="item",
            target_filesystem_path="/backup/restore",
        )

        assert result["status"] == TestStatus.ERROR.value

    def test_sdk_exception_handled_sdk_ex(self, backup, mock_client):
        """handle_error called on SDK exception."""
        mock_client.recovery_points.list.side_effect = RuntimeError("fs fail")

        result = backup.restore_to_filesystem(
            container_name="ctr",
            item_name="item",
            target_filesystem_path="/tmp",
        )

        assert result["status"] == TestStatus.ERROR.value

    def test_completed_job(self, backup, mock_client):
        """SUCCESS when job completes normally."""
        mock_client.job_details.get.return_value = _make_job("Completed")

        result = backup.check_restore_job(restore_job_id="j-1")

        assert result["status"] == TestStatus.SUCCESS.value
        assert result["restore_job"]["job_id"] == "j-1"
        assert "successfully" in result["message"]

    def test_completed_with_warnings(self, backup, mock_client):
        """WARNING when job status is ``CompletedWithWarnings``."""
        mock_client.job_details.get.return_value = _make_job(
            "CompletedWithWarnings",
        )

        result = backup.check_restore_job(restore_job_id="j-2")

        assert result["status"] == TestStatus.WARNING.value
        assert "warnings" in result["message"]

    def test_failed_job(self, backup, mock_client):
        """ERROR when job status is ``Failed``."""
        mock_client.job_details.get.return_value = _make_job("Failed")

        result = backup.check_restore_job(restore_job_id="j-3")

        assert result["status"] == TestStatus.ERROR.value
        assert "Failed" in result["message"]

    def test_cancelled_job(self, backup, mock_client):
        """ERROR when job status is ``Cancelled``."""
        mock_client.job_details.get.return_value = _make_job("Cancelled")

        result = backup.check_restore_job(restore_job_id="j-4")

        assert result["status"] == TestStatus.ERROR.value

    def test_timeout(self, mock_client, mocker):
        """ERROR when polling exceeds ``poll_timeout``."""
        mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        instance = AzureBackupHana(
            vault_resource_id=(
                "/subscriptions/sub"
                "/resourceGroups/rg"
                "/providers/Microsoft.RecoveryServices"
                "/vaults/v"
            ),
            subscription_id="sub",
            poll_interval=1,
            poll_timeout=1,
        )
        instance._client = mock_client
        mock_client.job_details.get.return_value = _make_job("InProgress")
        mocker.patch("src.module_utils.backup_restore.time.sleep")

        result = instance.check_restore_job(restore_job_id="j-5")

        assert result["status"] == TestStatus.ERROR.value
        assert "timed out" in result["message"]

    def test_sdk_exception_handled(self, backup, mock_client):
        """handle_error called on SDK exception."""
        mock_client.job_details.get.side_effect = RuntimeError("poll fail")

        result = backup.check_restore_job(restore_job_id="j-6")

        assert result["status"] == TestStatus.ERROR.value


class TestSetJobResultStatus:
    """Tests for ``_set_job_result_status`` helper."""

    @pytest.mark.parametrize(
        "status, expected_test_status",
        [
            ("Completed", TestStatus.SUCCESS.value),
            ("CompletedWithWarnings", TestStatus.WARNING.value),
            ("Failed", TestStatus.ERROR.value),
        ],
    )
    def test_status_mapping(
        self,
        backup,
        status,
        expected_test_status,
    ):
        """Correct ``TestStatus`` set for each terminal status."""
        backup._set_job_result_status("j-1", status, 10)
        assert backup.result["status"] == expected_test_status

    def test_timeout_mapping(self, backup):
        """ERROR with timeout message when elapsed >= poll_timeout."""
        backup._set_job_result_status(
            "j-1",
            "InProgress",
            backup.poll_timeout,
        )
        assert backup.result["status"] == TestStatus.ERROR.value
        assert "timed out" in backup.result["message"]

    def test_returns_first_rp_id(self, backup, mock_client):
        """First recovery point ID returned when list is non-empty."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(rp_id="/rp/first"),
            _make_recovery_point(rp_id="/rp/second"),
        ]
        rp_id = backup._resolve_recovery_point("ctr", "item")
        assert rp_id == "/rp/first"

    def test_returns_empty_when_no_rps(self, backup, mock_client):
        """Empty string returned when no recovery points exist."""
        mock_client.recovery_points.list.return_value = []
        rp_id = backup._resolve_recovery_point("ctr", "item")
        assert rp_id == ""

    def test_logs_pit_when_provided(self, backup, mock_client):
        """PIT timestamp is logged when provided."""
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(rp_id="/rp/first"),
        ]
        backup._resolve_recovery_point(
            "ctr",
            "item",
            "2026-03-01T00:00:00",
        )
        assert any("point-in-time" in log.lower() for log in backup.result["logs"])

    def test_original_restore_has_no_target_info(self, backup):
        """``target_info`` is ``None`` for original restore."""
        req = BackupRestoreHelper.build_workload_restore(
            rp_id="/rp/1",
            recovery_type=RecoveryType.ORIGINAL_LOCATION,
        )
        props = cast(AzureWorkloadSAPHanaRestoreRequest, req.properties)
        assert props.target_info is None
        assert props.recovery_type == "OriginalLocation"
        assert props.recovery_mode == "WorkloadRecovery"

    def test_alternate_restore_has_target_info(self, backup):
        """``target_info`` populated for alternate restore."""
        req = BackupRestoreHelper.build_workload_restore(
            rp_id="/rp/1",
            recovery_type=RecoveryType.ALTERNATE_LOCATION,
            target_container_name="ctr",
            target_database_name="db",
        )
        props = cast(AzureWorkloadSAPHanaRestoreRequest, req.properties)
        assert props.target_info is not None
        assert props.target_info.container_id == "ctr"
        assert props.target_info.database_name == "db"
        assert props.recovery_type == "AlternateLocation"
        assert props.recovery_mode == "WorkloadRecovery"

    def test_sdk_recovery_type_passthrough(self, backup):
        """Direct SDK values are accepted without mapping."""
        req = BackupRestoreHelper.build_workload_restore(
            rp_id="/rp/1",
            recovery_type=RecoveryType.ALTERNATE_LOCATION,
            target_container_name="ctr",
            target_database_name="db",
        )
        props = cast(AzureWorkloadSAPHanaRestoreRequest, req.properties)
        assert props.recovery_type == "AlternateLocation"
        assert props.target_info is not None

    def test_discover_dispatches_correctly(self, monkeypatch, mocker):
        """``run_module`` dispatches discover_protected_items."""
        result_kwargs = {}

        class FakeModule:
            def __init__(self, *args, **kwargs):
                self.params = {
                    "operation": "discover_protected_items",
                    "subscription_id": "sub",
                    "msi_client_id": "",
                    "vault_resource_id": (
                        "/subscriptions/sub"
                        "/resourceGroups/rg"
                        "/providers/Microsoft.RecoveryServices"
                        "/vaults/v"
                    ),
                    "database_sid": "",
                    "container_name": "",
                    "item_name": "",
                    "restore_point_time": "",
                    "target_container_name": "",
                    "target_database_name": "",
                    "target_filesystem_path": "",
                    "target_vm_name": "",
                    "target_vm_resource_group": "",
                    "restore_job_id": "",
                    "restore_mode": "",
                    "source_resource_id": "",
                    "poll_interval_seconds": 0,
                    "poll_timeout_seconds": 0,
                }

            def exit_json(self, **kwargs):
                nonlocal result_kwargs
                result_kwargs = kwargs

            def fail_json(self, **kwargs):
                nonlocal result_kwargs
                result_kwargs = kwargs

        monkeypatch.setattr(
            "src.modules.azure_backup_hana.AnsibleModule",
            FakeModule,
        )

        mock_client = mocker.MagicMock()
        mock_client.backup_protected_items.list.return_value = [
            _make_protected_item(),
        ]
        mock_client.recovery_points.list.return_value = [
            _make_recovery_point(),
        ]
        mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        mocker.patch(
            "src.modules.azure_backup_hana.RecoveryServicesBackupClient",
            return_value=mock_client,
        )

        run_module()

        assert result_kwargs.get("status") == TestStatus.SUCCESS.value

    def test_error_result_calls_fail_json(self, monkeypatch, mocker):
        """``fail_json`` called when operation returns ERROR status."""
        fail_kwargs = {}

        class FakeModule:
            def __init__(self, *args, **kwargs):
                self.params = {
                    "operation": "discover_protected_items",
                    "subscription_id": "sub",
                    "msi_client_id": "",
                    "vault_resource_id": (
                        "/subscriptions/sub"
                        "/resourceGroups/rg"
                        "/providers/Microsoft.RecoveryServices"
                        "/vaults/v"
                    ),
                    "database_sid": "",
                    "container_name": "",
                    "item_name": "",
                    "restore_point_time": "",
                    "target_container_name": "",
                    "target_database_name": "",
                    "target_filesystem_path": "",
                    "target_vm_name": "",
                    "target_vm_resource_group": "",
                    "restore_job_id": "",
                    "restore_mode": "",
                    "source_resource_id": "",
                    "poll_interval_seconds": 0,
                    "poll_timeout_seconds": 0,
                }

            def exit_json(self, **kwargs):
                pass

            def fail_json(self, **kwargs):
                nonlocal fail_kwargs
                fail_kwargs = kwargs

        monkeypatch.setattr(
            "src.modules.azure_backup_hana.AnsibleModule",
            FakeModule,
        )

        mock_client = mocker.MagicMock()
        mock_client.backup_protected_items.list.side_effect = RuntimeError("boom")
        mocker.patch(
            "src.modules.azure_backup_hana.ManagedIdentityCredential",
        )
        mocker.patch(
            "src.modules.azure_backup_hana.RecoveryServicesBackupClient",
            return_value=mock_client,
        )

        run_module()

        assert fail_kwargs.get("status") == TestStatus.ERROR.value
