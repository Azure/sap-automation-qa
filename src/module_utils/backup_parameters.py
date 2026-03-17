# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Parameter computation helpers for Azure Backup HANA reports.
"""

from typing import Any, Dict, List

try:
    from src.module_utils.enums import TestStatus, Parameters
except ImportError:
    from ansible.module_utils.enums import TestStatus, Parameters


class BackupParameterBuilder:
    """Builds HTML report parameter rows from SDK objects.

    All methods are static — the class serves as a logical
    namespace grouping parameter computation and formatting.
    """

    @staticmethod
    def compute_param_values(
        props: Any,
        rp_time: str,
        rp_type: str,
        last_job: Any,
        last_full: Any,
        db_status: str,
    ) -> Dict[str, Dict[str, str]]:
        """Compute values and statuses keyed by parameter key.

        :param props: SDK protected-item properties.
        :param rp_time: ISO timestamp of latest recovery point.
        :param rp_type: Type of the latest recovery point.
        :param last_job: Latest job for this DB (or ``None``).
        :param last_full: Latest full backup job (or ``None``).
        :param db_status: Computed PASSED/WARNING/FAILED status.
        :returns: Dict mapping parameter key to ``{"value": ..., "status": ...}``.
        """
        last_backup_time = (
            last_full.start_time.isoformat() if last_full and last_full.start_time else ""
        )
        policy_name = props.policy_name or ""
        if not policy_name and getattr(props, "policy_id", None):
            policy_name = (props.policy_id or "").rsplit("/", 1)[-1]
        last_job_op = last_job.operation or "N/A" if last_job else "N/A"
        last_job_st = last_job.status or "N/A" if last_job else "N/A"
        full_st = last_full.status or "N/A" if last_full else "N/A"
        full_tm = last_full.start_time.isoformat() if last_full and last_full.start_time else "N/A"

        return {
            "backup_status": {
                "value": db_status,
                "status": db_status,
            },
            "health_status": {
                "value": props.protected_item_health_status or "Unknown",
                "status": db_status,
            },
            "protection_status": {
                "value": (props.protection_status or "Unknown"),
                "status": db_status,
            },
            "last_backup_time": {
                "value": last_backup_time or "N/A",
                "status": TestStatus.INFO.value,
            },
            "latest_restore_point": {
                "value": rp_time,
                "status": TestStatus.INFO.value,
            },
            "backup_type": {
                "value": rp_type,
                "status": TestStatus.INFO.value,
            },
            "policy_name": {
                "value": policy_name,
                "status": TestStatus.INFO.value,
            },
            "last_job": {
                "value": (
                    f"{last_job_op} ({last_job_st})"
                    if last_job_op and last_job_op != "N/A"
                    else "N/A"
                ),
                "status": (
                    TestStatus.SUCCESS.value
                    if last_job_st.lower() in ("completed", "completedwithwarnings")
                    else TestStatus.WARNING.value
                ),
            },
            "last_full_backup": {
                "value": f"{full_st} at {full_tm}" if (full_st and full_st != "N/A") else "N/A",
                "status": (
                    TestStatus.SUCCESS.value
                    if full_st.lower() == "completed"
                    else TestStatus.WARNING.value
                ),
            },
        }

    @staticmethod
    def build_db_parameters(
        param_defs: List[Dict[str, str]],
        props: Any,
        rp_time: str,
        rp_type: str,
        is_hsr: bool,
        last_job: Any,
        last_full: Any,
        db_status: str,
    ) -> List[Dict[str, Any]]:
        """Build the HTML table parameter rows for one database.

        :param param_defs: Parameter definitions loaded from the role vars file.
        :param props: SDK protected-item properties.
        :param rp_time: ISO timestamp of latest recovery point.
        :param rp_type: Type of the latest recovery point.
        :param is_hsr: Whether the container is HSR-based.
        :param last_job: Latest job for this DB (or ``None``).
        :param last_full: Latest full backup job (or ``None``).
        :param db_status: Computed PASSED/WARNING/FAILED status.
        :returns: List of serialised ``Parameters`` dicts.
        """
        server_name = props.server_name or ""
        parent_name = props.parent_name or ""
        cat = f"{server_name}\\{parent_name}" if parent_name else server_name
        db_name = props.friendly_name or ""
        server_type = "HSR" if is_hsr else "Standalone Instance"

        results: List[Dict[str, Any]] = []
        for defn in param_defs:
            key = defn["key"]
            vals = BackupParameterBuilder.compute_param_values(
                props,
                rp_time,
                rp_type,
                last_job,
                last_full,
                db_status,
            ).get(
                key,
                {
                    "value": "N/A",
                    "status": TestStatus.WARNING.value,
                },
            )
            id_val = {
                "server_type": server_type,
                "db_name": db_name,
            }.get(
                defn.get("id_source", "db_name"),
                db_name,
            )
            expected = (
                defn.get(
                    "expected_value_hsr",
                    defn.get("expected_value", ""),
                )
                if is_hsr and "expected_value_hsr" in defn
                else defn.get("expected_value", "")
            )
            results.append(
                Parameters(
                    category=cat,
                    id=id_val,
                    name=defn["name"],
                    value=vals["value"],
                    expected_value=expected,
                    status=vals["status"],
                ).to_dict()
            )
        return results
