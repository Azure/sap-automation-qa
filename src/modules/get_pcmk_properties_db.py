# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the cluster configuration in HANA DB node.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Union, Any
import subprocess
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import TestStatus
    from ansible.module_utils.cluster_constants import (
        OS_PARAMETERS,
        CUSTOM_OS_PARAMETERS,
        CONSTRAINTS,
        CLUSTER_PROPERTIES,
        CLUSTER_RESOURCES,
        REQUIRED_PARAMETERS,
    )
except ImportError:
    from src.module_utils.sap_automation_qa import TestStatus
    from src.module_utils.cluster_constants import (
        OS_PARAMETERS,
        CUSTOM_OS_PARAMETERS,
        CONSTRAINTS,
        CLUSTER_PROPERTIES,
        CLUSTER_RESOURCES,
        REQUIRED_PARAMETERS,
    )


@dataclass
class ValidationResult:
    """
    Represents the result of a validation.
    """

    status: TestStatus
    messages: Dict[str, Any]
    details: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """
        Converts the validation result to a dictionary.

        :return: Dictionary representation of the validation result.
        :rtype: Dict
        """
        return {
            "message": self.messages,
            "status": self.status.value,
            **(self.details or {}),
        }


class CommandExecutor:
    """
    Executes system commands and parses XML output.
    """

    @staticmethod
    def run_subprocess(command: Union[List[str], str]) -> str:
        """
        Runs a subprocess command and returns its output.
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

    @classmethod
    def parse_xml_output(cls, command: List[str]) -> Optional[ET.Element]:
        """
        Parses the XML output of a command.
        """
        xml_output = cls.run_subprocess(command)
        if xml_output.startswith("<"):
            return ET.fromstring(xml_output)
        return None


@dataclass
class ValidationContext:
    """
    Context for validation, containing necessary parameters and command executor.
    """

    ansible_os_family: str
    sid: str = ""
    vm_name: str = ""
    cmd_executor: Optional[CommandExecutor] = None
    fencing_mechanism: str = ""


class ValidatorBase(ABC):
    """
    Abstract base class for validators.
    """

    def __init__(self, context: ValidationContext):
        """
        Initializes the validator with the given context.
        """
        self.context = context

    @abstractmethod
    def validate(self) -> ValidationResult:
        """
        Abstract method to perform validation.
        """
        pass

    def _format_parameter_result(self, name: str, value: str, expected: str) -> str:
        """
        Formats the parameter result for reporting.
        """
        return f"Name: {name}, Value: {value}, Expected Value: {expected}"


class ParameterValidatorMixin:
    """
    Mixin class for parameter validation.
    """

    def _check_and_add_parameter(
        self,
        key: str,
        value: str,
        expected: str,
        category: str,
        identifier: str,
        drift_parameters: dict,
        valid_parameters: dict,
    ) -> None:
        """
        Checks and adds the parameter to the appropriate list based on comparison.
        """
        result = self._format_parameter_result(key, value, expected)
        target_dict = drift_parameters if value != expected else valid_parameters
        target_dict[category][identifier].append(result)


class OSParameterValidator(ValidatorBase, ParameterValidatorMixin):
    """
    Validates the OS parameters by comparing actual and expected values.
    """

    def validate(self) -> ValidationResult:
        """
        Validates the OS parameters.
        """
        drift_parameters = []
        validated_parameters = []

        try:
            self._validate_parameters(
                OS_PARAMETERS[self.context.ansible_os_family],
                CUSTOM_OS_PARAMETERS[self.context.ansible_os_family],
                drift_parameters,
                validated_parameters,
            )

            if drift_parameters:
                return ValidationResult(
                    TestStatus.ERROR,
                    {
                        "Drift OS Parameters": drift_parameters,
                        "Validated OS Parameters": validated_parameters,
                    },
                )
            return ValidationResult(
                TestStatus.SUCCESS,
                {"Validated OS Parameters": validated_parameters},
            )
        except Exception as e:
            return ValidationResult(TestStatus.ERROR, {"Error": str(e)})

    def _validate_parameters(
        self,
        standard_params: Dict,
        custom_params: Dict,
        drift_parameters: List,
        validated_parameters: List,
    ) -> None:
        """
        Validates the standard and custom OS parameters.
        """
        for param_type, params in standard_params.items():
            base_args = (
                ["sysctl"] if param_type == "sysctl" else ["corosync-cmapctl", "-g"]
            )
            for param, details in params.items():
                output = self.context.cmd_executor.run_subprocess(base_args + [param])
                value = output.split("=")[1].strip()
                self._add_parameter_result(
                    param,
                    value,
                    details["expected_value"],
                    drift_parameters,
                    validated_parameters,
                )

        for param, details in custom_params.items():
            output = self.context.cmd_executor.run_subprocess(details["command"])
            value = self._extract_custom_param_value(output, details)
            self._add_parameter_result(
                param,
                value,
                details["expected_value"],
                drift_parameters,
                validated_parameters,
            )

    def _extract_custom_param_value(self, output: str, details: Dict) -> str:
        """
        Extracts the value of a custom parameter from the command output.
        """
        for line in output.splitlines():
            if details["parameter_name"] in line:
                return line.split(":")[1].strip()
        return ""

    def _add_parameter_result(
        self,
        name: str,
        value: str,
        expected: str,
        drift_parameters: List,
        validated_parameters: List,
    ) -> None:
        """
        Adds the parameter result to the appropriate list based on comparison.
        """
        result = self._format_parameter_result(name, value, expected)
        target_list = drift_parameters if value != expected else validated_parameters
        target_list.append(result)


class FenceValidator(ValidatorBase):
    """
    Validates the fence agent permissions.
    """

    def validate(self) -> ValidationResult:
        """
        Validates the fence agent permissions.
        """
        try:
            msi_value = self._get_msi_value()
            if msi_value and msi_value.strip().lower() == "true":
                return self._validate_fence_permissions()
            return ValidationResult(
                TestStatus.SUCCESS,
                {
                    "Fence agent permissions": "MSI value not found or using SPN configuration"
                },
            )
        except Exception as e:
            return ValidationResult(
                TestStatus.ERROR, {"Fence agent permissions": str(e)}
            )

    def _get_msi_value(self) -> Optional[str]:
        """
        Gets the MSI value based on the OS family.
        """
        if self.context.ansible_os_family == "REDHAT":
            return self._get_redhat_msi_value()
        elif self.context.ansible_os_family == "SUSE":
            return self._get_suse_msi_value()
        return None

    def _get_redhat_msi_value(self) -> Optional[str]:
        """
        Gets the MSI value for Red Hat OS.
        """
        stonith_config = json.loads(
            self.context.cmd_executor.run_subprocess(
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

    def _get_suse_msi_value(self) -> str:
        """
        Gets the MSI value for SUSE OS.
        """
        stonith_device_name = self.context.cmd_executor.run_subprocess(
            ["stonith_admin", "--list-registered"]
        ).splitlines()[0]
        return self.context.cmd_executor.run_subprocess(
            [
                "crm_resource",
                "--resource",
                stonith_device_name,
                "--get-parameter",
                "msi",
            ]
        )

    def _validate_fence_permissions(self) -> ValidationResult:
        """
        Validates the fence agent permissions using the MSI value.
        """
        fence_output = self.context.cmd_executor.run_subprocess(
            ["fence_azure_arm", "--msi", "--action=list"]
        )
        if "Error" in fence_output:
            return ValidationResult(
                TestStatus.ERROR, {"Fence agent permissions": fence_output}
            )
        if self.context.vm_name in fence_output:
            return ValidationResult(
                TestStatus.SUCCESS, {"Fence agent permissions": fence_output}
            )
        return ValidationResult(
            TestStatus.ERROR,
            {"Fence agent permissions": f"VM not found in list: {fence_output}"},
        )


class ConstraintValidator(ValidatorBase, ParameterValidatorMixin):
    """
    Validates the constraints in the cluster configuration.
    """

    def validate(self) -> ValidationResult:
        """
        Validates the constraints.
        """
        drift_parameters = defaultdict(lambda: defaultdict(list))
        valid_parameters = defaultdict(lambda: defaultdict(list))

        try:
            root = self.context.cmd_executor.parse_xml_output(
                ["cibadmin", "--query", "--scope", "constraints"]
            )
            if root is not None:
                self._validate_constraints(root, drift_parameters, valid_parameters)

            if drift_parameters:
                return ValidationResult(
                    TestStatus.ERROR,
                    {
                        "Valid Constraints parameters": valid_parameters,
                        "Drift in Constraints parameters": drift_parameters,
                    },
                )
            return ValidationResult(
                TestStatus.SUCCESS, {"Valid Constraints parameter": valid_parameters}
            )
        except Exception as e:
            return ValidationResult(
                TestStatus.ERROR, {"Constraints validation": str(e)}
            )

    def _validate_constraints(
        self, root: ET.Element, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        """
        Validates the constraints from the XML root element.
        """
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
        """
        Validates the attributes of a constraint.
        """
        constraint_id = constraint.attrib.get("id", "")
        expected_attrs = CONSTRAINTS[constraint_type]

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


class GlobalIniValidator(ValidatorBase):
    """
    Validates the global.ini properties for SAPHanaSR.
    """

    def validate(self) -> ValidationResult:
        """
        Validates the global.ini properties.
        """
        try:
            properties = self._read_global_ini_properties()
            expected_properties = self._get_expected_properties()

            if properties == expected_properties:
                return ValidationResult(
                    TestStatus.SUCCESS, {"SAPHanaSR Properties": properties}
                )
            return ValidationResult(
                TestStatus.ERROR,
                {
                    "SAPHanaSR Properties validation failed with expected properties": properties
                },
            )
        except FileNotFoundError as e:
            return ValidationResult(
                TestStatus.ERROR, {"Exception raised, file not found error": str(e)}
            )
        except Exception as e:
            return ValidationResult(
                TestStatus.ERROR, {"SAPHanaSR Properties validation failed": str(e)}
            )

    def _read_global_ini_properties(self) -> dict:
        """
        Reads the global.ini properties.
        """
        global_ini_path = (
            f"/usr/sap/{self.context.sid}/SYS/global/hdb/custom/config/global.ini"
        )
        with open(global_ini_path, "r", encoding="utf-8") as file:
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
        """
        Gets the expected properties for the global.ini file based on the OS family.
        """
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
        return expected_properties[self.context.ansible_os_family]


class ClusterParamValidator(ValidatorBase, ParameterValidatorMixin):
    """
    Validates cluster parameters by comparing actual and expected values.
    """

    def validate(self) -> ValidationResult:
        """
        Validates the cluster parameters.
        """
        drift_parameters = defaultdict(lambda: defaultdict(list))
        valid_parameters = defaultdict(lambda: defaultdict(list))

        try:
            self._validate_cluster_properties(drift_parameters, valid_parameters)
            self._validate_resource_parameters(drift_parameters, valid_parameters)

            return self._create_validation_result(valid_parameters, drift_parameters)
        except Exception as e:
            return ValidationResult(TestStatus.ERROR, {"Error message": str(e)})

    def _validate_cluster_properties(
        self, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        """
        Validates the cluster properties.
        """
        for resource_operation in CLUSTER_PROPERTIES["DEFAULTS"].keys():
            root = self.context.cmd_executor.parse_xml_output(
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
        """
        Processes the cluster properties.
        """
        for root_element in root:
            primitive_id = root_element.get("id")
            extracted_values = {
                nvpair.get("name"): nvpair.get("value")
                for nvpair in root_element.findall(".//nvpair")
            }

            recommended_values = CLUSTER_PROPERTIES["DEFAULTS"][resource_operation].get(
                primitive_id, {}
            )
            # combine the default values with fencing based values
            if self.context.fencing_mechanism in CLUSTER_PROPERTIES:
                recommended_values.update(
                    CLUSTER_PROPERTIES[self.context.fencing_mechanism].get(
                        primitive_id, {}
                    )
                )
            self._compare_parameters(
                extracted_values,
                recommended_values,
                resource_operation,
                primitive_id,
                drift_parameters,
                valid_parameters,
            )

    def _validate_resource_parameters(
        self, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        """
        Validates the resource parameters.
        """
        root = self.context.cmd_executor.parse_xml_output(
            ["cibadmin", "--query", "--scope", "resources"]
        )
        if root is not None:
            self._process_resources(root, drift_parameters, valid_parameters)

    def _process_resources(
        self, root: ET.Element, drift_parameters: dict, valid_parameters: dict
    ) -> None:
        """
        Processes the resource parameters.
        """
        cluster_resources = CLUSTER_RESOURCES[self.context.ansible_os_family]

        def compare_and_store_parameters(element, element_id, resource_key):
            expected_attrs = cluster_resources[resource_key]
            actual_attrs = self._get_actual_attributes(element)
            self._compare_parameters(
                actual_attrs,
                expected_attrs,
                "resources",
                element_id,
                drift_parameters,
                valid_parameters,
            )

        for primitive in root.findall(".//primitive"):
            resource_id = primitive.get("id")
            resource_type = self._get_resource_type(primitive)
            if resource_type in cluster_resources:
                compare_and_store_parameters(primitive, resource_id, resource_type)

        for meta in root.findall(".//meta_attributes"):
            meta_id = meta.get("id")
            matching_keys = [key for key in cluster_resources if key in meta_id]
            for key in matching_keys:
                compare_and_store_parameters(meta, meta_id, key)

    def _get_resource_type(self, primitive: ET.Element) -> str:
        """
        Gets the resource type from the primitive element.
        """
        resource_class = primitive.get("class")
        resource_provider = primitive.get("provider", "")
        resource_type = primitive.get("type")

        if resource_provider:
            return f"{resource_class}:{resource_provider}:{resource_type}"
        return f"{resource_class}:{resource_type}"

    def _get_actual_attributes(self, primitive: ET.Element) -> dict:
        """
        Gets the actual attributes from the primitive element.
        """
        attributes = {}
        for prop in primitive.findall(".//nvpair"):
            attributes[prop.get("name")] = prop.get("value")
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
        """
        Compares the actual and expected parameters.
        """
        for name, value in actual.items():
            if name in expected:
                self._check_and_add_parameter(
                    name,
                    value,
                    expected[name],
                    operation,
                    resource_id,
                    drift_parameters,
                    valid_parameters,
                )

    def _create_validation_result(
        self, valid_parameters: dict, drift_parameters: dict
    ) -> ValidationResult:
        """
        Creates the validation result.
        """
        valid_parameters_json = json.dumps(valid_parameters)
        missing_parameters = [
            parameter
            for parameter in REQUIRED_PARAMETERS
            if parameter not in valid_parameters_json
        ]

        if missing_parameters:
            return ValidationResult(
                TestStatus.WARNING,
                {
                    "Required parameters missing in cluster parameters": missing_parameters,
                    "Validated cluster parameters": valid_parameters,
                },
            )

        if drift_parameters:
            return ValidationResult(
                TestStatus.ERROR,
                {
                    "Validated cluster parameters": valid_parameters,
                    "Drift in cluster parameters": drift_parameters,
                },
            )

        return ValidationResult(
            TestStatus.SUCCESS, {"Validated cluster parameters": valid_parameters}
        )


@dataclass
class ResultAggregator:
    """
    Aggregates the results of the cluster parameter validations.
    """

    parameters: List[Dict[str, str]] = field(default_factory=list)
    error_message: str = ""
    message: str = "Cluster parameters validation completed"

    def add_validation_result(self, category: str, result: ValidationResult) -> None:
        """
        Adds a validation result to the aggregator.
        """
        result_dict = result.to_dict()

        for key, value in result_dict.get("message", {}).items():
            self._process_value(category, key, value)

        if result.status == TestStatus.ERROR and not self.error_message:
            self.error_message = f"Error in {category} validation"

    def _process_value(self, category: str, key: str, value: Any) -> None:
        """
        Processes a value from the validation result.
        """
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                self._process_value(category, f"{key}.{sub_key}", sub_value)
        elif isinstance(value, list):
            for item in value:
                self._categorize_parameter(category, key, str(item))
        else:
            self._categorize_parameter(category, key, str(value))

    def _categorize_parameter(self, category: str, key: str, value: str) -> None:
        """
        Categorizes a parameter from the validation result.
        """
        parent_key = key.split(".")[-1] if category != "os_parameters" else key
        param_entry = {
            "category": category,
            "type": parent_key,
        }

        if "Name:" in value:
            parts = value.split(", ")
            for part in parts:
                name, val = part.split(": ", 1)
                param_entry[name.lower()] = val

            if "Drift" in key:
                param_entry["status"] = TestStatus.ERROR.value
            elif "Valid" in key:
                param_entry["status"] = TestStatus.SUCCESS.value
        else:
            param_entry["value"] = value
            param_entry["status"] = TestStatus.INFO.value

        self.parameters.append(param_entry)

    def to_dict(self) -> Dict:
        """
        Converts the aggregated results to a dictionary.
        """
        result = {
            "parameters": self.parameters,
        }

        if self.error_message:
            result["message"] = self.error_message

        return result


class ClusterManager:
    """
    Manages the cluster operations and validations.
    """

    def __init__(self, module: AnsibleModule):
        """
        Initializes the ClusterManager with the given Ansible module.
        """
        self.module = module
        self.context = ValidationContext(
            ansible_os_family=module.params["ansible_os_family"],
            sid=module.params["sid"],
            vm_name=module.params["virtual_machine_name"],
            cmd_executor=CommandExecutor(),
            fencing_mechanism=module.params.get("fencing_mechanism", ""),
        )
        self.result_aggregator = ResultAggregator()

    def run(self) -> None:
        """
        Executes the main logic based on the action parameter.
        """
        try:
            if self.module.params["action"] == "get":
                self._handle_get_action()
        except Exception as e:
            self.module.fail_json(msg=str(e))

    def _handle_get_action(self) -> None:
        """
        Handles the 'get' action by running validations and processing results.
        """
        try:
            validators = self._create_validators()
            self._run_validations(validators)
            self._process_results()
        except Exception as e:
            self.result_aggregator.error_message = str(e)
            self.module.fail_json(msg=asdict(self.result_aggregator))

    def _create_validators(self) -> Dict[str, ValidatorBase]:
        """
        Creates a dictionary of validators for different cluster parameters.
        """
        return {
            "cluster": ClusterParamValidator(self.context),
            "sap_hana_sr": GlobalIniValidator(self.context),
            "os_parameters": OSParameterValidator(self.context),
            "fence_agent": FenceValidator(self.context),
            "constraints": ConstraintValidator(self.context),
        }

    def _run_validations(self, validators: Dict[str, ValidatorBase]) -> None:
        """
        Runs the validations using the provided validators.
        """
        for name, validator in validators.items():
            result = validator.validate()
            self.result_aggregator.add_validation_result(name, result)

    def _process_results(self) -> None:
        """
        Processes the validation results and exits the module with the appropriate status.
        """
        has_errors = any(
            param["status"] == TestStatus.ERROR.value
            for param in self.result_aggregator.parameters
        )
        result = {
            "changed": False,
            "status": TestStatus.NOT_STARTED.value,
            "message": "",
            "details": {},
        }

        result["status"] = (
            TestStatus.ERROR.value
            if (has_errors or self.result_aggregator.error_message)
            else TestStatus.SUCCESS
        )
        result["message"] = self.result_aggregator.message
        result["details"] = self.result_aggregator.to_dict()

        self.module.exit_json(**result)


def main() -> None:
    """
    Main entry point for the Ansible module.
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

    manager = ClusterManager(module)
    manager.run()


if __name__ == "__main__":
    main()
