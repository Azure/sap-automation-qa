# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the cluster configuration in HANA DB node.
"""

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import (
        SapAutomationQA,
        TestStatus,
        Parameters,
    )
except ImportError:
    from src.module_utils.sap_automation_qa import (
        SapAutomationQA,
        TestStatus,
        Parameters,
    )


class HAClusterValidator(SapAutomationQA):

    BASIC_CATEGORIES = {
        "crm_config": (".//cluster_property_set", "CRM_CONFIG_DEFAULTS"),
        "rsc_defaults": (".//meta_attributes", "RSC_DEFAULTS"),
        "op_defaults": (".//meta_attributes", "OP_DEFAULTS"),
        "constraints": (".//*", "CONSTRAINTS_DEFAULTS"),
    }

    RESOURCE_CATEGORIES = {
        "stonith": ".//primitive[@class='stonith']",
        "topology": ".//clone/primitive[@type='SAPHanaTopology']",
        "hana": ".//master/primitive[@type='SAPHana']",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "filesystem": ".//primitive[@type='Filesystem']",
    }

    def __init__(
        self,
        os_type,
        os_version,
        sid,
        instance_number,
        fencing_mechanism,
        virtual_machine_name,
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
        self.constants = self.load_constants("ansible.module_utils.pcmk_defaults.yaml")
        self.config = self.parse_ha_cluster_config()
        self.result.update(
            {
                "parameters": self.config,
            }
        )

    def get_resource_expected_value(
        self, resource_type, section, param_name, op_name=None
    ):
        """Get expected value for resource parameters"""
        resource_defaults = self.constants["RESOURCE_DEFAULTS"].get(resource_type, {})

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
        id=None,
        subcategory=None,
        op_name=None,
    ):
        if category in self.RESOURCE_CATEGORIES:
            expected_value = self.get_resource_expected_value(
                resource_type=category,
                section=subcategory,
                param_name=name,
                op_name=op_name,
            )
        else:
            _, defaults_key = self.BASIC_CATEGORIES[category]
            expected_value = (
                self.constants["VALID_CONFIGS"]
                .get(self.os_type, {})
                .get(self.os_version, {})
                .get(name, self.constants[defaults_key].get(name))
            )

        return Parameters(
            category=f"{category}_{subcategory}" if subcategory else category,
            id=id,
            name=name if not op_name else f"{op_name}_{name}",
            value=value,
            expected_value=expected_value if expected_value is not None else "",
            status=(
                TestStatus.INFO.value
                if expected_value is None
                else (
                    TestStatus.SUCCESS.value
                    if str(value) == str(expected_value)
                    else TestStatus.ERROR.value
                )
            ),
        ).to_dict()

    def parse_basic_config(self, element, category):
        """Parse basic configuration parameters"""
        parameters = []
        _, defaults_key = self.BASIC_CATEGORIES[category]

        for nvpair in element.findall(".//nvpair"):
            expected_value = (
                self.constants["VALID_CONFIGS"]
                .get(self.os_type, {})
                .get(self.os_version, {})
                .get(
                    nvpair.get("name"),
                    self.constants[defaults_key].get(nvpair.get("name")),
                )
            )

            parameters.append(
                Parameters(
                    category=category,
                    id=nvpair.get("id"),
                    name=nvpair.get("name"),
                    value=nvpair.get("value"),
                    expected_value=expected_value,
                    status=(
                        TestStatus.INFO.value
                        if expected_value is None
                        else (
                            TestStatus.SUCCESS.value
                            if str(nvpair.get("value")) == str(expected_value)
                            else TestStatus.ERROR.value
                        )
                    ),
                ).to_dict()
            )
        return parameters

    def _parse_resource(self, element, category):
        parameters = []

        # Parse meta attributes
        meta = element.find(".//meta_attributes")
        if meta is not None:
            for nvpair in meta.findall(".//nvpair"):
                parameters.append(
                    self._create_parameter(
                        category=category,
                        subcategory="meta_attributes",
                        id=nvpair.get("id"),
                        name=nvpair.get("name"),
                        value=nvpair.get("value"),
                    )
                )

        # Parse operations
        ops = element.find(".//operations")
        if ops is not None:
            for op in ops.findall(".//op"):
                for op_type in ["timeout", "interval"]:
                    parameters.append(
                        self._create_parameter(
                            category=category,
                            subcategory="operations",
                            id=op.get("id"),
                            name=op_type,
                            op_name=op.get("name"),
                            value=op.get(op_type),
                        )
                    )

        # Parse instance attributes
        inst = element.find(".//instance_attributes")
        if inst is not None:
            for nvpair in inst.findall(".//nvpair"):
                parameters.append(
                    self._create_parameter(
                        category=category,
                        subcategory="instance_attributes",
                        id=nvpair.get("id"),
                        name=nvpair.get("name"),
                        value=nvpair.get("value"),
                    )
                )

        return parameters

    def parse_ha_cluster_config(self):
        """Parse HA cluster configuration XML and return a list of properties."""
        parameters = []
        for scope in [
            "rsc_defaults",
            "crm_config",
            "op_defaults",
            "constraint",
            "resources",
        ]:
            self.category = scope
            root = self.parse_xml_output(
                self.execute_command_subprocess(
                    ["cibadmin", "--query", "--scope", scope]
                )
            )
            if not root:
                continue

            # Handle basic categories
            if self.category in self.BASIC_CATEGORIES:
                xpath = self.BASIC_CATEGORIES[self.category][0]
                for element in root.findall(xpath):
                    parameters.extend(self.parse_basic_config(element, self.category))

            # Handle resource categories
            elif self.category == "resources":
                for sub_category, xpath in self.RESOURCE_CATEGORIES.items():
                    elements = root.findall(xpath)
                    for element in elements:
                        parameters.extend(self._parse_resource(element, sub_category))
        return parameters


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
        )
    )

    manager = HAClusterValidator(
        os_type=module.params["ansible_os_family"],
        os_version=module.params["os_version"],
        instance_number=module.params["instance_number"],
        sid=module.params["sid"],
        virtual_machine_name=module.params["virtual_machine_name"],
        fencing_mechanism=module.params["fencing_mechanism"],
    )

    module.exit_json(**manager.result)


if __name__ == "__main__":
    main()
