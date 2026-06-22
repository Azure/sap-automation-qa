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
from src.module_utils.enums import (
    OperatingSystemFamily,
    HanaSRProvider,
    HanaTopology,
    TestStatus,
)

from tests.modules.pcmk_constants import (
    DB_DUMMY_XML_RSC,
    DB_DUMMY_XML_OP,
    DB_DUMMY_XML_CRM,
    DB_DUMMY_XML_CONSTRAINTS,
    DB_DUMMY_XML_RESOURCES,
    DB_DUMMY_XML_FULL_CIB,
    DB_DUMMY_XML_SCALEOUT_RESOURCES,
    DB_DUMMY_XML_SCALEOUT_CIB,
    DB_DUMMY_GLOBAL_INI_SCALEOUT,
    DB_DUMMY_XML_RHEL_ANGI_RESOURCES,
    DB_DUMMY_XML_RHEL_ANGI_CIB,
    DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_RESOURCES,
    DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_CIB,
    DB_DUMMY_GLOBAL_INI_RHEL_ANGI,
    DB_DUMMY_OS_COMMAND,
    DB_DUMMY_GLOBAL_INI_SAPHANASR,
    DB_DUMMY_GLOBAL_INI_ANGI,
    DB_DUMMY_CONSTANTS,
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
            return DB_DUMMY_OS_COMMAND
        if len(command) >= 2 and command[-1] in self.mock_outputs:
            return self.mock_outputs[command[-1]]
        return ""


class MockOpen:
    """
    Mock class for open function.
    """

    def __init__(self, file_content):
        self.file_content = file_content
        self.call_count = 0

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
            "rsc_defaults": DB_DUMMY_XML_RSC,
            "crm_config": DB_DUMMY_XML_CRM,
            "op_defaults": DB_DUMMY_XML_OP,
            "constraints": DB_DUMMY_XML_CONSTRAINTS,
            "resources": DB_DUMMY_XML_RESOURCES,
        }

    @pytest.fixture
    def validator(self, mock_xml_outputs):
        """
        Fixture for creating a TestableHAClusterValidator instance.
        """
        mock_execute = MockExecuteCommand(mock_xml_outputs)
        mock_open = MockOpen(DB_DUMMY_GLOBAL_INI_SAPHANASR)
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
                constants=DB_DUMMY_CONSTANTS,
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
        mock_open = MockOpen(DB_DUMMY_GLOBAL_INI_ANGI)
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
                constants=DB_DUMMY_CONSTANTS,
                saphanasr_provider=HanaSRProvider.ANGI,
                cib_output="",
            )
            yield validator
        finally:
            builtins.open = original_open

    @pytest.fixture
    def validator_scaleout_provider(self, mock_xml_outputs):
        """
        Fixture for creating a TestableHAClusterValidator instance with SCALEOUT provider.
        """
        mock_execute = MockExecuteCommand(mock_xml_outputs)
        mock_open = MockOpen(DB_DUMMY_GLOBAL_INI_SAPHANASR)
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
                constants=DB_DUMMY_CONSTANTS,
                saphanasr_provider=HanaSRProvider.SCALEOUT,
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
            constants=DB_DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
            cib_output=DB_DUMMY_XML_FULL_CIB,
        )

    @pytest.fixture
    def validator_scaleout(self, mock_xml_outputs):
        """
        Fixture for creating a scale-out HSR validator.
        """
        scaleout_outputs = mock_xml_outputs.copy()
        scaleout_outputs["resources"] = DB_DUMMY_XML_SCALEOUT_RESOURCES
        mock_execute = MockExecuteCommand(scaleout_outputs)
        mock_open = MockOpen(DB_DUMMY_GLOBAL_INI_SCALEOUT)
        original_open = builtins.open
        builtins.open = mock_open
        try:
            validator = TestableHAClusterValidator(
                mock_execute,
                mock_open,
                os_type=OperatingSystemFamily.REDHAT,
                sid="HN1",
                instance_number="03",
                fencing_mechanism="sbd",
                virtual_machine_name="hana-s1-db1",
                constants=DB_DUMMY_CONSTANTS,
                saphanasr_provider=HanaSRProvider.SAPHANASR,
                hana_topology=HanaTopology.SCALE_OUT_HSR,
                cib_output="",
            )
            yield validator
        finally:
            builtins.open = original_open

    @pytest.fixture
    def validator_scaleout_cib(self):
        """
        Fixture for creating a scale-out HSR validator with CIB output.
        """
        return HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HN1",
            instance_number="03",
            fencing_mechanism="sbd",
            virtual_machine_name="hana-s1-db1",
            constants=DB_DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
            hana_topology=HanaTopology.SCALE_OUT_HSR,
            cib_output=DB_DUMMY_XML_SCALEOUT_CIB,
        )

    @pytest.fixture
    def validator_rhel_angi(self):
        """
        Fixture for creating a RHEL + SAPHanaSR-angi scale-up validator with CIB output.
        """
        return HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HDB",
            instance_number="00",
            fencing_mechanism="AFA",
            virtual_machine_name="rh7dhdb00l043",
            constants=DB_DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.ANGI,
            hana_topology=HanaTopology.SCALE_UP,
            cib_output=DB_DUMMY_XML_RHEL_ANGI_CIB,
        )

    def test_rhel_angi_active_categories(self, validator_rhel_angi):
        """
        RHEL angi scale-up must use angi categories and drop SAPHanaSR/master ones.
        """
        categories = validator_rhel_angi._get_active_resource_categories()
        assert "angi_topology" in categories
        assert "angi_hana" in categories
        assert "angi_filesystem" in categories
        assert "angi_topology_meta" in categories
        assert "angi_hana_meta" in categories
        assert "angi_filesystem_meta" in categories
        assert "topology" not in categories
        assert "topology_meta" not in categories
        assert "hana" not in categories
        assert "hana_meta" not in categories

    def test_rhel_angi_resources_parsed(self, validator_rhel_angi):
        """
        RHEL angi resources (controller/topology/filesystem) and clone-level
        metadata (promotable, clone-max) must validate as SUCCESS.
        """
        root = ET.fromstring(DB_DUMMY_XML_RHEL_ANGI_RESOURCES)
        params = validator_rhel_angi._parse_resources_section(root)
        assert len(params) > 0
        categories = {p.get("category", "") for p in params}
        assert any(cat.startswith("angi_hana") for cat in categories)
        assert any(cat.startswith("angi_topology") for cat in categories)
        assert any(cat.startswith("angi_filesystem") for cat in categories)

        promotable = [p for p in params if p.get("name") == "promotable"]
        assert promotable, "clone-level promotable meta must be validated for angi controller"
        assert promotable[0].get("status") == TestStatus.SUCCESS.value

        non_info = [p for p in params if p.get("status") not in ("", TestStatus.INFO.value)]
        assert all(
            p.get("status") == TestStatus.SUCCESS.value
            for p in non_info
            if p.get("category", "").startswith("angi_")
        )

    def test_rhel_angi_global_ini(self, validator_rhel_angi):
        """
        RHEL angi global.ini (HanaSR + ChkSrv hooks) must validate.
        """
        original_open = builtins.open
        builtins.open = MockOpen(DB_DUMMY_GLOBAL_INI_RHEL_ANGI)
        try:
            params = validator_rhel_angi._parse_global_ini_parameters()
        finally:
            builtins.open = original_open
        assert len(params) > 0
        names = {(p.get("category", ""), p.get("name", ""), p.get("value", "")) for p in params}
        assert any(name == "HanaSR" for _, _, name in names)
        assert any(
            p.get("status") == TestStatus.SUCCESS.value
            for p in params
            if p.get("name") == "provider"
        )

    @pytest.fixture
    def validator_rhel_angi_scaleout(self):
        """
        Fixture for creating a RHEL + SAPHanaSR-angi scale-out (HSR) validator.
        """
        return HAClusterValidator(
            os_type=OperatingSystemFamily.REDHAT,
            sid="HN1",
            instance_number="03",
            fencing_mechanism="AFA",
            virtual_machine_name="rhel10-db01-s1",
            constants=DB_DUMMY_CONSTANTS,
            saphanasr_provider=HanaSRProvider.ANGI,
            hana_topology=HanaTopology.SCALE_OUT_HSR,
            cib_output=DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_CIB,
        )

    def test_rhel_angi_scaleout_active_categories(self, validator_rhel_angi_scaleout):
        """
        RHEL angi scale-out must use the ANGI scale-out resource categories.
        """
        categories = validator_rhel_angi_scaleout._get_active_resource_categories()
        assert "angi_topology" in categories
        assert "angi_scaleout_hana" in categories
        assert "angi_filesystem" in categories
        assert "scaleout_filesystem" in categories
        assert "nfs_attribute" in categories
        assert "scaleout_hana" not in categories
        assert "angi_hana" not in categories

    def test_rhel_angi_scaleout_resources_parsed(self, validator_rhel_angi_scaleout):
        """
        RHEL angi scale-out controller/topology/filesystem resources must validate
        as SUCCESS, including the SAPHanaController primitive-level priority meta.
        """
        root = ET.fromstring(DB_DUMMY_XML_RHEL_ANGI_SCALEOUT_RESOURCES)
        params = validator_rhel_angi_scaleout._parse_resources_section(root)
        assert len(params) > 0
        categories = {p.get("category", "") for p in params}
        assert any(cat.startswith("angi_scaleout_hana") for cat in categories)
        assert any(cat.startswith("angi_topology") for cat in categories)
        assert any(cat.startswith("angi_filesystem") for cat in categories)

        priority = [
            p
            for p in params
            if p.get("category", "").startswith("angi_scaleout_hana")
            and p.get("name") == "priority"
        ]
        assert priority, "SAPHanaController priority meta must be validated for angi scale-out"
        assert priority[0].get("value") == "100"
        assert priority[0].get("status") == TestStatus.SUCCESS.value

        non_info = [p for p in params if p.get("status") not in ("", TestStatus.INFO.value)]
        assert all(
            p.get("status") == TestStatus.SUCCESS.value
            for p in non_info
            if p.get("category", "").startswith("angi_scaleout_hana")
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
        xml_str = DB_DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator._parse_resources_section(root)
        assert len(params) > 0
        categories = [p.get("category", "") for p in params]
        assert not any("angi_topology" in cat for cat in categories)

    def test_parse_resources_section_angi(self, validator_angi):
        """
        Test _parse_resources_section method with ANGI provider.
        """
        xml_str = DB_DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator_angi._parse_resources_section(root)
        assert len(params) > 0
        categories = [p.get("category", "") for p in params]
        assert not any(cat == "topology" for cat in categories)
        assert not any("nfs_attribute" in cat for cat in categories)

    def test_parse_resources_section_scaleout(self, validator_scaleout):
        """
        Test _parse_resources_section method with SCALEOUT provider.
        """
        xml_str = DB_DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator_scaleout._parse_resources_section(root)
        assert len(params) > 0
        categories = [p.get("category", "") for p in params]
        assert not any("angi_hana" in cat for cat in categories)
        assert not any("angi_filesystem" in cat for cat in categories)
        assert any("nfs_attribute" in cat for cat in categories)

    def test_nfs_attribute_parameters(self, validator_scaleout):
        """
        Test NFS attribute resource parameters are parsed and validated.
        """
        xml_str = DB_DUMMY_XML_RESOURCES
        root = ET.fromstring(xml_str)
        params = validator_scaleout._parse_resources_section(root)
        nfs_params = [p for p in params if "nfs_attribute" in p.get("category", "")]
        assert len(nfs_params) > 0
        nfs_names = [p["name"] for p in nfs_params]
        assert "active_value" in nfs_names
        assert "inactive_value" in nfs_names
        assert "clone-node-max" in nfs_names
        assert "interleave" in nfs_names
        for p in nfs_params:
            if p["name"] in ("active_value", "inactive_value", "clone-node-max", "interleave"):
                assert (
                    p["status"] == TestStatus.SUCCESS.value
                ), f"NFS param {p['name']} expected SUCCESS, got {p['status']}"
        info_params = [p for p in nfs_params if p["name"] == "name"]
        for p in info_params:
            assert p["status"] == TestStatus.INFO.value

    def test_parse_global_ini_parameters_saphanasr(self, validator):
        """
        Test _parse_global_ini_parameters method with SAPHanaSR provider.
        """
        params = validator._parse_global_ini_parameters()
        assert len(params) > 0
        provider_params = [p for p in params if p["name"] == "provider"]
        assert len(provider_params) == 2
        provider_values = [p["value"] for p in provider_params]
        assert "SAPHanaSR" in provider_values
        assert "susChkSrv" in provider_values

    def test_parse_global_ini_parameters_angi(self, validator_angi):
        """
        Test _parse_global_ini_parameters method with ANGI provider.
        """
        params = validator_angi._parse_global_ini_parameters()
        assert len(params) > 0
        provider_params = [p for p in params if p["name"] == "provider"]
        assert len(provider_params) == 2
        provider_values = [p["value"] for p in provider_params]
        assert "susHanaSR" in provider_values
        assert "susChkSrv" in provider_values

    def test_parse_global_ini_parameters_with_list_expected_value(self, validator):
        """
        Test _parse_global_ini_parameters with list expected value matching.
        """
        params = validator._parse_global_ini_parameters()
        execution_params = [p for p in params if p["name"] == "execution_order"]
        assert len(execution_params) == 2
        for param in execution_params:
            assert param["status"] in [
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
        xml_str = DB_DUMMY_XML_RESOURCES
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
                    "pcmk_constants": DB_DUMMY_CONSTANTS,
                    "saphanasr_provider": "SAPHanaSR",
                    "hana_topology": "scale_up",
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
        builtins.open = MockOpen(DB_DUMMY_GLOBAL_INI_SAPHANASR)

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
                    "pcmk_constants": DB_DUMMY_CONSTANTS,
                    "saphanasr_provider": "SAPHanaSR",
                    "hana_topology": "scale_up",
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
        builtins.open = MockOpen(DB_DUMMY_GLOBAL_INI_SAPHANASR)
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
            xml_str = DB_DUMMY_XML_RESOURCES
            root = ET.fromstring(xml_str)
            xpaths = xpath if isinstance(xpath, list) else [xpath]
            elements = []
            for xp in xpaths:
                elements.extend(root.findall(xp))
            if elements:
                params = validator._parse_resource(elements[0], category)
                assert isinstance(params, list)

    def test_global_ini_section_detection(self, validator_angi):
        """
        Test global.ini section detection for different providers.
        """
        params = validator_angi._parse_global_ini_parameters()
        assert isinstance(params, list)

    def test_parse_global_ini_multiple_sections(self, validator):
        """
        Test that multiple sections are parsed correctly from global.ini.
        """
        params = validator._parse_global_ini_parameters()
        assert len(params) == 8
        param_names = [p["name"] for p in params]
        assert param_names.count("provider") == 2
        assert param_names.count("path") == 2
        assert param_names.count("execution_order") == 2
        assert param_names.count("action_on_host") == 1

    def test_parse_global_ini_angi_multiple_sections(self, validator_angi):
        """
        Test that multiple sections are parsed correctly for ANGI provider.
        """
        params = validator_angi._parse_global_ini_parameters()
        assert len(params) == 9
        param_names = [p["name"] for p in params]
        assert param_names.count("provider") == 2
        assert param_names.count("path") == 2
        assert param_names.count("execution_order") == 2
        assert param_names.count("action_on_host") == 1
        assert param_names.count("ha_dr_sushanasr") == 1
        assert param_names.count("ha_dr_suschksrv") == 1

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

    def test_scaleout_init(self, validator_scaleout):
        """
        Test scale-out validator initializes with correct topology.
        The detected provider is SAPHanaSR (not SAPHanaController)
        because Ansible detection returns the installed package name.
        """
        assert validator_scaleout.hana_topology == HanaTopology.SCALE_OUT_HSR
        assert validator_scaleout.saphanasr_provider == HanaSRProvider.SAPHANASR
        assert validator_scaleout.sid == "HN1"
        assert validator_scaleout.instance_number == "03"

    def test_scaleout_resource_categories_distinct(self):
        """
        Test that SCALEOUT_RESOURCE_CATEGORIES is distinct from RESOURCE_CATEGORIES.
        """
        scaleout = HAClusterValidator.SCALEOUT_RESOURCE_CATEGORIES
        scaleup = HAClusterValidator.RESOURCE_CATEGORIES
        assert "scaleout_filesystem" in scaleout
        assert "nfs_attribute" in scaleout
        assert "scaleout_hana" in scaleout
        assert "scaleout_topology" in scaleout
        assert "scaleout_filesystem" not in scaleup
        assert "scaleout_hana" not in scaleup

    def test_scaleout_parse_resources_finds_nfs(self, validator_scaleout):
        """
        Test that scale-out resource parsing finds NFS filesystem clones.
        """
        root = ET.fromstring(DB_DUMMY_XML_SCALEOUT_RESOURCES)
        params = validator_scaleout._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        assert any("scaleout_filesystem" in cat for cat in categories)

    def test_scaleout_parse_resources_finds_controller(self, validator_scaleout):
        """
        Test that scale-out resource parsing finds SAPHanaController.
        """
        root = ET.fromstring(DB_DUMMY_XML_SCALEOUT_RESOURCES)
        params = validator_scaleout._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        assert any("scaleout_hana" in cat for cat in categories)

    def test_scaleout_parse_resources_finds_topology(self, validator_scaleout):
        """
        Test that scale-out resource parsing finds SAPHanaTopology.
        """
        root = ET.fromstring(DB_DUMMY_XML_SCALEOUT_RESOURCES)
        params = validator_scaleout._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        assert any("scaleout_topology" in cat for cat in categories)

    def test_scaleout_parse_resources_finds_nfs_attributes(self, validator_scaleout):
        """
        Test that scale-out resource parsing finds NFS attribute resources.
        """
        root = ET.fromstring(DB_DUMMY_XML_SCALEOUT_RESOURCES)
        params = validator_scaleout._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        assert any("nfs_attribute" in cat for cat in categories)

    def test_scaleout_excludes_scaleup_categories(self, validator_scaleout):
        """
        Test that scale-out does not use scale-up specific categories.
        """
        root = ET.fromstring(DB_DUMMY_XML_SCALEOUT_RESOURCES)
        params = validator_scaleout._parse_resources_section(root)
        categories = [p.get("category", "") for p in params]
        assert not any(cat == "hana" for cat in categories)
        assert not any(cat == "topology" for cat in categories)
        assert not any(cat == "angi_hana" for cat in categories)

    def test_scaleout_validation_with_cib(self, validator_scaleout_cib):
        """
        Test scale-out validation using CIB output produces valid result.
        """
        result = validator_scaleout_cib.get_result()
        assert result["status"] in [
            TestStatus.SUCCESS.value,
            TestStatus.ERROR.value,
            TestStatus.WARNING.value,
        ]
        assert "parameters" in result["details"]
        assert "CIB output provided" in result["message"]

    def test_scaleout_global_ini_scaleout_path(self, validator_scaleout):
        """
        Test that scale-out validator reads SAPHanaSR-ScaleOut path.
        """
        params = validator_scaleout._parse_global_ini_parameters()
        path_params = [p for p in params if p["name"] == "path"]
        path_values = [p["value"] for p in path_params]
        assert any("/usr/share/SAPHanaSR-ScaleOut" in v for v in path_values)

    def test_scaleout_global_ini_provider_values(self, validator_scaleout):
        """
        Test scale-out global.ini has correct provider values.
        """
        params = validator_scaleout._parse_global_ini_parameters()
        provider_params = [p for p in params if p["name"] == "provider"]
        provider_values = [p["value"] for p in provider_params]
        assert "SAPHanaSR" in provider_values
        assert "ChkSrv" in provider_values

    def test_get_active_resource_categories_scaleout(self, validator_scaleout):
        """
        Test that scale-out validator returns scaleout categories.
        """
        cats = validator_scaleout._get_active_resource_categories()
        assert "scaleout_filesystem" in cats
        assert "nfs_attribute" in cats
        assert "scaleout_hana" in cats
        assert "scaleout_topology" in cats
        assert "topology" not in cats
        assert "hana" not in cats

    def test_get_active_resource_categories_angi(self, validator_angi):
        """
        Test that ANGI validator returns correct categories.
        """
        cats = validator_angi._get_active_resource_categories()
        assert "angi_topology" in cats
        assert "angi_hana" in cats
        assert "angi_filesystem" in cats
        assert "topology" not in cats

        assert validator_angi.saphanasr_provider == HanaSRProvider.ANGI
        assert validator_angi.hana_topology == HanaTopology.SCALE_UP
        defaults = validator_angi.constants["GLOBAL_INI"].get(validator_angi.os_type, {})
        assert validator_angi.saphanasr_provider.value in defaults

    def test_default_topology_is_scaleup(self, validator):
        """
        Test that default topology is SCALE_UP.
        """
        cats = validator._get_active_resource_categories()
        assert "topology" in cats
        assert "hana" in cats
        assert "scaleout_filesystem" not in cats
        assert "scaleout_hana" not in cats

        assert validator.hana_topology == HanaTopology.SCALE_UP

        assert validator.saphanasr_provider == HanaSRProvider.SAPHANASR
        assert validator.hana_topology == HanaTopology.SCALE_UP
        defaults = validator.constants["GLOBAL_INI"].get(validator.os_type, {})
        assert validator.saphanasr_provider.value in defaults

    def test_global_ini_provider_key_scaleout(self, validator_scaleout):
        """
        Test that scale-out dispatches to SAPHanaController regardless
        of the detected provider (which will be SAPHanaSR at runtime).
        """
        assert validator_scaleout.saphanasr_provider == (HanaSRProvider.SAPHANASR)
        assert validator_scaleout.hana_topology == (HanaTopology.SCALE_OUT_HSR)
        defaults = validator_scaleout.constants["GLOBAL_INI"].get(validator_scaleout.os_type, {})
        assert "SAPHanaController" in defaults

    def test_scaleout_migration_threshold_expected_value(self, validator_scaleout):
        """
        Test that scale-out HSR resolves migration-threshold to 50 via topology key.
        """
        result = validator_scaleout._get_expected_value("rsc_defaults", "migration-threshold")
        assert result is not None
        expected_value, is_required = result
        assert expected_value == ["50"]
        assert is_required is True
