# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_pcmk_properties_db module.
"""

import io
import xml.etree.ElementTree as ET
import pytest
from src.modules.get_pcmk_properties_db import HAClusterValidator, main
from src.module_utils.enums import OperatingSystemFamily, HanaSRProvider, TestStatus

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
    <nvpair name="cluster-name" value="hdb_HDB"/>
    <nvpair name="maintenance-mode" value="false"/>
  </cluster_property_set>
  <cluster_property_set id="SAPHanaSR">
    <nvpair name="hana_hdb_site_srHook_SITEA" value="SOK"/>
  </cluster_property_set>
</crm_config>"""

DUMMY_XML_CONSTRAINTS = """<constraints>
  <rsc_colocation id="col_saphana_ip" score="4000" rsc="g_ip_HDB_HDB00" with-rsc="msl_SAPHana_HDB_HDB00"/>
  <rsc_order id="ord_SAPHana" kind="Optional" first="cln_SAPHanaTopology_HDB_HDB00" then="msl_SAPHana_HDB_HDB00"/>
</constraints>"""

DUMMY_XML_RESOURCES = """<resources>
  <primitive id="stonith-sbd" class="stonith" type="external/sbd">
    <instance_attributes id="stonith-sbd-instance_attributes">
      <nvpair id="stonith-sbd-instance_attributes-pcmk_delay_max" name="pcmk_delay_max" value="30s"/>
      <nvpair name="login" value="12345-12345-12345-12345-12345" id="rsc_st_azure-instance_attributes-login"/>
      <nvpair name="passwd" value="********" id="rsc_st_azure-instance_attributes-passwd"/>
    </instance_attributes>
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
  <master id="msl_SAPHana_HDB_HDB00">
    <meta_attributes id="msl_SAPHana_HDB_HDB00-meta_attributes">
      <nvpair name="clone-max" value="2"/>
      <nvpair name="target-role" value="Started"/>
    </meta_attributes>
    <primitive id="rsc_SAPHana_HDB_HDB00" class="ocf" provider="suse" type="SAPHana">
      <instance_attributes id="rsc_SAPHana_HDB_HDB00-instance_attributes">
        <nvpair name="SID" value="HDB"/>
        <nvpair name="InstanceNumber" value="00"/>
      </instance_attributes>
    </primitive>
  </master>
  <group id="g_ip_HDB_HDB00">
    <primitive id="rsc_ip_HDB_HDB00" class="ocf" provider="heartbeat" type="IPaddr2">
      <instance_attributes id="rsc_ip_HDB_HDB00-instance_attributes">
        <nvpair name="ip" value="127.0.0.1"/>
      </instance_attributes>
    </primitive>
  </group>
</resources>"""

DUMMY_OS_COMMAND = """kernel.numa_balancing = 0"""

DUMMY_GLOBAL_INI = """[DEFAULT]
dumm1 = dummy2

[ha_dr_provider_sushanasr]
provider = SAPHanaSR-angi
"""

DUMMY_CONSTANTS = {
    "VALID_CONFIGS": {
        "REDHAT": {"stonith-enabled": "true"},
        "azure-fence-agent": {"priority": "10"},
    },
    "RSC_DEFAULTS": {
        "REDHAT": {
            "resource-stickiness": "1000",
            "migration-threshold": "5000",
        }
    },
    "OP_DEFAULTS": {
        "REDHAT": {
            "timeout": "600",
            "record-pending": "true",
        }
    },
    "CRM_CONFIG_DEFAULTS": {"stonith-enabled": "true"},
    "RESOURCE_DEFAULTS": {
        "REDHAT": {
            "fence_agent": {
                "meta_attributes": {"pcmk_delay_max": "15"},
                "operations": {"monitor": {"timeout": ["700", "700s"]}},
            },
            "sbd_stonith": {
                "meta_attributes": {"pcmk_delay_max": "15"},
                "operations": {"monitor": {"timeout": ["30", "30s"]}},
            },
            "hana": {"meta_attributes": {"clone-max": "2"}},
        }
    },
    "OS_PARAMETERS": {
        "DEFAULTS": {"sysctl": {"kernel.numa_balancing": "kernel.numa_balancing = 0"}}
    },
    "GLOBAL_INI": {"REDHAT": {"provider": "SAPHanaSR"}, "SUSE": {"provider": "SAPHanaSR-angi"}},
    "CONSTRAINTS": {"rsc_location": {"score": "INFINITY"}},
}


def fake_open_factory(file_content):
    """
    Factory function to create a fake open function that returns a StringIO object.

    :param file_content: Content to be returned by the fake open function.
    :type file_content: str
    :return: Fake open function.
    :rtype: function
    """

    def fake_open(*args, **kwargs):
        """
        Fake open function that returns a StringIO object.

        :param *args: Positional arguments.
        :param **kwargs: Keyword arguments.
        :return: Instance of StringIO with file content.
        :rtype: io.StringIO
        """
        return io.StringIO("\n".join(file_content))

    return fake_open


