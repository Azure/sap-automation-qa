#!/usr/bin/python
import subprocess
import json
from collections import defaultdict
import xml.etree.ElementTree as ET
from ansible.module_utils.basic import AnsibleModule

SUCCESS_STATUS = "PASSED"
ERROR_STATUS = "FAILED"
WARNING_STATUS = "WARNING"

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
            "pcmk_monitor_timeout": "120",
        },
        "health-azure-events": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "g_ip_": {
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
            "pcmk_monitor_timeout": "120",
        },
        "health-azure-events": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "g_ip_": {
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
    "corosync-cmapctl": {
        "runtime.config.totem.token": {"expected_value": "30000"},
        "runtime.config.totem.consensus": {"expected_value": "36000"},
    },
}

CUSTOM_OS_PARAMETERS = {
    "REDHAT": {
        "quorum.expected_votes": {
            "expected_value": "2",
            "parameter_name": "Expected votes",
            "command": ["pcs", "quorum", "status"],
        },
    }
}

REQUIRED_PARAMETERS = {
    "priority-fencing-delay",
}

CONSTRAINTS = {
    "rsc_colocation": {
        "score": "4000",
        "rsc-role": "Started",
        "with-rsc-role": "Promoted",
    },
    "rsc_order": {
        "first-action": "start",
        "then-action": "start",
        "symmetrical": "false",
    },
    "rsc_location": {
        "score-attribute": "#health-azure",
        "operation": "defined",
        "attribute": "#uname",
    },
}


