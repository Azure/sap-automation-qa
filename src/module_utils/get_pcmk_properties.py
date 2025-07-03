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
        :rtype: str
        """
        _, defaults_key = self.BASIC_CATEGORIES[category]

        fence_config = self.constants["VALID_CONFIGS"].get(self.fencing_mechanism, {})
        os_config = self.constants["VALID_CONFIGS"].get(self.os_type, {})

        return fence_config.get(name) or os_config.get(name, self.constants[defaults_key].get(name))

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
        :rtype: str
        """
        resource_defaults = (
            self.constants["RESOURCE_DEFAULTS"].get(self.os_type, {}).get(resource_type, {})
        )

        if section == "meta_attributes":
            return resource_defaults.get("meta_attributes", {}).get(param_name)
        elif section == "operations":
            ops = resource_defaults.get("operations", {}).get(op_name, {})
            return ops.get(param_name)
        elif section == "instance_attributes":
            return resource_defaults.get("instance_attributes", {}).get(param_name)
        return None

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
            expected_value = self._get_expected_value_for_category(
                category, subcategory, name, op_name
            )

        status = self._determine_parameter_status(value, expected_value)

        if isinstance(expected_value, list):
            expected_value = expected_value[0] if expected_value else ""

        return Parameters(
            category=f"{category}_{subcategory}" if subcategory else category,
            id=id if id else "",
            name=name if not op_name else f"{op_name}_{name}",
            value=value,
            expected_value=expected_value if expected_value is not None else "",
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

    def _determine_parameter_status(self, value, expected_value):
        """
        Determine the status of a parameter based on its value and expected value.

        :param value: The actual value of the parameter.
        :type value: str
        :param expected_value: The expected value of the parameter.
        :type expected_value: str or list or dict
        :return: The status of the parameter.
        :rtype: str
        """
        if expected_value is None or value == "":
            return TestStatus.INFO.value
        elif isinstance(expected_value, (str, list)):
            if isinstance(expected_value, list):
                return (
                    TestStatus.SUCCESS.value
                    if str(value) in expected_value
                    else TestStatus.ERROR.value
                )
            else:
                return (
                    TestStatus.SUCCESS.value
                    if str(value) == str(expected_value)
                    else TestStatus.ERROR.value
                )
        else:
            return TestStatus.ERROR.value

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
                        expected_value=expected_value,
                    )
                )

        return parameters

    def _parse_basic_config(self, element, category, subcategory=None):
        """
        Parse basic configuration parameters

        :param element: The XML element to parse.
        :type element: xml.etree.ElementTree.Element
        :param category: The category of the configuration parameter.
        :type category: str
        :param subcategory: The subcategory of the configuration parameter, defaults to None
        :type subcategory: str, optional
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        for nvpair in element.findall(".//nvpair"):
            parameters.append(
                self._create_parameter(
                    category=category,
                    subcategory=subcategory,
                    name=nvpair.get("name", ""),
                    value=nvpair.get("value", ""),
                    id=nvpair.get("id", ""),
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

    def _parse_constraints(self, root):
        """
        Parse constraints configuration parameters

        :param root: The XML root element to parse.
        :type root: xml.etree.ElementTree.Element
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        for element in root:
            tag = element.tag
            if tag in self.constants["CONSTRAINTS"]:
                for attr, expected in self.constants["CONSTRAINTS"][tag].items():
                    if element.get(attr) is not None:
                        parameters.append(
                            self._create_parameter(
                                category="constraints",
                                subcategory=tag,
                                id=element.get("id", ""),
                                name=attr,
                                value=element.get(attr),
                                expected_value=expected,
                            )
                        )
                    else:
                        continue
            else:
                continue
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

    def parse_ha_cluster_config(self):
        """
        Parse HA cluster configuration XML and return a list of properties.
        This is the main orchestration method that coordinates all parsing activities.
        """
        parameters = []

        scopes = [
            "rsc_defaults",
            "crm_config",
            "op_defaults",
            "constraints",
            "resources",
        ]

        for scope in scopes:
            if self._should_skip_scope(scope):
                continue

            self.category = scope
            if self.cib_output:
                root = self._get_scope_from_cib(scope)
            else:
                root = self.parse_xml_output(
                    self.execute_command_subprocess(CIB_ADMIN(scope=scope))
                )
            if not root:
                continue

            try:
                if self.category in self.BASIC_CATEGORIES:
                    xpath = self.BASIC_CATEGORIES[self.category][0]
                    for element in root.findall(xpath):
                        parameters.extend(self._parse_basic_config(element, self.category))

                elif self.category == "resources":
                    parameters.extend(self._parse_resources_section(root))

                elif self.category == "constraints":
                    parameters.extend(self._parse_constraints(root))

            except Exception as ex:
                self.result["message"] += f"Failed to get {self.category} configuration: {str(ex)}"
                continue
        try:
            if not self.cib_output:
                parameters.extend(self._parse_os_parameters())
            else:
                self.result["message"] += "CIB output provided, skipping OS parameters parsing. "
        except Exception as ex:
            self.result["message"] += f"Failed to get OS parameters: {str(ex)} \n"
        try:
            if not self.cib_output:
                parameters.extend(self._get_additional_parameters())
            else:
                self.result[
                    "message"
                ] += "CIB output provided, skipping additional parameters parsing. "
        except Exception as ex:
            self.result["message"] += f"Failed to get additional parameters: {str(ex)} \n"
        failed_parameters = [
            param
            for param in parameters
            if param.get("status", TestStatus.ERROR.value) == TestStatus.ERROR.value
        ]
        self.result.update(
            {
                "details": {"parameters": parameters},
                "status": (
                    TestStatus.ERROR.value if failed_parameters else TestStatus.SUCCESS.value
                ),
            }
        )
        self.result["message"] += "HA Parameter Validation completed successfully. "
