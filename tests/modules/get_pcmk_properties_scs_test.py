# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_pcmk_properties_scs module.
"""

import xml.etree.ElementTree as ET
import pytest
from src.modules.get_pcmk_properties_scs import HAClusterValidator, main
from src.module_utils.enums import OperatingSystemFamily, TestStatus

from tests.modules.pcmk_constants import (
    SCS_DUMMY_XML_RSC,
    SCS_DUMMY_XML_OP,
    SCS_DUMMY_XML_CRM,
    SCS_DUMMY_XML_CONSTRAINTS,
    SCS_DUMMY_XML_RESOURCES,
    SCS_DUMMY_XML_FULL_CIB,
    SCS_DUMMY_OS_COMMAND,
    SCS_DUMMY_CONSTANTS,
)


class MockExecuteCommand:
    """
    Mock class for execute_command_subprocess.
    """

    def __init__(self, mock_outputs):
        self.mock_outputs = mock_outputs

    def __call__(self, command, shell_command=False):
        command_str = " ".join(command) if isinstance(command, list) else str(command)
        if "sysctl" in command_str:
            return SCS_DUMMY_OS_COMMAND
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
            "rsc_defaults": SCS_DUMMY_XML_RSC,
            "crm_config": SCS_DUMMY_XML_CRM,
            "op_defaults": SCS_DUMMY_XML_OP,
            "constraints": SCS_DUMMY_XML_CONSTRAINTS,
            "resources": SCS_DUMMY_XML_RESOURCES,
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
            constants=SCS_DUMMY_CONSTANTS,
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
            constants=SCS_DUMMY_CONSTANTS,
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
            constants=SCS_DUMMY_CONSTANTS,
            cib_output=SCS_DUMMY_XML_FULL_CIB,
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
        xml_str = SCS_DUMMY_XML_RESOURCES
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
        xml_str = SCS_DUMMY_XML_RESOURCES
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
                    "pcmk_constants": SCS_DUMMY_CONSTANTS,
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
            constants=SCS_DUMMY_CONSTANTS,
            cib_output=SCS_DUMMY_XML_FULL_CIB,
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
