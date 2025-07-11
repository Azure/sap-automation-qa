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
from ansible.module_utils.facts.compat import ansible_facts

try:
    from ansible.module_utils.get_pcmk_properties import BaseHAClusterValidator
    from ansible.module_utils.enums import OperatingSystemFamily, TestStatus
except ImportError:
    from src.module_utils.get_pcmk_properties import BaseHAClusterValidator
    from src.module_utils.enums import OperatingSystemFamily, TestStatus


DOCUMENTATION = r"""
---
module: get_pcmk_properties_scs
short_description: Validates Pacemaker cluster configurations for SAP ASCS/ERS
description:
    - Validates Pacemaker cluster configurations against predefined standards for SAP Application
    Tier ASCS/ERS deployments
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
    nfs_provider:
        description:
            - NFS provider type (e.g., AFS, ANF)
        type: str
        required: false
        default: ""
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


class HAClusterValidator(BaseHAClusterValidator):
    """
    Validates High Availability cluster configurations for SAP ASCS/ERS.

    This class extends BaseHAClusterValidator to provide ASCS/ERS-specific validation
    functionality including NFS provider handling and ASCS/ERS resource configurations.
    """

    RESOURCE_CATEGORIES = {
        "sbd_stonith": ".//primitive[@type='external/sbd']",
        "fence_agent": ".//primitive[@type='fence_azure_arm']",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "azurelb": ".//primitive[@type='azure-lb']",
        "azureevents": ".//primitive[@type='azure-events-az']",
    }

    def __init__(
        self,
        os_type: OperatingSystemFamily,
        sid: str,
        scs_instance_number: str,
        ers_instance_number: str,
        virtual_machine_name: str,
        constants: dict,
        fencing_mechanism: str,
        cib_output: str,
        nfs_provider=None,
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
        self.scs_instance_number = scs_instance_number
        self.ers_instance_number = ers_instance_number
        self.nfs_provider = nfs_provider
        self.parse_ha_cluster_config()

    def _get_expected_value_for_category(self, category, subcategory, name, op_name):
        """
        Get expected value based on category type with SCS-specific logic.

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
        if category in self.RESOURCE_CATEGORIES or category in ["ascs", "ers"]:
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
        Determine the status of a parameter with SCS-specific logic for NFS provider.

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
        elif isinstance(expected_value, dict):
            provider_values = expected_value.get(self.nfs_provider, expected_value.get("AFS", []))
            return (
                TestStatus.SUCCESS.value
                if str(value) in provider_values
                else TestStatus.ERROR.value
            )
        else:
            return TestStatus.ERROR.value

    def _parse_resources_section(self, root):
        """
        Parse resources section with ASCS/ERS-specific logic.

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

        for group in root.findall(".//group"):
            group_id = group.get("id", "")
            if "ASCS" in group_id:
                for element in group.findall(".//primitive[@type='SAPInstance']"):
                    parameters.extend(self._parse_resource(element, "ascs"))
            elif "ERS" in group_id:
                for element in group.findall(".//primitive[@type='SAPInstance']"):
                    parameters.extend(self._parse_resource(element, "ers"))

        return parameters


def main() -> None:
    """
    Main entry point for the Ansible module.
    """
    try:
        module = AnsibleModule(
            argument_spec=dict(
                sid=dict(type="str"),
                ascs_instance_number=dict(type="str"),
                ers_instance_number=dict(type="str"),
                virtual_machine_name=dict(type="str"),
                pcmk_constants=dict(type="dict"),
                fencing_mechanism=dict(type="str"),
                nfs_provider=dict(type="str", default=""),
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
                ascs_instance_number=dict(type="str"),
                ers_instance_number=dict(type="str"),
                virtual_machine_name=dict(type="str"),
                pcmk_constants=dict(type="dict"),
                fencing_mechanism=dict(type="str"),
                nfs_provider=dict(type="str", default=""),
                cib_output=dict(type="str", required=False, default=""),
                os_family=dict(type="str", required=False, default="UNKNOWN"),
            )
        )
        os_family = module.params.get("os_family", "UNKNOWN").upper()

    validator = HAClusterValidator(
        sid=module.params["sid"],
        scs_instance_number=module.params["ascs_instance_number"],
        ers_instance_number=module.params["ers_instance_number"],
        os_type=OperatingSystemFamily(os_family.upper()),
        virtual_machine_name=module.params["virtual_machine_name"],
        constants=module.params["pcmk_constants"],
        fencing_mechanism=module.params["fencing_mechanism"],
        nfs_provider=module.params.get("nfs_provider"),
        cib_output=module.params.get("cib_output"),
    )
    module.exit_json(**validator.get_result())


if __name__ == "__main__":
    main()
