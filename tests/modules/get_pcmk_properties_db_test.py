# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_pcmk_properties_db module.
"""

import builtins
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
  <primitive id="rsc_ip_HDB_HDB00" class="ocf" provider="heartbeat" type="IPaddr2">
    <instance_attributes>
      <nvpair name="ip" value="127.0.0.1"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_azure_lb" class="ocf" provider="heartbeat" type="azure-lb">
    <instance_attributes>
      <nvpair name="port" value="62500"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_filesystem" class="ocf" provider="heartbeat" type="Filesystem">
    <instance_attributes>
      <nvpair name="device" value="/dev/sda1"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_fence_azure" class="stonith" type="fence_azure_arm">
    <instance_attributes>
      <nvpair name="login" value="testuser"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_angi_fs" class="ocf" provider="suse" type="SAPHanaFilesystem">
    <instance_attributes>
      <nvpair name="filesystem" value="/hana/data"/>
    </instance_attributes>
  </primitive>
  <primitive id="rsc_angi_controller" class="ocf" provider="suse" type="SAPHanaController">
    <instance_attributes>
      <nvpair name="SID" value="HDB"/>
    </instance_attributes>
  </primitive>
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

DUMMY_GLOBAL_INI_SAPHANASR = """[DEFAULT]
dummy1 = dummy2

[ha_dr_provider_SAPHanaSR]
provider = SAPHanaSR
path = /usr/share/SAPHanaSR
execution_order = 1
"""

DUMMY_GLOBAL_INI_ANGI = """[DEFAULT]
dummy1 = dummy2

