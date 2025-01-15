# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the cluster configuration in HANA DB node.
"""
import subprocess
import json
from collections import defaultdict
import xml.etree.ElementTree as ET
from ansible.module_utils.basic import AnsibleModule
from src.library.constants import (
    SUCCESS_STATUS,
    ERROR_STATUS,
    WARNING_STATUS,
    CLUSTER_PROPERTIES,
    CLUSTER_RESOURCES,
    OS_PARAMETERS,
    CUSTOM_OS_PARAMETERS,
    REQUIRED_PARAMETERS,
    CONSTRAINTS,
    PARAMETER_VALUE_FORMAT,
)

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
        SID (str): Database SID
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


def validate_resource_parameters(
    ansible_os_family: str, drift_parameters: dict, valid_parameters: dict
):
    """Validate resource parameters.

    Args:
        ansible_os_family (str): Ansible OS family
        drift_parameters (dict): Dictionary to store drift parameters
        valid_parameters (dict): Dictionary to store valid parameters
    """
    resource_mapping = {}
    root = parse_xml_output(["cibadmin", "--query", "--scope", "resources"])
    for primitive in root.findall(".//primitive"):
        resource_id = primitive.get("id")
        resource_class = primitive.get("class")
        resource_provider = primitive.get("provider", "")
        resource_type = primitive.get("type")
        properties = {
            prop.get("name"): prop.get("value")
            for prop in primitive.findall(".//nvpair")
        }

        if resource_provider:
            resource_full_type = f"{resource_class}:{resource_provider}:{resource_type}"
        else:
            resource_full_type = f"{resource_class}:{resource_type}"

        resource_mapping[resource_full_type] = resource_id

    for resource_type, resource_id in resource_mapping.items():
        expected_attributes = CLUSTER_RESOURCES[ansible_os_family].get(
            resource_type, {}
        )
        actual_attributes = {}

        primitive = root.find(f".//primitive[@id='{resource_id}']")
        if primitive is not None:
            for prop in primitive.findall(".//nvpair"):
                actual_attributes[prop.get("name")] = prop.get("value")

            for op in primitive.findall(".//op"):
                name = (
                    f"{op.get('name')}-{op.get('role', 'NoRole')}-interval"
                    if op.get("role")
                    else f"{op.get('name')}-interval"
                )
                actual_attributes[name] = op.get("interval")
                name = (
                    f"{op.get('name')}-{op.get('role', 'NoRole')}-timeout"
                    if op.get("role")
                    else f"{op.get('name')}-timeout"
                )
                actual_attributes[name] = op.get("timeout")
        for name, value in actual_attributes.items():
            if name in expected_attributes:
                if value != expected_attributes[name]:
                    drift_parameters["resources"][resource_id].append(
                        PARAMETER_VALUE_FORMAT
                        % (
                            name,
                            value,
                            expected_attributes[name],
                        )
                    )
                else:
                    valid_parameters["resources"][resource_id].append(
                        PARAMETER_VALUE_FORMAT
                        % (
                            name,
                            value,
                            expected_attributes[name],
                        )
                    )


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


def validate_cluster_params(ansible_os_family: str):
    """Validate pacemaker cluster parameters for DB and SCS

    Args:
        ansible_os_family (str): Ansible OS family
    Returns:
        dict: Validated cluster parameters
    """
    drift_parameters = defaultdict(lambda: defaultdict(list))
    valid_parameters = defaultdict(lambda: defaultdict(list))
    try:
        for resource_operation in CLUSTER_PROPERTIES.keys():
            root = parse_xml_output(
                ["cibadmin", "--query", "--scope", resource_operation]
            )
            if root is not None:
                for root_element in root:
                    primitive_id = root_element.get("id")
                    extracted_values = {
                        primitive_id: {
                            nvpair.get("name"): nvpair.get("value")
                            for nvpair in root_element.findall(".//nvpair")
                        }
                    }
                    recommended_for_primitive = CLUSTER_PROPERTIES[
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
        validate_resource_parameters(
            ansible_os_family, drift_parameters, valid_parameters
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


def run_module():
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
    if action == "get":
        cluster_result = validate_cluster_params(
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
        try:
            module.exit_json(
                msg="Cluster parameters validation completed",
                details={
                    **cluster_result.get("msg", {}),
                    **sap_hana_sr_result.get("msg", {}),
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
                            sap_hana_sr_result,
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
    elif action == "visualize":
        if xml_file is None:
            module.fail_json(msg="XML file path is required for visualization.")
        else:
            result = visualize_cluster_actions(xml_file)
            if "error" in result:
                module.fail_json(msg=result["error"])
            module.exit_json(changed=True, msg=result["msg"])


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
