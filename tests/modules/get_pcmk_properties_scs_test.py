# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_pcmk_properties_scs module.
"""

import xml.etree.ElementTree as ET
import pytest
from src.modules.get_pcmk_properties_scs import HAClusterValidator, main
from src.module_utils.enums import OperatingSystemFamily, TestStatus

DUMMY_XML_RSC = """<rsc_defaults>
  <meta_attributes id="build-resource-defaults">
    <nvpair id="build-resource-stickiness" name="resource-stickiness" value="1000"/>
    <nvpair name="migration-threshold" value="5000"/>
  </meta_attributes>
</rsc_defaults>"""

DUMMY_XML_OP = """<op_defaults>
  <meta_attributes id="op-options">
    <nvpair name="timeout" value="600"/>
    <nvpair name="record-pending" value="true"/>
  </meta_attributes>
</op_defaults>"""

DUMMY_XML_CRM = """<crm_config>
  <cluster_property_set id="cib-bootstrap-options">
    <nvpair name="stonith-enabled" value="true"/>
    <nvpair name="cluster-name" value="scs_S4D"/>
    <nvpair name="maintenance-mode" value="false"/>
  </cluster_property_set>
</crm_config>"""

DUMMY_XML_CONSTRAINTS = """<constraints>
  <rsc_colocation id="col_scs_ip" score="4000" rsc="g_ip_S4D_ASCS00" with-rsc="rsc_sap_S4D_ASCS00"/>
  <rsc_order id="ord_SCS" kind="Optional" first="rsc_sap_S4D_ASCS00" then="rsc_sap_S4D_ERS10"/>
  <rsc_location id="loc_test" score="INFINITY" rsc="test_resource"/>
</constraints>"""

DUMMY_XML_RESOURCES = """<resources>
  <primitive id="stonith-sbd" class="stonith" type="external/sbd">
    <instance_attributes id="stonith-sbd-instance_attributes">
      <nvpair id="stonith-sbd-instance_attributes-pcmk_delay_max" name="pcmk_delay_max" value="30s"/>
      <nvpair name="login" value="12345-12345-12345-12345-12345" id="rsc_st_azure-instance_attributes-login"/>
      <nvpair name="password" value="********" id="rsc_st_azure-instance_attributes-password"/>
    </instance_attributes>
    <meta_attributes id="stonith-sbd-meta_attributes">
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <operations id="stonith-sbd-operations">
      <op name="monitor" interval="10" timeout="600" id="stonith-sbd-monitor"/>
      <op name="start" interval="0" timeout="20" id="stonith-sbd-start"/>
    </operations>
  </primitive>
  <primitive id="rsc_fence_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="login" value="testuser"/>
      <nvpair name="resourceGroup" value="test-rg"/>
    </instance_attributes>
    <meta_attributes>
      <nvpair name="pcmk_delay_max" value="15"/>
    </meta_attributes>
    <operations>
      <op name="monitor" interval="10" timeout="700"/>
    </operations>
  </primitive>
  <primitive id="rsc_ip_S4D_ASCS00" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="10.0.1.100"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_lb" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62500"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_events" class="ocf" provider="heartbeat" type="azure-events-az">
    <instance_attributes>
      <nvpair name="subscriptionId" value="12345"/>
    </instance_attributes>
  </primitive>
  <group id="g_sap_S4D_ASCS00">
    <primitive id="rsc_sap_S4D_ASCS00" class="ocf" provider="heartbeat" type="SAPInstance">
      <instance_attributes>
        <nvpair name="InstanceName" value="S4D_ASCS00_sapascs"/>
        <nvpair name="START_PROFILE" value="/sapmnt/S4D/profile/S4D_ASCS00_sapascs"/>
      </instance_attributes>
      <meta_attributes>
        <nvpair name="target-role" value="Started"/>
      </meta_attributes>
      <operations>
        <op name="monitor" interval="10" timeout="600"/>
      </operations>
    </primitive>
  </group>
  <group id="g_sap_S4D_ERS10">
    <primitive id="rsc_sap_S4D_ERS10" class="ocf" provider="heartbeat" type="SAPInstance">
      <instance_attributes>
        <nvpair name="InstanceName" value="S4D_ERS10_sapers"/>
        <nvpair name="START_PROFILE" value="/sapmnt/S4D/profile/S4D_ERS10_sapers"/>
      </instance_attributes>
      <meta_attributes>
        <nvpair name="target-role" value="Started"/>
      </meta_attributes>
      <operations>
        <op name="monitor" interval="10" timeout="600"/>
      </operations>
    </primitive>
  </group>
