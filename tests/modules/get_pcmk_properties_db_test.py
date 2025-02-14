# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_pcmk_properties_db module.
"""

import io
import pytest
from src.modules.get_pcmk_properties_db import HAClusterValidator, main

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

[ha_dr_provider_SAPHanaSR]
provider = SAPHanaSR
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
            "stonith": {
                "meta_attributes": {"priority": "10"},
                "operations": {"monitor": {"timeout": "30"}},
            },
            "hana": {"meta_attributes": {"clone-max": "2"}},
        }
    },
    "OS_PARAMETERS": {
        "DEFAULTS": {"sysctl": {"kernel.numa_balancing": "kernel.numa_balancing = 0"}}
    },
    "GLOBAL_INI": {"REDHAT": {"provider": "SAPHanaSR"}},
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
        """

        def mock_execute_command(*args, **kwargs):
            """
            Mock function to replace execute_command_subprocess.

            :return: Mocked command output.
            :rtype: str
            """
            command = args[1] if len(args) > 1 else kwargs.get("command")
            if "sysctl" in command:
                return DUMMY_OS_COMMAND
            return mock_xml_outputs.get(command[-1], "")

        monkeypatch.setattr(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess",
            mock_execute_command,
        )
        monkeypatch.setattr("builtins.open", fake_open_factory(DUMMY_GLOBAL_INI))
        return HAClusterValidator(
            os_type="REDHAT",
            os_version="9.2",
            sid="PRD",
            instance_number="00",
            fencing_mechanism="AFA",
            virtual_machine_name="vmname",
            constants=DUMMY_CONSTANTS,
        )

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
            def __init__(self, *args, **kwargs):
                self.params = {
                    "sid": "PRD",
                    "instance_number": "00",
                    "ansible_os_family": "REDHAT",
                    "virtual_machine_name": "vm_name",
                    "fencing_mechanism": "AFA",
                    "os_version": "9.2",
                    "pcmk_constants": DUMMY_CONSTANTS,
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
