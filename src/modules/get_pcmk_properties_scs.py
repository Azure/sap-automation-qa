# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Pacemaker Cluster Configuration Validator.

This module provides functionality to validate Pacemaker cluster configurations
against predefined standards for SAP Application Tier ASCS/ERS deployments.

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
module: get_pcmk_properties_scs
short_description: Validates Pacemaker cluster configurations for SAP ASCS/ERS
description:
    - Validates Pacemaker cluster configurations against predefined standards for SAP Application Tier ASCS/ERS deployments
    - Checks basic cluster properties, resource configurations, constraints, and OS parameters
    - Provides detailed validation results for each parameter
    - Supports different configurations based on operating system and fencing mechanism
options:
    sid:
        description:
            - SAP System ID (SID)
        type: str
        required: true
    ascs_instance_number:
        description:
            - SAP ASCS instance number
        type: str
        required: true
    ers_instance_number:
        description:
            - SAP ERS instance number
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
    pcmk_constants:
        description:
            - Dictionary of constants for validation
        type: dict
        required: true
    fencing_mechanism:
        description:
            - Type of fencing mechanism used
        type: str
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
- name: Validate Pacemaker cluster configuration for SAP ASCS/ERS
  get_pcmk_properties_scs:
    sid: "S4D"
    ascs_instance_number: "00"
    ers_instance_number: "10"
    ansible_os_family: "{{ ansible_os_family|lower }}"
    virtual_machine_name: "{{ ansible_hostname }}"
    pcmk_constants: "{{ pcmk_validation_constants }}"
    fencing_mechanism: "sbd"
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
                    sample: "crm_config_meta_attributes"
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
        "stonith": ".//primitive[@class='stonith']",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "azurelb": ".//primitive[@type='azure-lb']",
        "azureevents": ".//primitive[@type='azure-events-az']",
    }

    def __init__(
        self,
        os_type,
        sid,
        scs_instance_number,
        ers_instance_number,
        virtual_machine_name,
        constants,
        fencing_mechanism,
        category=None,
    ):
        super().__init__()
        self.os_type = os_type
        self.category = category
        self.sid = sid
        self.scs_instance_number = scs_instance_number
        self.ers_instance_number = ers_instance_number
        self.virtual_machine_name = virtual_machine_name
        self.fencing_mechanism = fencing_mechanism
        self.constants = constants
        self.parse_ha_cluster_config()

    def _get_expected_value(self, category, name):
        """
        Get expected value for basic configuration parameters.

        :param category: Category of the parameter
        :type category: str
        :param name: Name of the parameter
        :type name: str
        :return: Expected value of the parameter
        :rtype: str
        """
        _, defaults_key = self.BASIC_CATEGORIES[category]

        fence_config = self.constants["VALID_CONFIGS"].get(self.fencing_mechanism, {})
        os_config = self.constants["VALID_CONFIGS"].get(self.os_type, {})

        return fence_config.get(name) or os_config.get(name, self.constants[defaults_key].get(name))

    def _get_resource_expected_value(self, resource_type, section, param_name, op_name=None):
        """
        Get expected value for resource-specific configuration parameters.

        :param resource_type: Type of the resource (e.g., stonith, ipaddr)
        :type resource_type: str
        :param section: Section of the resource (e.g., meta_attributes, operations)
        :type section: str
        :param param_name: Name of the parameter
        :type param_name: str
        :param op_name: Name of the operation (if applicable)
        :type op_name: str
        :return: Expected value of the parameter
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
        Create a Parameters object for a given configuration parameter.

        :param category: Category of the parameter
        :type category: str
        :param name: Name of the parameter
        :type name: str
        :param value: Value of the parameter
        :type value: str
        :param expected_value: Expected value of the parameter
        :type expected_value: str
        :param id: ID of the parameter (optional)
        :type id: str
        :param subcategory: Subcategory of the parameter (optional)
        :type subcategory: str
        :param op_name: Operation name (optional)
        :type op_name: str
        :return: Parameters object
        :rtype: Parameters
        """
        if expected_value is None:
            if category in self.RESOURCE_CATEGORIES or category in ["ascs", "ers"]:
                expected_value = self._get_resource_expected_value(
                    resource_type=category,
                    section=subcategory,
                    param_name=name,
                    op_name=op_name,
                )
            else:
                expected_value = self._get_expected_value(category, name)

        return Parameters(
            category=f"{category}_{subcategory}" if subcategory else category,
            id=id if id else "",
            name=name if not op_name else f"{op_name}_{name}",
            value=value,
            expected_value=expected_value if expected_value is not None else "",
            status=(
                TestStatus.INFO.value
                if expected_value is None or value == ""
                else (
                    TestStatus.SUCCESS.value
                    if str(value) == str(expected_value)
                    else TestStatus.ERROR.value
                )
            ),
        ).to_dict()

    def _parse_nvpair_elements(self, elements, category, subcategory=None, op_name=None):
        """
        Parse nvpair elements and return a list of Parameters objects.

        :param elements: List of XML elements to parse
        :type elements: List[ElementTree.Element]
        :param category: Category of the parameters
        :type category: str
        :param subcategory: Subcategory of the parameters
        :type subcategory: str
        :param op_name: Operation name (if applicable)
        :type op_name: str
        :return: List of Parameters objects
        :rtype: List[Parameters]
        """
        parameters = []
        for nvpair in elements:
            parameters.append(
                self._create_parameter(
                    category=category,
                    subcategory=subcategory,
                    op_name=op_name,
                    id=nvpair.get("id", ""),
                    name=nvpair.get("name", ""),
                    value=nvpair.get("value", ""),
                )
            )
        return parameters

    def _parse_resource(self, element, category):
        """
        Parse resource-specific configuration parameters

        :param element: XML element to parse
        :type element: ElementTree.Element
        :param category: Resource category (e.g., stonith, ipaddr)
        :type category: str
        :return: List of Parameters objects for the resource
        :rtype: List[Parameters]
        """
        parameters = []

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

    def _parse_basic_config(self, element, category, subcategory=None):
        """
        Parse basic configuration parameters

        :param element: XML element to parse
        :type element: ElementTree.Element
        :param category: Category of the parameters
        :type category: str
        :param subcategory: Subcategory of the parameters
        :type subcategory: str
        :return: List of Parameters objects for basic configuration
        :rtype: List[Parameters]
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

    def _parse_os_parameters(self):
        """
        Parse OS-specific parameters

        :return: List of Parameters objects for OS parameters
        :rtype: List[Parameters]
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

    def _parse_constraints(self, root):
        """
        Parse constraints configuration parameters

        :param root: XML root element
        :type root: ElementTree.Element
        :return: List of Parameters objects for constraints
        :rtype: List[Parameters]
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

                    for group in root.findall(".//group"):
                        group_id = group.get("id", "")
                        if "ASCS" in group_id:
                            for element in group.findall(".//primitive[@type='SAPInstance']"):
                                parameters.extend(self._parse_resource(element, "ascs"))
                        elif "ERS" in group_id:
                            for element in group.findall(".//primitive[@type='SAPInstance']"):
                                parameters.extend(self._parse_resource(element, "ers"))

                except Exception as ex:
                    self.result[
                        "message"
                    ] += f"Failed to get resources configuration for {self.category}: {str(ex)}"
                    continue

            elif self.category == "constraints":
                try:
                    parameters.extend(self._parse_constraints(root))
                except Exception as e:
                    self.result["message"] += f"Failed to get constraints configuration: {str(e)}"
                    continue

        try:
            parameters.extend(self._parse_os_parameters())
        except Exception as ex:
            self.result["message"] += f"Failed to get OS parameters: {str(ex)} \n"

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
            ascs_instance_number=dict(type="str"),
            ers_instance_number=dict(type="str"),
            ansible_os_family=dict(type="str"),
            virtual_machine_name=dict(type="str"),
            pcmk_constants=dict(type="dict"),
            fencing_mechanism=dict(type="str"),
        )
    )

    validator = HAClusterValidator(
        sid=module.params["sid"],
        scs_instance_number=module.params["ascs_instance_number"],
        ers_instance_number=module.params["ers_instance_number"],
        os_type=module.params["ansible_os_family"],
        virtual_machine_name=module.params["virtual_machine_name"],
        constants=module.params["pcmk_constants"],
        fencing_mechanism=module.params["fencing_mechanism"],
    )
    module.exit_json(**validator.get_result())


if __name__ == "__main__":
    main()
