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
    from ansible.module_utils.enums import (
        OperatingSystemFamily,
        HanaSRProvider,
        HanaTopology,
        TestStatus,
    )
    from ansible.module_utils.commands import CIB_ADMIN
except ImportError:
    from src.module_utils.get_pcmk_properties import BaseHAClusterValidator
    from src.module_utils.enums import (
        OperatingSystemFamily,
        HanaSRProvider,
        HanaTopology,
        TestStatus,
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
    hana_topology:
        description:
            - SAP HANA topology type (scale_up, scale_out_hsr, scale_out_standby)
        type: str
        required: false
        default: scale_up
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
        "sbd_stonith": [".//primitive[@type='external/sbd']", ".//primitive[@type='fence_sbd']"],
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
        "azureevents": ".//primitive[@type='azure-events-az']",
    }
    SCALEOUT_RESOURCE_CATEGORIES = {
        "sbd_stonith": [".//primitive[@type='external/sbd']", ".//primitive[@type='fence_sbd']"],
        "fence_agent": ".//primitive[@type='fence_azure_arm']",
        "scaleout_topology": (".//clone/primitive[@type='SAPHanaTopology']"),
        "scaleout_topology_legacy": (".//clone/primitive[@type='SAPHanaTopologyScaleOut']"),
        "scaleout_hana": (".//primitive[@type='SAPHanaController']"),
        "scaleout_filesystem": (".//clone/primitive[@type='Filesystem']"),
        "nfs_attribute": ".//clone",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "azurelb": ".//primitive[@type='azure-lb']",
        "azureevents": ".//primitive[@type='azure-events-az']",
    }
    ANGI_SCALEOUT_RESOURCE_CATEGORIES = {
        "sbd_stonith": [".//primitive[@type='external/sbd']", ".//primitive[@type='fence_sbd']"],
        "fence_agent": ".//primitive[@type='fence_azure_arm']",
        "angi_topology": ".//clone/primitive[@type='SAPHanaTopology']",
        "angi_scaleout_hana": ".//primitive[@type='SAPHanaController']",
        "angi_filesystem": ".//primitive[@type='SAPHanaFilesystem']",
        "scaleout_filesystem": ".//clone/primitive[@type='Filesystem']",
        "nfs_attribute": ".//clone",
        "ipaddr": ".//primitive[@type='IPaddr2']",
        "azurelb": ".//primitive[@type='azure-lb']",
        "azureevents": ".//primitive[@type='azure-events-az']",
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
        hana_topology: HanaTopology = HanaTopology.SCALE_UP,
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
        self.hana_topology = hana_topology
        self.validate_from_constants()

    def _get_active_resource_categories(self):
        """
        Get the resource categories applicable to the current topology and provider.

        :return: A dictionary of resource category names to XPath expressions.
        :rtype: dict
        """
        if self.hana_topology == HanaTopology.SCALE_OUT_HSR:
            if self.saphanasr_provider == HanaSRProvider.ANGI:
                return self.ANGI_SCALEOUT_RESOURCE_CATEGORIES.copy()
            return self.SCALEOUT_RESOURCE_CATEGORIES.copy()

        categories = self.RESOURCE_CATEGORIES.copy()
        if self.saphanasr_provider == HanaSRProvider.ANGI:
            categories.pop("topology", None)
        else:
            categories.pop("angi_topology", None)
            categories.pop("angi_filesystem", None)
            categories.pop("angi_hana", None)
        return categories

    def _get_expected_value_for_category(self, category, subcategory, name, op_name):
        """
        Get expected value based on category type, topology-aware.

        :param category: The category of the configuration parameter.
        :type category: str
        :param subcategory: The subcategory of the parameter.
        :type subcategory: str
        :param name: The name of the configuration parameter.
        :type name: str
        :param op_name: The name of the operation (if applicable).
        :type op_name: str
        :return: The expected value for the configuration parameter.
        :rtype: str or list or dict or None
        """
        all_resource_cats = (
            set(self.RESOURCE_CATEGORIES)
            | set(self.SCALEOUT_RESOURCE_CATEGORIES)
            | set(self.ANGI_SCALEOUT_RESOURCE_CATEGORIES)
        )
        if category in all_resource_cats:
            return self._get_resource_expected_value(
                resource_type=category,
                section=subcategory,
                param_name=name,
                op_name=op_name,
            )
        return self._get_expected_value(category, name)

    @property
    def _is_scale_out(self):
        """Check if this is a scale-out cluster (by topology or provider)."""
        return (
            self.hana_topology == HanaTopology.SCALE_OUT_HSR
            or self.saphanasr_provider == HanaSRProvider.SCALEOUT
        )

    _SCALEOUT_SKIP_CRM_CONFIG = {"priority-fencing-delay"}
    _SCALEOUT_SKIP_RSC_DEFAULTS = {"priority"}

    def _validate_basic_constants(self, category):
        """
        Override base to skip parameters not applicable
        to scale-out clusters.
        """
        if self._is_scale_out:
            skip_set = set()
            if category == "crm_config":
                skip_set = self._SCALEOUT_SKIP_CRM_CONFIG
            elif category == "rsc_defaults":
                skip_set = self._SCALEOUT_SKIP_RSC_DEFAULTS

            if skip_set:
                orig = self.constants
                _, constants_key = self.BASIC_CATEGORIES[category]
                filtered = {
                    k: v
                    for k, v in self.constants.get(constants_key, {}).items()
                    if k not in skip_set
                }
                self.constants = {**orig, constants_key: filtered}
                try:
                    return super()._validate_basic_constants(category)
                finally:
                    self.constants = orig

        return super()._validate_basic_constants(category)

    def _parse_os_parameters(self):
        """
        Override base to apply >= comparison for corosync
        totem parameters on scale-out clusters.
        """
        parameters = super()._parse_os_parameters()
        if not self._is_scale_out:
            return parameters

        _GTE_PARAMS = {
            "runtime.config.totem.token": 30000,
            "runtime.config.totem.consensus": 36000,
        }
        for param in parameters:
            if param.get("name") not in _GTE_PARAMS:
                continue
            threshold = _GTE_PARAMS[param["name"]]
            raw = param.get("value", "")
            try:
                actual = int(raw.split("=")[-1].strip())
            except (ValueError, IndexError):
                continue
            if actual >= threshold:
                param["status"] = "PASSED"
                param["expected_value"] = f">= {threshold}"
            else:
                param["status"] = "FAILED"
                param["expected_value"] = f">= {threshold}"
        return parameters

    def _parse_resources_section(self, root):
        """
        Parse resources section with topology and provider-aware logic.

        :param root: The XML root element to parse.
        :type root: xml.etree.ElementTree.Element
        :return: A list of parameter dictionaries.
        :rtype: list
        """
        parameters = []
        resource_categories = self._get_active_resource_categories()

        if (
            self.hana_topology == HanaTopology.SCALE_OUT_HSR
            and self.saphanasr_provider != HanaSRProvider.ANGI
        ):
            modern = root.findall(resource_categories.get("scaleout_topology", ""))
            if modern:
                resource_categories.pop("scaleout_topology_legacy", None)
            else:
                resource_categories.pop("scaleout_topology", None)

        for sub_category, xpath in resource_categories.items():
            xpaths = xpath if isinstance(xpath, list) else [xpath]
            elements = []
            for xp in xpaths:
                elements.extend(root.findall(xp))
            for element in elements:
                if (
                    sub_category == "nfs_attribute"
                    and element.find("primitive[@type='attribute']") is None
                ):
                    continue
                parameters.extend(self._parse_resource(element, sub_category))

        return parameters

    def _check_required_resources(self):
        """
        Check required resources using topology-aware categories.
        """
        if "RESOURCE_DEFAULTS" not in self.constants:
            return

        try:
            if self.cib_output:
                resource_scope = self._get_scope_from_cib("resources")
            else:
                resource_scope = self.parse_xml_output(
                    self.execute_command_subprocess(CIB_ADMIN(scope="resources"))
                )
            if resource_scope is None:
                return

            all_cats = dict(self.RESOURCE_CATEGORIES)
            all_cats.update(self.SCALEOUT_RESOURCE_CATEGORIES)
            all_cats.update(self.ANGI_SCALEOUT_RESOURCE_CATEGORIES)

            for resource_type, resource_config in (
                self.constants["RESOURCE_DEFAULTS"].get(self.os_type, {}).items()
            ):
                if not isinstance(resource_config, dict):
                    continue
                if resource_config.get("required", False):
                    if resource_type in all_cats:
                        xpath = all_cats[resource_type]
                        xpaths = xpath if isinstance(xpath, list) else [xpath]
                        elements = []
                        for xp in xpaths:
                            elements.extend(resource_scope.findall(xp))
                        if not elements:
                            self.missing_required_items.append(
                                {
                                    "type": "resource",
                                    "name": resource_type,
                                    "xpath": xpath,
                                }
                            )
                            self.result["status"] = TestStatus.WARNING.value
        except Exception as ex:
            self.result["message"] += f"Error checking required resources: {ex!s} "

    def _validate_resource_constants(self):
        """
        Resource validation with HANA-specific logic and offline validation support.
        Validates resource constants by iterating through expected parameters.
        Also checks for required resources.

        :return: A list of parameter dictionaries
        :rtype: list
        """
        parameters = []

        try:
            if self.cib_output:
                resource_scope = self._get_scope_from_cib("resources")
            else:
                resource_scope = self.parse_xml_output(
                    self.execute_command_subprocess(CIB_ADMIN(scope="resources"))
                )
            if resource_scope is not None:
                parameters.extend(self._parse_resources_section(resource_scope))

            self._check_required_resources()
        except Exception as ex:
            self.result["message"] += f"Error validating resource constants: {str(ex)} "

        return parameters

    def _parse_global_ini_parameters(self):
        """
        Parse global.ini parameters specific to SAP HANA.

        :return: A list of parameter dictionaries containing validation results.
        :rtype: list
        """
        parameters = []
        if self.saphanasr_provider == HanaSRProvider.ANGI:
            global_ini_key = self.saphanasr_provider.value
        elif self.hana_topology == HanaTopology.SCALE_OUT_HSR:
            global_ini_key = "SAPHanaController"
        else:
            global_ini_key = self.saphanasr_provider.value

        global_ini_defaults = (
            self.constants["GLOBAL_INI"].get(self.os_type, {}).get(global_ini_key, {})
        )

        try:
            with open(
                f"/usr/sap/{self.sid}/SYS/global/hdb/custom/config/global.ini",
                "r",
                encoding="utf-8",
            ) as file:
                global_ini_content = file.read().splitlines()

            for section_name, section_properties in global_ini_defaults.items():
                try:
                    section_start = global_ini_content.index(f"[{section_name}]")
                    next_section_start = len(global_ini_content)
                    for i in range(section_start + 1, len(global_ini_content)):
                        if global_ini_content[i].strip().startswith("["):
                            next_section_start = i
                            break

                    properties_slice = global_ini_content[section_start + 1 : next_section_start]

                    global_ini_properties = {
                        key.strip(): val.strip().rstrip("/")
                        for line in properties_slice
                        for key, sep, val in [line.partition("=")]
                        if sep and key.strip()
                    }

                    for param_name, expected_config in section_properties.items():
                        value = global_ini_properties.get(param_name, "")
                        expected_value = expected_config.get("value", "")

                        self.log(
                            logging.INFO,
                            f"param_name: {param_name}, value: {value}, "
                            + f"expected_value: {expected_value}",
                        )
                        parameters.append(
                            self._create_parameter(
                                category="global_ini",
                                id=section_name,
                                name=param_name,
                                value=value,
                                expected_value=expected_value,
                            )
                        )
                except ValueError:
                    self.log(logging.WARNING, f"Section {section_name} not found in global.ini")
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
                hana_topology=dict(
                    type="str",
                    required=False,
                    default="scale_up",
                ),
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
                hana_topology=dict(
                    type="str",
                    required=False,
                    default="scale_up",
                ),
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
        hana_topology=HanaTopology(module.params.get("hana_topology", "scale_up")),
        cib_output=module.params.get("cib_output"),
    )

    module.exit_json(**validator.get_result())


if __name__ == "__main__":
    main()
