# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Pacemaker Cluster Configuration Validator.

This module provides functionality to validate Pacemaker cluster configurations
against predefined standards for SAP HANA deployments.

Classes:
    HAClusterValidator: Main validator class for cluster configurations.
"""

import logging
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.facts.compat import ansible_facts

try:
    from ansible.module_utils.get_pcmk_properties import BaseHAClusterValidator
    from ansible.module_utils.enums import OperatingSystemFamily, HanaSRProvider
except ImportError:
    from src.module_utils.get_pcmk_properties import BaseHAClusterValidator
    from src.module_utils.enums import OperatingSystemFamily, HanaSRProvider

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
    pcmk_constants:
        description:
            - Dictionary of constants for validation
        type: dict
        required: true
    saphanasr_provider:
        description:
            - SAP HANA SR provider type (e.g., SAPHanaSR, SAPHanaSR-angi)
        type: str
        required: true
    cib_output:
        description:
            - Output from cibadmin command to query Pacemaker configuration
        type: str
        required: false
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
    virtual_machine_name: "{{ ansible_hostname }}"
    fencing_mechanism: "sbd"
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


class HAClusterValidator(BaseHAClusterValidator):
    """
    Validates High Availability cluster configurations for SAP HANA.

    This class extends BaseHAClusterValidator to provide HANA-specific validation
    functionality including global.ini parameter validation and HANA-specific
    resource configurations.
    """

    RESOURCE_CATEGORIES = {
        "sbd_stonith": ".//primitive[@type='external/sbd']",
        "fence_agent": ".//primitive[@type='fence_azure_arm']",
        "topology": ".//clone/primitive[@type='SAPHanaTopology']",
        "angi_topology": ".//clone/primitive[@type='SAPHanaTopology']",
        "topology_meta": ".//clone/meta_attributes",
        "hana": ".//master/primitive[@type='SAPHana']",
        "hana_meta": ".//master/meta_attributes",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "filesystem": ".//primitive[@type='Filesystem']",
        "azurelb": ".//primitive[@type='azure-lb']",
        "angi_filesystem": ".//primitive[@type='SAPHanaFilesystem']",
        "angi_hana": ".//primitive[@type='SAPHanaController']",
    }

    def __init__(
        self,
        os_type: OperatingSystemFamily,
        sid: str,
        instance_number: str,
        fencing_mechanism: str,
        virtual_machine_name: str,
        constants: dict,
        saphanasr_provider: HanaSRProvider,
        cib_output: str,
        category=None,
    ):
        super().__init__(
            os_type=os_type,
            sid=sid,
            virtual_machine_name=virtual_machine_name,
            constants=constants,
            fencing_mechanism=fencing_mechanism,
            category=category,
            cib_output=cib_output,
        )
        self.instance_number = instance_number
        self.saphanasr_provider = saphanasr_provider
        self.parse_ha_cluster_config()

    def _parse_resources_section(self, root):
        """
        Parse resources section with HANA-specific logic.

        :param root: The XML root element to parse.
        :type root: xml.etree.ElementTree.Element
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        resource_categories = self.RESOURCE_CATEGORIES.copy()
        if self.saphanasr_provider == HanaSRProvider.ANGI:
            resource_categories.pop("topology", None)
        else:
            resource_categories.pop("angi_topology", None)

        for sub_category, xpath in resource_categories.items():
            elements = root.findall(xpath)
            for element in elements:
                parameters.extend(self._parse_resource(element, sub_category))

        return parameters

    def _parse_global_ini_parameters(self):
        """
        Parse global.ini parameters specific to SAP HANA.

        :return: A list of parameter dictionaries containing validation results.
        :rtype: list
        """
        parameters = []
        global_ini_defaults = (
            self.constants["GLOBAL_INI"]
            .get(self.os_type, {})
            .get(self.saphanasr_provider.value, {})
        )

        try:
            with open(
                f"/usr/sap/{self.sid}/SYS/global/hdb/custom/config/global.ini",
                "r",
                encoding="utf-8",
            ) as file:
                global_ini_content = file.read().splitlines()

            section_start = (
                global_ini_content.index("[ha_dr_provider_sushanasr]")
                if self.saphanasr_provider == HanaSRProvider.ANGI
                else global_ini_content.index("[ha_dr_provider_SAPHanaSR]")
            )
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

                self.log(
                    logging.INFO,
                    f"param_name: {param_name}, value: {value}, expected_value: {expected_value}",
                )
                parameters.append(
                    self._create_parameter(
                        category="global_ini",
                        name=param_name,
                        value=value,
                        expected_value=expected_value,
                    )
                )
        except Exception as ex:
            self.log(logging.ERROR, f"Error parsing global.ini: {str(ex)}")

        return parameters

    def _get_additional_parameters(self):
        """
        Get HANA-specific additional parameters (global.ini).

        :return: A list of global.ini parameter dictionaries.
        :rtype: list
        """
        return self._parse_global_ini_parameters()


def main() -> None:
    """
    Main entry point for the Ansible module.
    """

    try:
        module = AnsibleModule(
            argument_spec=dict(
                sid=dict(type="str"),
                instance_number=dict(type="str"),
                virtual_machine_name=dict(type="str"),
                fencing_mechanism=dict(type="str"),
                pcmk_constants=dict(type="dict"),
                saphanasr_provider=dict(type="str"),
                cib_output=dict(type="str", required=False, default=""),
                os_family=dict(type="str", required=False),
                filter=dict(type="str", required=False, default="os_family"),
            )
        )
        os_family = module.params.get("os_family") or ansible_facts(module).get(
            "os_family", "UNKNOWN"
        )
    except Exception:
        module = AnsibleModule(
            argument_spec=dict(
                sid=dict(type="str"),
                instance_number=dict(type="str"),
                virtual_machine_name=dict(type="str"),
                fencing_mechanism=dict(type="str"),
                pcmk_constants=dict(type="dict"),
                saphanasr_provider=dict(type="str"),
                cib_output=dict(type="str", required=False, default=""),
                os_family=dict(type="str", required=False),
            )
        )
        os_family = module.params.get("os_family", "UNKNOWN")

    validator = HAClusterValidator(
        os_type=OperatingSystemFamily(os_family.upper()),
        instance_number=module.params["instance_number"],
        sid=module.params["sid"],
        virtual_machine_name=module.params["virtual_machine_name"],
        fencing_mechanism=module.params["fencing_mechanism"],
        constants=module.params["pcmk_constants"],
        saphanasr_provider=HanaSRProvider(module.params["saphanasr_provider"]),
        cib_output=module.params.get("cib_output"),
    )

    module.exit_json(**validator.get_result())


if __name__ == "__main__":
    main()
