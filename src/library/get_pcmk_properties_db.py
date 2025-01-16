# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the cluster configuration in HANA DB node.
"""
from enum import Enum
from functools import lru_cache
from typing import Dict, List, Optional, Union, Any
import subprocess
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from ansible.module_utils.basic import AnsibleModule


class Status(Enum):
    SUCCESS = "PASSED"
    ERROR = "FAILED"
    WARNING = "WARNING"


@dataclass
class ValidationResult:
    status: Status
    messages: Dict[str, Any]
    details: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "msg": self.messages,
            "status": self.status.value,
            **(self.details or {}),
        }


SUCCESS_STATUS = "PASSED"
ERROR_STATUS = "FAILED"
WARNING_STATUS = "WARNING"

CLUSTER_RESOURCES = {
    "SUSE": {
        "ocf:heartbeat:SAPHanaTopology": {
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "monitor-interval": "10",
            "monitor-timeout": "600",
            "start-interval": "0",
            "start-timeout": "600",
            "stop-interval": "0",
            "stop-timeout": "300",
        },
        "ocf:heartbeat:SAPHana": {
            "notify": "true",
            "clone-max": "2",
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
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
        "stonith:fence_azure_arm": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "monitor-timeout": "120",
        },
        "ocf:heartbeat:azure-events-az": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "ocf:heartbeat:azure-lb": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
            "resource-stickiness": "0",
        },
        "ocf:heartbeat:IPaddr2": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
    },
    "REDHAT": {
        "ocf:heartbeat:SAPHanaTopology": {
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "monitor-interval": "10",
            "monitor-timeout": "600",
            "start-interval": "0s",
            "start-timeout": "600",
            "stop-interval": "0s",
            "stop-timeout": "300",
        },
        "ocf:heartbeat:SAPHana": {
            "notify": "true",
            "clone-max": "2",
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
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
        "stonith:fence_azure_arm": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15s",
            "monitor-interval": "3600",
            "pcmk_monitor_timeout": "120",
        },
        "ocf:heartbeat:azure-events-az": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "ocf:heartbeat:azure-lb": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
        "ocf:heartbeat:IPaddr2": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
    },
}
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

PARAMETER_VALUE_FORMAT = "Name: %s, Value: %s, Expected Value: %s"


class CommandExecutor:
    @staticmethod
    def run_subprocess(command: Union[List[str], str]) -> str:
        try:
            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                encoding="utf-8",
            ) as proc:
                return proc.stdout.read()
        except subprocess.CalledProcessError as e:
            return str(e)

    @classmethod
    def parse_xml_output(cls, command: List[str]) -> Optional[ET.Element]:
        xml_output = cls.run_subprocess(command)
        if xml_output.startswith("<"):
            return ET.fromstring(xml_output)
        return None


class ClusterValidator:
    def __init__(self, ansible_os_family: str, sid: str, virtual_machine_name: str):
        self.ansible_os_family = ansible_os_family
        self.sid = sid
        self.vm_name = virtual_machine_name
        self.cmd_executor = CommandExecutor()

    def _get_msi_value(self) -> Optional[str]:
        if self.ansible_os_family == "REDHAT":
            stonith_config = json.loads(
                self.cmd_executor.run_subprocess(
                    ["pcs", "stonith", "config", "--output-format=json"]
                )
            )
            return next(
                (
                    nvpair.get("value")
                    for nvpair in stonith_config.get("primitives", [])[0]
                    .get("instance_attributes", [])[0]
                    .get("nvpairs", [])
                    if nvpair.get("name") == "msi"
                ),
                None,
            )
        elif self.ansible_os_family == "SUSE":
            stonith_device_name = self.cmd_executor.run_subprocess(
                ["stonith_admin", "--list-registered"]
            ).splitlines()[0]
            return self.cmd_executor.run_subprocess(
                [
                    "crm_resource",
                    "--resource",
                    stonith_device_name,
                    "--get-parameter",
                    "msi",
                ]
            )
        return None

    def _validate_fence_permissions(self) -> ValidationResult:
        fence_output = self.cmd_executor.run_subprocess(
            ["fence_azure_arm", "--msi", "--action=list"]
        )
        if "Error" in fence_output:
            return ValidationResult(
                Status.ERROR, {"Fence agent permissions": fence_output}
            )
        if self.vm_name in fence_output:
            return ValidationResult(
                Status.SUCCESS, {"Fence agent permissions": fence_output}
            )
        return ValidationResult(
            Status.ERROR,
            {"Fence agent permissions": f"VM not found in list: {fence_output}"},
        )

    def validate_location_constraints(self) -> bool:
        try:
            root = self.cmd_executor.parse_xml_output(
                ["cibadmin", "--query", "--scope", "constraints"]
            )
            if root is not None:
                if root.find(".//rsc_location") is not None:
                    health_location = root.find(
                        ".//rsc_location[@rsc-pattern='!health-.*']"
                    )
                    if health_location is None:
                        return bool(root.find(".//rsc_location"))
            return False
        except Exception:
            return False

    def validate_fence_azure_arm(self) -> ValidationResult:
        try:
            msi_value = self._get_msi_value()
            if msi_value and msi_value.strip().lower() == "true":
                return self._validate_fence_permissions()
            return ValidationResult(
                Status.SUCCESS,
                {
                    "Fence agent permissions": "MSI value not found or the stonith is configured using SPN."
                },
            )
        except json.JSONDecodeError as e:
            return ValidationResult(Status.ERROR, {"Fence agent permissions": str(e)})
        except Exception as e:
            return ValidationResult(Status.ERROR, {"Fence agent permissions": str(e)})

    def validate_os_parameters(self) -> ValidationResult:
        validator = OSParameterValidator(self.ansible_os_family, self.cmd_executor)
        return validator.validate()

    def validate_constraints(self) -> ValidationResult:
        validator = ConstraintValidator(
            self.ansible_os_family, self.sid, self.cmd_executor
        )
        return validator.validate()

    def validate_global_ini(self) -> ValidationResult:
        validator = GlobalIniValidator(self.sid, self.ansible_os_family)
        return validator.validate()

    def validate_cluster_params(self) -> ValidationResult:
        validator = ClusterParamValidator(self.ansible_os_family, self.cmd_executor)
        return validator.validate()


class OSParameterValidator:
    def __init__(self, ansible_os_family: str, cmd_executor: CommandExecutor):
        self.ansible_os_family = ansible_os_family
        self.cmd_executor = cmd_executor

    def validate(self) -> ValidationResult:
        drift_parameters = []
        validated_parameters = []

        try:
            self._validate_custom_parameters(drift_parameters, validated_parameters)
            self._validate_stack_parameters(drift_parameters, validated_parameters)

            if drift_parameters:
                return ValidationResult(
                    Status.ERROR,
                    {
                        "Drift OS and Corosync Parameters": drift_parameters,
                        "Validated OS and Corosync Parameters": validated_parameters,
                    },
                )
            return ValidationResult(
                Status.SUCCESS,
                {"Validated OS and Corosync Parameters": validated_parameters},
            )
        except Exception as e:
            return ValidationResult(
                Status.ERROR, {"Error OS and Corosync Parameters": str(e)}
            )

    def _validate_custom_parameters(
        self, drift_parameters: List, validated_parameters: List
    ) -> None:
        for parameter, details in CUSTOM_OS_PARAMETERS[self.ansible_os_family].items():
            output = self.cmd_executor.run_subprocess(details["command"]).splitlines()
            parameter_value = next(
                (
                    line.split(":")[1].strip()
                    for line in output
                    if details["parameter_name"] in line
                ),
                None,
            )
            self._add_parameter_result(
                parameter,
                parameter_value,
                details["expected_value"],
                drift_parameters,
                validated_parameters,
            )

    def _validate_stack_parameters(
        self, drift_parameters: List, validated_parameters: List
    ) -> None:
        for stack_name, stack_details in OS_PARAMETERS[self.ansible_os_family].items():
            base_args = (
                ["sysctl"] if stack_name == "sysctl" else ["corosync-cmapctl", "-g"]
            )
            for parameter, details in stack_details.items():
                output = self.cmd_executor.run_subprocess(base_args + [parameter])
                parameter_value = output.split("=")[1].strip()
                self._add_parameter_result(
                    parameter,
                    parameter_value,
                    details["expected_value"],
                    drift_parameters,
                    validated_parameters,
                )

    @staticmethod
    def _add_parameter_result(
        name: str, value: str, expected: str, drift: List, validated: List
    ) -> None:
        result = PARAMETER_VALUE_FORMAT % (name, value, expected)
        if value != expected:
            drift.append(result)
        else:
            validated.append(result)


class ConstraintValidator:
    def __init__(self, ansible_os_family: str, sid: str, cmd_executor: CommandExecutor):
        self.ansible_os_family = ansible_os_family
        self.sid = sid
        self.cmd_executor = cmd_executor

    def validate(self) -> ValidationResult:
        drift_parameters = defaultdict(lambda: defaultdict(list))
        valid_parameters = defaultdict(lambda: defaultdict(list))

        try:
            root = self.cmd_executor.parse_xml_output(
                ["cibadmin", "--query", "--scope", "constraints"]
            )
            if root is not None:
                self._validate_constraints(root, drift_parameters, valid_parameters)

            if drift_parameters:
                return ValidationResult(
                    Status.ERROR,
                    {
                        "Valid Constraints parameters": valid_parameters,
                        "Drift in Constraints parameters": drift_parameters,
                    },
                )
            return ValidationResult(
                Status.SUCCESS, {"Valid Constraints parameter": valid_parameters}
            )
        except Exception as e:
            return ValidationResult(Status.ERROR, {"Constraints validation": str(e)})

    def _validate_constraints(
        self, root: ET.Element, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        for constraint in root:
            constraint_type = constraint.tag
            if constraint_type in CONSTRAINTS:
                self._validate_constraint_attributes(
                    constraint, constraint_type, drift_parameters, valid_parameters
                )

    def _validate_constraint_attributes(
        self,
        constraint: ET.Element,
        constraint_type: str,
        drift_parameters: dict,
        valid_parameters: dict,
    ) -> None:
        constraint_id = constraint.attrib.get("id", "")
        expected_attrs = CONSTRAINTS[constraint_type]

        # Validate main attributes
        for key, value in constraint.attrib.items():
            if key in expected_attrs:
                self._check_and_add_parameter(
                    key,
                    value,
                    expected_attrs[key],
                    constraint_type,
                    constraint_id,
                    drift_parameters,
                    valid_parameters,
                )

        # Validate child elements
        for child in constraint:
            for key, value in child.attrib.items():
                if key in expected_attrs:
                    self._check_and_add_parameter(
                        key,
                        value,
                        expected_attrs[key],
                        constraint_type,
                        constraint_id,
                        drift_parameters,
                        valid_parameters,
                    )

    def _check_and_add_parameter(
        self,
        key: str,
        value: str,
        expected: str,
        constraint_type: str,
        constraint_id: str,
        drift_parameters: dict,
        valid_parameters: dict,
    ) -> None:
        result = PARAMETER_VALUE_FORMAT % (key, value, expected)
        if value != expected:
            drift_parameters[constraint_type][constraint_id].append(result)
        else:
            valid_parameters[constraint_type][constraint_id].append(result)


class GlobalIniValidator:
    def __init__(self, sid: str, ansible_os_family: str):
        self.sid = sid
        self.ansible_os_family = ansible_os_family
        self.global_ini_path = f"/usr/sap/{sid}/SYS/global/hdb/custom/config/global.ini"

    def validate(self) -> ValidationResult:
        try:
            properties = self._read_global_ini_properties()
            expected_properties = self._get_expected_properties()

            if properties == expected_properties:
                return ValidationResult(
                    Status.SUCCESS, {"SAPHanaSR Properties": properties}
                )
            return ValidationResult(
                Status.ERROR,
                {
                    "SAPHanaSR Properties validation failed with the expected properties": properties
                },
            )
        except FileNotFoundError as e:
            return ValidationResult(
                Status.ERROR, {"Exception raised, file not found error": str(e)}
            )
        except Exception as e:
            return ValidationResult(
                Status.ERROR, {"SAPHanaSR Properties validation failed": str(e)}
            )

    def _read_global_ini_properties(self) -> dict:
        with open(self.global_ini_path, "r") as file:
            global_ini = [line.strip() for line in file.readlines()]

        try:
            section_start = global_ini.index("[ha_dr_provider_SAPHanaSR]")
            properties_slice = global_ini[section_start + 1 : section_start + 4]

            return {
                prop.split("=")[0].strip(): prop.split("=")[1].strip()
                for prop in properties_slice
            }
        except (ValueError, IndexError) as e:
            raise ValueError(f"Failed to parse global.ini: {str(e)}")

    def _get_expected_properties(self) -> dict:
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
        return expected_properties[self.ansible_os_family]


class ClusterParamValidator:
    def __init__(self, ansible_os_family: str, cmd_executor: CommandExecutor):
        self.ansible_os_family = ansible_os_family
        self.cmd_executor = cmd_executor

    def validate(self) -> ValidationResult:
        drift_parameters = defaultdict(lambda: defaultdict(list))
        valid_parameters = defaultdict(lambda: defaultdict(list))

        try:
            self._validate_cluster_properties(drift_parameters, valid_parameters)
            self._validate_resource_parameters(drift_parameters, valid_parameters)

            validation_result = self._create_validation_result(
                valid_parameters, drift_parameters
            )
            return validation_result

        except Exception as e:
            return ValidationResult(Status.ERROR, {"Error message": str(e)})

    def _validate_cluster_properties(
        self, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        for resource_operation in CLUSTER_PROPERTIES.keys():
            root = self.cmd_executor.parse_xml_output(
                ["cibadmin", "--query", "--scope", resource_operation]
            )
            if root is not None:
                self._process_cluster_properties(
                    root, resource_operation, drift_parameters, valid_parameters
                )

    def _process_cluster_properties(
        self,
        root: ET.Element,
        resource_operation: str,
        drift_parameters: dict,
        valid_parameters: dict,
    ) -> None:
        for root_element in root:
            primitive_id = root_element.get("id")
            extracted_values = {
                primitive_id: {
                    nvpair.get("name"): nvpair.get("value")
                    for nvpair in root_element.findall(".//nvpair")
                }
            }

            recommended_values = CLUSTER_PROPERTIES[resource_operation].get(
                primitive_id, {}
            )
            self._compare_parameters(
                extracted_values[primitive_id],
                recommended_values,
                resource_operation,
                primitive_id,
                drift_parameters,
                valid_parameters,
            )

    def _validate_resource_parameters(
        self, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        root = self.cmd_executor.parse_xml_output(
            ["cibadmin", "--query", "--scope", "resources"]
        )
        if root is not None:
            self._process_resources(root, drift_parameters, valid_parameters)

    def _process_resources(
        self, root: ET.Element, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        for primitive in root.findall(".//primitive"):
            resource_id = primitive.get("id")
            resource_type = self._get_resource_type(primitive)

            if resource_type in CLUSTER_RESOURCES[self.ansible_os_family]:
                expected_attrs = CLUSTER_RESOURCES[self.ansible_os_family][
                    resource_type
                ]
                actual_attrs = self._get_actual_attributes(primitive)

                self._compare_parameters(
                    actual_attrs,
                    expected_attrs,
                    "resources",
                    resource_id,
                    drift_parameters,
                    valid_parameters,
                )

    def _get_resource_type(self, primitive: ET.Element) -> str:
        resource_class = primitive.get("class")
        resource_provider = primitive.get("provider", "")
        resource_type = primitive.get("type")

        if resource_provider:
            return f"{resource_class}:{resource_provider}:{resource_type}"
        return f"{resource_class}:{resource_type}"

    def _get_actual_attributes(self, primitive: ET.Element) -> dict:
        attributes = {}

        # Get nvpair attributes
        for prop in primitive.findall(".//nvpair"):
            attributes[prop.get("name")] = prop.get("value")

        # Get operation attributes
        for op in primitive.findall(".//op"):
            name_prefix = f"{op.get('name')}-{op.get('role', 'NoRole')}"
            attributes[f"{name_prefix}-interval"] = op.get("interval")
            attributes[f"{name_prefix}-timeout"] = op.get("timeout")

        return attributes

    def _compare_parameters(
        self,
        actual: dict,
        expected: dict,
        operation: str,
        resource_id: str,
        drift_parameters: dict,
        valid_parameters: dict,
    ) -> None:
        for name, value in actual.items():
            if name in expected:
                result = PARAMETER_VALUE_FORMAT % (name, value, expected[name])
                if value != expected[name]:
                    drift_parameters[operation][resource_id].append(result)
                else:
                    valid_parameters[operation][resource_id].append(result)

    def _create_validation_result(
        self, valid_parameters: dict, drift_parameters: dict
    ) -> ValidationResult:
        valid_parameters_json = json.dumps(valid_parameters)
        missing_parameters = [
            parameter
            for parameter in REQUIRED_PARAMETERS
            if parameter not in valid_parameters_json
        ]

        if missing_parameters:
            return ValidationResult(
                Status.WARNING,
                {
                    "Required parameters missing in cluster parameters": missing_parameters,
                    "Validated cluster parameters": valid_parameters,
                },
            )

        if drift_parameters:
            return ValidationResult(
                Status.ERROR,
                {
                    "Validated cluster parameters": valid_parameters,
                    "Drift in cluster parameters": drift_parameters,
                },
            )

        return ValidationResult(
            Status.SUCCESS, {"Validated cluster parameters": valid_parameters}
        )


class ClusterManager:
    def __init__(self, module: AnsibleModule):
        self.module = module
        self.params = module.params

    def run(self) -> None:
        try:
            if self.params["action"] == "get":
                self._handle_get_action()
        except Exception as e:
            self.module.fail_json(msg=str(e))

    def _handle_get_action(self) -> None:
        validator = ClusterValidator(
            self.params["ansible_os_family"],
            self.params["sid"],
            self.params["virtual_machine_name"],
        )

        consolidated_results = {
            "validated_parameters": [],
            "drift_parameters": [],
            "informational_parameters": [],
            "error_message": "",
            "message": "Cluster parameters validation completed",
        }

        try:
            validations = {
                "cluster": validator.validate_cluster_params(),
                "sap_hana_sr": validator.validate_global_ini(),
                "os_parameters": validator.validate_os_parameters(),
                "fence": validator.validate_fence_azure_arm(),
                "constraints": validator.validate_constraints(),
            }

            for validation_name, result in validations.items():
                self._process_validation_result(
                    consolidated_results, validation_name, result
                )

            overall_status = (
                Status.SUCCESS
                if not consolidated_results["drift_parameters"]
                and not consolidated_results["error_message"]
                else Status.ERROR
            )

            self.module.exit_json(
                msg=consolidated_results["message"],
                details=consolidated_results,
                status=overall_status.value,
            )

        except Exception as e:
            consolidated_results["error_message"] = str(e)
            self.module.fail_json(msg=str(e), details=consolidated_results)

    def _process_validation_result(
        self, consolidated_results: dict, validation_name: str, result: ValidationResult
    ) -> None:
        result_dict = result.to_dict()

        # Process messages from the validation result
        for key, value in result_dict.get("msg", {}).items():
            if isinstance(value, list):
                # Handle list values
                for item in value:
                    self._categorize_parameter(
                        consolidated_results, f"{validation_name}.{key}", item
                    )
            elif isinstance(value, dict):
                # Handle nested dictionaries
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, list):
                        for item in sub_value:
                            self._categorize_parameter(
                                consolidated_results,
                                f"{validation_name}.{key}.{sub_key}",
                                item,
                            )
                    else:
                        self._categorize_parameter(
                            consolidated_results,
                            f"{validation_name}.{key}.{sub_key}",
                            str(sub_value),
                        )
            else:
                # Handle simple values
                self._categorize_parameter(
                    consolidated_results, f"{validation_name}.{key}", str(value)
                )

        # Process any error messages
        if (
            result.status == Status.ERROR
            and "error_message" not in consolidated_results
        ):
            consolidated_results["error_message"] = (
                f"Error in {validation_name} validation"
            )

    def _categorize_parameter(
        self, consolidated_results: dict, category: str, value: str
    ) -> None:
        if "Drift" in category or "FAILED" in value:
            consolidated_results["drift_parameters"].append(f"{category}: {value}")
        elif "Valid" in category or "PASSED" in value:
            consolidated_results["validated_parameters"].append(f"{category}: {value}")
        else:
            consolidated_results["informational_parameters"].append(
                f"{category}: {value}"
            )


def main() -> None:
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

    manager = ClusterManager(module)
    manager.run()


if __name__ == "__main__":
    main()
