#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import subprocess
import json
import xml.etree.ElementTree as ET
from datetime import datetime

CLUSTER_DEFAULTS = {
    "crm_config": [
        {
            "cluster_property_set": [
                {
                    "nvpair": {
                        "have-watchdog": '{"DB":"false","SCS":"false"}',
                        "cluster-infrastructure": '{"DB":"corosync","SCS":"corosync"}',
                        "stonith-enabled": '{"DB":"true","SCS":"true"}',
                        "concurrent-fencing": '{"DB":"true","SCS":"true"}',
                        "stonith-timeout": '{"DB":"900s","SCS":"900"}',
                        "maintenance-mode": '{"DB":"false","SCS":"false"}',
                        "azure-events_globalPullState": '{"DB":"IDLE","SCS":"IDLE"}',
                        "priority-fencing-delay": '{"DB":"30","SCS":"30"}',
                    }
                }
            ]
        }
    ],
    "constraints": [
        {
            "rsc_colocation": [{"score": '{"DB":"-5000","SCS":"-5000"}'}],
            "rsc_order": [
                {
                    "kind": '{"DB":"OPTIONAL","SCS":"OPTIONAL"}',
                    "symmetrical": '{"DB":"false","SCS":"false"}',
                    "first-action": '{"DB":"start","SCS":"start"}',
                    "then-action": '{"DB":"stop","SCS":"stop"}',
                }
            ],
        }
    ],
    "rsc_defaults": [
        {
            "meta_attributes": [
                {
                    "nvpair": {
                        "resource-stickiness": '{"DB":"1000","SCS":"1"}',
                        "migration-threshold": '{"DB":"5000","SCS":"3"}',
                        "priority": '{"DB":"1","SCS":"1"}',
                    },
                }
            ]
        }
    ],
    "op_defaults": [
        {
            "meta_attributes": [
                {
                    "nvpair": {
                        "timeout": '{"DB":"600","SCS":"600"}',
                        "record-pending": '{"DB":"true","SCS":"true"}',
                    },
                }
            ]
        }
    ],
    "resources": [
        {
            "primitive": {
                "fence_azure_arm": {
                    "instance_attributes": [
                        {
                            "nvpair": {
                                "pcmk_monitor_retries": '{"DB":"4","SCS":"4"}',
                                "pcmk_action_limit": '{"DB":"3","SCS":"3"}',
                                "power_timeout": '{"DB":"240","SCS":"240"}',
                                "pcmk_reboot_timeout": '{"DB":"900","SCS":"900"}',
                            }
                        }
                    ],
                    "operations": [
                        {
                            "op": {
                                "monitor": '{"interval": "0s"}',
                                "stop": '{"timeout": "20s", "interval": "0s"}',
                                "start": '{"timeout": "20s", "interval": "0s"}',
                            },
                        }
                    ],
                }
            }
        },
        {
            "clone": {
                "meta_attributes": [
                    {
                        "nvpair": {
                            "interleave": '{"DB":"true","SCS":"true"}',
                            "clone-node-max": '{"DB":"1","SCS":"1"}',
                            "target-role": '{"DB":"Started","SCS":"Started"}',
                        }
                    }
                ],
            }
        },
        {
            "master": {
                "meta_attributes": [
                    {
                        "notify": '{"DB":"true"}',
                        "clone-max": '{"DB":"2"}',
                        "clone-node-max": '{"DB":"1"}',
                        "target-role": '{"DB":"Started"}',
                        "interleave": '{"DB":"true"}',
                    }
                ],
                "primitive": {
                    "instance_attributes": [
                        {
                            "nvpair": {
                                "PREFER_SITE_TAKEOVER": '{"DB":"true"}',
                                "DUPLICATE_PRIMARY_TIMEOUT": '{"DB":"7200"}',
                                "AUTOMATED_REGISTER": '{"DB":"true"}',
                            },
                        }
                    ],
                    "operations": [
                        {
                            "op": {
                                "start": '{"interval": "0", "timeout": "3600"}',
                                "stop": '{"interval": "0", "timeout": "3600"}',
                                "promote": '{"interval": "0", "timeout": "3600"}',
                                "demote": '{"timeout": "320", "interval": "0s"}',
                            }
                        }
                    ],
                },
            },
        },
    ],
}

RESOURCES_CLONE_DEFAULTS = {
    "clone": {
        "primitive": [
            {
                "azure-events": {
                    "operations": [
                        {
                            "op": {
                                "monitor": '{"interval": "10s","timeout": "240s"}',
                                "start": '{"interval": "0s","timeout": "10s"}',
                                "stop": '{"interval": "0s","timeout": "10s"}',
                            }
                        }
                    ],
                }
            },
            {
                "SAPHanaTopology": {
                    "operations": [
                        {
                            "op": {
                                "monitor": '{"interval": "10","timeout": "600"}',
                                "start": '{"interval": "0","timeout": "600"}',
                                "stop": '{"interval": "0","timeout": "300"}',
                            }
                        }
                    ],
                }
            },
        ],
    }
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
            key: value
            for prop in ha_dr_provider_SAPHnaSR_properties
            for key, value in [prop.split("=")]
        }

        expected_properties = {
            "provider": "SAPHNASR",
            "path": "/hana/shared/myHooks",
            "execution_order": 1,
        }
        if ha_dr_provider_SAPHanaSR_dict == expected_properties:
            return {"msg": f"SAPHanaSR Properties" + "{ha_dr_provider_SAPHanaSR_dict}."}
        else:
            return {
                "error": f"SAPHanaSR Properties"
                + " the expected properties. {ha_dr_provider_SAPHanaSR_dict}"
            }
    except FileNotFoundError as e:
        return {"error": f"Exception raised, file not found error: {str(e)}"}
    except Exception as e:
        return {
            "error": f"SAPHanaSR Properties validation failed: {str(e)} {global_ini}"
        }


