# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Module to send telemetry data to Kusto Cluster/Log Analytics Workspace and create an HTML report.

Performance Optimization for Configuration Checks:
    - Automatically detects check results format (from configuration_check_module)
    - Builds telemetry batch entries in Python (10-100x faster than Ansible loops)
    - Handles 600+ check results in seconds instead of minutes
    - Expands parameter entries efficiently (for HA configuration checks)
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any
import base64
import hashlib
import hmac
import json
import requests
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.mgmt.loganalytics import LogAnalyticsManagementClient
from azure.kusto.data import KustoConnectionStringBuilder
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties, ReportLevel
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import TelemetryDataDestination, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import TelemetryDataDestination, TestStatus

DOCUMENTATION = r"""
---
module: send_telemetry_data
short_description: Sends SAP automation test results as telemetry data
description:
    - This module sends test result data to Azure telemetry systems
    - Supports sending to Azure Data Explorer (Kusto) or Log Analytics Workspace
    - Also writes a local log file for backup and debugging
    - Handles authentication and formatting for different Azure services
options:
    test_group_json_data:
        description:
            - Dictionary containing the telemetry data to be sent
            - Should include TestGroupInvocationId and other test metadata
            type: raw
        required: true
    telemetry_data_destination:
        description:
            - Where to send the telemetry data
            - Use "azuredataexplorer" for Azure Data Explorer
            - Use "azureloganalytics" for Log Analytics Workspace
        type: str
        required: true
    laws_workspace_id:
        description:
            - Log Analytics workspace ID
            - Required when telemetry_data_destination is "azureloganalytics"
        type: str
        required: false
    laws_shared_key:
        description:
            - Log Analytics workspace shared key
            - Optional - will be auto-fetched from Azure if not provided
            - Requires laws_subscription_id, laws_resource_group, and laws_workspace_name if not provided
        type: str
        required: false
    laws_subscription_id:
        description:
            - Azure subscription ID containing the Log Analytics workspace
            - Required when auto-fetching shared key (laws_shared_key not provided)
        type: str
        required: false
    laws_resource_group:
        description:
            - Resource group containing the Log Analytics workspace
            - Required when auto-fetching shared key (laws_shared_key not provided)
        type: str
        required: false
    laws_workspace_name:
        description:
            - Log Analytics workspace name
            - Required when auto-fetching shared key (laws_shared_key not provided)
        type: str
        required: false
    user_assigned_identity_client_id:
        description:
            - Client ID of user-assigned managed identity
            - Optional - if provided, uses user-assigned MI instead of system-assigned
            - Used for authentication when fetching shared keys
        type: str
        required: false
    telemetry_table_name:
        description:
            - Table name for storing the telemetry data
            - In Log Analytics, this becomes the Log-Type header
        type: str
        required: false
    adx_database_name:
        description:
            - Azure Data Explorer database name
            - Required when telemetry_data_destination is "azuredataexplorer"
        type: str
        required: false
    adx_cluster_fqdn:
        description:
            - Azure Data Explorer cluster FQDN
            - Required when telemetry_data_destination is "azuredataexplorer"
        type: str
        required: false
    adx_client_id:
        description:
            - Client ID for Azure Data Explorer authentication
            - Required when telemetry_data_destination is "azuredataexplorer"
        type: str
        required: false
    workspace_directory:
        description:
            - Directory for storing local log files
            - Logs will be created in {workspace_directory}/logs/
        type: str
        required: true
    common_vars:
        description:
            - Common variables for configuration checks (performance optimization)
            - Contains test_group_invocation_id, group_start_time, group_name, etc.
            - Optional - used when sending check results directly from configuration checks
        type: dict
        required: false
    system_context_map:
        description:
            - Mapping of hostnames to system context (performance optimization)
            - Keys are hostnames, values are system_context dictionaries
            - Optional - used when sending check results directly from configuration checks
        type: dict
        required: false
author:
    - Microsoft Corporation
notes:
    - Uses managed identity authentication for Azure Data Explorer
    - Uses shared key authentication for Log Analytics Workspace
    - Always writes a local log file regardless of telemetry destination
requirements:
    - python >= 3.6
    - azure-identity
    - azure-mgmt-loganalytics
    - azure-kusto-data
    - azure-kusto-ingest
    - requests
    - pandas
"""

