# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Pacemaker Cluster Configuration Validator.

This module provides functionality to validate Pacemaker cluster configurations
against predefined standards for SAP HANA deployments.

Classes:
    HAClusterValidator: Main validator class for cluster configurations.
"""

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import (
        SapAutomationQA,
        TestStatus,
        Parameters,
    )
    from ansible.module_utils.commands import CIB_ADMIN
except ImportError:
    from src.module_utils.sap_automation_qa import (
        SapAutomationQA,
        TestStatus,
        Parameters,
    )
    from src.module_utils.commands import CIB_ADMIN

DOCUMENTATION = r"""
---
module: get_pcmk_properties_db
short_description: Validates Pacemaker cluster configurations for SAP HANA
description:
    - Validates Pacemaker cluster configurations against predefined standards for SAP HANA deployments
    - Checks basic cluster properties, resource configurations, and constraints
    - Verifies OS parameters and global.ini settings
    - Provides detailed validation results for each parameter
options:
    sid:
        description:
            - SAP HANA database SID
        type: str
        required: true
    instance_number:
        description:
            - SAP HANA instance number
        type: str
        required: true
    ansible_os_family:
        description:
            - Operating system family (redhat, suse, etc.)
        type: str
        required: true
    virtual_machine_name:
        description:
            - Name of the virtual machine
        type: str
        required: true
    fencing_mechanism:
        description:
            - Type of fencing mechanism used
        type: str
        required: true
    os_version:
        description:
            - Operating system version
        type: str
        required: true
    pcmk_constants:
        description:
            - Dictionary of constants for validation
        type: dict
        required: true
author:
    - Microsoft Corporation
notes:
    - Module requires root privileges to execute cluster management commands
    - Relies on cibadmin to query Pacemaker configuration
    - Validates configurations against predefined standards in pcmk_constants
requirements:
    - python >= 3.6
    - Pacemaker cluster environment
"""

EXAMPLES = r"""
- name: Validate Pacemaker cluster configuration for SAP HANA
  get_pcmk_properties_db:
    sid: "HDB"
    instance_number: "00"
    ansible_os_family: "{{ ansible_os_family|lower }}"
    virtual_machine_name: "{{ ansible_hostname }}"
    fencing_mechanism: "sbd"
    os_version: "{{ ansible_distribution_version }}"
    pcmk_constants: "{{ pcmk_validation_constants }}"
  register: pcmk_validation_result

- name: Display cluster validation results
  debug:
    var: pcmk_validation_result

- name: Fail if cluster configuration is invalid
  fail:
    msg: "Pacemaker cluster configuration does not meet requirements"
  when: pcmk_validation_result.status == 'ERROR'
"""

RETURN = r"""
status:
    description: Status of the validation
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Descriptive message about the validation results
    returned: always
    type: str
    sample: "HA Parameter Validation completed successfully."
details:
    description: Detailed validation results
    returned: always
    type: dict
    contains:
        parameters:
            description: List of validated parameters
            returned: always
            type: list
            elements: dict
            contains:
                category:
                    description: Category of the parameter
                    type: str
                    sample: "crm_config"
                id:
                    description: ID of the parameter
                    type: str
                    sample: "cib-bootstrap-options-stonith-enabled"
                name:
                    description: Name of the parameter
                    type: str
                    sample: "stonith-enabled"
                value:
                    description: Actual value found
                    type: str
                    sample: "true"
                expected_value:
                    description: Expected value for comparison
                    type: str
                    sample: "true"
                status:
                    description: Result of the comparison
                    type: str
                    sample: "SUCCESS"
