# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_pcmk_properties module.
"""

import io
import xml.etree.ElementTree as ET
import pytest
from src.module_utils.get_pcmk_properties import BaseHAClusterValidator
from src.module_utils.enums import OperatingSystemFamily, TestStatus

DUMMY_XML_RSC = """<rsc_defaults>
  <meta_attributes id="build-resource-defaults">
    <nvpair id="build-resource-stickiness" name="resource-stickiness" value="1000"/>
    <nvpair name="migration-threshold" value="5000"/>
    <nvpair name="passwd" value="secret"/>
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
    <nvpair name="cluster-name" value="hdb_HDB"/>
    <nvpair name="maintenance-mode" value="false"/>
    <nvpair name="stonith-timeout" value="900"/>
  </cluster_property_set>
</crm_config>"""

DUMMY_XML_CONSTRAINTS = """<constraints>
  <rsc_colocation id="col_saphana_ip" score="4000" rsc="g_ip_HDB_HDB00" with-rsc="msl_SAPHana_HDB_HDB00"/>
  <rsc_order id="ord_SAPHana" kind="Optional" first="cln_SAPHanaTopology_HDB_HDB00" then="msl_SAPHana_HDB_HDB00"/>
  <rsc_location id="loc_test" score="INFINITY" rsc="test_resource"/>
  <unknown_constraint id="unknown_test" attribute="value"/>
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
  <clone id="cln_SAPHanaTopology_HDB_HDB00">
    <meta_attributes id="cln_SAPHanaTopology_HDB_HDB00-meta_attributes">
      <nvpair name="clone-node-max" value="1"/>
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <primitive id="rsc_SAPHanaTopology_HDB_HDB00" class="ocf" provider="suse" type="SAPHanaTopology">
      <operations id="rsc_sap2_HDB_HDB00-operations">
        <op name="monitor" interval="10" timeout="600"/>
      </operations>
      <instance_attributes id="rsc_SAPHanaTopology_HDB_HDB00-instance_attributes">
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
      </instance_attributes>
    </primitive>
  </clone>
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
            "cluster-name": {"value": "hdb_HDB", "required": False},
            "stonith-timeout": {"value": "900", "required": False},
        },
        "azure-fence-agent": {
            "priority": {"value": "10", "required": False},
            "stonith-timeout": {"value": "210", "required": False},
        },
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
                "instance_attributes": {"login": {"value": "testuser", "required": False}},
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
            "test_resource": {
                "meta_attributes": {"clone-max": {"value": "2", "required": False}},
                "operations": {
                    "monitor": {"timeout": {"value": ["600", "600s"], "required": False}}
                },
                "instance_attributes": {"SID": {"value": "HDB", "required": False}},
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


def fake_open_factory(file_content):
    """Factory function to create a fake open function."""

    def fake_open(*args, **kwargs):
        return io.StringIO(file_content)

    return fake_open


class TestableBaseHAClusterValidator(BaseHAClusterValidator):
    """
    Testable implementation of BaseHAClusterValidator for testing purposes.
    """

    RESOURCE_CATEGORIES = {
        "sbd_stonith": ".//primitive[@type='external/sbd']",
        "fence_agent": ".//primitive[@type='fence_azure_arm']",
        "test_resource": ".//primitive[@id='rsc_SAPHanaTopology_HDB_HDB00']",
    }

    def _get_additional_parameters(self):
        """
        Mock implementation of additional parameters.
        """
        return [
            self._create_parameter(
                category="additional",
                name="test_param",
                value="test_value",
                expected_value="test_value",
            )
        ]


class TestBaseHAClusterValidator:
    """
    Test cases for the BaseHAClusterValidator class.
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
    def validator(self, monkeypatch, mock_xml_outputs):
        """
        Fixture for creating a TestableBaseHAClusterValidator instance.
        """

        def mock_execute_command(*args, **kwargs):
            """
            Mock function to replace execute_command_subprocess.
            """
            command = args[0] if args else kwargs.get("command", [])
            if not command or not isinstance(command, (list, str)):
                return ""
            command_str = " ".join(command) if isinstance(command, list) else str(command)
            if "sysctl" in command_str:
                return DUMMY_OS_COMMAND
            if isinstance(command, list) and len(command) >= 2 and command[-1] in mock_xml_outputs:
                return mock_xml_outputs[command[-1]]
            return ""

        monkeypatch.setattr(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess",
            mock_execute_command,
        )

        return TestableBaseHAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HDB",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            fencing_mechanism="sbd",
            cib_output="",
        )

    @pytest.fixture
    def validator_with_cib(self):
        """
        Fixture for creating a validator with CIB output.
        """
        return TestableBaseHAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HDB",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            fencing_mechanism="sbd",
            cib_output=DUMMY_XML_FULL_CIB,
        )

    def test_init(self, validator):
        """
        Test the __init__ method.
        """
        assert validator.os_type == "REDHAT"
        assert validator.sid == "HDB"
        assert validator.virtual_machine_name == "vmname"
        assert validator.fencing_mechanism == "sbd"
        assert validator.constants == DUMMY_CONSTANTS
        assert validator.cib_output == ""

    def test_get_expected_value_fence_config(self, validator):
        """
        Test _get_expected_value method with fence configuration.
        """
        validator.fencing_mechanism = "azure-fence-agent"
        expected = validator._get_expected_value("crm_config", "stonith-timeout")
        assert expected == ("210", False)

    def test_get_resource_expected_value_instance_attributes(self, validator):
        """
        Test _get_resource_expected_value method for instance_attributes section.
        """
        expected = validator._get_resource_expected_value(
            "fence_agent", "instance_attributes", "login"
        )
        assert expected == ("testuser", False)

    def test_get_resource_expected_value_invalid_section(self, validator):
        """
        Test _get_resource_expected_value method for invalid section.
        """
        expected = validator._get_resource_expected_value("fence_agent", "invalid_section", "param")
        assert expected is None

    def test_create_parameter_with_expected_value(self, validator):
        """
        Test _create_parameter method with provided expected value.
        """
        param = validator._create_parameter(
            category="test",
            name="test_param",
            value="test_value",
            expected_value="test_value",
            id="test_id",
        )
        assert param["category"] == "test"
        assert param["name"] == "test_param"
        assert param["value"] == "test_value"
        assert param["expected_value"] == "test_value"
        assert param["status"] == TestStatus.SUCCESS.value
        assert param["id"] == "test_id"

    def test_create_parameter_with_subcategory(self, validator):
        """
        Test _create_parameter method with subcategory.
        """
        param = validator._create_parameter(
            category="test",
            subcategory="sub",
            name="test_param",
            value="test_value",
            expected_value="test_value",
        )
        assert param["category"] == "test_sub"

    def test_determine_parameter_status_success_string(self, validator):
        """
        Test _determine_parameter_status method with matching string values.
        """
        status = validator._determine_parameter_status("true", ("true", False))
        assert status == TestStatus.SUCCESS.value

    def test_determine_parameter_status_error_string(self, validator):
        """
        Test _determine_parameter_status method with non-matching string values.
        """
        status = validator._determine_parameter_status("true", ("false", False))
        assert status == TestStatus.ERROR.value

    def test_parse_resource_with_operations(self, validator):
        """
        Test _parse_resource method with operations.
        """
        xml_str = """<primitive>
            <operations>
                <op name="monitor" interval="10" timeout="600" id="monitor_op"/>
                <op name="start" interval="0" timeout="20" id="start_op"/>
            </operations>
        </primitive>"""
        params = validator._parse_resource(ET.fromstring(xml_str), "test_resource")
        timeout_params = [p for p in params if p["name"].endswith("_timeout")]
        interval_params = [p for p in params if p["name"].endswith("_interval")]
        assert len(timeout_params) == 2
        assert len(interval_params) == 2

    def test_parse_resources_section(self, validator):
        """
        Test _parse_resources_section method.
        """
        xml_str = DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator._parse_resources_section(root)
        assert len(params) > 0

    def test_should_skip_scope_redhat_op_defaults(self, validator):
        """
        Test _should_skip_scope method for REDHAT op_defaults.
        """
        assert validator._should_skip_scope("op_defaults")

    def test_should_skip_scope_non_redhat_op_defaults(self):
        """
        Test _should_skip_scope method for non-REDHAT op_defaults.
        """
        validator = TestableBaseHAClusterValidator(
            os_type=OperatingSystemFamily.SUSE,
            sid="HDB",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            fencing_mechanism="sbd",
            cib_output="",
        )
        assert not validator._should_skip_scope("op_defaults")

    def test_get_scope_from_cib_with_cib_output(self, validator_with_cib):
        """
        Test _get_scope_from_cib method with CIB output.
        """
        scope_element = validator_with_cib._get_scope_from_cib("resources")
        assert scope_element is not None
        assert scope_element.tag == "resources"

    def test_get_scope_from_cib_without_cib_output(self, validator):
        """
        Test _get_scope_from_cib method without CIB output.
        """
        scope_element = validator._get_scope_from_cib("resources")
        assert scope_element is None

    def test_get_expected_value_for_category_resource(self, validator):
        """
        Test _get_expected_value_for_category method for resource category.
        """
        expected = validator._get_expected_value_for_category(
            "fence_agent", "meta_attributes", "pcmk_delay_max", None
        )
        assert expected == ("15", False)

    def test_get_expected_value_for_category_basic(self, validator):
        """
        Test _get_expected_value_for_category method for basic category.
        """
        expected = validator._get_expected_value_for_category(
            "crm_config", None, "stonith-enabled", None
        )
        assert expected == ("true", False)

    def test_determine_parameter_status_with_required_parameter(self, validator):
        """
        Test _determine_parameter_status method with required parameter.
        """
        status = validator._determine_parameter_status("", ("expected_value", True))
        assert status == TestStatus.WARNING.value

    def test_get_scope_from_cib_invalid_scope(self, validator_with_cib):
        """
        Test _get_scope_from_cib method with invalid scope.
        """
        scope_element = validator_with_cib._get_scope_from_cib("invalid_scope")
        assert scope_element is None

    def test_check_required_resources_missing(self, validator):
        """
        Test _check_required_resources method when required resource is missing.
        """
        validator.constants["RESOURCE_DEFAULTS"]["REDHAT"]["required_missing_resource"] = {
            "required": True,
            "meta_attributes": {},
        }
        validator.RESOURCE_CATEGORIES["required_missing_resource"] = (
            ".//primitive[@type='NonExistent']"
        )
        validator._check_required_resources()

        # Check that missing resource was tracked
        assert len(validator.missing_required_items) > 0
        assert any(
            item["type"] == "resource" and item["name"] == "required_missing_resource"
            for item in validator.missing_required_items
        )
        assert validator.result["status"] == TestStatus.WARNING.value

    def test_check_required_resources_present(self, validator):
        """
        Test _check_required_resources method when required resource is present.
        Uses CIB output to avoid command execution for more reliable testing.
        """
        constants = DUMMY_CONSTANTS.copy()
        constants["RESOURCE_DEFAULTS"] = {
            "REDHAT": {"sbd_stonith": {"required": True, "meta_attributes": {}}}
        }

        validator_with_cib = TestableBaseHAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HDB",
            virtual_machine_name="vmname",
            constants=constants,
            fencing_mechanism="sbd",
            cib_output=DUMMY_XML_FULL_CIB,
        )
        validator_with_cib._check_required_resources()
        assert (
            "Required resource 'sbd_stonith' not found" not in validator_with_cib.result["message"]
        )

    def test_check_required_resources_optional(self, validator):
        """
        Test _check_required_resources method with optional resource missing.
        """
        validator.constants["RESOURCE_DEFAULTS"]["REDHAT"]["optional_resource"] = {
            "required": False,
            "meta_attributes": {},
        }
        validator.RESOURCE_CATEGORIES["optional_resource"] = ".//primitive[@type='NonExistent']"
        validator._check_required_resources()
        assert "Required resource 'optional_resource'" not in validator.result["message"]
