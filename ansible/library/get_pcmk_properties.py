#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import subprocess
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

CLUSTER_PROPERTIES = {
    "crm_config": {
        "cib-bootstrap-options": {
            "have-watchdog": "false",
            "cluster-infrastructure": "corosync",
            "stonith-enabled": "true",
            "concurrent-fencing": "true",
            "stonith-timeout": "900s",
            "maintenance-mode": "false",
            "azure-events_globalPullState": "IDLE",
            "priority-fencing-delay": "30",
        }
    },
    "rsc_defaults": {
        "build-resource-defaults": {
            "resource-stickiness": "1000",
            "migration-threshold": "5000",
            "priority": "1",
        }
    },
    "op_defaults": {
        "op-options": {
            "timeout": "600",
            "record-pending": "true",
        }
    },
    "resources": {
        "cln_SAPHanaTopology": {
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "SID": "SID",
            "InstanceNumber": "XX",
            "InstanceNumber": "00",
            "monitor-interval": "10",
            "monitor-timeout": "600",
            "start-interval": "0",
            "start-timeout": "600",
            "stop-interval": "0",
            "stop-timeout": "300",
        },
        "msl_SAPHana": {
            "notify": "true",
            "clone-max": "2",
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "SID": "SID",
            "InstanceNumber": "XX",
            "PREFER_SITE_TAKEOVER": "true",
            "DUPLICATE_PRIMARY_TIMEOUT": "7200",
            "AUTOMATED_REGISTER": "true",
            "start-interval": "0",
            "start-timeout": "3600",
            "stop-interval": "0",
            "stop-timeout": "3600",
            "promote-interval": "0",
            "promote-timeout": "3600",
            "monitor-Master-interval": "60",
            "monitor-Master-timeout": "700",
            "monitor-Slave-interval": "61",
            "monitor-Slave-timeout": "700",
            "demote-interval": "0s",
            "demote-timeout": "320",
        },
        "rsc_st_azure": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "monitor-timeout": "120",
        },
        "health-azure-events": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
    },
}


def location_constraints_exists():
    """Check if location constraints exist in the pacemaker cluster.

    This function checks if there are any location constraints defined in the
    pacemaker cluster. It uses the `cibadmin` command-line tool to query the
    cluster's constraints and parses the XML output to determine if any
    location constraints are present.

    Returns:
        bool: True if location constraints exist, False otherwise.
    """
    try:
        with subprocess.Popen(
            ["cibadmin", "--query", "--scope", "constraints"],
            stdout=subprocess.PIPE,
            encoding="utf-8",
        ) as proc:
            xml_output = proc.stdout.read()
        return ET.fromstring(xml_output).find(".//rsc_location") is not None
    except subprocess.CalledProcessError:
        return False


def validate_global_ini_properties(DB_SID: str):
    """Validate SAPHanaSR properties in global.ini file.

    Args:
        DB_SID (str): Database SID

    Returns:
        AnsibleModule.exit_json: SAPHanaSR Properties: {properties}
    """
    try:
        global_ini_file_path = (
            f"/usr/sap/{DB_SID}/SYS/global/hdb/custom/config/global.ini"
        )
        with open(global_ini_file_path, "r") as file:
            global_ini = [line.strip() for line in file.readlines()]
        ha_dr_provider_SAPHnaSR = global_ini.index("[ha_dr_provider_SAPHanaSR]")
        ha_dr_provider_SAPHnaSR_properties = global_ini[
            ha_dr_provider_SAPHnaSR + 1 : ha_dr_provider_SAPHnaSR + 4
        ]
        ha_dr_provider_SAPHanaSR_dict = {
            key.strip(): value.strip()
            for prop in ha_dr_provider_SAPHnaSR_properties
            for key, value in [prop.split("=")]
        }

        expected_properties_sles = {
            "provider": "SAPHanaSR",
            "path": "/usr/share/SAPHanaSR",
            "execution_order": "1",
        }
        if ha_dr_provider_SAPHanaSR_dict == expected_properties_sles:
            return {
                "msg": f"SAPHanaSR Properties: " + f"{ha_dr_provider_SAPHanaSR_dict}."
            }
        else:
            return {
                "error": f"SAPHanaSR Properties validation failed with"
                + f" the expected properties. Properties: {ha_dr_provider_SAPHanaSR_dict}"
            }
    except FileNotFoundError as e:
        return {"error": f"Exception raised, file not found error: {str(e)}"}
    except Exception as e:
        return {
            "error": f"SAPHanaSR Properties validation failed: {str(e)} {global_ini}"
        }


