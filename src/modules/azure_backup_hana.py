# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Ansible module to validate and test Azure Backup for SAP HANA databases.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from ansible.module_utils.basic import AnsibleModule
from azure.identity import ManagedIdentityCredential
from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
from azure.mgmt.recoveryservicesbackup.models import (
    ProtectedItemResource,
    AzureVmWorkloadSAPHanaDatabaseProtectedItem,
)

try:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import TestStatus, BackupOperation
    from src.module_utils.backup_discovery import BackupDiscovery
    from src.module_utils.backup_restore import BackupRestoreHelper
except ImportError:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import TestStatus, BackupOperation
    from ansible.module_utils.backup_discovery import BackupDiscovery
    from ansible.module_utils.backup_restore import BackupRestoreHelper


DOCUMENTATION = r"""
---
module: azure_backup_hana
short_description: Validates and tests Azure Backup for SAP HANA databases
description:
    - Discovers protected SAP HANA databases in a Recovery Services vault
    - Verifies backup configuration status and last restore points
    - Triggers restore operations (to database or filesystem)
    - Monitors restore job status until completion or timeout
options:
    operation:
        description:
            - The backup operation to perform.
        type: str
        required: true
        choices:
            - discover_protected_items
            - check_restore_points
            - restore_to_database
            - restore_to_filesystem
            - check_restore_job
    vault_resource_id:
        description:
            - Full ARM resource ID of the Recovery Services vault.
        type: str
        required: true
    database_sid:
        description:
            - SAP HANA database SID (e.g. H05).
        type: str
        required: false
    container_name:
        description:
            - Backup container name
              (e.g. VMAppContainer;Compute;rg;vmname).
        type: str
        required: false
    item_name:
        description:
            - Backup item name
              (e.g. saphanadatabase;h05;systemdb).
        type: str
        required: false
    restore_point_time:
        description:
            - Point-in-time for restore in UTC (ISO 8601).
              If omitted, the latest recovery point is used.
        type: str
        required: false
    target_container_name:
        description:
            - Target container for cross-VM restore.
        type: str
        required: false
    target_database_name:
        description:
            - Target database name for cross-VM restore
              (e.g. saphanadatabase;h05;systemdb).
        type: str
        required: false
    target_filesystem_path:
        description:
            - Filesystem path for restore-as-files
              (e.g. /sapinstall/hana_backup/S01/).
        type: str
        required: false
    target_vm_name:
        description:
            - Target VM name for restore-as-files
              (only for HA/cross-VM).
        type: str
        required: false
    target_vm_resource_group:
        description:
            - Target VM resource group for restore-as-files.
        type: str
        required: false
    restore_job_id:
        description:
            - Job ID of a previously triggered restore
              (for check_restore_job).
        type: str
        required: false
    poll_interval_seconds:
        description:
            - Polling interval in seconds when waiting
              for restore job.
        type: int
        required: false
        default: 30
    poll_timeout_seconds:
        description:
            - Maximum seconds to wait for restore job
              completion.
        type: int
        required: false
        default: 7200
    parameter_definitions:
        description:
            - List of parameter definition dicts loaded from
              the role vars file (backup-parameters.yml).
        type: list
        elements: dict
        required: false
        default: []
    subscription_id:
        description:
            - Azure subscription ID that contains the vault.
        type: str
        required: true
    msi_client_id:
        description:
            - Client ID of a user-assigned managed identity.
              Omit or leave empty to use the system-assigned MI.
        type: str
        required: false
        default: ""
author:
    - Microsoft Corporation
notes:
    - Uses the azure-mgmt-recoveryservicesbackup Python SDK.
    - Requires the managed identity to have Backup Operator role
      on the Recovery Services vault.
requirements:
    - python >= 3.10
    - azure-identity
    - azure-mgmt-recoveryservicesbackup
"""

EXAMPLES = r"""
- name: Discover protected HANA databases
  azure_backup_hana:
    operation: discover_protected_items
    vault_resource_id: "/subscriptions/xxxx/resourceGroups/my-rg/providers/Microsoft.RecoveryServices/vaults/my-vault"
    subscription_id: "{{ subscription_id }}"
    msi_client_id: "{{ msi_client_id | default('') }}"

- name: Check restore points for all items
  azure_backup_hana:
    operation: check_restore_points
    vault_resource_id: "{{ backup_vault_resource_id }}"
    subscription_id: "{{ subscription_id }}"
"""

