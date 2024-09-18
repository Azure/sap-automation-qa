#!/usr/bin/python
import subprocess
import json
from collections import defaultdict
import xml.etree.ElementTree as ET
from ansible.module_utils.basic import AnsibleModule


CLUSTER_PROPERTIES_SUSE = {
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
        "vip_": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
            "resource-stickiness": "0",
        },
    },
}

CLUSTER_PROPERTIES_REDHAT = {
    "crm_config": {
        "cib-bootstrap-options": {
            "have-watchdog": "false",
            "cluster-infrastructure": "corosync",
            "stonith-enabled": "true",
            "concurrent-fencing": "true",
            "stonith-timeout": "900",
            "maintenance-mode": "false",
            "azure-events_globalPullState": "IDLE",
            "priority-fencing-delay": "15s",
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
    "constraints": {
        "rsc_colocation": {
            "score": "4000",
            "rsc-role": "Started",
        },
        "rsc_order": {
            "first-action": "start",
            "then-action": "start",
        },
    },
    "resources": {
        "SAPHanaTopology": {
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "SID": "SID",
            "InstanceNumber": "XX",
            "InstanceNumber": "00",
            "monitor-interval": "10",
            "monitor-timeout": "600",
            "start-interval": "0s",
            "start-timeout": "600",
            "stop-interval": "0s",
            "stop-timeout": "300",
        },
        "SAPHana_": {
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
            "start-interval": "0s",
            "start-timeout": "3600",
            "stop-interval": "0s",
            "stop-timeout": "3600",
            "promote-interval": "0s",
            "promote-timeout": "3600",
            "monitor-Master-interval": "59",
            "monitor-Master-timeout": "700",
            "monitor-Slave-interval": "61",
            "monitor-Slave-timeout": "700",
            "demote-interval": "0s",
            "demote-timeout": "3600",
        },
        "rsc_st_azure": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15s",
            "monitor-interval": "3600",
        },
        "health-azure-events": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "vip_": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
    },
}

OS_PARAMETERS = {
    "sysctl": {
        "net.ipv4.tcp_timestamps": {"expected_value": "1"},
        "vm.swappiness": {"expected_value": "10"},
    },
    "corosync-cmapctl -g": {
        "runtime.config.totem.token": {"expected_value": "30000"},
        "runtime.config.totem.consensus": {"expected_value": "36000"},
    },
}

REQUIRED_PARAMETERS = {
    "priority-fencing-delay",
}


def define_custom_parameters(module_params, cluster_properties):
    """Get custom value for certain parameters depending on user input and OS family

    Args:
        module_params (dict): Ansible module parameters
        cluster_properties (dict): Dictionary of cluster properties

    Returns:
        str: Value of the key from the custom dictionary
    """
    if module_params.get("ansible_os_family") == "SUSE":
        cluster_properties["resources"]["msl_SAPHana"]["SID"] = module_params.get("sid")
        cluster_properties["resources"]["msl_SAPHana"]["InstanceNumber"] = (
            module_params.get("instance_number")
        )
        cluster_properties["resources"]["cln_SAPHanaTopology"]["SID"] = (
            module_params.get("sid")
        )
        cluster_properties["resources"]["cln_SAPHanaTopology"]["InstanceNumber"] = (
            module_params.get("instance_number")
        )
    else:
        cluster_properties["resources"]["SAPHana_"]["SID"] = module_params.get("sid")
        cluster_properties["resources"]["SAPHana_"]["InstanceNumber"] = (
            module_params.get("instance_number")
        )
        cluster_properties["resources"]["SAPHanaTopology"]["SID"] = module_params.get(
            "sid"
        )
        cluster_properties["resources"]["SAPHanaTopology"]["InstanceNumber"] = (
            module_params.get("instance_number")
        )
    return cluster_properties


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
        if ET.fromstring(xml_output).find(".//rsc_location") is not None:
            health_location = ET.fromstring(xml_output).find(
                ".//rsc_location[@rsc-pattern='!health-.*']"
            )
            if health_location is None:
                return ET.fromstring(xml_output).find(".//rsc_location")
        return False
    except subprocess.CalledProcessError:
        return False


def validate_os_parameters(SID: str, ansible_os_family: str):
    """Validate SAP OS parameters.

    Args:
        SID (str): Database SID
        ansible_os_family (str): Ansible OS family

    Returns:
        dict: SAP VM Parameters
    """
    try:
        drift_parameters = {}
        validated_parameters = {}
        for stack_name, stack_details in OS_PARAMETERS.items():
            for parameter, details in stack_details.items():
                with subprocess.Popen(
                    [stack_name, parameter], stdout=subprocess.PIPE, encoding="utf-8"
                ) as proc:
                    output = proc.stdout.read()
                    parameter_value = output.split("=")[1].strip()
                    if parameter_value != details["expected_value"]:
                        drift_parameters[parameter] = parameter_value
                    else:
                        validated_parameters[parameter] = parameter_value
        if drift_parameters:
            return {
                "msg": {
                    "SAP OS parameters with drift": drift_parameters,
                    "SAP OS parameters": validated_parameters,
                },
                "status": "FAILED",
            }

        return {
            "msg": {"SAP OS Parameters": validated_parameters},
            "status": "PASSED",
        }
    except Exception as e:
        return {
            "msg": {"SAP OS Parameters validation failed": str(e)},
            "status": "FAILED",
        }


def validate_global_ini_properties(SID: str, ansible_os_family: str):
    """Validate SAPHanaSR properties in global.ini file.

    Args:
        SID (str): Database SID
        anible_os_family (str): Ansible OS family

    Returns:
        dict: SAPHanaSR Properties
    """
    try:
        global_ini_file_path = f"/usr/sap/{SID}/SYS/global/hdb/custom/config/global.ini"
        with open(global_ini_file_path, "r") as file:
            global_ini = [line.strip() for line in file.readlines()]

        ha_dr_provider_SAPHnaSR = global_ini.index("[ha_dr_provider_SAPHanaSR]")
        ha_dr_provider_SAPHnaSR_properties = global_ini[
            ha_dr_provider_SAPHnaSR + 1 : ha_dr_provider_SAPHnaSR + 4
        ]
        ha_dr_provider_SAPHanaSR_dict = {
            prop.split("=")[0].strip(): prop.split("=")[1].strip()
            for prop in ha_dr_provider_SAPHnaSR_properties
        }

        expected_properties = {
            "SUSE": {
                "provider": "SAPHanaSR",
                "path": "/usr/share/SAPHanaSR",
                "execution_order": "1",
            },
            "REDHAT": {
                "provider": "SAPHanaSR",
                "path": "/hana/shared/myHooks",
                "execution_order": "1",
            },
        }

        if ha_dr_provider_SAPHanaSR_dict == expected_properties[ansible_os_family]:
            return {
                "msg": {"SAPHanaSR Properties": ha_dr_provider_SAPHanaSR_dict},
                "status": "PASSED",
            }
        else:
            return {
                "msg": {
                    "SAPHanaSR Properties validation failed with the expected properties. ": ha_dr_provider_SAPHanaSR_dict
                },
                "status": "FAILED",
            }
    except FileNotFoundError as e:
        return {
            "msg": {"Exception raised, file not found error": str(e)},
            "status": "FAILED",
        }
    except Exception as e:
        return {
            "msg": {"SAPHanaSR Properties validation failed": f"{str(e)} {global_ini}"},
            "status": "FAILED",
        }


def validate_cluster_params(cluster_properties: dict, ansible_os_family: str):
    """Validate pacemaker cluster parameters for DB and SCS

    Args:
        cluster_properties (dict): Dictionary of recommended values of cluster properties
        ansible_os_family (str): Ansible OS family
    Returns:
        dict: Validated cluster parameters
    """
    try:
        drift_parameters = defaultdict(lambda: defaultdict(list))
        valid_parameters = defaultdict(lambda: defaultdict(list))

        for resource_operation, _ in cluster_properties.items():
            with subprocess.Popen(
                ["cibadmin", "--query", "--scope", f"{resource_operation}"],
                stdout=subprocess.PIPE,
                encoding="utf-8",
            ) as proc:
                xml_output = proc.stdout.read()
            # check if xml_output is empty of not xml output
            if not xml_output.startswith("<"):
                continue
            root = ET.fromstring(xml_output)

            for root_element in root:
                root_id = root_element.get("id")
                extracted_values = {root_id: {}}

                # Extract nvpair parameters and their values from XML
                extracted_values[root_id] = {
                    nvpair.get("name"): nvpair.get("value")
                    for nvpair in root_element.findall(".//nvpair")
                }

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
                for key in cluster_properties[resource_operation].keys():
                    if root_id.startswith(key):
                        recommended_for_root = cluster_properties[resource_operation][
                            key
                        ]
                        for name, value in extracted_values[root_id].items():
                            if name in recommended_for_root:
                                if value != recommended_for_root.get(name):
                                    drift_parameters[resource_operation][
                                        root_id
                                    ].append(f"{name}: {value}")
                                else:
                                    valid_parameters[resource_operation][
                                        root_id
                                    ].append(f"{name}: {value}")
        valid_parameters_json = json.dumps(valid_parameters)
        missing_parameters = [
            parameter
            for parameter in REQUIRED_PARAMETERS
            if parameter not in valid_parameters_json
        ]
        if missing_parameters:
            return {
                "msg": {
                    "Required parameters missing in cluster parameters": missing_parameters,
                    "Validated cluster parameters": valid_parameters,
                },
                "status": "WARNING",
            }

        location_constraints = location_constraints_exists()
        error_messages = []
        if drift_parameters:
            error_messages.append({"Drift in cluster parameters": drift_parameters})

        if location_constraints:
            error_messages.append(
                {"Location constraints detected": location_constraints}
            )
        if error_messages:
            return {
                "msg": {
                    "Validated cluster parameters": valid_parameters,
                    "Errors": error_messages,
                },
                "status": "FAILED",
            }

        return {
            "msg": {"Validated cluster parameters": valid_parameters},
            "status": "PASSED",
        }

    except subprocess.CalledProcessError as e:
        return {"error": str(e), "status": "FAILED"}


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
            xml_file=dict(type="str"),
            sid=dict(type="str"),
            instance_number=dict(type="str"),
            ansible_os_family=dict(type="str"),
        )
    )
    action = module.params["action"]
    xml_file = module.params.get("xml_file")
    ansible_os_family = module.params.get("ansible_os_family")
    cluster_properties = (
        CLUSTER_PROPERTIES_SUSE
        if ansible_os_family == "SUSE"
        else CLUSTER_PROPERTIES_REDHAT
    )

    custom_cluster_properties = define_custom_parameters(
        module.params, cluster_properties
    )

    if action == "get":
        cluster_result = validate_cluster_params(
            cluster_properties=custom_cluster_properties,
            ansible_os_family=ansible_os_family,
        )
        sap_hana_sr_result = validate_global_ini_properties(
            SID=module.params.get("sid"), ansible_os_family=ansible_os_family
        )
        os_parameters_result = validate_os_parameters(
            SID=module.params.get("sid"), ansible_os_family=ansible_os_family
        )
        cluster_result_msg = cluster_result["msg"]
        sap_hana_sr_result_msg = sap_hana_sr_result["msg"]
        os_parameters_result_msg = os_parameters_result["msg"]
        module.exit_json(
            msg="Cluster parameters validation completed",
            details={
                **cluster_result_msg,
                **sap_hana_sr_result_msg,
                **os_parameters_result_msg,
            },
            status=(
                "PASSED"
                if cluster_result["status"] == "PASSED"
                and sap_hana_sr_result["status"] == "PASSED"
                and os_parameters_result["status"] == "PASSED"
                else "FAILED"
            ),
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
