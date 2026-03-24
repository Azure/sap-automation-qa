# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Restore operation helpers for Azure Backup HANA.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, cast, Dict, List, Optional
from azure.core.exceptions import HttpResponseError
from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
from azure.mgmt.recoveryservicesbackup.models import (
    RecoveryPointResource,
    RestoreRequestResource,
    AzureWorkloadSAPHanaRestoreRequest,
    TargetRestoreInfo,
    RecoveryType,
    RecoveryMode,
    OverwriteOptions,
    BackupManagementType,
    AzureWorkloadJob,
)

try:
    from src.module_utils.enums import TestStatus
    from src.module_utils.commands import AZURE_ERROR_HINTS
except ImportError:
    from ansible.module_utils.enums import TestStatus
    from ansible.module_utils.commands import AZURE_ERROR_HINTS


class BackupRestoreHelper:
    """Restore operations for Azure Backup HANA.

    :param client: Authenticated Recovery Services Backup client.
    :param vault_name: Name of the Recovery Services vault.
    :param vault_resource_group: Resource group of the vault.
    :param subscription_id: Azure subscription ID.
    :param poll_interval: Seconds between job status polls.
    :param poll_timeout: Maximum seconds to wait for job completion.
    :param log_fn: Optional callback ``(level, message)`` for structured logging.
    """

    TERMINAL_JOB_STATUSES = frozenset(
        {
            "completed",
            "failed",
            "cancelled",
            "completedwithwarnings",
        }
    )

    def __init__(
        self,
        client: RecoveryServicesBackupClient,
        vault_name: str,
        vault_resource_group: str,
        subscription_id: str,
        poll_interval: int = 30,
        poll_timeout: int = 7200,
        log_fn: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        self._client = client
        self._vault_name = vault_name
        self._vault_rg = vault_resource_group
        self._subscription_id = subscription_id
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._log = log_fn or (lambda _lvl, _msg: None)

    @staticmethod
    def rp_name_from_id(rp_id: str) -> str:
        """Extract the recovery-point name from its ARM id.

        :param rp_id: Full ARM resource ID.
        :returns: Last segment (the RP name).
        """
        return rp_id.rsplit("/", 1)[-1] if rp_id else ""

    @staticmethod
    def build_container_id(
        subscription_id: str,
        vm_name: str,
        resource_group: str,
    ) -> str:
        """Build the ARM container resource ID for a VM.

        :param subscription_id: Azure subscription ID.
        :param vm_name: Target VM name.
        :param resource_group: Target VM resource group.
        :returns: ARM resource ID for the container.
        """
        return (
            f"/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute"
            f"/virtualMachines/{vm_name}"
        )

    def _vm_id_to_container_id(
        self,
        vm_resource_id: str,
    ) -> str:
        """Convert a VM Compute ARM ID to a protection container ID.

        :param vm_resource_id: ARM resource ID of the VM (``/subscriptions/.../Microsoft.Compute/
            virtualMachines/{name}``).
        :returns: Full ARM ID of the corresponding protection container in the vault.
        """
        parts = vm_resource_id.strip("/").split("/")
        lookup = {parts[i].lower(): parts[i + 1] for i in range(0, len(parts) - 1, 2)}
        rg = lookup.get("resourcegroups", "")
        vm = lookup.get("virtualmachines", "")
        return (
            f"/subscriptions/{self._subscription_id}"
            f"/resourceGroups/{self._vault_rg}"
            f"/providers"
            f"/Microsoft.RecoveryServices"
            f"/vaults/{self._vault_name}"
            f"/backupFabrics/Azure"
            f"/protectionContainers"
            f"/VMAppContainer;Compute;{rg};{vm}"
        )

    @staticmethod
    def _format_azure_error(
        exc: HttpResponseError,
        source_resource_id: str = "",
    ) -> str:
        """Extract a clear error message from an Azure SDK HttpResponseError.

        :param exc: The caught ``HttpResponseError``.
        :param source_resource_id: ARM ID of the source VM (for context).
        :returns: Human-readable error string with error code and remediation hint.
        """
        error_code = getattr(exc.error, "code", None) if exc.error else None
        error_msg = getattr(exc.error, "message", str(exc)) if exc.error else str(exc)
        hint = AZURE_ERROR_HINTS.get(error_code or "", "")

        parts = [f"Azure Backup restore failed ({error_code or 'Unknown'}): {error_msg}"]
        if hint:
            parts.append(f"Hint: {hint}")
        if source_resource_id:
            parts.append(f"Source VM: {source_resource_id}")
        return " | ".join(parts)

    def find_latest_restore_job_id(
        self,
        item_name: str,
        started_after: float,
    ) -> str:
        """Find the most recent restore job for a protected item.

        :param item_name: Protected item name.
        :param started_after: Epoch timestamp; only jobs started after this time are considered.
        :returns: Job ID string (empty if not found).
        """
        try:
            jobs = self._client.backup_jobs.list(
                vault_name=self._vault_name,
                resource_group_name=self._vault_rg,
                filter=f"backupManagementType eq '{BackupManagementType.AZURE_WORKLOAD.value}'",
            )
            for job in jobs:
                props = job.properties
                if props is None:
                    continue
                operation = (props.operation or "").lower()
                if operation != "restore":
                    continue
                friendly = (props.entity_friendly_name or "").lower()
                item_short = item_name.rsplit(";", 1)[-1].lower()
                if item_short not in friendly:
                    continue
                if props.start_time and props.start_time.timestamp() >= started_after:
                    job_id = (job.name or "").strip()
                    if job_id:
                        return job_id
        except Exception:
            logging.getLogger(__name__).debug(
                "Could not find restore job via jobs API.",
                exc_info=True,
            )
        return ""

    @staticmethod
    def build_workload_restore(
        rp_id: str,
        recovery_type: RecoveryType,
        target_container_name: str = "",
        target_database_name: str = "",
        source_resource_id: str = "",
    ) -> RestoreRequestResource:
        """Construct a workload restore request model.

        :param rp_id: Recovery point ARM resource ID.
        :param recovery_type: SDK ``RecoveryType`` enum value.
        :param target_container_name: For cross-VM restores. Must be the full ARM ID of the target
            protection container inside the Recovery Services vault.
        :param target_database_name: For cross-VM restores.
        :param source_resource_id: ARM resource ID of the source VM. When empty the field is omitted
            from the request (required for HSR containers where the protected item has no source VM).
        :returns: SDK ``RestoreRequestResource`` object.
        """
        is_alternate = recovery_type == RecoveryType.ALTERNATE_LOCATION
        target_info = (
            TargetRestoreInfo(
                overwrite_option=OverwriteOptions.OVERWRITE,
                container_id=target_container_name,
                database_name=target_database_name,
            )
            if is_alternate
            else None
        )
        return RestoreRequestResource(
            properties=AzureWorkloadSAPHanaRestoreRequest(
                recovery_type=recovery_type,
                source_resource_id=(source_resource_id or None),
                target_info=target_info,
                recovery_mode=RecoveryMode.WORKLOAD_RECOVERY,
            ),
        )

    @staticmethod
    def build_filesystem_restore_request(
        rp_id: str,
        target_filesystem_path: str,
        container_id: Optional[str],
        source_resource_id: str = "",
    ) -> RestoreRequestResource:
        """Construct a restore-as-files request model.

        :param rp_id: Recovery point ARM resource ID.
        :param target_filesystem_path: Destination path.
        :param container_id: Protection container ARM ID (or ``None``).
        :param source_resource_id: ARM resource ID of the source VM.
        :returns: SDK ``RestoreRequestResource`` object.
        """
        return RestoreRequestResource(
            properties=AzureWorkloadSAPHanaRestoreRequest(
                recovery_type=RecoveryType.ALTERNATE_LOCATION,
                recovery_mode=RecoveryMode.FILE_RECOVERY,
                source_resource_id=(source_resource_id or None),
                target_info=TargetRestoreInfo(
                    overwrite_option=OverwriteOptions.OVERWRITE,
                    container_id=container_id,
                    target_directory_for_file_restore=(target_filesystem_path),
                ),
            ),
        )

    @staticmethod
    def map_job_result_status(
        job_id: str,
        status: str,
        elapsed: int,
        poll_timeout: int,
    ) -> tuple[str, str]:
        """Map a terminal job status to TestStatus and message.

        :param job_id: Azure Backup job ID.
        :param status: Final job status string.
        :param elapsed: Seconds elapsed during polling.
        :param poll_timeout: Maximum allowed seconds.
        :returns: ``(test_status_value, message)`` tuple.
        """
        lower = status.lower()
        if lower == "completed":
            return (
                TestStatus.SUCCESS.value,
                f"Restore job {job_id} completed " f"successfully in {elapsed}s.",
            )
        if lower == "completedwithwarnings":
            return (
                TestStatus.WARNING.value,
                f"Restore job {job_id} completed " f"with warnings in {elapsed}s.",
            )
        if elapsed >= poll_timeout:
            return (
                TestStatus.ERROR.value,
                f"Restore job {job_id} timed out after " f"{elapsed}s (last status: {status}).",
            )
        return (
            TestStatus.ERROR.value,
            f"Restore job {job_id} ended with " f"status '{status}'.",
        )

    def _list_recovery_points(
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
        :param target_container_name: Target container (cross-VM / HSR).
        :param target_database_name: Target DB (cross-VM / HSR).
        :param source_resource_id: ARM resource ID of the source VM.
        :returns: Result dict with ``restore_job``, ``status``, and ``message`` keys.
        :raises Exception: Propagated from SDK calls.
        """
        self._log(
            logging.INFO,
            "Triggering restore-to-database for " f"item='{item_name}'.",
        )
        rp_id = self.resolve_recovery_point(
            container_name,
            item_name,
            restore_point_time,
        )
        if not rp_id:
            return {
                "status": TestStatus.ERROR.value,
                "message": ("No suitable recovery point found."),
            }

        is_cross_vm = bool(target_container_name)
        recovery_type = (
            RecoveryType.ALTERNATE_LOCATION if is_cross_vm else RecoveryType.ORIGINAL_LOCATION
        )
        use_target = recovery_type == RecoveryType.ALTERNATE_LOCATION
        resolved_container = target_container_name if use_target else ""

        if resolved_container and ("Microsoft.Compute/virtualMachines" in resolved_container):
            resolved_container = self._vm_id_to_container_id(
                resolved_container,
            )
        elif resolved_container and not resolved_container.startswith("/subscriptions/"):
            resolved_container = (
                f"/subscriptions/{self._subscription_id}"
                f"/resourceGroups/{self._vault_rg}"
                f"/providers"
                f"/Microsoft.RecoveryServices"
                f"/vaults/{self._vault_name}"
                f"/backupFabrics/Azure"
                f"/protectionContainers"
                f"/{resolved_container}"
            )

        resolved_db = target_database_name if use_target else ""

        self._log(
            logging.INFO,
            "Restore params: recovery_type=%s "
            "target_container=%s "
            "target_db=%s source_vm=%s"
            % (
                recovery_type,
                resolved_container,
                resolved_db,
                source_resource_id,
            ),
        )

        restore_request = self.build_workload_restore(
            rp_id=rp_id,
            recovery_type=recovery_type,
            target_container_name=resolved_container,
            target_database_name=resolved_db,
            source_resource_id=source_resource_id,
        )

        trigger_time = time.time()
        try:
            self._client.restores.begin_trigger(
                vault_name=self._vault_name,
                resource_group_name=self._vault_rg,
                fabric_name="Azure",
                container_name=container_name,
                protected_item_name=item_name,
                recovery_point_id=self.rp_name_from_id(
                    rp_id,
                ),
                parameters=restore_request,
            )
        except HttpResponseError as exc:
            raise RuntimeError(
                self._format_azure_error(exc, source_resource_id),
            ) from exc
        time.sleep(5)
        job_id = self.find_latest_restore_job_id(item_name, trigger_time)
        if not job_id:
            raise RuntimeError(
                "Restore was triggered but no matching "
                "restore job was found via the backup "
                "jobs API. Check Azure portal."
            )
        return {
            "restore_job": {
                "job_id": job_id,
                "recovery_point_id": rp_id,
                "recovery_type": recovery_type,
            },
            "status": TestStatus.SUCCESS.value,
            "message": ("Restore-to-database triggered. " f"Job ID: {job_id}"),
        }

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
        :param target_filesystem_path: Destination path on the VM.
        :param target_vm_name: Target VM for the files.
        :param target_vm_resource_group: Target VM resource group.
        :param restore_point_time: Optional PIT in UTC ISO-8601.
        :param source_resource_id: ARM resource ID of the source VM.
        :returns: Result dict with ``restore_job``, ``status``, and ``message`` keys.
        :raises Exception: Propagated from SDK calls.
        """
        self._log(
            logging.INFO,
            "Triggering restore-to-filesystem for "
            f"item='{item_name}' -> "
            f"'{target_filesystem_path}'.",
        )
        rp_id = self.resolve_recovery_point(
            container_name,
            item_name,
            restore_point_time,
        )
        if not rp_id:
            return {
                "status": TestStatus.ERROR.value,
                "message": ("No suitable recovery point found."),
            }

        if target_vm_name:
            vm_arm_id = self.build_container_id(
                self._subscription_id,
                target_vm_name,
                (target_vm_resource_group or self._vault_rg),
            )
            container_id = self._vm_id_to_container_id(vm_arm_id)
        else:
            container_id = None
        trigger_time = time.time()
        try:
            self._client.restores.begin_trigger(
                vault_name=self._vault_name,
                resource_group_name=self._vault_rg,
                fabric_name="Azure",
                container_name=container_name,
                protected_item_name=item_name,
                recovery_point_id=(self.rp_name_from_id(rp_id)),
                parameters=(
                    self.build_filesystem_restore_request(
                        rp_id,
                        target_filesystem_path,
                        container_id,
                        source_resource_id,
                    )
                ),
            )
        except HttpResponseError as exc:
            raise RuntimeError(
                self._format_azure_error(exc, source_resource_id),
            ) from exc
        time.sleep(5)
        job_id = self.find_latest_restore_job_id(item_name, trigger_time)
        if not job_id:
            raise RuntimeError(
                "Restore-to-filesystem was triggered but "
                "no matching restore job was found via "
                "the backup jobs API. Check Azure portal."
            )
        return {
            "restore_job": {
                "job_id": job_id,
                "recovery_point_id": rp_id,
                "restore_mode": "RestoreAsFiles",
                "target_path": target_filesystem_path,
            },
            "status": TestStatus.SUCCESS.value,
            "message": ("Restore-to-filesystem triggered. " f"Job ID: {job_id}"),
        }

    def check_restore_job(
        self,
        restore_job_id: str,
    ) -> Dict[str, Any]:
        """Poll a restore job until it completes or times out.

        :param restore_job_id: Azure Backup job ID.
        :returns: Result dict with ``restore_job``, ``status``, and ``message`` keys.
        :raises Exception: Propagated from SDK calls.
        """
        self._log(
            logging.INFO,
            f"Polling restore job '{restore_job_id}'.",
        )
        elapsed = 0
        final_status = "Unknown"
        job_props: Optional[AzureWorkloadJob] = None

        while elapsed < self._poll_timeout:
            job = self._client.job_details.get(
                vault_name=self._vault_name,
                resource_group_name=self._vault_rg,
                job_name=restore_job_id,
            )
            job_props = cast(AzureWorkloadJob, job.properties)
            final_status = (job_props.status if job_props else "Unknown") or "Unknown"
            self._log(
                logging.INFO,
                f"Job {restore_job_id}: " f"status={final_status} " f"(elapsed={elapsed}s)",
            )
            if final_status.lower() in self.TERMINAL_JOB_STATUSES:
                break
            time.sleep(self._poll_interval)
            elapsed += self._poll_interval

        error_details: List[str] = []
        if job_props and job_props.error_details:
            for err in job_props.error_details:
                code = err.error_code or "Unknown"
                msg = err.error_string or "No details"
                detail = "Error Code: %s, Error: %s" % (code, msg)
                if err.recommendations:
                    detail += " Recommendations: %s" % "; ".join(err.recommendations)
                error_details.append(detail)
                self._log(logging.ERROR, f"Job {restore_job_id} error: {detail}")

        test_status, message = self.map_job_result_status(
            restore_job_id,
            final_status,
            elapsed,
            self._poll_timeout,
        )
        return {
            "restore_job": {
                "job_id": restore_job_id,
                "status": final_status,
                "elapsed_seconds": elapsed,
                "error_details": error_details,
            },
            "status": test_status,
            "message": message,
        }

    @staticmethod
    def _parse_pit_timestamp(
        restore_point_time: str,
    ) -> Optional[datetime]:
        """Parse an ISO-8601 PIT string to a tz-aware datetime.

        :param restore_point_time: ISO-8601 UTC timestamp.
        :returns: Parsed ``datetime`` or ``None`` on failure.
        """
        text = restore_point_time.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    def resolve_recovery_point(
        self,
        container_name: str,
        item_name: str,
        restore_point_time: str = "",
    ) -> str:
        """Return the recovery-point ID for a restore.

        :param container_name: Backup container name.
        :param item_name: Backup item name.
        :param restore_point_time: Optional PIT in ISO-8601 UTC.
        :returns: Recovery point resource ID (empty on failure).
        """
        rp_list = self._list_recovery_points(
            container_name,
            item_name,
        )
        if not rp_list:
            self._log(
                logging.WARNING,
                f"No recovery points for {item_name}.",
            )
            return ""

        pit = self._parse_pit_timestamp(restore_point_time)
        if pit is None:
            return rp_list[0].id or ""

        self._log(
            logging.INFO,
            f"Using point-in-time {pit.isoformat()} to select recovery point.",
        )
        candidates = []
        for rp in rp_list:
            props = rp.properties
            rp_time = getattr(props, "recovery_point_time_in_utc", None)
            if rp_time is None:
                continue
            if rp_time.tzinfo is None:
                rp_time = rp_time.replace(tzinfo=timezone.utc)
            if rp_time <= pit:
                candidates.append((rp_time, rp))

        if not candidates:
            self._log(
                logging.WARNING,
                "No recovery point at or before "
                f"{pit.isoformat()} for {item_name}. "
                "Falling back to the latest point.",
            )
            return rp_list[0].id or ""

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]
        self._log(
            logging.INFO,
            "Selected recovery point " f"{best.id} at {candidates[0][0].isoformat()}.",
        )
        return best.id or ""