[ha_dr_provider_sushanasr]
provider = SAPHanaSR-angi
path = /usr/share/SAPHanaSR-angi
execution_order = 1
"""

DUMMY_CONSTANTS = {
    "VALID_CONFIGS": {
        "REDHAT": {
            "stonith-enabled": {"value": "true", "required": False},
            "cluster-name": {"value": "hdb_HDB", "required": False},
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
            "hana": {
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
    "GLOBAL_INI": {
        "REDHAT": {
            "SAPHanaSR": {
                "provider": {"value": "SAPHanaSR", "required": False},
                "path": {"value": "/usr/share/SAPHanaSR", "required": False},
                "execution_order": {"value": ["1", "2"], "required": False},
            }
        },
        "SUSE": {
            "SAPHanaSR-angi": {
                "provider": {"value": "SAPHanaSR-angi", "required": False},
                "path": {"value": "/usr/share/SAPHanaSR-angi", "required": False},
            }
        },
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


class MockOpen:
    """
    Mock class for open function.
    """

    def __init__(self, file_content):
        self.file_content = file_content

    def __call__(self, *args, **kwargs):
        return io.StringIO(self.file_content)


class TestableHAClusterValidator(HAClusterValidator):
    """
    Testable version of HAClusterValidator with mocked dependencies.
    """

    def __init__(self, mock_execute_command, mock_open, *args, **kwargs):
        self._mock_execute_command = mock_execute_command
        self._mock_open = mock_open
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
        mock_open = MockOpen(DUMMY_GLOBAL_INI_SAPHANASR)
        original_open = builtins.open
        builtins.open = mock_open
        try:
            validator = TestableHAClusterValidator(
                mock_execute,
                mock_open,
                os_type=OperatingSystemFamily.REDHAT,
                sid="HDB",
                instance_number="00",
                fencing_mechanism="sbd",
                virtual_machine_name="vmname",
                constants=DUMMY_CONSTANTS,
                saphanasr_provider=HanaSRProvider.SAPHANASR,
                cib_output="",
            )
            yield validator
        finally:
            builtins.open = original_open

    @pytest.fixture
    def validator_angi(self, mock_xml_outputs):
        """
        Fixture for creating a TestableHAClusterValidator instance with ANGI provider.
        """
        mock_execute = MockExecuteCommand(mock_xml_outputs)
        mock_open = MockOpen(DUMMY_GLOBAL_INI_ANGI)
        original_open = builtins.open
        builtins.open = mock_open
        try:
            validator = TestableHAClusterValidator(
                mock_execute,
                mock_open,
                os_type=OperatingSystemFamily.SUSE,
                sid="HDB",
                instance_number="00",
                fencing_mechanism="sbd",
                virtual_machine_name="vmname",
                constants=DUMMY_CONSTANTS,
                saphanasr_provider=HanaSRProvider.ANGI,
                cib_output="",
            )
            yield validator
        finally:
            builtins.open = original_open

    @pytest.fixture
    def validator_with_cib(self):
        """
        Fixture for creating a validator with CIB output.
        """
        return HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HDB",
            instance_number="00",
            fencing_mechanism="sbd",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
            cib_output=DUMMY_XML_FULL_CIB,
        )

    def test_init(self, validator):
        """
        Test the __init__ method.
        """
        assert validator.os_type == "REDHAT"
        assert validator.sid == "HDB"
        assert validator.instance_number == "00"
        assert validator.saphanasr_provider == HanaSRProvider.SAPHANASR

    def test_parse_resources_section_saphanasr(self, validator):
        """
        Test _parse_resources_section method with SAPHanaSR provider.
        """
        xml_str = DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator._parse_resources_section(root)
        assert len(params) > 0
        categories = [p.get("category", "") for p in params]
        assert not any("angi_topology" in cat for cat in categories)

    def test_parse_resources_section_angi(self, validator_angi):
        """
        Test _parse_resources_section method with ANGI provider.
        """
        xml_str = DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator_angi._parse_resources_section(root)
        assert len(params) > 0
        categories = [p.get("category", "") for p in params]
        assert not any(cat == "topology" for cat in categories)

    def test_parse_global_ini_parameters_saphanasr(self, validator):
        """
        Test _parse_global_ini_parameters method with SAPHanaSR provider.
        """
        params = validator._parse_global_ini_parameters()
        assert len(params) > 0
        provider_params = [p for p in params if p["name"] == "provider"]
        assert len(provider_params) == 1
        assert provider_params[0]["value"] == "SAPHanaSR"

    def test_parse_global_ini_parameters_angi(self, validator_angi):
        """
        Test _parse_global_ini_parameters method with ANGI provider.
        """
        params = validator_angi._parse_global_ini_parameters()
        assert len(params) > 0
        provider_params = [p for p in params if p["name"] == "provider"]
        assert len(provider_params) == 1
        assert provider_params[0]["value"] == "SAPHanaSR-angi"

    def test_parse_global_ini_parameters_with_list_expected_value(self, validator):
        """
        Test _parse_global_ini_parameters with list expected value matching.
        """
        params = validator._parse_global_ini_parameters()
        execution_params = [p for p in params if p["name"] == "execution_order"]
        if execution_params:
            assert execution_params[0]["status"] in [
                TestStatus.SUCCESS.value,
                TestStatus.INFO.value,
            ]

    def test_parse_global_ini_parameters_exception_handling(self, validator):
        """
        Test _parse_global_ini_parameters exception handling.
        """
        original_open = builtins.open

        def mock_open_error(*args, **kwargs):
            raise FileNotFoundError("File not found")

        builtins.open = mock_open_error
        try:
            params = validator._parse_global_ini_parameters()
            assert len(params) == 0
        finally:
            builtins.open = original_open

    def test_get_additional_parameters(self, validator):
        """
        Test _get_additional_parameters method.
        """
        params = validator._get_additional_parameters()
        assert isinstance(params, list)
        assert len(params) > 0

    def test_resource_categories_coverage(self, validator):
        """
        Test all resource categories are parsed correctly.
        """
        xml_str = DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        expected_categories = [
            "sbd_stonith",
            "topology",
            "hana",
            "ipaddr",
            "azurelb",
            "filesystem",
            "fence_agent",
        ]
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
                    "sid": "HDB",
                    "instance_number": "00",
                    "virtual_machine_name": "vmname",
                    "fencing_mechanism": "sbd",
                    "pcmk_constants": DUMMY_CONSTANTS,
                    "saphanasr_provider": "SAPHanaSR",
                    "cib_output": "",
                    "os_family": "RedHat",
                }

            def exit_json(self, **kwargs):
                nonlocal mock_result
                mock_result = kwargs

        def mock_ansible_facts(module):
            return {"os_family": "RedHat"}

        import src.modules.get_pcmk_properties_db as module_under_test

        original_ansible_module = module_under_test.AnsibleModule
        original_ansible_facts = module_under_test.ansible_facts
        original_open = builtins.open
        module_under_test.AnsibleModule = MockAnsibleModule
        module_under_test.ansible_facts = mock_ansible_facts
        builtins.open = MockOpen(DUMMY_GLOBAL_INI_SAPHANASR)

        try:
            main()
            assert "status" in mock_result
            assert "message" in mock_result
        finally:
            module_under_test.AnsibleModule = original_ansible_module
            module_under_test.ansible_facts = original_ansible_facts
            builtins.open = original_open

    def test_main_with_exception_fallback(self):
        """
        Test main function with exception handling fallback.
        """
        mock_result = {}

        class MockAnsibleModuleFallback:
            def __init__(self, argument_spec=None, **kwargs):
                self.params = {
                    "sid": "HDB",
                    "instance_number": "00",
                    "virtual_machine_name": "vmname",
                    "fencing_mechanism": "sbd",
                    "pcmk_constants": DUMMY_CONSTANTS,
                    "saphanasr_provider": "SAPHanaSR",
                    "cib_output": "",
                    "os_family": "RedHat",
                }

            def exit_json(self, **kwargs):
                nonlocal mock_result
                mock_result = kwargs

        call_count = 0

        def mock_ansible_module_factory(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return MockAnsibleModuleFallback(*args, **kwargs)

        import src.modules.get_pcmk_properties_db as module_under_test

        original_ansible_module = module_under_test.AnsibleModule
        original_open = builtins.open
        module_under_test.AnsibleModule = mock_ansible_module_factory
        builtins.open = MockOpen(DUMMY_GLOBAL_INI_SAPHANASR)
        try:
            main()
            assert "status" in mock_result
        finally:
            module_under_test.AnsibleModule = original_ansible_module
            builtins.open = original_open

    def test_all_resource_types_parsed(self, validator):
        """
        Test that all defined resource categories can be parsed.
        """
        for category, xpath in HAClusterValidator.RESOURCE_CATEGORIES.items():
            xml_str = DUMMY_XML_RESOURCES
            root = ET.fromstring(xml_str)
            elements = root.findall(xpath)
            if elements:
                params = validator._parse_resource(elements[0], category)
                assert isinstance(params, list)

    def test_global_ini_section_detection(self, validator_angi):
        """
        Test global.ini section detection for different providers.
        """
        params = validator_angi._parse_global_ini_parameters()
        assert isinstance(params, list)

    def test_get_expected_value_methods(self, validator):
        """
        Test inherited expected value methods.
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
