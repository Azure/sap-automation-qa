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
        Get expected value for basic configuration parameters.
        """
        _, defaults_key = self.BASIC_CATEGORIES[category]

        fence_config = self.constants["VALID_CONFIGS"].get(self.fencing_mechanism, {})
        os_config = self.constants["VALID_CONFIGS"].get(self.os_type, {})

        return fence_config.get(name) or os_config.get(
            name, self.constants[defaults_key].get(name)
        )

    def _get_resource_expected_value(
        self, resource_type, section, param_name, op_name=None
    ):
        """
        Get expected value for resource-specific configuration parameters.
        """
        resource_defaults = (
            self.constants["RESOURCE_DEFAULTS"]
            .get(self.os_type, {})
            .get(resource_type, {})
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

    def _parse_nvpair_elements(
        self, elements, category, subcategory=None, op_name=None
    ):
        """
        Parse nvpair elements and return a list of Parameters objects.
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

    def _parse_os_parameters(self):
        """
        Parse OS-specific parameters
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

        ops = element.find(".//operations")
        if ops is not None:
            for op in ops.findall(".//op"):
                for op_type in ["timeout", "interval"]:
                    parameters.append(
                        self._create_parameter(
                            category=category,
                            subcategory="operations",
                            id=op.get("id", ""),
                            name=op_type,
                            op_name=op.get("name", ""),
                            value=op.get(op_type, ""),
                        )
                    )
        return parameters

    def _parse_constraints(self, root):
        """
        Parse constraints configuration parameters
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
            root = self.parse_xml_output(
                self.execute_command_subprocess(CIB_ADMIN(scope=scope))
            )
            if not root:
                continue

            if self.category in self.BASIC_CATEGORIES:
                try:
                    xpath = self.BASIC_CATEGORIES[self.category][0]
                    for element in root.findall(xpath):
                        parameters.extend(
                            self._parse_basic_config(element, self.category)
                        )
                except Exception as e:
                    self.result[
                        "message"
                    ] += f"Failed to get {self.category} configuration: {str(e)}"
                    continue

            elif self.category == "resources":
                try:
                    for sub_category, xpath in self.RESOURCE_CATEGORIES.items():
                        elements = root.findall(xpath)
                        for element in elements:
                            parameters.extend(
                                self._parse_resource(element, sub_category)
                            )
                except Exception as e:
                    self.result[
                        "message"
                    ] += f"Failed to get resources configuration for {self.category}: {str(e)}"
                    continue

            elif self.category == "constraints":
                try:
                    parameters.extend(self._parse_constraints(root))
                except Exception as e:
                    self.result[
                        "message"
                    ] += f"Failed to get constraints configuration: {str(e)}"
                    continue

        try:
            parameters.extend(self._parse_os_parameters())
        except Exception as e:
            self.result["message"] += f"Failed to get OS parameters: {str(e)} \n"

        try:
            parameters.extend(self._parse_global_ini_parameters())
        except Exception as e:
            self.result[
                "message"
            ] += f"Failed to get global.ini parameters: {str(e)} \n"

        failed_parameters = [
            param
            for param in parameters
            if param.get("status", TestStatus.ERROR.value) == TestStatus.ERROR.value
        ]
        self.result.update(
            {
                "details": {"parameters": parameters},
                "status": (
                    TestStatus.ERROR.value
                    if failed_parameters
                    else TestStatus.SUCCESS.value
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
