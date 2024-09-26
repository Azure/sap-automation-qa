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
            "resource-stickiness": "1",
            "migration-threshold": "3",
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
        "rsc_st_azure": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "pcmk_monitor_timeout": "120",
            "monitor-timeout": "120",
            "stop-interval": "0s",
            "stop-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
        },
        "health-azure-events": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "nc_SID_ASCS": {
            "monitor-interval": "10",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "vip_SID_ASCS": {
            "monitor-interval": "10",
            "monitor-timeout": "20",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "rsc_sapstartsrv_SID_ASCS_IN": {
            "monitor-interval": "120s",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "60s",
            "stop-interval": "0s",
            "stop-timeout": "60s",
        },
        "rsc_sap_SID_ASCS_IN": {
            "AUTOMATIC_RECOVER": "false",
            "MINIMAL_PROBE": "true",
            "resource-stickiness": "5000",
            "priority": "100",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
        "nc_SID_ERS": {
            "port": "62010",
            "monitor-interval": "10",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "vip_SID_ERS": {
            "monitor-interval": "10",
            "monitor-timeout": "20",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "rsc_sapstartsrv_SID_ERS_IN": {
            "monitor-interval": "120s",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "60s",
            "stop-interval": "0s",
            "stop-timeout": "60s",
        },
        "rsc_sap_SID_ERS_IN": {
            "AUTOMATIC_RECOVER": "false",
            "IS_ERS": "true",
            "MINIMAL_PROBE": "true",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
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
            "resource-stickiness": "1",
            "migration-threshold": "3",
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
        "rsc_st_azure": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "pcmk_monitor_timeout": "120",
            "monitor-timeout": "120",
            "stop-interval": "0s",
            "stop-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
        },
        "health-azure-events": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "nc_SID_ASCS": {
            "monitor-interval": "10",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "vip_SID_ASCS": {
            "monitor-interval": "10",
            "monitor-timeout": "20",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "rsc_sapstartsrv_SID_ASCS_IN": {
            "monitor-interval": "120s",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "60s",
            "stop-interval": "0s",
            "stop-timeout": "60s",
        },
        "rsc_sap_SID_ASCS_IN": {
            "AUTOMATIC_RECOVER": "false",
            "MINIMAL_PROBE": "true",
            "resource-stickiness": "5000",
            "priority": "100",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
        "nc_SID_ERS": {
            "port": "62010",
            "monitor-interval": "10",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "vip_SID_ERS": {
            "monitor-interval": "10",
            "monitor-timeout": "20",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "rsc_sapstartsrv_SID_ERS_IN": {
            "monitor-interval": "120s",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "60s",
            "stop-interval": "0s",
            "stop-timeout": "60s",
        },
        "rsc_sap_SID_ERS_IN": {
            "AUTOMATIC_RECOVER": "false",
            "IS_ERS": "true",
            "MINIMAL_PROBE": "true",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
    },
}

OS_PARAMETERS = {
    "REDHAT": {
        "sysctl": {
            "net.ipv4.tcp_timestamps": {"expected_value": "1"},
            "vm.swappiness": {"expected_value": "10"},
        },
        "corosync-cmapctl": {
            "runtime.config.totem.token": {"expected_value": "30000"},
            "runtime.config.totem.consensus": {"expected_value": "36000"},
        },
    },
    "SUSE": {
        "sysctl": {
            "net.ipv4.tcp_timestamps": {"expected_value": "1"},
            "vm.swappiness": {"expected_value": "10"},
        },
        "corosync-cmapctl": {
            "runtime.config.totem.token": {"expected_value": "30000"},
            "runtime.config.totem.consensus": {"expected_value": "36000"},
            "quorum.expected_votes": {"expected_value": "2"},
        },
    },
}

CUSTOM_OS_PARAMETERS = {
    "REDHAT": {
        "quorum.expected_votes": {
            "expected_value": "2",
            "parameter_name": "Expected votes",
            "command": ["pcs", "quorum", "status"],
        },
    },
    "SUSE": {},
}

REQUIRED_PARAMETERS = {
    "priority-fencing-delay",
}

CONSTRAINTS = {
    "rsc_colocation": {
        "score": "-5000",
        "rsc-role": "Started",
        "with-rsc-role": "Promoted",
    },
    "rsc_order": {
        "first-action": "start",
        "then-action": "stop",
        "symmetrical": "false",
    },
    "rsc_location": {
        "score-attribute": "#health-azure",
        "operation": "defined",
        "attribute": "#uname",
    },
}

PARAMETER_VALUE_FORMAT = "Name: %s, Value: %s, Expected Value: %s"


def run_subprocess(command):
    """Run a subprocess command and return the output.

    Args:
        command (list[str]): The command to run.

    Returns:
        output: The output of the command.
    """
    try:
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        ) as proc:
            return proc.stdout.read()
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
    ascs_instance_number = module_params.get("ascs_instance_number")
    ers_instance_number = module_params.get("ers_instance_number")
    for props, details in list(cluster_properties["resources"].items()):
        new_props = props
        if "SID" in props:
            new_props = new_props.replace("SID", sid)

        if "ASCS" in props and "_IN" in props:
            new_props = new_props.replace("_IN", ascs_instance_number)
        elif "ERS" in props and "_IN" in props:
            new_props = new_props.replace("_IN", ers_instance_number)

        cluster_properties["resources"][new_props] = details
        if new_props != props:
            del cluster_properties["resources"][props]
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
        msi_value = None
        if ansible_os_family == "REDHAT":
            stonith_config = json.loads(
                run_subprocess(
                    command=["pcs", "stonith", "config", "--output-format=json"]
                )
            )
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
        elif ansible_os_family == "SUSE":
            stonith_device_name = run_subprocess(
                command=["stonith_admin", "--list-registered"]
            ).splitlines()[0]
            msi_value = run_subprocess(
                command=[
                    "crm_resource",
                    "--resource",
                    f"{stonith_device_name}",
                    "--get-parameter",
                    "msi",
                ]
            )

        if msi_value and msi_value.strip().lower() == "true":
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
        SID (str): SID
        ansible_os_family (str): Ansible OS family

    Returns:
        dict: SAP VM Parameters
    """
    drift_parameters = []
    validated_parameters = []
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
                drift_parameters.append(
                    PARAMETER_VALUE_FORMAT
                    % (parameter, parameter_value, details["expected_value"])
                )
            else:
                validated_parameters.append(
                    PARAMETER_VALUE_FORMAT
                    % (parameter, parameter_value, details["expected_value"])
                )

        for stack_name, stack_details in OS_PARAMETERS[ansible_os_family].items():
            base_args = (
                ["sysctl"] if stack_name == "sysctl" else ["corosync-cmapctl", "-g"]
            )
            for parameter, details in stack_details.items():
                output = run_subprocess(base_args + [parameter])
                parameter_value = output.split("=")[1].strip()
                if parameter_value != details["expected_value"]:
                    drift_parameters.append(
                        PARAMETER_VALUE_FORMAT
                        % (parameter, parameter_value, details["expected_value"])
                    )
                else:
                    validated_parameters.append(
                        PARAMETER_VALUE_FORMAT
                        % (parameter, parameter_value, details["expected_value"])
                    )

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
        SID (str):  SID
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
                                    PARAMETER_VALUE_FORMAT
                                    % (
                                        key,
                                        value,
                                        cluster_properties[constraint_type][key],
                                    )
                                )
                            else:
                                valid_parameters[constraint_type][constraint_id].append(
                                    PARAMETER_VALUE_FORMAT
                                    % (
                                        key,
                                        value,
                                        cluster_properties[constraint_type][key],
                                    )
                                )
                    for child in constraint:
                        for key, value in child.attrib.items():
                            if key in cluster_properties[constraint_type]:
                                if value != cluster_properties[constraint_type][key]:
                                    drift_parameters[constraint_type][
                                        constraint_id
                                    ].append(
                                        PARAMETER_VALUE_FORMAT
                                        % (
                                            key,
                                            value,
                                            cluster_properties[constraint_type][key],
                                        )
                                    )
                                else:
                                    valid_parameters[constraint_type][
                                        constraint_id
                                    ].append(
                                        PARAMETER_VALUE_FORMAT
                                        % (
                                            key,
                                            value,
                                            cluster_properties[constraint_type][key],
                                        )
                                    )
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
                root_elements = (
                    root.findall(".//primitive") if root.tag == "resources" else [root]
                )
                for root_element in root_elements:
                    primitive_id = root_element.get("id")
                    extracted_values = {
                        primitive_id: {
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
                        extracted_values[primitive_id][name] = op.get("interval")
                        name = (
                            f"{op.get('name')}-{op.get('role', 'NoRole')}-timeout"
                            if op.get("role")
                            else f"{op.get('name')}-timeout"
                        )
                        extracted_values[primitive_id][name] = op.get("timeout")
                    recommended_for_primitive = cluster_properties[
                        resource_operation
                    ].get(primitive_id, {})
                    for name, value in extracted_values[primitive_id].items():
                        if name in recommended_for_primitive:
                            if value != recommended_for_primitive[name]:
                                drift_parameters[resource_operation][
                                    primitive_id
                                ].append(
                                    PARAMETER_VALUE_FORMAT
                                    % (
                                        name,
                                        value,
                                        recommended_for_primitive[name],
                                    )
                                )
                            else:
                                valid_parameters[resource_operation][
                                    primitive_id
                                ].append(
                                    PARAMETER_VALUE_FORMAT
                                    % (
                                        name,
                                        value,
                                        recommended_for_primitive[name],
                                    )
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
        if drift_parameters:
            return {
                "msg": {
                    "Validated cluster parameters": valid_parameters,
                    "Drift in cluster parameters": drift_parameters,
                },
                "status": ERROR_STATUS,
            }
        return {
            "msg": {"Validated cluster parameters": valid_parameters},
            "status": SUCCESS_STATUS,
        }
    except Exception as e:
        return {"msg": {"Error message": str(e)}, "status": ERROR_STATUS}


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
    cluster_result = validate_cluster_params(
        cluster_properties=custom_cluster_properties,
        ansible_os_family=ansible_os_family,
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
    try:
        module.exit_json(
            msg="Cluster parameters validation completed",
            details={
                **cluster_result.get("msg", {}),
                **os_parameters_result.get("msg", {}),
                **fence_azure_arm_result.get("msg", {}),
                **constraints.get("msg", {}),
            },
            status=(
                SUCCESS_STATUS
                if all(
                    result["status"] == SUCCESS_STATUS
                    for result in [
                        cluster_result,
                        os_parameters_result,
                        fence_azure_arm_result,
                        constraints,
                    ]
                )
                else ERROR_STATUS
            ),
        )
    except Exception as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