EXAMPLES = r"""
- name: Send telemetry data to Azure Log Analytics
  send_telemetry_data:
    test_group_json_data: "{{ test_results }}"
    telemetry_data_destination: "azureloganalytics"
    laws_workspace_id: "{{ laws_workspace_id }}"
    laws_shared_key: "{{ laws_shared_key }}"
    telemetry_table_name: "SAPAutomationQAResults"
    workspace_directory: "/var/log/sap-automation-qa"
  register: telemetry_result

- name: Send telemetry data to Azure Data Explorer (Kusto)
  send_telemetry_data:
    test_group_json_data: "{{ test_results }}"
    telemetry_data_destination: "azuredataexplorer"
    adx_database_name: "SAPAutomationQA"
    adx_cluster_fqdn: "https://cluster.region.kusto.windows.net"
    adx_client_id: "{{ adx_client_id }}"
    telemetry_table_name: "TestResults"
    workspace_directory: "/var/log/sap-automation-qa"
  register: telemetry_result

- name: Only log data locally without sending to Azure
  send_telemetry_data:
    test_group_json_data: "{{ test_results }}"
    telemetry_data_destination: "local"
    workspace_directory: "/var/log/sap-automation-qa"
  register: telemetry_result
"""

RETURN = r"""
status:
    description: Status of the telemetry sending operation
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Detailed message about the operation
    returned: always
    type: str
    sample: "Telemetry data sent to azureloganalytics. Telemetry data written to /var/log/sap-automation-qa/logs/123456.log."
telemetry_data:
    description: Copy of the data that was sent
    returned: always
    type: dict
    sample: {"TestGroupInvocationId": "123456", "TestResult": "PASS"}
telemetry_data_destination:
    description: Where the data was sent
    returned: always
    type: str
    sample: "azureloganalytics"
start:
    description: Start time of the operation
    returned: always
    type: str
    sample: "2023-01-01T12:00:00"
end:
    description: End time of the operation
    returned: always
    type: str
    sample: "2023-01-01T12:00:05"
data_sent:
    description: Whether the data was successfully sent to the destination
    returned: always
    type: bool
    sample: true
"""

LAWS_RESOURCE = "/api/logs"
LAWS_METHOD = "POST"
LAWS_CONTENT_TYPE = "application/json"