def validate_pacemaker_resource_clone_params(host_type):
    """Validate pacemaker cluster (resources>clone) parameters for DB and SCS

    Args:
        host_type (string): Host type DB or SCS

    Returns:
        success: No drift parameters found. Validated <parameters>
        error: Drift parameters found: <parameters>
    """
    try:
        drift_parameters, valid_parameters = [], []

        def parse_default_data(root_element, data=RESOURCES_CLONE_DEFAULTS, path=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        if key == "azure-events" or key == "SAPHanaTopology":
                            root_element = root.findall(f".//primitive[@type='{key}']")
                            parse_default_data(root_element, value, f"{path}")
                        else:
                            parse_default_data(root_element, value, f"{path}/{key}")
                    else:
                        query_param = (
                            root_element[0].find(
                                f"./{('/').join(path.split('/')[3:])}/[@name='{key}']"
                            )
                            if root_element
                            else None
                        )
                        if query_param is not None:
                            value = json.loads(value)
                            for k, v in value.items():
                                if query_param.attrib.get(k) != v:
                                    drift_parameters.append(key)
                                else:
                                    valid_parameters.append(key)
            elif isinstance(data, list):
                for item in data:
                    parse_default_data(root_element, item, path)

        with subprocess.Popen(
            ["cibadmin", "--query", "--scope", "resources"],
            stdout=subprocess.PIPE,
            encoding="utf-8",
        ) as proc:
            xml_output = proc.stdout.read()
        root = ET.fromstring(xml_output)
        if root is not None:
            parse_default_data(root_element=root)
        if drift_parameters:
            return {"error": f"Resource Parameters: {', '.join(drift_parameters)}"}
        return {"msg": f"Resource Parameters: {', '.join(valid_parameters)}"}

    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


def validate_pacemaker_cluster_params(host_type):
    """Validate pacemaker cluster parameters for DB and SCS

    Args:
        host_type (string): Host type DB or SCS

    Returns:
        success: No drift parameters found. Validated <parameters>
        error: Drift parameters found: <parameters>
    """
    try:
        drift_parameters, valid_parameters = [], []

        for resource_operation, _ in CLUSTER_DEFAULTS.items():
            with subprocess.Popen(
                ["cibadmin", "--query", "--scope", f"{resource_operation}"],
                stdout=subprocess.PIPE,
                encoding="utf-8",
            ) as proc:
                xml_output = proc.stdout.read()
            root = ET.fromstring(xml_output)

            def parse_default_data(data=CLUSTER_DEFAULTS, path=""):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, (dict, list)):
                            parse_default_data(value, f"{path}/{key}")
                        else:
                            query_param = root.find(
                                f"./{('/').join(path.split('/')[2:])}/[@name='{key}']"
                            )
                            if query_param is not None:
                                value = json.loads(value)

                                if query_param.attrib.get("value"):
                                    if (
                                        query_param.attrib.get("value")
                                        != value[host_type]
                                    ):
                                        drift_parameters.append(key)
                                    else:
                                        valid_parameters.append(key)
                                else:
                                    for k, v in value.items():
                                        if query_param.attrib.get(k) != v:
                                            drift_parameters.append(key)
                                        else:
                                            valid_parameters.append(key)
                elif isinstance(data, list):
                    for item in data:
                        parse_default_data(item, path)

            if root is not None:
                parse_default_data()
        if drift_parameters:
            return {"error": f"Cluster Parameters: {', '.join(drift_parameters)}"}
        return {"msg": f"Cluster Parameters: {', '.join(valid_parameters)}"}

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
            database_sid=dict(type="str"),
        )
    )

    action = module.params["action"]
    host_type = module.params.get("host_type")
    xml_file = module.params.get("xml_file")
    database_sid = module.params.get("database_sid")

    if action == "get":
        if location_constraints_exists():
            module.fail_json(changed=False, msg="Location constraints found.")
        else:
            cluster_result = validate_pacemaker_cluster_params(host_type)
            resource_result = validate_pacemaker_resource_clone_params(host_type)
            sap_hana_sr_result = validate_global_ini_properties(DB_SID=database_sid)
            if any(
                "error" in result
                for result in [cluster_result, resource_result, sap_hana_sr_result]
            ):
                error_messages = [
                    result["error"]
                    for result in [cluster_result, resource_result, sap_hana_sr_result]
                    if "error" in result
                ]
                module.fail_json(msg=", ".join(error_messages))
            module.exit_json(
                msg=f"No drift parameters found. This list of validated parameters: "
                + f"{cluster_result['msg']}, {resource_result['msg']}, {sap_hana_sr_result['msg']}"
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