RETURN = r"""
status:
    description: Overall status of the operation
    returned: always
    type: str
    sample: "PASSED"
message:
    description: Human-readable summary
    returned: always
    type: str
    sample: "All 3 protected items are healthy."
protected_items:
    description: List of discovered protected backup items
    returned: when operation == discover_protected_items
    type: list
    sample: [{"name": "s05", "hana_system": "sles16hdb05/H05",
              "server_type": "Standalone Instance",
              "backup_status": "Healthy"}]
restore_points:
    description: Recovery point details per item
    returned: when operation == check_restore_points
    type: list
restore_job:
    description: Restore job details
    returned: when operation in (restore_to_database,
              restore_to_filesystem, check_restore_job)
    type: dict
"""


class AzureBackupHana(SapAutomationQA):
    """
    Manages Azure Backup operations for SAP HANA databases.
    """

    _DEFAULT_POLL_INTERVAL = 30
    _DEFAULT_POLL_TIMEOUT = 7200

    def __init__(
        self,
        vault_resource_id: str,
        subscription_id: str,
        msi_client_id: str = "",
        database_sid: str = "",
        source_vm_name: str = "",
        poll_interval: int = _DEFAULT_POLL_INTERVAL,
        poll_timeout: int = _DEFAULT_POLL_TIMEOUT,
        parameter_definitions: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        super().__init__()
        vault_name, vault_rg = self.parse_vault_resource_id(
            vault_resource_id,
        )
        self.vault_resource_id = vault_resource_id
        self.vault_name = vault_name
        self.vault_resource_group = vault_rg
        self.subscription_id = subscription_id
        self.database_sid = database_sid
        self.source_vm_name = source_vm_name
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.parameter_definitions: List[Dict[str, str]] = (
            parameter_definitions if parameter_definitions else []
        )
        self._client: Optional[RecoveryServicesBackupClient] = None
        self._msi_client_id = msi_client_id
        self._discovery_obj: Optional[BackupDiscovery] = None
        self._restore_obj: Optional[BackupRestoreHelper] = None
        self.result.update(
            {
                "protected_items": [],
                "restore_points": [],
                "restore_job": {},
                "start": datetime.now().isoformat(),
                "end": None,
            }
        )

    @property
    def client(self) -> RecoveryServicesBackupClient:
        """Lazily create and cache the Recovery Services Backup client.

        :returns: Authenticated SDK client.
        :raises RuntimeError: When authentication fails.
        """
        if self._client is not None:
            return self._client

        try:
            credential = (
                ManagedIdentityCredential(
                    client_id=self._msi_client_id,
                )
                if self._msi_client_id
                else ManagedIdentityCredential()
            )
            self._client = RecoveryServicesBackupClient(
                credential=credential,
                subscription_id=self.subscription_id,
            )
            self.log(
                logging.INFO,
                "Authenticated to Azure Recovery Services " f"(sub={self.subscription_id}).",
            )
            return self._client
        except Exception as exc:
            msg = "Failed to authenticate to Azure Recovery " f"Services Backup. {exc}"
            self.log(logging.ERROR, msg)
            raise RuntimeError(msg) from exc

    @property
    def discovery(self) -> BackupDiscovery:
        """Lazily create and cache the discovery helper.

        :returns: ``BackupDiscovery`` instance wired to the current client and vault configuration.
        """
        if self._discovery_obj is None:
            self._discovery_obj = BackupDiscovery(
                client=self.client,
                vault_name=self.vault_name,
                vault_resource_group=(self.vault_resource_group),
                source_vm_name=self.source_vm_name,
                parameter_definitions=(self.parameter_definitions),
                log_fn=self.log,
            )
        return self._discovery_obj

    @property
    def restore_helper(self) -> BackupRestoreHelper:
        """Lazily create and cache the restore helper.

        :returns: ``BackupRestoreHelper`` instance wired to the current client and vault configuration.
        """
        if self._restore_obj is None:
            self._restore_obj = BackupRestoreHelper(
                client=self.client,
                vault_name=self.vault_name,
                vault_resource_group=(self.vault_resource_group),
                subscription_id=self.subscription_id,
                poll_interval=self.poll_interval,
                poll_timeout=self.poll_timeout,
                log_fn=self.log,
            )
        return self._restore_obj

    @staticmethod
    def parse_vault_resource_id(
        resource_id: str,
    ) -> tuple[str, str]:
        """Extract vault name and resource group from an ARM ID.

        :param resource_id: Full ARM resource ID of the vault.
        :returns: ``(vault_name, resource_group)`` tuple.
        :raises ValueError: When the ID cannot be parsed.
        """
        parts = resource_id.strip("/").split("/")
        lookup = {parts[i].lower(): parts[i + 1] for i in range(0, len(parts) - 1, 2)}
        rg = lookup.get("resourcegroups", "")
        name = lookup.get("vaults", "")
        if not rg or not name:
            raise ValueError(
                "Cannot parse vault resource ID: "
                f"{resource_id!r}. Expected format: "
                "/subscriptions/{sub}/resourceGroups/"
                "{rg}/providers/Microsoft.Recovery"
                "Services/vaults/{name}"
            )
        return name, rg

    @staticmethod
    def _get_props(
        item: ProtectedItemResource,
    ) -> AzureVmWorkloadSAPHanaDatabaseProtectedItem:
        """Return typed HANA properties from a protected item.

        :param item: SDK ``ProtectedItemResource`` instance.
        :returns: Narrowed HANA protected item properties.
        """
        return item.properties

    def discover_protected_items(self) -> Dict[str, Any]:
        """Discover and validate all SAP HANA protected databases

        :returns: Result dict
        """
        try:
            self.result.update(self.discovery.discover())
        except Exception as exc:
            self.handle_error(exc)
        finally:
            self.result["end"] = datetime.now().isoformat()
        return self.result

    def check_restore_points(self) -> Dict[str, Any]:
        """Fetch and report the latest restore points forall items.

        :returns: Result dict with ``restore_points`` list.
        """
        try:
            self.result.update(
                self.discovery.check_restore_points(),
            )
        except Exception as exc:
            self.handle_error(exc)
        finally:
            self.result["end"] = datetime.now().isoformat()
        return self.result

    def restore_to_database(
        self,
        container_name: str,
        item_name: str,
        restore_point_time: str = "",
        target_container_name: str = "",
        target_database_name: str = "",
        source_resource_id: str = "",
    ) -> Dict[str, Any]:
        """Trigger a restore-to-database via Azure Backup SDK.

        :param container_name: Source backup container.
        :param item_name: Source backup item name.
        :param restore_point_time: Optional PIT in UTC ISO-8601.
        :param target_container_name: Target container (cross-VM).
        :param target_database_name: Target DB (cross-VM).
        :param source_resource_id: ARM resource ID of the
            source VM.  For HSR this must be the primary node\'s
            VM ARM ID.
        :returns: Result dict with ``restore_job`` details.
        """
        try:
            self.result.update(
                self.restore_helper.restore_to_database(
                    container_name=container_name,
                    item_name=item_name,
                    restore_point_time=restore_point_time,
                    target_container_name=(target_container_name),
                    target_database_name=(target_database_name),
                    source_resource_id=source_resource_id,
                )
            )
        except Exception as exc:
            self.handle_error(exc)
        finally:
            self.result["end"] = datetime.now().isoformat()
        return self.result

    def restore_to_filesystem(
        self,
        container_name: str,
        item_name: str,
        target_filesystem_path: str,
        target_vm_name: str = "",
        target_vm_resource_group: str = "",
        restore_point_time: str = "",
        source_resource_id: str = "",
    ) -> Dict[str, Any]:
        """Trigger a restore-as-files to a filesystem path.

        :param container_name: Source backup container.
        :param item_name: Source backup item name.
        :param target_filesystem_path: Destination path.
        :param target_vm_name: Target VM for the files.
        :param target_vm_resource_group: Target VM resource group.
        :param restore_point_time: Optional PIT in UTC ISO-8601.
        :param source_resource_id: ARM resource ID of the source VM.
        :returns: Result dict with ``restore_job`` details.
        """
        try:
            self.result.update(
                self.restore_helper.restore_to_filesystem(
                    container_name=container_name,
                    item_name=item_name,
                    target_filesystem_path=(target_filesystem_path),
                    target_vm_name=target_vm_name,
                    target_vm_resource_group=(target_vm_resource_group),
                    restore_point_time=restore_point_time,
                    source_resource_id=source_resource_id,
                )
            )
        except Exception as exc:
            self.handle_error(exc)
        finally:
            self.result["end"] = datetime.now().isoformat()
        return self.result

    def check_restore_job(
        self,
        restore_job_id: str,
    ) -> Dict[str, Any]:
        """Poll a restore job until it completes or times out.

        :param restore_job_id: Azure Backup job ID.
        :returns: Result dict with final job status.
        """
        try:
            self.result.update(
                self.restore_helper.check_restore_job(
                    restore_job_id,
                ),
            )
        except Exception as exc:
            self.handle_error(exc)
        finally:
            self.result["end"] = datetime.now().isoformat()
        return self.result

    def _set_job_result_status(
        self,
        job_id: str,
        status: str,
        elapsed: int,
    ) -> None:
        """Map a terminal job status to the appropriate result.

        :param job_id: Azure Backup job ID.
        :param status: Final job status string.
        :param elapsed: Seconds elapsed during polling.
        """
        test_status, message = BackupRestoreHelper.map_job_result_status(
            job_id,
            status,
            elapsed,
            self.poll_timeout,
        )
        self.result["status"] = test_status
        self.result["message"] = message

    def _resolve_recovery_point(
        self,
        container_name: str,
        item_name: str,
        restore_point_time: str = "",
    ) -> str:
        """Return the recovery-point ID to use for a restore.

        :param container_name: Backup container name.
        :param item_name: Backup item name.
        :param restore_point_time: Optional PIT timestamp.
        :returns: Recovery point resource ID (empty on
            failure).
        """
        return self.restore_helper.resolve_recovery_point(
            container_name,
            item_name,
            restore_point_time,
        )


def run_module() -> None:
    """Ansible module entry point."""

    module = AnsibleModule(
        argument_spec=dict(
            operation=dict(
                type="str",
                required=True,
                choices=[op.value for op in BackupOperation],
            ),
            subscription_id=dict(type="str", required=True),
            msi_client_id=dict(type="str", required=False, default=""),
            vault_resource_id=dict(type="str", required=True),
            database_sid=dict(type="str", required=False, default=""),
            container_name=dict(type="str", required=False, default=""),
            item_name=dict(type="str", required=False, default=""),
            restore_point_time=dict(type="str", required=False, default=""),
            target_container_name=dict(type="str", required=False, default=""),
            target_database_name=dict(type="str", required=False, default=""),
            target_filesystem_path=dict(type="str", required=False, default=""),
            target_vm_name=dict(type="str", required=False, default=""),
            target_vm_resource_group=dict(type="str", required=False, default=""),
            restore_mode=dict(type="str", required=False, default=""),
            source_resource_id=dict(type="str", required=False, default=""),
            source_vm_name=dict(type="str", required=False, default=""),
            restore_job_id=dict(type="str", required=False, default=""),
            poll_interval_seconds=dict(type="int", required=False, default=30),
            poll_timeout_seconds=dict(type="int", required=False, default=7200),
            parameter_definitions=dict(
                type="list",
                elements="dict",
                required=False,
                default=[],
            ),
        ),
        supports_check_mode=False,
    )
    params = module.params

    operation = BackupOperation(params["operation"])
    backup = AzureBackupHana(
        vault_resource_id=params["vault_resource_id"],
        subscription_id=params["subscription_id"],
        msi_client_id=params.get("msi_client_id", ""),
        database_sid=params.get("database_sid", ""),
        source_vm_name=params.get("source_vm_name", ""),
        poll_interval=params.get(
            "poll_interval_seconds",
            AzureBackupHana._DEFAULT_POLL_INTERVAL,
        ),
        poll_timeout=params.get(
            "poll_timeout_seconds",
            AzureBackupHana._DEFAULT_POLL_TIMEOUT,
        ),
        parameter_definitions=params.get(
            "parameter_definitions",
            [],
        ),
    )

    dispatch: Dict[BackupOperation, Callable[[], Dict[str, Any]]] = {
        BackupOperation.DISCOVER_PROTECTED_ITEMS: (backup.discover_protected_items),
        BackupOperation.CHECK_RESTORE_POINTS: (backup.check_restore_points),
        BackupOperation.RESTORE_TO_DATABASE: lambda: (
            backup.restore_to_database(
                container_name=params["container_name"],
                item_name=params["item_name"],
                restore_point_time=params.get(
                    "restore_point_time",
                    "",
                ),
                target_container_name=params.get(
                    "target_container_name",
                    "",
                ),
                target_database_name=params.get(
                    "target_database_name",
                    "",
                ),
                source_resource_id=params.get(
                    "source_resource_id",
                    "",
                ),
            )
        ),
        BackupOperation.RESTORE_TO_FILESYSTEM: lambda: (
            backup.restore_to_filesystem(
                container_name=params["container_name"],
                item_name=params["item_name"],
                target_filesystem_path=params["target_filesystem_path"],
                target_vm_name=params.get(
                    "target_vm_name",
                    "",
                ),
                target_vm_resource_group=params.get(
                    "target_vm_resource_group",
                    "",
                ),
                restore_point_time=params.get(
                    "restore_point_time",
                    "",
                ),
                source_resource_id=params.get(
                    "source_resource_id",
                    "",
                ),
            )
        ),
        BackupOperation.CHECK_RESTORE_JOB: lambda: (
            backup.check_restore_job(
                restore_job_id=params["restore_job_id"],
            )
        ),
    }

    handler = dispatch.get(operation)
    if handler is None:
        module.fail_json(
            msg=f"Unsupported operation: {operation.value}",
        )
        return

    result: Dict[str, Any] = handler()

    if result.get("status") == TestStatus.ERROR.value:
        module.fail_json(msg=result.get("message", ""), **result)
    else:
        module.exit_json(**result)


def main() -> None:
    """Module main entry point."""
    run_module()


if __name__ == "__main__":
    main()