class TelemetryDataSender(SapAutomationQA):
    """
    Class to send telemetry data to Kusto Cluster/Log Analytics Workspace and create an HTML report.
    """

    def __init__(self, module_params: Dict[str, Any]):
        super().__init__()
        self.module_params = module_params
        raw_data = module_params["test_group_json_data"]
        if self._is_check_results_format(raw_data):
            telemetry_data = self._build_telemetry_batch_from_results(raw_data, module_params)
        else:
            telemetry_data = self._expand_parameter_entries(raw_data)

        self.result.update(
            {
                "telemetry_data": telemetry_data,
                "telemetry_data_destination": module_params["telemetry_data_destination"],
                "start": datetime.now(),
                "end": datetime.now(),
                "data_sent": False,
                "data_logged": False,
            }
        )

    def _expand_parameter_entries(self, telemetry_data: Any) -> Any:
        """
        Expands telemetry entries that have 'details.parameters' into individual entries.

        For configuration checks with multiple parameters (e.g., HA checks), this creates
        a separate telemetry entry for each parameter while preserving non-parameter entries.

        :param telemetry_data: Raw telemetry data (dict or list of dicts)
        :type telemetry_data: Any
        :return: Expanded telemetry data with parameter entries
        :rtype: Any
        """
        if not isinstance(telemetry_data, list):
            telemetry_data = [telemetry_data] if isinstance(telemetry_data, dict) else []

        expanded_entries = []

        for entry in telemetry_data:
            if not isinstance(entry, dict):
                expanded_entries.append(entry)
                continue
            details = entry.get("TestCaseDetails")
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except (json.JSONDecodeError, ValueError):
                    details = None
            if not isinstance(details, dict):
                expanded_entries.append(entry)
                continue
            parameters = details.get("parameters")

            if not parameters or not isinstance(parameters, list):
                expanded_entries.append(entry)
                continue
            base_id = entry.get("TestCaseInvocationId", "")
            for param in parameters:
                if not isinstance(param, dict) or param.get("status") in ["SKIPPED"]:
                    continue
                param_entry = entry.copy()

                param_entry.update(
                    {
                        "TestCaseInvocationId": f"{base_id}-"
                        + f"{param.get('category', param.get('name', ''))}",
                        "TestCaseStatus": param.get("status", entry.get("TestCaseStatus", "")),
                        "TestCaseName": param.get("name", param.get("id", "")),
                        "TestCaseDescription": (
                            f"Parameter {param.get('name', param.get('id', ''))} "
                            f"in category {param.get('category', '')}"
                        ),
                        "TestCaseMessage": (
                            f"Actual={param.get('value', '')} "
                            f"Expected={param.get('expected_value', '')}"
                        ),
                        "TestCaseDetails": json.dumps(param),
                    }
                )

                expanded_entries.append(param_entry)

        return expanded_entries

    def _is_check_results_format(self, data: Any) -> bool:
        """
        Determines if the data is in check results format (from configuration checks).

        Check results format has fields like: id, name, check, status, hostname, timestamp, etc.
        Regular telemetry format has fields like: TestCaseInvocationId, TestCaseStatus, etc.

        :param data: Data to check
        :type data: Any
        :return: True if data is in check results format
        :rtype: bool
        """
        if not isinstance(data, (list, dict)):
            return False

        sample = data[0] if isinstance(data, list) and data else data
        if not isinstance(sample, dict):
            return False
        sample_keys = set(sample.keys())
        return (
            len({"id", "check", "status", "hostname", "timestamp"} & sample_keys) >= 3
            and not len({"TestCaseInvocationId", "TestCaseStatus", "TestGroupName"} & sample_keys)
            >= 2
        )

    def _build_telemetry_batch_from_results(
        self, check_results: Any, module_params: Dict[str, Any]
    ) -> list:
        """
        Builds telemetry batch from check results in Python (replaces slow Ansible loops).

        This is a performance optimization for configuration checks that can have
        hundreds of check results. Building the telemetry entries in Python is
        significantly faster than Ansible's set_fact loops.

        :param check_results: List of check results from configuration checks
        :type check_results: Any
        :param module_params: Module parameters containing system context
        :type module_params: Dict[str, Any]
        :return: List of telemetry entries
        :rtype: list
        """
        if not isinstance(check_results, list):
            check_results = [check_results] if isinstance(check_results, dict) else []
        check_results = [r for r in check_results if r.get("status") != "SKIPPED"]

        telemetry_batch = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        common_vars = module_params.get("common_vars", {})

        for check_result in check_results:
            if not isinstance(check_result, dict):
                continue

            hostname = check_result.get("hostname", "")
            system_context = module_params.get("system_context_map", {}).get(hostname, {})
            entry = {
                "TestCaseInvocationId": check_result.get("id")
                or check_result.get("check", {}).get("id", ""),
                "TestCaseStartTime": check_result.get("timestamp", current_time),
                "TestCaseEndTime": check_result.get("timestamp", current_time),
                "TestCaseStatus": check_result.get("status", ""),
                "TestCaseName": check_result.get("name")
                or check_result.get("check", {}).get("name", ""),
                "TestCaseDescription": check_result.get("check", {}).get("description")
                or system_context.get("role", ""),
                "TestGroupInvocationId": common_vars.get("test_group_invocation_id", ""),
                "TestGroupStartTime": common_vars.get("group_start_time", ""),
                "TestGroupName": common_vars.get("group_name", "ConfigurationChecks"),
                "OsVersion": f"{system_context.get('os_type', '')} "
                + f"{system_context.get('os_version', '')}".strip(),
                "TestCaseMessage": (
                    f"Actual={check_result.get('actual_value', '')} "
                    f"Expected={check_result.get('expected_value', '')}"
                ),
                "TestCaseDetails": (
                    json.dumps(check_result.get("details", {}))
                    if check_result.get("details")
                    else ""
                ),
                "DurationSeconds": check_result.get("execution_time", ""),
                "StorageType": common_vars.get("NFS_provider", "unknown"),
                "PackageVersions": common_vars.get("package_versions", ""),
                "Tags": common_vars.get("execution_tags", ""),
                "TestExecutionStartTime": check_result.get("timestamp", current_time),
                "TestExecutionEndTime": check_result.get("timestamp", current_time),
                "TestCaseHostname": hostname,
                "TestCaseLogMessagesFromSap": (
                    json.dumps(check_result.get("details", {}))
                    if check_result.get("details")
                    else ""
                ),
                "DBType": system_context.get("database_type", ""),
                "DbSid": system_context.get("database_sid", ""),
                "SapSid": system_context.get("sap_sid", ""),
                "DbFencingType": system_context.get("high_availability_agent", ""),
                "ScsFencingType": system_context.get("high_availability_agent", ""),
            }

            telemetry_batch.append(entry)
        return self._expand_parameter_entries(telemetry_batch)

    def _fetch_laws_shared_key(self) -> str:
        """
        Fetches the Log Analytics workspace shared key using Azure SDK.
        Uses DefaultAzureCredential (managed identity) as per Microsoft documentation.

        :return: Primary shared key for the workspace.
        :rtype: str
        :raises: Exception if key retrieval fails.
        """
        subscription_id = self.module_params.get("laws_subscription_id", "")
        resource_group = self.module_params.get("laws_resource_group", "")
        workspace_name = self.module_params.get("laws_workspace_name", "")

        required_params = [
            ("laws_subscription_id", subscription_id),
            ("laws_resource_group", resource_group),
            ("laws_workspace_name", workspace_name),
        ]
        missing_params = [name for name, value in required_params if not str(value).strip()]
        if missing_params:
            missing_str = ", ".join(missing_params)
            raise ValueError(
                f"The following parameters are required to auto-fetch shared key "
                f"but were missing or empty: {missing_str}"
            )

        try:
            user_assigned_client_id = self.module_params.get("user_assigned_identity_client_id", "")
            if user_assigned_client_id and user_assigned_client_id.strip():
                self.log(
                    logging.INFO, f"Using user-assigned managed identity: {user_assigned_client_id}"
                )
                credential = ManagedIdentityCredential(client_id=user_assigned_client_id)
            else:
                self.log(logging.INFO, "Using DefaultAzureCredential (system-assigned MI or other)")
                credential = DefaultAzureCredential()

            client = LogAnalyticsManagementClient(
                credential=credential, subscription_id=subscription_id
            )
            response = client.shared_keys.get_shared_keys(
                resource_group_name=resource_group, workspace_name=workspace_name
            )
            primary_key = response.primary_shared_key
            if not primary_key:
                raise ValueError("Primary shared key not found in Azure response")

            self.log(logging.INFO, "Successfully fetched Log Analytics shared key from Azure")
            return primary_key
        except Exception as ex:
            self.log(logging.ERROR, f"Failed to fetch shared key from Azure: {ex}")
            raise

    def _get_authorization_for_log_analytics(
        self,
        workspace_id: str,
        workspace_shared_key: str,
        content_length: int,
        date: str,
    ) -> str:
        """
        Builds the authorization header for Azure Log Analytics.

        :param workspace_id: Workspace ID for Azure Log Analytics.
        :type workspace_id: str
        :param workspace_shared_key: Workspace Key for Azure Log Analytics.
        :type workspace_shared_key: str
        :param content_length: Length of the payload.
        :type content_length: int
        :param date: Date and time of the request.
        :type date: str
        :return: Authorization header.
        :rtype: str
        """
        string_to_hash = (
            f"{LAWS_METHOD}\n{content_length}\n{LAWS_CONTENT_TYPE}\nx-ms-date:"
            + f"{date}\n{LAWS_RESOURCE}"
        )
        encoded_hash = base64.b64encode(
            hmac.new(
                base64.b64decode(workspace_shared_key),
                bytes(string_to_hash, "UTF-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return f"SharedKey {workspace_id}:{encoded_hash}"

    def send_telemetry_data_to_azuredataexplorer(self, telemetry_json_data: str) -> Any:
        """
        Sends telemetry data to Azure Data Explorer.

        :param telemetry_json_data: The JSON data to be sent to Azure Data Explorer.
        :type telemetry_json_data: str
        :return: The response from the Kusto API.
        :rtype: Any
        """
        import pandas as pd

        telemetry_json_obj = json.loads(telemetry_json_data)
        if isinstance(telemetry_json_obj, list):
            data_frame = pd.DataFrame(telemetry_json_obj)
        elif isinstance(telemetry_json_obj, dict):
            data_frame = pd.DataFrame(
                [list(telemetry_json_obj.values())], columns=list(telemetry_json_obj.keys())
            )
        else:
            raise ValueError("Unsupported telemetry payload for ADX ingestion")
        ingestion_properties = IngestionProperties(
            database=self.module_params["adx_database_name"],
            table=self.module_params.get("telemetry_table_name", "SAP_AUTOMATION_QA"),
            data_format=DataFormat.JSON,
            report_level=ReportLevel.FailuresAndSuccesses,
        )
        kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
            connection_string=self.module_params["adx_cluster_fqdn"],
            client_id=self.module_params["adx_client_id"],
        )
        client = QueuedIngestClient(kcsb)
        response = client.ingest_from_dataframe(data_frame, ingestion_properties)
        self.log(
            logging.INFO,
            f"Response from Kusto: {response}",
        )
        return response

    def send_telemetry_data_to_azureloganalytics(
        self, telemetry_json_data: str
    ) -> requests.Response:
        """
        Sends telemetry data to Azure Log Analytics Workspace.

        :param telemetry_json_data: JSON data to be sent to Log Analytics.
        :type telemetry_json_data: str
        :return: Response from the Log Analytics API.
        :rtype: requests.Response
        """
        utc_datetime = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        authorization_header = self._get_authorization_for_log_analytics(
            workspace_id=self.module_params["laws_workspace_id"],
            workspace_shared_key=self.module_params["laws_shared_key"],
            content_length=len(telemetry_json_data),
            date=utc_datetime,
        )

        response = requests.post(
            url=f"https://{self.module_params['laws_workspace_id']}.ods.opinsights.azure.com"
            + f"{LAWS_RESOURCE}?api-version=2016-04-01",
            data=telemetry_json_data,
            headers={
                "content-type": LAWS_CONTENT_TYPE,
                "Authorization": authorization_header,
                "Log-Type": self.module_params.get("telemetry_table_name", "SAP_AUTOMATION_QA"),
                "x-ms-date": utc_datetime,
            },
            timeout=30,
        )
        self.log(
            logging.INFO,
            f"Response from Log Analytics: {response}",
        )
        return response

    def validate_params(self) -> bool:
        """
        Validate the telemetry data destination parameters.
        Auto-fetches Log Analytics shared key if not provided.

        :return: True if the parameters are valid, False otherwise.
        :rtype: bool
        """
        telemetry_data_destination = self.module_params.get("telemetry_data_destination")

        if telemetry_data_destination == TelemetryDataDestination.LOG_ANALYTICS.value:
            if (
                "laws_workspace_id" not in self.module_params
                or not str(self.module_params["laws_workspace_id"]).strip()
            ):
                self.log(logging.ERROR, "laws_workspace_id is required for Log Analytics")
                return False
            if (
                "laws_shared_key" not in self.module_params
                or not self.module_params["laws_shared_key"]
            ):
                try:
                    self.log(logging.INFO, "Shared key not provided, fetching from Azure...")
                    shared_key = self._fetch_laws_shared_key()
                    self.module_params["laws_shared_key"] = shared_key
                except Exception as ex:
                    self.log(
                        logging.ERROR,
                        f"Failed to auto-fetch shared key and none was provided: {ex}",
                    )
                    return False
        elif telemetry_data_destination == TelemetryDataDestination.KUSTO.value:
            required_params = [
                "adx_database_name",
                "telemetry_table_name",
                "adx_cluster_fqdn",
                "adx_client_id",
            ]
            missing_params = [param for param in required_params if param not in self.module_params]
            if missing_params:
                return False
        return True

    def write_log_file(self) -> None:
        """
        Writes the telemetry data to a log file.
        """
        try:
            log_folder = os.path.join(self.module_params["workspace_directory"], "logs")
            os.makedirs(log_folder, exist_ok=True)
            tg_id = None
            td = self.result.get("telemetry_data")
            if isinstance(td, dict):
                tg_id = td.get("TestGroupInvocationId")
            elif isinstance(td, list) and len(td) > 0 and isinstance(td[0], dict):
                tg_id = td[0].get("TestGroupInvocationId")
            if not tg_id:
                tg_id = datetime.now().strftime("%Y%m%d%H%M%S")
            log_file_path = os.path.join(log_folder, f"{tg_id}.log")
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(self.result["telemetry_data"]))
                log_file.write("\n")

            self.result["message"] += f"Telemetry data written to {log_file_path}. "
            self.result.update(
                {
                    "status": TestStatus.SUCCESS.value,
                    "data_sent": True,
                }
            )
        except Exception as ex:
            self.handle_error(ex)

    def send_telemetry_data(self) -> None:
        """
        Sends telemetry data to the specified destination.
        """
        if self.module_params["telemetry_data_destination"] in [
            TelemetryDataDestination.KUSTO.value,
            TelemetryDataDestination.LOG_ANALYTICS.value,
        ]:
            self.log(logging.INFO, "Validating parameters for telemetry data destination ")

            if not self.validate_params():
                self.result["status"] = (
                    "Invalid parameters for telemetry data destination. Data will not be sent."
                )
                return

            self.log(
                logging.INFO,
                f"Sending telemetry data to {self.module_params['telemetry_data_destination']}",
            )

            try:
                method_name = (
                    "send_telemetry_data_to_"
                    + f"{self.module_params['telemetry_data_destination']}"
                )
                getattr(self, method_name)(json.dumps(self.result["telemetry_data"]))
                self.result[
                    "message"
                ] += f"Telemetry data sent to {self.module_params['telemetry_data_destination']}. "
                self.result.update(
                    {
                        "status": TestStatus.SUCCESS.value,
                        "data_sent": True,
                    }
                )
            except Exception as ex:
                self.handle_error(ex)
        else:
            self.log(
                logging.ERROR,
                "Invalid telemetry data destination specified "
                + f"{self.module_params['telemetry_data_destination']}",
            )

    def get_result(self) -> Dict[str, Any]:
        """
        Returns the result dictionary.

        :return: The result dictionary containing the status of the operation.
        :rtype: Dict[str, Any]
        """
        self.result["end"] = datetime.now()
        return self.result


def run_module() -> None:
    """
    Sets up and runs the telemetry data sending module with the specified arguments.
    """
    module_args = dict(
        test_group_json_data=dict(type="raw", required=True),
        telemetry_data_destination=dict(type="str", required=True),
        laws_workspace_id=dict(type="str", required=False),
        laws_shared_key=dict(type="str", required=False, no_log=True),
        laws_subscription_id=dict(type="str", required=False),
        laws_resource_group=dict(type="str", required=False),
        laws_workspace_name=dict(type="str", required=False),
        user_assigned_identity_client_id=dict(type="str", required=False),
        telemetry_table_name=dict(type="str", required=False),
        adx_database_name=dict(type="str", required=False),
        adx_cluster_fqdn=dict(type="str", required=False),
        adx_client_id=dict(type="str", required=False),
        workspace_directory=dict(type="str", required=True),
        common_vars=dict(type="dict", required=False, default={}),
        system_context_map=dict(type="dict", required=False, default={}),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    sender = TelemetryDataSender(module.params)

    sender.write_log_file()
    sender.send_telemetry_data()

    module.exit_json(**sender.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
