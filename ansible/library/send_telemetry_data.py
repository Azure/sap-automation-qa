"""Module to send telemetry data to Kusto Cluster/Log Analyics Workspace and create a HTML report.
"""

import os
from datetime import datetime
from ansible.module_utils.basic import AnsibleModule
import json
import requests
import base64, hashlib, hmac
from datetime import datetime
import sys
from azure.kusto.data import KustoConnectionStringBuilder
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest import (
    QueuedIngestClient,
    IngestionProperties,
    ReportLevel,
    IngestionStatus,
    IngestionResult,
)

LAWS_RESOURCE = "/api/logs"
LAWS_METHOD = "POST"
LAWS_CONTENT_TYPE = "application/json"


def get_authorization_for_log_analytics(
    workspace_id,
    workspace_shared_key,
    content_length,
    datetime,
):
    """Builds the authorization header for Azure Log Analytics

    Args:
        workspace_id (string): Workspace ID for Azure Log Analytics
        workspace_shared_key (string): Workspace Key for Azure Log Analytics
        content_length (int): Length of the payload
        date (datetime): Date and time of the request

    Returns:
        string: Authorization header
    """

    string_to_hash = (
        LAWS_METHOD
        + "\n"
        + str(content_length)
        + "\n"
        + LAWS_CONTENT_TYPE
        + "\n"
        + "x-ms-date:"
        + datetime
        + "\n"
        + LAWS_RESOURCE
    )
    encoded_hash = base64.b64encode(
        hmac.new(
            base64.b64decode(workspace_shared_key),
            bytes(string_to_hash, "UTF-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return "SharedKey {}:{}".format(workspace_id, encoded_hash)


def send_telemetry_data_to_dataexplorer(telemetry_json_data, module_params):
    """Sends telemetry data to Azure Data Explorer

    Args:
        telemetry_json_data (JSON): JSON data to be sent to Kusto
        module_params (dict): Ansible Module parameters

    Raises:
        ex: Exception raised during the process

    Returns:
        IngestKustoResponse: Response from the Kusto API
    """
    try:
        import pandas

        telemetry_json_data = json.loads(telemetry_json_data)

        data_frame = pandas.DataFrame(
            [telemetry_json_data.values()],
            columns=telemetry_json_data.keys(),
        )
        ingestion_properties = IngestionProperties(
            database=module_params["adx_database_name"],
            table=module_params["telemetry_table_name"],
            data_format=DataFormat.JSON,
            report_level=ReportLevel.FailuresAndSuccesses,
        )
        kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
            connection_string=module_params["adx_cluster_fqdn"],
            client_id=module_params["adx_client_id"],
        )
        client = QueuedIngestClient(kcsb)
        response = client.ingest_from_dataframe(data_frame, ingestion_properties)
        return response
    except Exception as ex:
        raise ex


def send_telemetry_data_to_loganalytics(telemetry_json_data, module_params):
    """Sends telemetry data to Azure Log Analytics Workspace

    Args:
        telemetry_json_data (json): JSON data to be sent to Log Analytics
        module_params (dict): Module parameters
    Returns:
        response: Response from the Log Analytics API
    """
    try:
        utc_datetime = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        authorization_header = get_authorization_for_log_analytics(
            workspace_id=module_params["laws_workspace_id"],
            workspace_shared_key=module_params["laws_shared_key"],
            content_length=len(telemetry_json_data),
            datetime=utc_datetime,
        )

        response = requests.post(
            url=f"https://{module_params['laws_workspace_id']}.ods.opinsights.azure.com{LAWS_RESOURCE}?api-version=2016-04-01",
            data=telemetry_json_data,
            headers={
                "content-type": LAWS_CONTENT_TYPE,
                "Authorization": authorization_header,
                "Log-Type": module_params["telemetry_table_name"],
                "x-ms-date": utc_datetime,
            },
        )
        return response
    except Exception as ex:
        raise ex


def run_module():
    """
    Main function to send telemetry data to Kusto
    Cluster/Log Analytics Workspace and create a HTML report.
    """
    module_args = dict(
        test_group_json_data=dict(type="dict", required=True),
        telemetry_data_destination=dict(type="str", required=True),
        laws_workspace_id=dict(type="str", required=False),
        laws_shared_key=dict(type="str", required=False),
        telemetry_table_name=dict(type="str", required=True),
        adx_database_name=dict(type="str", required=False),
        adx_cluster_fqdn=dict(type="str", required=False),
        adx_client_id=dict(type="str", required=False),
        workspace_directory=dict(type="str", required=True),
    )
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    telemetry_data = module.params["test_group_json_data"]
    result = {
        "changed": False,
        "telemetry_data": telemetry_data,
        "telemetry_data_destination": module.params["telemetry_data_destination"],
        "status": None,
        "start": datetime.now(),
        "end": datetime.now(),
    }

    # Create log files named invocation id for the test group invocation and
    # append all the test case result to the file
    log_folder = f"/{module.params['workspace_directory']}/logs"
    os.makedirs(log_folder, exist_ok=True)
    with open(
        f"{log_folder}/{telemetry_data['TestGroupInvocationId']}.log", "a"
    ) as log_file:
        log_file.write(json.dumps(telemetry_data))
        log_file.write("\n")

    # Send telemetry data to the destination
    try:
        method_name = (
            "send_telemetry_data_to_" + module.params["telemetry_data_destination"]
        )
        response = getattr(
            sys.modules[__name__],
            method_name,
        )(json.dumps(telemetry_data), module.params)
        result["status"] = f"Response: {response}"
    except Exception as e:
        result["status"] = f"Error sending telemetry data {e}"
        module.fail_json(msg=f"Error sending telemetry data {e}", **result)
    module.exit_json(**result)


if __name__ == "__main__":
    run_module()