</resources>"""

DUMMY_XML_FULL_CIB = f"""<?xml version="1.0" encoding="UTF-8"?>
<cib>
  <configuration>
    {DUMMY_XML_CRM}
    {DUMMY_XML_RSC}
    {DUMMY_XML_OP}
    {DUMMY_XML_CONSTRAINTS}
    {DUMMY_XML_RESOURCES}
  </configuration>
</cib>"""

DUMMY_OS_COMMAND = """kernel.numa_balancing = 0"""

DUMMY_CONSTANTS = {
    "VALID_CONFIGS": {
        "REDHAT": {
            "stonith-enabled": {"value": "true", "required": False},
            "cluster-name": {"value": "scs_S4D", "required": False},
        },
        "azure-fence-agent": {"priority": {"value": "10", "required": False}},
        "sbd": {"pcmk_delay_max": {"value": "30", "required": False}},
    },
    "RSC_DEFAULTS": {
        "resource-stickiness": {"value": "1000", "required": False},
        "migration-threshold": {"value": "5000", "required": False},
    },
    "OP_DEFAULTS": {
        "timeout": {"value": "600", "required": False},
        "record-pending": {"value": "true", "required": False},
    },
    "CRM_CONFIG_DEFAULTS": {
        "stonith-enabled": {"value": "true", "required": False},
        "maintenance-mode": {"value": "false", "required": False},
    },
    "RESOURCE_DEFAULTS": {
        "REDHAT": {
            "fence_agent": {
                "meta_attributes": {
                    "pcmk_delay_max": {"value": "15", "required": False},
                    "target-role": {"value": "Started", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["700", "700s"], "required": False},
                        "interval": {"value": "10", "required": False},
                    },
                    "start": {"timeout": {"value": "20", "required": False}},
                },
                "instance_attributes": {
                    "login": {"value": "testuser", "required": False},
                    "resourceGroup": {"value": "test-rg", "required": False},
                },
            },
            "sbd_stonith": {
                "meta_attributes": {
                    "pcmk_delay_max": {"value": "30", "required": False},
                    "target-role": {"value": "Started", "required": False},
                },
                "operations": {
                    "monitor": {
                        "timeout": {"value": ["30", "30s"], "required": False},
                        "interval": {"value": "10", "required": False},
                    },
                    "start": {"timeout": {"value": "20", "required": False}},
                },
            },
            "ascs": {
                "meta_attributes": {"target-role": {"value": "Started", "required": False}},
                "operations": {
                    "monitor": {"timeout": {"value": ["600", "600s"], "required": False}}
                },
                "instance_attributes": {
                    "InstanceName": {"value": "S4D_ASCS00_sapascs", "required": False}
                },
            },
            "ers": {
                "meta_attributes": {"target-role": {"value": "Started", "required": False}},
                "operations": {
                    "monitor": {"timeout": {"value": ["600", "600s"], "required": False}}
                },
                "instance_attributes": {
                    "InstanceName": {"value": "S4D_ERS10_sapers", "required": False}
                },
            },
            "ipaddr": {
                "instance_attributes": {
                    "ip": {
                        "value": {"AFS": ["10.0.1.100"], "ANF": ["10.0.1.101"]},
                        "required": False,
                    }
                }
            },
        }
    },
    "OS_PARAMETERS": {
        "DEFAULTS": {
            "sysctl": {
                "kernel.numa_balancing": {"value": "kernel.numa_balancing = 0", "required": False}
            }
        }
    },
    "CONSTRAINTS": {
        "rsc_location": {"score": {"value": "INFINITY", "required": False}},
        "rsc_colocation": {"score": {"value": "4000", "required": False}},
        "rsc_order": {"kind": {"value": "Optional", "required": False}},
    },
}


class MockExecuteCommand:
    """
    Mock class for execute_command_subprocess.
    """

    def __init__(self, mock_outputs):
        self.mock_outputs = mock_outputs

    def __call__(self, command, shell_command=False):
        command_str = " ".join(command) if isinstance(command, list) else str(command)
        if "sysctl" in command_str:
            return DUMMY_OS_COMMAND
        if len(command) >= 2 and command[-1] in self.mock_outputs:
            return self.mock_outputs[command[-1]]
        return ""


class TestableHAClusterValidator(HAClusterValidator):
    """
    Testable version of HAClusterValidator with mocked dependencies.
    """

    def __init__(self, mock_execute_command, *args, **kwargs):
        self._mock_execute_command = mock_execute_command
        super().__init__(*args, **kwargs)

    def execute_command_subprocess(self, command, shell_command=False):
        return self._mock_execute_command(command, shell_command)


class TestHAClusterValidator:
    """
    Test cases for the HAClusterValidator class.
    """

    @pytest.fixture
    def mock_xml_outputs(self):
        """
        Fixture for providing mock XML outputs.
        """
        return {
            "rsc_defaults": DUMMY_XML_RSC,
            "crm_config": DUMMY_XML_CRM,
            "op_defaults": DUMMY_XML_OP,
            "constraints": DUMMY_XML_CONSTRAINTS,
            "resources": DUMMY_XML_RESOURCES,
        }

    @pytest.fixture
    def validator(self, mock_xml_outputs):
        """
        Fixture for creating a TestableHAClusterValidator instance.
        """
        mock_execute = MockExecuteCommand(mock_xml_outputs)
        return TestableHAClusterValidator(
            mock_execute,
            os_type=OperatingSystemFamily.REDHAT,
            sid="S4D",
            scs_instance_number="00",
            ers_instance_number="10",
            fencing_mechanism="sbd",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            cib_output="",
            nfs_provider="AFS",
        )

    @pytest.fixture
    def validator_anf(self, mock_xml_outputs):
        """
        Fixture for creating a validator with ANF provider.
        """
        mock_execute = MockExecuteCommand(mock_xml_outputs)
        return TestableHAClusterValidator(
            mock_execute,
            os_type=OperatingSystemFamily.REDHAT,
            sid="S4D",
            scs_instance_number="00",
            ers_instance_number="10",
            fencing_mechanism="sbd",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            cib_output="",
            nfs_provider="ANF",
        )

    @pytest.fixture
    def validator_with_cib(self):
        """
        Fixture for creating a validator with CIB output.
        """
        return HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="S4D",
            scs_instance_number="00",
            ers_instance_number="10",
            fencing_mechanism="sbd",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            cib_output=DUMMY_XML_FULL_CIB,
        )

    def test_init(self, validator):
        """
        Test the __init__ method.
        """
        assert validator.os_type == "REDHAT"
        assert validator.sid == "S4D"
        assert validator.scs_instance_number == "00"
        assert validator.ers_instance_number == "10"
        assert validator.nfs_provider == "AFS"

    def test_get_expected_value_for_category_resource(self, validator):
        """
        Test _get_expected_value_for_category method for resource category.
        """
        expected = validator._get_expected_value_for_category(
            "fence_agent", "meta_attributes", "pcmk_delay_max", None
        )
        assert expected == ("15", False)

    def test_get_expected_value_for_category_ascs_ers(self, validator):
        """
        Test _get_expected_value_for_category method for ASCS/ERS categories.
        """
        expected = validator._get_expected_value_for_category(
            "ascs", "meta_attributes", "target-role", None
        )
        assert expected == ("Started", False)
        expected = validator._get_expected_value_for_category(
            "ers", "meta_attributes", "target-role", None
        )
        assert expected == ("Started", False)

    def test_get_expected_value_for_category_basic(self, validator):
        """
        Test _get_expected_value_for_category method for basic category.
        """
        expected = validator._get_expected_value_for_category(
            "crm_config", None, "stonith-enabled", None
        )
        assert expected == ("true", False)

    def test_determine_parameter_status_with_list_expected_value(self, validator):
        """
        Test _determine_parameter_status method with list expected value.
        """
        status = validator._determine_parameter_status(
            "10.0.1.101", (["10.0.1.100", "10.0.1.101"], False)
        )
        assert status == TestStatus.SUCCESS.value

    def test_determine_parameter_status_info_cases(self, validator):
        """
        Test _determine_parameter_status method for INFO status cases.
        """
        status = validator._determine_parameter_status(
            "10.0.1.102", {"AFS": ["10.0.1.100"], "ANF": ["10.0.1.101"]}
        )
        assert status == TestStatus.ERROR.value
        validator.nfs_provider = "UNKNOWN"
        status = validator._determine_parameter_status(
            "10.0.1.100", {"AFS": ["10.0.1.100"], "ANF": ["10.0.1.101"]}
        )
        assert status == TestStatus.SUCCESS.value
        status = validator._determine_parameter_status("500", ["600", "600s"])
        assert status == TestStatus.ERROR.value
        status = validator._determine_parameter_status("value", None)
        assert status == TestStatus.INFO.value
        status = validator._determine_parameter_status("", "expected")
        assert status == TestStatus.INFO.value
        status = validator._determine_parameter_status("value", 123)
        assert status == TestStatus.ERROR.value

    def test_parse_resources_section_with_ascs_ers_groups(self, validator):
        """
        Test _parse_resources_section method with ASCS/ERS groups.
        """
        xml_str = DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator._parse_resources_section(root)
        assert len(params) > 0
        categories = [p.get("category", "") for p in params]
        ascs_found = any("ascs" in cat for cat in categories)
        ers_found = any("ers" in cat for cat in categories)
        assert ascs_found
        assert ers_found

    def test_parse_resources_section_all_resource_types(self, validator):
        """
        Test _parse_resources_section method covers all resource types.
        """
        xml_str = DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        expected_categories = ["sbd_stonith", "fence_agent", "ipaddr", "azurelb", "azureevents"]
        found_categories = []
        for cat in expected_categories:
            if any(cat in category for category in categories):
                found_categories.append(cat)

        assert len(found_categories) > 0

    def test_parse_ha_cluster_config_with_cib(self, validator_with_cib):
        """
        Test parse_ha_cluster_config method with CIB output.
        """
        result = validator_with_cib.get_result()
        assert result["status"] in [TestStatus.SUCCESS.value, TestStatus.ERROR.value]
        assert "parameters" in result["details"]
        assert "CIB output provided" in result["message"]

    def test_main_with_ansible_module(self):
        """
        Test main function with successful AnsibleModule creation.
        """
        mock_result = {}

        class MockAnsibleModule:
            def __init__(self, argument_spec=None, **kwargs):
                self.params = {
                    "sid": "S4D",
                    "ascs_instance_number": "00",
                    "ers_instance_number": "10",
                    "virtual_machine_name": "vmname",
                    "pcmk_constants": DUMMY_CONSTANTS,
                    "fencing_mechanism": "sbd",
                    "nfs_provider": "AFS",
                    "cib_output": "",
                    "filter": "os_family",
                }

            def exit_json(self, **kwargs):
                nonlocal mock_result
                mock_result = kwargs

        def mock_ansible_facts(module):
            return {"os_family": "SUSE"}

        import src.modules.get_pcmk_properties_scs as module_under_test

        original_ansible_module = module_under_test.AnsibleModule
        original_ansible_facts = module_under_test.ansible_facts
        module_under_test.AnsibleModule = MockAnsibleModule
        module_under_test.ansible_facts = mock_ansible_facts
        try:
            main()
            assert "status" in mock_result
            assert "message" in mock_result
        finally:
            module_under_test.AnsibleModule = original_ansible_module
            module_under_test.ansible_facts = original_ansible_facts

    def test_validator_initialization_calls_parse(self):
        """
        Test that validator initialization calls parse_ha_cluster_config.
        """
        validator = HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="S4D",
            scs_instance_number="00",
            ers_instance_number="10",
            fencing_mechanism="sbd",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            cib_output=DUMMY_XML_FULL_CIB,
        )
        result = validator.get_result()
        assert "status" in result
        assert "details" in result

    def test_resource_categories_defined(self, validator):
        """
        Test that RESOURCE_CATEGORIES are properly defined.
        """
        expected_categories = ["sbd_stonith", "fence_agent", "ipaddr", "azurelb", "azureevents"]
        for category in expected_categories:
            assert category in HAClusterValidator.RESOURCE_CATEGORIES
            assert HAClusterValidator.RESOURCE_CATEGORIES[category].startswith(".//")

    def test_successful_validation_result(self, validator):
        """
        Test that validator returns proper result structure.
        """
        result = validator.get_result()
        assert "status" in result
        assert "message" in result
        assert "details" in result
        assert "parameters" in result["details"]
        assert isinstance(result["details"]["parameters"], list)

    def test_parse_resource_with_operations(self, validator):
        """
        Test _parse_resource method with operations section.
        """
        xml_str = """<primitive>
            <operations>
                <op name="monitor" interval="10" timeout="600" id="monitor_op"/>
                <op name="start" interval="0" timeout="20" id="start_op"/>
            </operations>
        </primitive>"""
        element = ET.fromstring(xml_str)
        params = validator._parse_resource(element, "ascs")
        timeout_params = [p for p in params if p["name"].endswith("_timeout")]
        interval_params = [p for p in params if p["name"].endswith("_interval")]
        assert len(timeout_params) == 2
        assert len(interval_params) == 2

    def test_get_expected_value_methods_coverage(self, validator):
        """
        Test inherited expected value methods for coverage.
        """
        validator.fencing_mechanism = "azure-fence-agent"
        expected = validator._get_expected_value("crm_config", "priority")
        assert expected == ("10", False)
        expected = validator._get_expected_value("crm_config", "stonith-enabled")
        assert expected == ("true", False)
        expected = validator._get_resource_expected_value(
            "fence_agent", "meta_attributes", "pcmk_delay_max"
        )
        assert expected == ("15", False)
        expected = validator._get_resource_expected_value(
            "fence_agent", "operations", "timeout", "monitor"
        )
        assert expected == (["700", "700s"], False)
        expected = validator._get_resource_expected_value(
            "fence_agent", "instance_attributes", "login"
        )
        assert expected == ("testuser", False)
        expected = validator._get_resource_expected_value("fence_agent", "unknown_section", "param")
        assert expected is None
