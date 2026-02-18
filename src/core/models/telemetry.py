# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Telemetry configuration model."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

_SERVICE_LOG_TABLE_SUFFIX = "ServiceLogs"


@dataclass(frozen=True)
class TelemetryConfig:
    """
    Immutable telemetry destination configuration.
    """

    telemetry_data_destination: Optional[str] = None

    laws_workspace_id: Optional[str] = None
    laws_shared_key: Optional[str] = None
    laws_subscription_id: Optional[str] = None
    laws_resource_group: Optional[str] = None
    laws_workspace_name: Optional[str] = None

    adx_database_name: Optional[str] = None
    adx_cluster_fqdn: Optional[str] = None
    adx_client_id: Optional[str] = None

    telemetry_table_name: Optional[str] = None
    service_log_table_name: Optional[str] = None
    user_assigned_identity_client_id: Optional[str] = None

    batch_size: int = 100
    flush_interval_seconds: float = 60.0

    @property
    def has_log_analytics(self) -> bool:
        """
        True when Log Analytics credentials are available.
        """
        return bool(self.laws_workspace_id) and bool(
            self.laws_shared_key
            or (self.laws_subscription_id and self.laws_resource_group and self.laws_workspace_name)
        )

    @property
    def has_adx(self) -> bool:
        """
        True when ADX credentials are available.
        """
        return bool(self.adx_database_name and self.adx_cluster_fqdn and self.adx_client_id)

    @property
    def is_enabled(self) -> bool:
        """
        True when any telemetry destination is configured.
        """
        return self.has_log_analytics or self.has_adx

    def service_table(self) -> str:
        """Table name for service telemetry logs.

        Appends ``ServiceLogs`` to the base table name so service
        telemetry goes to a separate table from Ansible test results.
        """
        base = self.telemetry_table_name or "SAP_AUTOMATION_QA"
        return self.service_log_table_name or f"{base}_{_SERVICE_LOG_TABLE_SUFFIX}"
