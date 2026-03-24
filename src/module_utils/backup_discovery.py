# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Discovery and validation helpers for Azure Backup HANA.
"""

import re
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, cast
from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
from azure.mgmt.recoveryservicesbackup.models import (
    ProtectedItemResource,
    AzureVmWorkloadSAPHanaDatabaseProtectedItem,
    RecoveryPointResource,
    AzureWorkloadSAPHanaRecoveryPoint,
    AzureWorkloadJob,
    BackupManagementType,
    DataSourceType,
    ProtectedItemHealthStatus,
    ProtectionStatus,
)

try:
    from src.module_utils.enums import TestStatus
    from src.module_utils.backup_parameters import BackupParameterBuilder
except ImportError:
    from ansible.module_utils.enums import TestStatus
    from ansible.module_utils.backup_parameters import BackupParameterBuilder


class BackupDiscovery:
    """Discovery and validation for Azure Backup HANA items.

    :param client: Authenticated Recovery Services Backup client.
    :param vault_name: Name of the Recovery Services vault.
    :param vault_resource_group: Resource group of the vault.
    :param source_vm_name: Azure VM name to scope results to.
    :param parameter_definitions: YAML-loaded parameter defs for HTML report generation.
    :param log_fn: Optional callback ``(level, message)``.
    """

    HANA_BACKUP_FILTER = (
        f"backupManagementType eq '{BackupManagementType.AZURE_WORKLOAD.value}' "
        f"and itemType eq '{DataSourceType.SAP_HANA_DATABASE.value}'"
    )

    def __init__(
        self,
        client: RecoveryServicesBackupClient,
        vault_name: str,
        vault_resource_group: str,
        source_vm_name: str = "",
        parameter_definitions: Optional[List[Dict[str, str]]] = None,
        log_fn: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        self._client = client
        self._vault_name = vault_name
        self._vault_rg = vault_resource_group
        self._source_vm = (source_vm_name or "").lower().strip()
        self._param_defs: List[Dict[str, str]] = (
            parameter_definitions if parameter_definitions else []
        )
        self._log = log_fn or (lambda _lvl, _msg: None)

    def _matches_source_vm(
        self,
        container_name: str,
        server_name: str = "",
    ) -> bool:
        """Check whether a container belongs to the source VM.

        :param container_name: Backup container name.
        :param server_name: HANA server hostname from item properties (used for HSR matching).
        :returns: ``True`` when no filter is set, the container  matches the source VM,
            or -- for HSR -- the server name shares a significant identifier with the VM name.
        """
        if not self._source_vm:
            return True
        lower_container = (container_name or "").lower()
        if self._source_vm in lower_container:
            return True
        if self.is_hsr_container(container_name):
            lower_server = (server_name or "").lower().strip()
            if not lower_server:
                return False

            if min(len(self._source_vm), len(lower_server)) >= 5 and (
                self._source_vm in lower_server or lower_server in self._source_vm
            ):
                return True

            parts = re.split(r"[-_]", self._source_vm)
            for part in parts:
                if len(part) >= 5 and part in lower_server:
                    return True

            server_parts = re.split(r"[-_]", lower_server)
            for part in server_parts:
                if len(part) >= 5 and part in self._source_vm:
                    return True
            return False
        return False

    @staticmethod
    def get_props(
        item: ProtectedItemResource,
    ) -> AzureVmWorkloadSAPHanaDatabaseProtectedItem:
        """Return typed HANA properties from a protected item.

        :param item: SDK ``ProtectedItemResource`` instance.
        :returns: Narrowed HANA protected item properties.
        """
        return cast(AzureVmWorkloadSAPHanaDatabaseProtectedItem, item.properties)

    @staticmethod
    def is_hsr_container(
        container_name: str,
    ) -> bool:
        """Check whether the container is an HSR container.

        :param container_name: Backup container name.
        :returns: ``True`` when the container is HSR-based.
        """
        return "hanahsrcontainer" in (container_name or "").lower()

    @staticmethod
    def evaluate_db_status(
        props: AzureVmWorkloadSAPHanaDatabaseProtectedItem,
        has_restore_point: bool,
        is_hsr: bool,
        last_job: Optional[AzureWorkloadJob] = None,
    ) -> str:
        """Derive a per-database PASSED/WARNING/FAILED status.

        :param props: SDK protected-item properties.
        :param has_restore_point: Whether at least one RP exists.
        :param is_hsr: Whether the container is HSR.
        :param last_job: Most recent backup job, if any.
        :returns: ``PASSED``, ``WARNING``, or ``FAILED``.
        """
        h = (props.protected_item_health_status or "Unknown").lower()
        p = (props.protection_status or "Unknown").lower()

        rejected_protection = (
            ProtectionStatus.NOT_PROTECTED.lower(),
            ProtectionStatus.PROTECTION_FAILED.lower(),
            ProtectionStatus.INVALID.lower(),
        )
        if p in rejected_protection:
            return TestStatus.ERROR.value
        if not has_restore_point:
            return TestStatus.ERROR.value
        if h == ProtectedItemHealthStatus.HEALTHY.lower():
            return TestStatus.SUCCESS.value
        if is_hsr and h == "unknown":
            return TestStatus.SUCCESS.value
        return TestStatus.WARNING.value

    @staticmethod
    def latest_rp_summary(
        rp_list: List[RecoveryPointResource],
    ) -> tuple[str, str]:
        """Extract time and type from the latest RP.

        :param rp_list: List of SDK ``RecoveryPointResource``.
        :returns: ``(rp_time_iso, rp_type)`` tuple.
        """
        if not rp_list or rp_list[0].properties is None:
            return ("N/A", "N/A")
        rp = cast(AzureWorkloadSAPHanaRecoveryPoint, rp_list[0].properties)
        rp_time = (
            rp.recovery_point_time_in_utc.isoformat() if rp.recovery_point_time_in_utc else "N/A"
        )
        return (rp_time, rp.type or "N/A")

    def list_protected_items(
        self,
    ) -> Iterable[ProtectedItemResource]:
        """Iterate over SAP HANA protected items in the vault.

        :returns: Iterable of SDK ``ProtectedItemResource``.
        """
        return self._client.backup_protected_items.list(
            vault_name=self._vault_name,
            resource_group_name=self._vault_rg,
            filter=self.HANA_BACKUP_FILTER,
        )

    def list_recovery_points(
        self,
        container_name: str,
        item_name: str,
    ) -> List[RecoveryPointResource]:
        """Fetch recovery points for a protected item.

        :param container_name: Backup container name.
        :param item_name: Backup item name.
        :returns: List of SDK ``RecoveryPointResource``.
        """
        return list(
            self._client.recovery_points.list(
                vault_name=self._vault_name,
                resource_group_name=self._vault_rg,
                fabric_name="Azure",
                container_name=container_name,
                protected_item_name=item_name,
            )
        )

    def fetch_recent_jobs(
        self,
    ) -> Dict[str, Dict[str, Optional[AzureWorkloadJob]]]:
        """Fetch recent backup jobs and index by container+DB name.

        :returns: Per-DB dict mapping to
            ``{"last_job": ..., "last_full_backup": ...}``
            where values are SDK ``AzureWorkloadJob`` or ``None``.
        """
        job_filter = f"backupManagementType eq '{BackupManagementType.AZURE_WORKLOAD.value}'"
        result: Dict[str, Dict[str, Optional[AzureWorkloadJob]]] = {}
        _empty: Dict[str, Optional[AzureWorkloadJob]] = {
            "last_job": None,
            "last_full_backup": None,
        }
        try:
            jobs = self._client.backup_jobs.list(
                vault_name=self._vault_name,
                resource_group_name=self._vault_rg,
                filter=job_filter,
            )
            for job in jobs:
                props = job.properties
                if not isinstance(props, AzureWorkloadJob):
                    continue
                raw_name = (props.entity_friendly_name or "").lower()
                if not raw_name:
                    continue

                op = (props.operation or "").lower()
                if not (op.startswith("backup") or op.startswith("restore")):
                    continue

                vm_hint = ""
                bracket_idx = raw_name.find("[")
                if bracket_idx > 0:
                    vm_hint = raw_name[bracket_idx + 1 :].rstrip("]  ").strip()
                    raw_name = raw_name[:bracket_idx].rstrip()

                short_name = raw_name
                for sep in (":", ";"):
                    if sep in raw_name:
                        short_name = raw_name.rsplit(sep, 1)[-1]
                        break

                if vm_hint:
                    db_key = f"{vm_hint}::{short_name}"
                else:
                    db_key = f"::{short_name}"

                entry = result.setdefault(
                    db_key,
                    dict(_empty),
                )
                if entry["last_job"] is None:
                    entry["last_job"] = props
                if entry["last_full_backup"] is None and (props.operation or "").lower().startswith(
                    "backup"
                ):
                    entry["last_full_backup"] = props
        except Exception as exc:
            self._log(
                logging.WARNING,
                f"Could not fetch backup jobs: {exc}",
            )
        return result

    @staticmethod
    def has_usable_restore_point(
        rp_list: List[RecoveryPointResource],
    ) -> bool:
        """Check whether at least one RP has a real recovery time.

        :param rp_list: Recovery point resources from the SDK.
        :returns: ``True`` when a real restore point exists.
        """
        for rp_resource in rp_list:
            if rp_resource.properties is None:
                continue
            rp = cast(AzureWorkloadSAPHanaRecoveryPoint, rp_resource.properties)
            if rp.recovery_point_time_in_utc is not None:
                return True
            if getattr(rp, "time_ranges", None):
                return True
        return False

    @staticmethod
    def _match_jobs_for_item(
        job_index: Dict[str, Dict[str, Optional[AzureWorkloadJob]]],
        container_name: str,
        friendly_name: str,
        server_name: str = "",
    ) -> Dict[str, Optional[AzureWorkloadJob]]:
        """Find the best matching job entry for a protected item.

        :param job_index: Index returned by ``fetch_recent_jobs``.
        :param container_name: Backup container name of the item.
        :param friendly_name: DB friendly name (e.g. ``hdb``).
        :param server_name: Server hostname from the protected item.
            Used for HSR matching where the job references the node
            hostname rather than the HSR container name.
        :returns: Dict with ``last_job`` and ``last_full_backup``.
        """
        db_name = friendly_name.lower()
        empty: Dict[str, Optional[AzureWorkloadJob]] = {
            "last_job": None,
            "last_full_backup": None,
        }
        is_hsr = BackupDiscovery.is_hsr_container(container_name)
        server_lower = (server_name or "").lower().strip()
        for key, entry in job_index.items():
            sep_idx = key.find("::")
            if sep_idx < 0:
                continue
            vm_hint = key[:sep_idx]
            key_db = key[sep_idx + 2 :]
            if key_db != db_name:
                continue
            if vm_hint and vm_hint in container_name.lower():
                return entry
            if is_hsr and server_lower and vm_hint == server_lower:
                return entry
        return job_index.get(f"::{db_name}", empty)

    def discover(self) -> Dict[str, Any]:
        """Discover and validate protected HANA databases.

        :returns: Dict with ``protected_items``
        :raises Exception: Propagated from SDK calls.
        """
        vm_label = f" for VM '{self._source_vm}'" if self._source_vm else ""
        self._log(
            logging.INFO,
            f"Discovering protected HANA items in vault " f"'{self._vault_name}'{vm_label}",
        )
        protected: List[Dict[str, Any]] = []
        restore_pts: List[Dict[str, Any]] = []
        status_counts: Dict[str, int] = {
            TestStatus.SUCCESS.value: 0,
            TestStatus.WARNING.value: 0,
            TestStatus.ERROR.value: 0,
        }
        job_index = self.fetch_recent_jobs()
        parameters: List[Dict[str, Any]] = []
        skipped = 0

        for item in self.list_protected_items():
            props = self.get_props(item)
            container = props.container_name or ""
            item_name = item.name or ""

            if not self._matches_source_vm(
                container,
                server_name=props.server_name or "",
            ):
                skipped += 1
                continue

            is_hsr = self.is_hsr_container(container_name=container)

            rp_list = self.list_recovery_points(
                container_name=container,
                item_name=item_name,
            )
            rp_time, rp_type = self.latest_rp_summary(
                rp_list,
            )
            has_rp = self.has_usable_restore_point(rp_list)
            db_jobs = self._match_jobs_for_item(
                job_index,
                container,
                props.friendly_name or "",
                server_name=props.server_name or "",
            )
            last_job: Optional[AzureWorkloadJob] = db_jobs.get("last_job")
            last_full: Optional[AzureWorkloadJob] = db_jobs.get("last_full_backup")

            db_status = self.evaluate_db_status(
                props=props,
                has_restore_point=has_rp,
                is_hsr=is_hsr,
                last_job=last_job,
            )
            status_counts[db_status] = status_counts.get(db_status, 0) + 1

            server_name = props.server_name or ""
            parent_name = props.parent_name or ""
            protected.append(
                {
                    "name": props.friendly_name or "",
                    "hana_system": (
                        f"{server_name}\\{parent_name}" if parent_name else server_name
                    ),
                    "server_type": ("HSR" if is_hsr else "Standalone Instance"),
                    "backup_status": db_status,
                    "health_status": (props.protected_item_health_status or "Unknown"),
                    "protection_status": (props.protection_status or "Unknown"),
                    "last_backup_time": (
                        last_full.start_time.isoformat()
                        if last_full and last_full.start_time
                        else ""
                    ),
                    "latest_restore_point": rp_time,
                    "backup_type": rp_type,
                    "policy_name": (
                        props.policy_name or (props.policy_id or "").rsplit("/", 1)[-1] or ""
                    ),
                    "container_name": container,
                    "item_name": item_name,
                    "last_job_operation": (last_job.operation or "N/A" if last_job else "N/A"),
                    "last_job_status": (last_job.status or "N/A" if last_job else "N/A"),
                    "last_job_time": (
                        last_job.start_time.isoformat()
                        if last_job and last_job.start_time
                        else "N/A"
                    ),
                    "last_full_backup_status": (last_full.status or "N/A" if last_full else "N/A"),
                    "last_full_backup_time": (
                        last_full.start_time.isoformat()
                        if last_full and last_full.start_time
                        else "N/A"
                    ),
                }
            )

            restore_pts.append(
                {
                    "item_name": (props.friendly_name or ""),
                    "container_name": container,
                    "backup_item_name": item_name,
                    "recovery_point_count": len(rp_list),
                    "latest_recovery_point_time": rp_time,
                    "latest_recovery_point_type": rp_type,
                }
            )

            parameters.extend(
                BackupParameterBuilder.build_db_parameters(
                    self._param_defs,
                    props,
                    rp_time,
                    rp_type,
                    is_hsr,
                    last_job,
                    last_full,
                    db_status,
                )
            )

        if skipped:
            self._log(
                logging.INFO,
                f"Skipped {skipped} item(s) not matching " f"source VM '{self._source_vm}'.",
            )

        if status_counts.get(TestStatus.ERROR.value, 0):
            status = TestStatus.ERROR.value
        elif status_counts.get(TestStatus.WARNING.value, 0):
            status = TestStatus.WARNING.value
        elif protected:
            status = TestStatus.SUCCESS.value
        else:
            status = TestStatus.ERROR.value

        total = len(protected)
        passed = status_counts.get(TestStatus.SUCCESS.value, 0)
        warned = status_counts.get(TestStatus.WARNING.value, 0)
        failed = status_counts.get(TestStatus.ERROR.value, 0)

        return {
            "protected_items": protected,
            "restore_points": restore_pts,
            "details": {"parameters": parameters},
            "status": status,
            "message": (
                f"{total} database(s) discovered: "
                f"{passed} PASSED, {warned} WARNING, "
                f"{failed} FAILED."
            ),
        }

    def check_restore_points(self) -> Dict[str, Any]:
        """Fetch and report latest restore points.

        :returns: Dict with ``restore_points``, ``status``, and ``message`` keys.
        :raises Exception: Propagated from SDK calls.
        """
        self._log(
            logging.INFO,
            "Checking restore points for protected items.",
        )
        all_points: List[Dict[str, Any]] = []
        items_without_rp = 0
        item_count = 0

        for item in self.list_protected_items():
            props = self.get_props(item)
            container = props.container_name or ""
            if not self._matches_source_vm(
                container,
                server_name=props.server_name or "",
            ):
                continue
            item_count += 1
            item_name = item.name or ""

            rp_list = self.list_recovery_points(
                container,
                item_name,
            )
            rp_time, rp_type = self.latest_rp_summary(
                rp_list,
            )
            if not rp_list:
                items_without_rp += 1

            all_points.append(
                {
                    "item_name": (props.friendly_name or ""),
                    "container_name": container,
                    "backup_item_name": item_name,
                    "recovery_point_count": len(rp_list),
                    "latest_recovery_point_time": rp_time,
                    "latest_recovery_point_type": rp_type,
                }
            )

        if items_without_rp:
            status = TestStatus.WARNING.value
            message = f"{items_without_rp} of {item_count} item(s) have no recovery points."
        else:
            status = TestStatus.SUCCESS.value
            message = f"All {item_count} item(s) have recovery points."

        return {
            "restore_points": all_points,
            "status": status,
            "message": message,
        }