"""


class HAClusterValidator(SapAutomationQA):
    """
    Validates High Availability cluster configurations.

    This class validates Pacemaker cluster configurations against predefined
    standards for SAP HANA deployments. It checks both basic cluster properties
    and resource-specific configurations.

    Attributes:
        BASIC_CATEGORIES (Dict): Mapping of basic configuration categories to their XPaths
        RESOURCE_CATEGORIES (Dict): Mapping of resource types to their XPaths
    """

    BASIC_CATEGORIES = {
        "crm_config": (".//cluster_property_set", "CRM_CONFIG_DEFAULTS"),
        "rsc_defaults": (".//meta_attributes", "RSC_DEFAULTS"),
        "op_defaults": (".//meta_attributes", "OP_DEFAULTS"),
    }

    CONSTRAINTS_CATEGORIES = (".//*", "CONSTRAINTS_DEFAULTS")

    RESOURCE_CATEGORIES = {
        "sbd_stonith": ".//primitive[@type='external/sbd']",
        "fence_agent": ".//primitive[@type='fence_azure_arm']",
        "topology": ".//clone/primitive[@type='SAPHanaTopology']",
        "topology_meta": ".//clone/meta_attributes",
        "hana": ".//master/primitive[@type='SAPHana']",
        "hana_meta": ".//master/meta_attributes",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "filesystem": ".//primitive[@type='Filesystem']",
        "azurelb": ".//primitive[@type='azure-lb']",
    }

    def __init__(
        self,
        os_type,
        os_version,
        sid,
        instance_number,
        fencing_mechanism,
        virtual_machine_name,
        constants,
        category=None,
    ):
        super().__init__()
        self.os_type = os_type
        self.os_version = os_version
        self.category = category
        self.sid = sid
        self.instance_number = instance_number
        self.fencing_mechanism = fencing_mechanism
        self.virtual_machine_name = virtual_machine_name
        self.constants = constants
        self.parse_ha_cluster_config()

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
            if category in self.RESOURCE_CATEGORIES:
                expected_value = self._get_resource_expected_value(
                    resource_type=category,
                    section=subcategory,
                    param_name=name,
                    op_name=op_name,
                )
            else:
                expected_value = self._get_expected_value(category, name)

        if expected_value is None or value == "":
            status = TestStatus.INFO.value
        elif isinstance(expected_value, (str, list)):
            if isinstance(expected_value, list):
                status = (
                    TestStatus.SUCCESS.value
                    if str(value) in expected_value
                    else TestStatus.ERROR.value
                )
                expected_value = expected_value[0]
            else:
                status = (
                    TestStatus.SUCCESS.value
                    if str(value) == str(expected_value)
                    else TestStatus.ERROR.value
                )
        else:
            status = TestStatus.ERROR.value

        return Parameters(
            category=f"{category}_{subcategory}" if subcategory else category,
            id=id if id else "",
            name=name if not op_name else f"{op_name}_{name}",
            value=value,
            expected_value=expected_value if expected_value is not None else "",
            status=status if status else TestStatus.ERROR.value,
        ).to_dict()

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

    def _parse_global_ini_parameters(self):
        """
        Parse global.ini parameters

        :return: A list of parameter dictionaries containing validation results.
        :rtype: list
        """
        parameters = []
        global_ini_defaults = self.constants["GLOBAL_INI"].get(self.os_type, {})

        with open(
            f"/usr/sap/{self.sid}/SYS/global/hdb/custom/config/global.ini",
            "r",
            encoding="utf-8",
        ) as file:
            global_ini_content = file.read().splitlines()

        section_start = global_ini_content.index("[ha_dr_provider_SAPHanaSR]")
        properties_slice = global_ini_content[section_start + 1 : section_start + 4]

        global_ini_properties = {
            key.strip(): val.strip()
            for line in properties_slice
            for key, sep, val in [line.partition("=")]
            if sep
        }

        for param_name, expected_value in global_ini_defaults.items():
            value = global_ini_properties.get(param_name, "")
            if isinstance(expected_value, list):
                if value in expected_value:
                    expected_value = value
            parameters.append(
                self._create_parameter(
                    category="global_ini",
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

        if category in ["hana_meta", "topology_meta"]:
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

    def parse_ha_cluster_config(self):
        """
        Parse HA cluster configuration XML and return a list of properties.
        """
        parameters = []

        for scope in [
            "rsc_defaults",
            "crm_config",
            "op_defaults",
            "constraints",
            "resources",
        ]:
            if scope == "op_defaults" and self.os_type == "REDHAT":
                continue
            self.category = scope
            root = self.parse_xml_output(self.execute_command_subprocess(CIB_ADMIN(scope=scope)))
            if not root:
                continue

            if self.category in self.BASIC_CATEGORIES:
                try:
                    xpath = self.BASIC_CATEGORIES[self.category][0]
                    for element in root.findall(xpath):
                        parameters.extend(self._parse_basic_config(element, self.category))
                except Exception as ex:
                    self.result[
                        "message"
                    ] += f"Failed to get {self.category} configuration: {str(ex)}"
                    continue

            elif self.category == "resources":
                try:
                    for sub_category, xpath in self.RESOURCE_CATEGORIES.items():
                        elements = root.findall(xpath)
                        for element in elements:
                            parameters.extend(self._parse_resource(element, sub_category))
                except Exception as ex:
                    self.result[
                        "message"
                    ] += f"Failed to get resources configuration for {self.category}: {str(ex)}"
                    continue

            elif self.category == "constraints":
                try:
                    parameters.extend(self._parse_constraints(root))
                except Exception as ex:
                    self.result["message"] += f"Failed to get constraints configuration: {str(ex)}"
                    continue

        try:
            parameters.extend(self._parse_os_parameters())
        except Exception as ex:
            self.result["message"] += f"Failed to get OS parameters: {str(ex)} \n"

        try:
            parameters.extend(self._parse_global_ini_parameters())
        except Exception as ex:
            self.result["message"] += f"Failed to get global.ini parameters: {str(ex)} \n"

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
        self.result["message"] += "HA Parameter Validation completed successfully."


def main() -> None:
    """
    Main entry point for the Ansible module.
    """
    module = AnsibleModule(
        argument_spec=dict(
            sid=dict(type="str"),
            instance_number=dict(type="str"),
            ansible_os_family=dict(type="str"),
            virtual_machine_name=dict(type="str"),
            fencing_mechanism=dict(type="str"),
            os_version=dict(type="str"),
            pcmk_constants=dict(type="dict"),
        )
    )

    validator = HAClusterValidator(
        os_type=module.params["ansible_os_family"],
        os_version=module.params["os_version"],
        instance_number=module.params["instance_number"],
        sid=module.params["sid"],
        virtual_machine_name=module.params["virtual_machine_name"],
        fencing_mechanism=module.params["fencing_mechanism"],
        constants=module.params["pcmk_constants"],
    )

    module.exit_json(**validator.get_result())


if __name__ == "__main__":
    main()