def run_subprocess(command):
    """Run a subprocess command and return the output.

    Args:
        command (list[str]): The command to run.

    Returns:
        output: The output of the command.
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return str(e)


def parse_xml_output(command):
    """Parse the XML output of a command.

    Args:
        command (list[str]): The command to run.

    Returns:
        xml: The parsed XML output.
    """
    xml_output = run_subprocess(command)
    if xml_output.startswith("<"):
        return ET.fromstring(xml_output)
    return None


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
        root = parse_xml_output(["cibadmin", "--query", "--scope", "constraints"])
        if root is not None:
            if root.find(".//rsc_location") is not None:
                health_location = root.find(
                    ".//rsc_location[@rsc-pattern='!health-.*']"
                )
                if health_location is None:
                    return root.find(".//rsc_location")
        return False
    except Exception as ex:
        return False


def define_custom_parameters(module_params, cluster_properties):
    """Get custom value for certain parameters depending on user input and OS family

    Args:
        module_params (dict): Ansible module parameters
        cluster_properties (dict): Dictionary of cluster properties

    Returns:
        str: Value of the key from the custom dictionary
    """
    os_family = module_params.get("ansible_os_family")
    sid = module_params.get("sid")
    instance_number = module_params.get("instance_number")
    if os_family == "SUSE":
        cluster_properties["resources"]["msl_SAPHana"]["SID"] = sid
        cluster_properties["resources"]["msl_SAPHana"][
            "InstanceNumber"
        ] = instance_number
        cluster_properties["resources"]["cln_SAPHanaTopology"]["SID"] = sid
        cluster_properties["resources"]["cln_SAPHanaTopology"][
            "InstanceNumber"
        ] = instance_number
    else:
        cluster_properties["resources"]["SAPHana_"]["SID"] = sid
        cluster_properties["resources"]["SAPHana_"]["InstanceNumber"] = instance_number
        cluster_properties["resources"]["SAPHanaTopology"]["SID"] = sid
        cluster_properties["resources"]["SAPHanaTopology"][
            "InstanceNumber"
        ] = instance_number
    return cluster_properties


def validate_fence_azure_arm(ansible_os_family: str, virtual_machine_name: str):
    """
    Validate the permissions of the fence agent in Azure ARM.

    Args:
        ansible_os_family (str): Ansible OS family
        virtual_machine_name (str): Virtual machine name

    Returns:
        dict: Fence agent permissions
    """
    try:
        command = (
            ["crm", "stonith", "config", "--output-format=json"]
            if ansible_os_family == "SUSE"
            else ["pcs", "stonith", "config", "--output-format=json"]
        )
        stonith_config = json.loads(run_subprocess(command))
        msi_value = next(
            (
                nvpair.get("value")
                for nvpair in stonith_config.get("primitives", [])[0]
                .get("instance_attributes", [])[0]
                .get("nvpairs", [])
                if nvpair.get("name") == "msi"
            ),
            None,
        )
        if msi_value and msi_value.lower() == "true":
            fence_azure_arm_output = run_subprocess(
                ["fence_azure_arm", "--msi", "--action=list"]
            )
            if "Error" in fence_azure_arm_output:
                return {
                    "msg": {"Fence agent permissions": fence_azure_arm_output},
                    "status": ERROR_STATUS,
                }
            if virtual_machine_name in fence_azure_arm_output:
                return {
                    "msg": {"Fence agent permissions": fence_azure_arm_output},
                    "status": SUCCESS_STATUS,
                }
            return {
                "msg": {
                    "Fence agent permissions": f"The virtual machine is not found "
                    + f"in the list of virtual machines {fence_azure_arm_output}"
                },
                "status": ERROR_STATUS,
            }
        return {
            "msg": {
                "Fence agent permissions": "MSI value not found or the stonith is configured using SPN."
            },
            "status": SUCCESS_STATUS,
        }
    except json.JSONDecodeError as e:
        return {"msg": {"Fence agent permissions": str(e)}, "status": "FAILED"}
    except Exception as e:
        return {"msg": {"Fence agent permissions": str(e)}, "status": "FAILED"}


def validate_os_parameters(SID: str, ansible_os_family: str):
    """Validate SAP OS parameters.

    Args:
        SID (str): Database SID
        ansible_os_family (str): Ansible OS family

    Returns:
        dict: SAP VM Parameters
    """
    drift_parameters = {}
    validated_parameters = {}
    try:
        for parameter, details in CUSTOM_OS_PARAMETERS[ansible_os_family].items():
            output = run_subprocess(details["command"]).splitlines()
            parameter_value = next(
                (
                    line.split(":")[1].strip()
                    for line in output
                    if details["parameter_name"] in line
                ),
                None,
            )
            if parameter_value != details["expected_value"]:
                drift_parameters[parameter] = parameter_value
            else:
                validated_parameters[parameter] = parameter_value

        for stack_name, stack_details in OS_PARAMETERS.items():
            base_args = (
                ["sysctl"] if stack_name == "sysctl" else ["corosync-cmapctl", "-g"]
            )
            for parameter, details in stack_details.items():
                output = run_subprocess(base_args + [parameter])
                parameter_value = output.split("=")[1].strip()
                if parameter_value != details["expected_value"]:
                    drift_parameters[parameter] = parameter_value
                else:
                    validated_parameters[parameter] = parameter_value

        if drift_parameters:
            return {
                "msg": {
                    "Drift OS and Corosync Parameters": drift_parameters,
                    "Validated OS and Corosync Parameters": validated_parameters,
                },
                "status": ERROR_STATUS,
            }
        return {
            "msg": {"Validated OS and Corosync Parameters": validated_parameters},
            "status": SUCCESS_STATUS,
        }
    except Exception as e:
        return {
            "msg": {"Error OS and Corosync Parameters": str(e)},
            "status": ERROR_STATUS,
        }


def validate_constraints(SID: str, ansible_os_family: str):
    """
    Validate constraints in the pacemaker cluster.

    Args:
        SID (str): Database SID
        ansible_os_family (str): Ansible OS family
    Returns:
        dict: Validated constraints
    """
    drift_parameters = defaultdict(lambda: defaultdict(list))
    valid_parameters = defaultdict(lambda: defaultdict(list))
    try:
        cluster_properties = CONSTRAINTS
        root = parse_xml_output(["cibadmin", "--query", "--scope", "constraints"])
        if root is not None:
            for constraint in root:
                constraint_type = constraint.tag
                if constraint_type in cluster_properties:
                    constraint_id = constraint.attrib.get("id", "")
                    for key, value in constraint.attrib.items():
                        if key in cluster_properties[constraint_type]:
                            if value != cluster_properties[constraint_type][key]:
                                drift_parameters[constraint_type][constraint_id].append(
                                    f"{key}: {value}"
                                )
                            else:
                                valid_parameters[constraint_type][constraint_id].append(
                                    f"{key}: {value}"
                                )
                    for child in constraint:
                        for key, value in child.attrib.items():
                            if key in cluster_properties[constraint_type]:
                                if value != cluster_properties[constraint_type][key]:
                                    drift_parameters[constraint_type][
                                        constraint_id
                                    ].append(f"{key}: {value}")
                                else:
                                    valid_parameters[constraint_type][
                                        constraint_id
                                    ].append(f"{key}: {value}")
        if drift_parameters:
            return {
                "msg": {
                    "Valid Constraints parameters": valid_parameters,
                    "Drift in Constraints parameters": drift_parameters,
                },
                "status": ERROR_STATUS,
            }
        return {
            "msg": {"Valid Constraints parameter": valid_parameters},
            "status": SUCCESS_STATUS,
        }
    except Exception as e:
        return {"msg": {"Constraints validation": str(e)}, "status": ERROR_STATUS}


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
                "status": SUCCESS_STATUS,
            }
        return {
            "msg": {
                "SAPHanaSR Properties validation failed with the expected properties. ": ha_dr_provider_SAPHanaSR_dict
            },
            "status": ERROR_STATUS,
        }
    except FileNotFoundError as e:
        return {
            "msg": {"Exception raised, file not found error": str(e)},
            "status": ERROR_STATUS,
        }
    except Exception as e:
        return {
            "msg": {"SAPHanaSR Properties validation failed": f"{str(e)} {global_ini}"},
            "status": ERROR_STATUS,
        }


def validate_cluster_params(cluster_properties: dict, ansible_os_family: str):
    """Validate pacemaker cluster parameters for DB and SCS

    Args:
        cluster_properties (dict): Dictionary of recommended values of cluster properties
        ansible_os_family (str): Ansible OS family
    Returns:
        dict: Validated cluster parameters
    """
    drift_parameters = defaultdict(lambda: defaultdict(list))
    valid_parameters = defaultdict(lambda: defaultdict(list))
    try:
        for resource_operation in cluster_properties.keys():
            root = parse_xml_output(
                ["cibadmin", "--query", "--scope", resource_operation]
            )
            if root is not None:
                for root_element in root:
                    root_id = root_element.get("id")
                    extracted_values = {
                        root_id: {
                            nvpair.get("name"): nvpair.get("value")
                            for nvpair in root_element.findall(".//nvpair")
                        }
                    }
                    for op in root_element.findall(".//op"):
                        name = (
                            f"{op.get('name')}-{op.get('role', 'NoRole')}-interval"
                            if op.get("role")
                            else f"{op.get('name')}-interval"
                        )
                        extracted_values[root_id][name] = op.get("interval")
                        name = (
                            f"{op.get('name')}-{op.get('role', 'NoRole')}-timeout"
                            if op.get("role")
                            else f"{op.get('name')}-timeout"
                        )
                        extracted_values[root_id][name] = op.get("timeout")
                    recommended_for_root = next(
                        (
                            cluster_properties[resource_operation][key]
                            for key in cluster_properties[resource_operation].keys()
                            if root_id.startswith(key)
                        ),
                        {},
                    )
                    for name, value in extracted_values[root_id].items():
                        if name in recommended_for_root:
                            if value != recommended_for_root[name]:
                                drift_parameters[resource_operation][root_id].append(
                                    f"{name}: {value}"
                                )
                            else:
                                valid_parameters[resource_operation][root_id].append(
                                    f"{name}: {value}"
                                )
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
                "status": WARNING_STATUS,
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
                "status": ERROR_STATUS,
            }
        return {
            "msg": {"Validated cluster parameters": valid_parameters},
            "status": SUCCESS_STATUS,
        }
    except Exception as e:
        return {"Error": str(e), "status": ERROR_STATUS}


def visualize_cluster_actions(xml_file):
    """Visualize cluster actions using crm_simulate.

    Args:
        xml_file (string): XML string
    """
    dot_file = f"{xml_file}.dot"
    try:
        run_subprocess(
            [
                "crm_simulate",
                "--simulate",
                "--xml-file",
                xml_file,
                "--save-dotfile",
                dot_file,
            ]
        )
    except Exception as e:
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
            virtual_machine_name=dict(type="str"),
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
        fence_azure_arm_result = validate_fence_azure_arm(
            ansible_os_family=ansible_os_family,
            virtual_machine_name=module.params.get("virtual_machine_name"),
        )
        constraints = validate_constraints(
            SID=module.params.get("sid"), ansible_os_family=ansible_os_family
        )
        module.exit_json(
            msg="Cluster parameters validation completed",
            details={
                **cluster_result["msg"],
                **sap_hana_sr_result["msg"],
                **os_parameters_result["msg"],
                **fence_azure_arm_result["msg"],
                **constraints["msg"],
            },
            status=(
                SUCCESS_STATUS
                if all(
                    result["status"] == SUCCESS_STATUS
                    for result in [
                        cluster_result,
                        sap_hana_sr_result,
                        os_parameters_result,
                        fence_azure_arm_result,
                        constraints,
                    ]
                )
                else ERROR_STATUS
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
