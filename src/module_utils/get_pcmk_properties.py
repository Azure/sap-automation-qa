# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Base Pacemaker Cluster Configuration Validator.

This module provides base functionality to validate Pacemaker cluster configurations
against predefined standards for SAP deployments.

Classes:
    BaseHAClusterValidator: Base validator class for cluster configurations.
"""

from abc import ABC

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import OperatingSystemFamily, Parameters, TestStatus
    from ansible.module_utils.commands import CIB_ADMIN
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import OperatingSystemFamily, Parameters, TestStatus
    from src.module_utils.commands import CIB_ADMIN


class BaseHAClusterValidator(SapAutomationQA, ABC):
    """
    Base class for validating DB/SCS High Availability cluster configurations.

    This abstract base class provides common functionality for validating
    Pacemaker cluster configurations against predefined standards for SAP deployments.
    It contains shared methods for parsing and validating cluster configurations.

    Attributes:
        BASIC_CATEGORIES (Dict): Mapping of basic configuration categories to their XPaths
        RESOURCE_CATEGORIES (Dict): Mapping of resource types to their XPaths (in subclasses)
    """

    BASIC_CATEGORIES = {
        "crm_config": (".//cluster_property_set", "CRM_CONFIG_DEFAULTS"),
        "rsc_defaults": (".//meta_attributes", "RSC_DEFAULTS"),
        "op_defaults": (".//meta_attributes", "OP_DEFAULTS"),
    }

    CONSTRAINTS_CATEGORIES = (".//*", "CONSTRAINTS_DEFAULTS")
    RESOURCE_CATEGORIES = {}

    def __init__(
        self,
        os_type: OperatingSystemFamily,
        sid: str,
        virtual_machine_name: str,
        constants: dict,
        fencing_mechanism: str,
        cib_output: str = "",
        category=None,
    ):
        """
        Initialize the base validator.

        :param os_type: Operating system family
        :type os_type: OperatingSystemFamily
        :param sid: SAP System ID
        :type sid: str
        :param virtual_machine_name: Name of the virtual machine
        :type virtual_machine_name: str
        :param constants: Dictionary of constants for validation
        :type constants: dict
        :param fencing_mechanism: Type of fencing mechanism used
        :type fencing_mechanism: str
        :param category: Category being processed (optional)
        :type category: str
        """
        super().__init__()
        self.os_type = os_type.value.upper()
        self.category = category
        self.sid = sid
        self.virtual_machine_name = virtual_machine_name
        self.fencing_mechanism = fencing_mechanism
        self.constants = constants
        self.cib_output = cib_output

    def _get_expected_value(self, category, name):
        """
        Get expected value for a given configuration parameter.

        :param category: The category of the configuration parameter.
        :type category: str
        :param name: The name of the configuration parameter.
        :type name: str
        :return: The expected value for the configuration parameter.
        :rtype: tuple(str, bool)
        """
        _, defaults_key = self.BASIC_CATEGORIES[category]

        fence_config = self.constants["VALID_CONFIGS"].get(self.fencing_mechanism, {})
        os_config = self.constants["VALID_CONFIGS"].get(self.os_type, {})

        fence_param = fence_config.get(name, {})
        if fence_param:
            if isinstance(fence_param, dict) and fence_param.get("value"):
                return (fence_param.get("value", ""), fence_param.get("required", False))
            elif isinstance(fence_param, (str, list)):
                return (fence_param, False)

        os_param = os_config.get(name, {})
        if os_param:
            if isinstance(os_param, dict) and os_param.get("value"):
                return (os_param.get("value", ""), os_param.get("required", False))
            elif isinstance(os_param, (str, list)):
                return (os_param, False)

        default_param = self.constants[defaults_key].get(name, {})
        if default_param:
            if isinstance(default_param, dict) and default_param.get("value"):
                return (default_param.get("value", ""), default_param.get("required", False))
            elif isinstance(default_param, (str, list)):
                return (default_param, False)

        return None

    def _get_resource_expected_value(self, resource_type, section, param_name, op_name=None):
        """
        Get expected value for a given resource configuration parameter.

        :param resource_type: The type of the resource.
        :type resource_type: str
        :param section: The section of the resource configuration.
        :type section: str
        :param param_name: The name of the configuration parameter.
        :type param_name: str
        :param op_name: The name of the operation (if applicable), defaults to None
        :type op_name: str, optional
        :return: The expected value for the resource configuration parameter.
        :rtype: tuple(str, bool)
        """
        resource_defaults = (
            self.constants["RESOURCE_DEFAULTS"].get(self.os_type, {}).get(resource_type, {})
        )
        attr = None
        if section == "meta_attributes":
            attr = resource_defaults.get("meta_attributes", {}).get(param_name)
        elif section == "operations":
            ops = resource_defaults.get("operations", {}).get(op_name, {})
            attr = ops.get(param_name)
        elif section == "instance_attributes":
            attr = resource_defaults.get("instance_attributes", {}).get(param_name)

        return (attr.get("value"), attr.get("required", False)) if attr else None

    def _create_parameter(
        self,
        category,
        name,
        value,
        expected_value=None,
        id=None,
        subcategory=None,
        op_name=None,
    ):
        """
        Create a parameter dictionary for the given configuration.

        :param category: The category of the configuration parameter.
        :type category: str
        :param name: The name of the configuration parameter.
        :type name: str
        :param value: The value of the configuration parameter.
        :type value: str
        :param expected_value: The expected value for the configuration parameter, defaults to None
        :type expected_value: str, optional
        :param id: The ID of the configuration parameter, defaults to None
        :type id: str, optional
        :param subcategory: The subcategory of the configuration parameter, defaults to None
        :type subcategory: str, optional
        :param op_name: The name of the operation (if applicable), defaults to None
        :type op_name: str, optional
        :return: A dictionary representing the parameter.
        :rtype: dict
        """
        if expected_value is None:
            expected_config = self._get_expected_value_for_category(
                category, subcategory, name, op_name
            )
        else:
            if isinstance(expected_value, tuple) and len(expected_value) == 2:
                expected_config = expected_value  # Already in correct format
            else:
                expected_config = (expected_value, False)

        status = self._determine_parameter_status(value, expected_config)

        display_expected_value = None
        if expected_config is None:
            display_expected_value = ""
        else:
            if isinstance(expected_config, tuple):
                display_expected_value = expected_config[0]
            else:
                display_expected_value = expected_config

        if isinstance(display_expected_value, list):
            display_expected_value = display_expected_value[0] if display_expected_value else ""
        elif isinstance(display_expected_value, dict):
            display_expected_value = (
                [
                    item
                    for val in display_expected_value.values()
                    for item in (val if isinstance(val, list) else [val])
                ]
                if display_expected_value
                else ""
            )

        return Parameters(
            category=f"{category}_{subcategory}" if subcategory else category,
            id=id if id else "",
            name=name if not op_name else f"{op_name}_{name}",
            value=value,
            expected_value=display_expected_value if display_expected_value is not None else "",
            status=status if status else TestStatus.ERROR.value,
        ).to_dict()

    def _get_expected_value_for_category(self, category, subcategory, name, op_name):
        """
        Get expected value based on category type.
        This method can be overridden by subclasses for custom logic.

        :param category: The category of the configuration parameter.
        :type category: str
        :param subcategory: The subcategory of the configuration parameter.
        :type subcategory: str
        :param name: The name of the configuration parameter.
        :type name: str
        :param op_name: The name of the operation (if applicable).
        :type op_name: str
        :return: The expected value for the configuration parameter.
        :rtype: str or list or dict
        """
        if category in self.RESOURCE_CATEGORIES:
            return self._get_resource_expected_value(
                resource_type=category,
                section=subcategory,
                param_name=name,
                op_name=op_name,
            )
        else:
            return self._get_expected_value(category, name)

    def _determine_parameter_status(self, value, expected_config):
        """
        Determine the status of a parameter based on its value and expected value.

        :param value: The actual value of the parameter.
        :type value: str
        :param expected_config: The expected value of the parameter and bool indicating if required.
        :type expected_config: tuple(str, bool)
        :return: The status of the parameter.
        :rtype: str
        """
        if expected_config is None:
            return TestStatus.INFO.value

        if isinstance(expected_config, tuple):
            expected_value, is_required = expected_config
        elif isinstance(expected_config, dict):
            expected_value = expected_config.get("value")
            is_required = expected_config.get("required", False)
        else:
            expected_value = expected_config
            is_required = False

        if not value or value == "":
            if is_required:
                return TestStatus.WARNING.value
            else:
                return TestStatus.INFO.value

        if expected_value is None or expected_value == "":
            return TestStatus.INFO.value
        elif isinstance(expected_value, list):
            return (
                TestStatus.SUCCESS.value if str(value) in expected_value else TestStatus.ERROR.value
            )
        else:
            return (
                TestStatus.SUCCESS.value
                if str(value) == str(expected_value)
                else TestStatus.ERROR.value
            )

    def _parse_nvpair_elements(self, elements, category, subcategory=None, op_name=None):
        """
        Parse nvpair elements and create parameter dictionaries.

        :param elements: List of nvpair elements to parse.
        :type elements: list
        :param category: The category of the configuration parameter.
        :type category: str
        :param subcategory: The subcategory of the configuration parameter, defaults to None
        :type subcategory: str, optional
        :param op_name: The name of the operation (if applicable), defaults to None
        :type op_name: str, optional
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        for nvpair in elements:
            name = nvpair.get("name", "")
            if name in ["passwd", "password", "login"]:
                continue
            else:
                parameters.append(
                    self._create_parameter(
                        category=category,
                        subcategory=subcategory,
                        op_name=op_name,
                        id=nvpair.get("id", ""),
                        name=name,
                        value=nvpair.get("value", ""),
                    )
                )
        return parameters

    def _parse_os_parameters(self):
        """
        Parse and validate OS-specific configuration parameters.

        :return: A list of parameter dictionaries containing validation results.
        :rtype: list
        """
        parameters = []

        os_parameters = self.constants["OS_PARAMETERS"].get("DEFAULTS", {})

        for section, params in os_parameters.items():
            for param_name, expected_value in params.items():
                value = (
                    self.execute_command_subprocess(command=[section, param_name])
                    .strip()
                    .split("\n")[0]
                )
                parameters.append(
                    self._create_parameter(
                        category="os",
                        id=section,
                        name=param_name,
                        value=value,
                        expected_value=expected_value.get("value", "") if expected_value else None,
                    )
                )

        return parameters

    def _parse_resource(self, element, category):
        """
        Parse resource-specific configuration parameters

        :param element: The XML element to parse.
        :type element: xml.etree.ElementTree.Element
        :param category: The category of the resource.
        :type category: str
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        if category.endswith("_meta"):
            param_dict = self._parse_nvpair_elements(
                elements=element.findall(".//nvpair"),
                category=category.split("_")[0],
                subcategory="meta_attributes",
            )
            parameters.extend(param_dict)

        for attr in ["meta_attributes", "instance_attributes"]:
            attr_elements = element.find(f".//{attr}")
            if attr_elements is not None:
                parameters.extend(
                    self._parse_nvpair_elements(
                        elements=attr_elements.findall(".//nvpair"),
                        category=category,
                        subcategory=attr,
                    )
                )

        operations = element.find(".//operations")
        if operations is not None:
            for operation in operations.findall(".//op"):
                for op_type in ["timeout", "interval"]:
                    parameters.append(
                        self._create_parameter(
                            category=category,
                            subcategory="operations",
                            id=operation.get("id", ""),
                            name=op_type,
                            op_name=operation.get("name", ""),
                            value=operation.get(op_type, ""),
                        )
                    )
        return parameters

    def _parse_resources_section(self, root):
        """
        Parse resources section - can be overridden by subclasses for custom resource parsing.

        :param root: The XML root element to parse.
        :type root: xml.etree.ElementTree.Element
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        for sub_category, xpath in self.RESOURCE_CATEGORIES.items():
            elements = root.findall(xpath)
            for element in elements:
                parameters.extend(self._parse_resource(element, sub_category))
        return parameters

    def _get_additional_parameters(self):
        """
        Get additional parameters specific to subclasses.
        This method should be overridden by subclasses to add their specific parameters.

        :return: A list of additional parameter dictionaries.
        :rtype: list
        """
        return []

    def _should_skip_scope(self, scope):
        """
        Determine if a scope should be skipped.
        Can be overridden by subclasses for custom logic.

        :param scope: The scope to check.
        :type scope: str
        :return: True if scope should be skipped, False otherwise.
        :rtype: bool
        """
        return scope == "op_defaults" and self.os_type == OperatingSystemFamily.REDHAT.value.upper()

    def _get_scope_from_cib(self, scope):
        """
        Extract specific scope data from loaded CIB data.

        :param scope: The scope to extract (e.g., 'resources', 'constraints')
        :type scope: str
        :return: XML element for the scope
        :rtype: xml.etree.ElementTree.Element or None
        """
        if self.cib_output:
            self.cib_output = (
                self.parse_xml_output(self.cib_output)
                if isinstance(self.cib_output, str)
                else self.cib_output
            )
        else:
            return None

        scope_mappings = {
            "resources": ".//resources",
            "constraints": ".//constraints",
            "crm_config": ".//crm_config",
            "rsc_defaults": ".//rsc_defaults",
            "op_defaults": ".//op_defaults",
        }

        xpath = scope_mappings.get(scope)
        if xpath:
            return self.cib_output.find(xpath)
        return None

    def validate_from_constants(self):
        """
        Constants-first validation approach: iterate through constants and validate against CIB.
        This ensures all expected parameters are checked, with offline validation support.
        """
        parameters = []

        for category in ["crm_config", "rsc_defaults", "op_defaults"]:
            if not self._should_skip_scope(category):
                parameters.extend(self._validate_basic_constants(category))
        parameters.extend(self._validate_resource_constants())
        parameters.extend(self._validate_constraint_constants())
        try:
            if not self.cib_output:
                parameters.extend(self._parse_os_parameters())
            else:
                self.result["message"] += "CIB output provided, skipping OS parameters parsing. "
        except Exception as ex:
            self.result["message"] += f"Failed to get OS parameters: {str(ex)} "

        try:
            if not self.cib_output:
                parameters.extend(self._get_additional_parameters())
            else:
                self.result[
                    "message"
                ] += "CIB output provided, skipping additional parameters parsing. "
        except Exception as ex:
            self.result["message"] += f"Failed to get additional parameters: {str(ex)} "

        failed_parameters = [
            param
            for param in parameters
            if param.get("status", TestStatus.ERROR.value) == TestStatus.ERROR.value
        ]
        warning_parameters = [
            param for param in parameters if param.get("status", "") == TestStatus.WARNING.value
        ]

        if failed_parameters:
            overall_status = TestStatus.ERROR.value
        elif warning_parameters:
            overall_status = TestStatus.WARNING.value
        else:
            overall_status = TestStatus.SUCCESS.value

        self.result.update(
            {
                "details": {"parameters": parameters},
                "status": overall_status,
            }
        )
        self.result["message"] += "HA Parameter Validation completed successfully. "

    def _validate_basic_constants(self, category):
        """
        Validate basic configuration constants with offline validation support.
        Uses existing CIB parsing logic but focuses on constants-first approach.
        Creates dynamic subcategories based on element IDs found in CIB.

        :param category: The category to validate (crm_config, rsc_defaults, op_defaults)
        :type category: str
        :return: A list of parameter dictionaries
        :rtype: list
        """
        parameters = []

        if category not in self.BASIC_CATEGORIES:
            return parameters

        _, constants_key = self.BASIC_CATEGORIES[category]
        category_constants = self.constants.get(constants_key, {})

        for param_name, expected_config in category_constants.items():
            param_value, param_id = self._find_param_with_element_info(category, param_name)
            expected_result = self._get_expected_value(category, param_name)
            if expected_result:
                expected_value, is_required = expected_result
                expected_config_tuple = (expected_value, is_required)
            else:
                if isinstance(expected_config, dict):
                    expected_value = expected_config.get("value", "")
                    is_required = expected_config.get("required", False)
                    expected_config_tuple = (expected_value, is_required)
                else:
                    expected_value = str(expected_config)
                    expected_config_tuple = (expected_value, False)

            parameters.append(
                self._create_parameter(
                    category=category,
                    name=param_name,
                    value=param_value,
                    expected_value=expected_config_tuple,
                    subcategory=param_id if param_id else "",
                    id=param_id,
                )
            )

        return parameters

    def _find_param_with_element_info(self, category, param_name):
        """
        Find a parameter value and its own unique ID in CIB XML.
        Returns both the parameter value and the parameter's own ID (not container ID).

        :param category: The category scope to search in (crm_config, rsc_defaults, op_defaults)
        :type category: str
        :param param_name: The parameter name to find
        :type param_name: str
        :return: Tuple of (parameter_value, parameter_id) or ("", "") if not found
        :rtype: tuple(str, str)
        """
        param_value, param_id = "", ""
        try:
            if self.cib_output:
                root = self._get_scope_from_cib(category)
            else:
                root = self.parse_xml_output(
                    self.execute_command_subprocess(CIB_ADMIN(scope=category))
                )

            if not root:
                return param_value, param_id

            if category in self.BASIC_CATEGORIES:
                for element in root.findall(self.BASIC_CATEGORIES[category][0]):
                    for nvpair in element.findall(".//nvpair"):
                        if nvpair.get("name") == param_name:
                            param_id = nvpair.get("id", "")
                            param_value = nvpair.get("value", "")
                            return param_value, param_id

        except Exception as ex:
            self.result[
                "message"
            ] += f"Error finding parameter {param_name} in {category}: {str(ex)} "

        return param_value, param_id

    def _validate_resource_constants(self):
        """
        Resource validation - to be overridden by subclasses.
        Base implementation returns empty list.

        :return: A list of parameter dictionaries
        :rtype: list
        """
        return []

    def _validate_constraint_constants(self):
        """
        Validate constraint constants with offline validation support.
        Uses constants-first approach to validate constraints against CIB.

        :return: A list of parameter dictionaries
        :rtype: list
        """
        parameters = []

        if "CONSTRAINTS" not in self.constants:
            return parameters

        try:
            if self.cib_output:
                constraints_scope = self._get_scope_from_cib("constraints")
            else:
                constraints_scope = self.parse_xml_output(
                    self.execute_command_subprocess(CIB_ADMIN(scope="constraints"))
                )

            if constraints_scope is not None:
                for constraint_type, constraint_config in self.constants["CONSTRAINTS"].items():
                    elements = constraints_scope.findall(f".//{constraint_type}")

                    for element in elements:
                        for attr_name, expected_config in constraint_config.items():
                            actual_value = element.get(attr_name, "")
                            expected_value = (
                                expected_config.get("value")
                                if isinstance(expected_config, dict)
                                else expected_config
                            )

                            parameters.append(
                                self._create_parameter(
                                    category="constraints",
                                    subcategory=constraint_type,
                                    id=element.get("id", ""),
                                    name=attr_name,
                                    value=actual_value,
                                    expected_value=expected_value,
                                )
                            )

        except Exception as ex:
            self.result["message"] += f"Error validating constraint constants: {str(ex)} "

        return parameters