class TestHAClusterValidator:
    """
    Test cases for the HAClusterValidator class.
    """

    @pytest.fixture
    def mock_xml_outputs(self):
        """
        Fixture for providing mock XML outputs.

        :return: Mock XML outputs.
        :rtype: dict
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
        Fixture for creating a HAClusterValidator instance.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        :param mock_xml_outputs: Mock XML outputs.
        :type mock_xml_outputs: dict
        :return: HAClusterValidator instance.
        :rtype: HAClusterValidator
        """

        def mock_execute_command(*args, **kwargs):
            """
            Mock function to replace execute_command_subprocess.

            :param *args: Positional arguments.
            :param **kwargs: Keyword arguments.
            :return: Mocked command output.
            :rtype: str
            """
            command = str(args[1]) if len(args) > 1 else str(kwargs.get("command"))
            if "sysctl" in command:
                return DUMMY_OS_COMMAND
            return mock_xml_outputs.get(command[-1], "")

        monkeypatch.setattr(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess",
            mock_execute_command,
        )
        monkeypatch.setattr("builtins.open", fake_open_factory(DUMMY_GLOBAL_INI))
        return HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            os_version="9.2",
            sid="PRD",
            instance_number="00",
            fencing_mechanism="AFA",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
        )

    @pytest.fixture
    def validator_angi(self, monkeypatch, mock_xml_outputs):
        """
        Fixture for creating a HAClusterValidator instance.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        :param mock_xml_outputs: Mock XML outputs.
        :type mock_xml_outputs: dict
        :return: HAClusterValidator instance.
        :rtype: HAClusterValidator
        """

        def mock_execute_command(*args, **kwargs):
            """
            Mock function to replace execute_command_subprocess.

            :param *args: Positional arguments.
            :param **kwargs: Keyword arguments.
            :return: Mocked command output.
            :rtype: str
            """
            command = str(args[1]) if len(args) > 1 else str(kwargs.get("command"))
            if "sysctl" in command:
                return DUMMY_OS_COMMAND
            return mock_xml_outputs.get(command[-1], "")

        monkeypatch.setattr(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess",
            mock_execute_command,
        )
        monkeypatch.setattr("builtins.open", fake_open_factory(DUMMY_GLOBAL_INI))
        return HAClusterValidator(
            os_type=OperatingSystemFamily.SUSE,
            os_version="9.2",
            sid="PRD",
            instance_number="00",
            fencing_mechanism="AFA",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.ANGI,
        )

    def test_get_expected_value_fence_config(self, validator):
        """
        Test _get_expected_value method with fence configuration.
        """
        validator.fencing_mechanism = "azure-fence-agent"
        expected = validator._get_expected_value("crm_config", "priority")
        assert expected == "10"

    def test_get_expected_value_os_config(self, validator):
        """
        Test _get_expected_value method with OS configuration.
        """
        expected = validator._get_expected_value("crm_config", "stonith-enabled")
        assert expected == "true"

    def test_get_expected_value_defaults(self, validator):
        """
        Test _get_expected_value method with defaults.
        """
        expected = validator._get_expected_value("crm_config", "unknown-param")
        assert expected is None

    def test_get_resource_expected_value_meta_attributes(self, validator):
        """
        Test _get_resource_expected_value method for meta_attributes section.
        """
        expected = validator._get_resource_expected_value(
            "fence_agent", "meta_attributes", "pcmk_delay_max"
        )
        assert expected == "15"

    def test_get_resource_expected_value_operations(self, validator):
        """
        Test _get_resource_expected_value method for operations section.
        """
        expected = validator._get_resource_expected_value(
            "fence_agent", "operations", "timeout", "monitor"
        )
        assert expected == ["700", "700s"]

    def test_get_resource_expected_value_unknown_section(self, validator):
        """
        Test _get_resource_expected_value method for unknown section.
        """
        expected = validator._get_resource_expected_value("fence_agent", "unknown_section", "param")
        assert expected is None

    def test_create_parameter_with_empty_value(self, validator):
        """
        Test _create_parameter method when value is empty.
        """
        param = validator._create_parameter(
            category="test_category", name="test_param", value="", expected_value="expected"
        )
        assert param["status"] == TestStatus.INFO.value

    def test_create_parameter_with_list_expected_value_success(self, validator):
        """
        Test _create_parameter method with list expected value - success case.
        """
        param = validator._create_parameter(
            category="test_category",
            name="test_param",
            value="value1",
            expected_value=["value1", "value2"],
        )
        assert param["status"] == TestStatus.SUCCESS.value
        assert param["expected_value"] == "value1"

    def test_create_parameter_with_list_expected_value_error(self, validator):
        """
        Test _create_parameter method with list expected value - error case.
        """
        param = validator._create_parameter(
            category="test_category",
            name="test_param",
            value="value3",
            expected_value=["value1", "value2"],
        )
        assert param["status"] == TestStatus.ERROR.value

    def test_create_parameter_with_string_expected_value_success(self, validator):
        """
        Test _create_parameter method with string expected value - success case.
        """
        param = validator._create_parameter(
            category="test_category",
            name="test_param",
            value="expected_value",
            expected_value="expected_value",
        )
        assert param["status"] == TestStatus.SUCCESS.value

    def test_create_parameter_with_string_expected_value_error(self, validator):
        """
        Test _create_parameter method with string expected value - error case.
        """
        param = validator._create_parameter(
            category="test_category",
            name="test_param",
            value="actual_value",
            expected_value="expected_value",
        )
        assert param["status"] == TestStatus.ERROR.value

    def test_create_parameter_with_invalid_expected_value_type(self, validator):
        """
        Test _create_parameter method with invalid expected value type.
        """
        param = validator._create_parameter(
            category="test_category",
            name="test_param",
            value="test_value",
            expected_value={"invalid": "type"},
        )
        assert param["status"] == TestStatus.ERROR.value

    def test_create_parameter_with_none_expected_value(self, validator):
        """
        Test _create_parameter method when expected_value is None.
        """
        param = validator._create_parameter(
            category="crm_config", name="test_param", value="test_value", expected_value=None
        )
        assert param["status"] == TestStatus.INFO.value

    def test_parse_global_ini_parameters_angi_provider(self, validator_angi):
        """
        Test _parse_global_ini_parameters method with ANGI provider.
        Covers lines 420-447.
        """
        result = validator_angi.get_result()
        assert "details" in result
        assert "parameters" in result["details"]

    def test_parse_basic_config(self, validator):
        """
        Test _parse_basic_config method.
        Covers lines 462-473.
        """
        xml_str = """<test>
            <nvpair name="test_param" value="test_value" id="test_id"/>
            <nvpair name="another_param" value="another_value" id="another_id"/>
        </test>"""
        params = validator._parse_basic_config(
            ET.fromstring(xml_str), "crm_config", "test_subcategory"
        )
        assert len(params) == 2
        assert params[0]["category"] == "crm_config_test_subcategory"
        assert params[0]["name"] == "test_param"
        assert params[0]["value"] == "test_value"

    def test_parse_resource_hana_meta_and_topology_meta(self, validator):
        """
        Test _parse_resource method for hana_meta and topology_meta categories.
        Covers lines 486-521.
        """
        xml_str = """<primitive>
            <nvpair name="meta_param" value="meta_value" id="meta_id"/>
        </primitive>"""
        element = ET.fromstring(xml_str)
        params = validator._parse_resource(element, "hana_meta")
        assert len(params) > 0
        params = validator._parse_resource(element, "topology_meta")
        assert len(params) > 0

    def test_parse_constraints_with_valid_constraints(self, validator_angi):
        """
        Test _parse_constraints method with valid constraints.
        Covers lines 532-552.
        """
        xml_str = """<constraints>
            <rsc_location id="loc_test" score="INFINITY" rsc="test_resource"/>
            <rsc_colocation id="col_test" score="4000" rsc="resource1"/>
            <rsc_order id="ord_test" kind="Optional" first="resource1"/>
            <unknown_constraint id="unknown_test" attribute="value"/>
        </constraints>"""
        root = ET.fromstring(xml_str)
        params = validator_angi._parse_constraints(root)
        constraint_params = [p for p in params if p["category"] == "constraints_rsc_location"]
        assert len(constraint_params) >= 1

    def test_parse_ha_cluster_config_redhat_skip_op_defaults(self, monkeypatch):
        """
        Test parse_ha_cluster_config method with REDHAT OS skipping op_defaults.
        Covers lines 574-607.
        """

        def mock_execute_command(*args, **kwargs):
            return "<dummy/>"

        monkeypatch.setattr(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess",
            mock_execute_command,
        )
        monkeypatch.setattr("builtins.open", fake_open_factory(DUMMY_GLOBAL_INI))
        validator = HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            os_version="9.2",
            sid="PRD",
            instance_number="00",
            fencing_mechanism="AFA",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
        )
        result = validator.get_result()
        assert "details" in result

    def test_parse_ha_cluster_config_success(self, validator):
        """
        Test the parse_ha_cluster_config method for successful parsing.

        :param validator: HAClusterValidator instance.
        :type validator: HAClusterValidator
        """
        result = validator.get_result()
        assert result["status"] == "PASSED"

    def test_main_method(self, monkeypatch):
        """
        Test the main method of the module.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch:
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class for AnsibleModule.
            """

            def __init__(self, *args, **kwargs):
                self.params = {
                    "sid": "PRD",
                    "instance_number": "00",
                    "virtual_machine_name": "vm_name",
                    "fencing_mechanism": "AFA",
                    "os_version": "9.2",
                    "pcmk_constants": DUMMY_CONSTANTS,
                    "saphanasr_provider": HanaSRProvider.SAPHANASR.value,
                }

            def exit_json(self, **kwargs):
                nonlocal mock_result
                mock_result = kwargs

        monkeypatch.setattr(
            "src.modules.get_pcmk_properties_db.AnsibleModule",
            MockAnsibleModule,
        )

        main()

        assert mock_result["status"] == "PASSED"