def validate_cluster_params(cluster_properties: dict):
    """Validate pacemaker cluster parameters for DB and SCS

    Args:
        cluster_properties (dict): Dictionary of recommended values of
                                    cluster properties

    Returns:
        success: No drift parameters found. Validated <parameters>
        error: Drift parameters found: <parameters>
    """
    try:
        drift_parameters, valid_parameters = defaultdict(
            lambda: defaultdict(list)
        ), defaultdict(lambda: defaultdict(list))

        for resource_operation, _ in cluster_properties.items():
            with subprocess.Popen(
                ["cibadmin", "--query", "--scope", f"{resource_operation}"],
                stdout=subprocess.PIPE,
                encoding="utf-8",
            ) as proc:
                xml_output = proc.stdout.read()
            root = ET.fromstring(xml_output)

            for root_element in root:
                root_id = root_element.get("id")
                extracted_values = {root_id: {}}

                # Extract nvpair parameters and their values from XML
                for nvpair in root_element.findall(".//nvpair"):
                    name = nvpair.get("name")
                    value = nvpair.get("value")
                    extracted_values[root_id][name] = value

                # Extract operation parameters
                for op in root_element.findall(".//op"):
                    name = (
                        f"{op.get('name')}-{op.get('role', 'NoRole')}-interval"
                        if op.get("role")
                        else f"{op.get('name')}-interval"
                    )
                    value = op.get("interval")
                    extracted_values[root_id][name] = value

                    name = (
                        f"{op.get('name')}-{op.get('role', 'NoRole')}-timeout"
                        if op.get("role")
                        else f"{op.get('name')}-timeout"
                    )
                    value = op.get("timeout")
                    extracted_values[root_id][name] = value

                recommended_for_root = {}
                for key in CLUSTER_PROPERTIES[resource_operation].keys():
                    if root_id.startswith(key):
                        recommended_for_root = CLUSTER_PROPERTIES[resource_operation][
                            key
                        ]
                        for name, value in extracted_values[root_id].items():
                            if name in recommended_for_root:
                                if value != recommended_for_root.get(name):
                                    drift_parameters[resource_operation][
                                        root_id
                                    ].append({name: value})
                                else:
                                    valid_parameters[resource_operation][
                                        root_id
                                    ].append({name: value})
        if drift_parameters:
            return {
                "error": f"Drift in cluster parameters: {json.dumps(drift_parameters)}"
                + f"Validated cluster parameters: {json.dumps(valid_parameters)}"
            }
        return {"msg": f"Validated cluster parameters: {json.dumps(valid_parameters)}"}

    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


def visualize_cluster_actions(xml_file):
    """Visualize cluster actions using crm_simulate.

    Args:
        xml_file (string): XML string
    """
    dot_file = f"{xml_file}.dot"
    try:
        with subprocess.Popen(
            [
                "crm_simulate",
                "--simulate",
                "--xml-file",
                xml_file,
                "--save-dotfile",
                dot_file,
            ],
            stdout=subprocess.PIPE,
            text=True,
        ) as proc:
            proc.stdout.read()
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


def main():
    """
    Main function to parse, validate and visualize pacemaker cluster parameters.
    """
    module = AnsibleModule(
        argument_spec=dict(
            action=dict(type="str", choices=["get", "visualize"], required=True),
            host_type=dict(type="str"),
            xml_file=dict(type="str"),
            sid=dict(type="str"),
            instance_number=dict(type="str"),
        )
    )
    action = module.params["action"]
    host_type = module.params.get("host_type")
    xml_file = module.params.get("xml_file")
    sid = module.params.get("sid")
    instance_number = module.params.get("instance_number")

    # load the CLUSTER_PROPERTIES dictionary with SID and InstanceNumber
    # in the resource parameters

    CLUSTER_PROPERTIES["resources"]["msl_SAPHana"]["SID"] = sid
    CLUSTER_PROPERTIES["resources"]["msl_SAPHana"]["InstanceNumber"] = instance_number
    CLUSTER_PROPERTIES["resources"]["cln_SAPHanaTopology"]["SID"] = sid
    CLUSTER_PROPERTIES["resources"]["cln_SAPHanaTopology"][
        "InstanceNumber"
    ] = instance_number

    if action == "get":
        if location_constraints_exists():
            module.fail_json(changed=False, msg="Location constraints found.")
        else:
            cluster_result = validate_cluster_params(
                cluster_properties=CLUSTER_PROPERTIES,
            )
            sap_hana_sr_result = validate_global_ini_properties(DB_SID=sid)
            if any(
                "error" in result for result in [cluster_result, sap_hana_sr_result]
            ):
                error_messages = [
                    result["error"]
                    for result in [cluster_result, sap_hana_sr_result]
                    if "error" in result
                ]
                module.fail_json(msg=", ".join(error_messages))
            module.exit_json(
                msg=f"No drift parameters found. This list of validated parameters: "
                + f"{cluster_result['msg']}, {sap_hana_sr_result['msg']}"
            )

    elif action == "visualize":
        if xml_file is None:
            module.fail_json(msg="XML file path is required for visualization.")
        else:
            result = visualize_cluster_actions(xml_file)
            if "error" in result:
                module.fail_json(msg=result["error"])
            module.exit_json(changed=True, msg=result["msg"])


if __name__ == "__main__":
    main()
