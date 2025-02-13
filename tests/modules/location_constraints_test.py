# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the location_constraints module converted to a class-based approach.
"""

import xml.etree.ElementTree as ET
import pytest
from src.modules.location_constraints import LocationConstraintsManager, main

LC_STR = """<constraints>
    <rsc_location id="location-rsc_SAPHana_HDB_HA1" rsc="rsc_SAPHana_HDB_HA1" node="node1" score="INFINITY"/>
    <rsc_location id="location-rsc_SAPHana_HDB_HA1" rsc="rsc_SAPHana_HDB_HA1" node="node2" score="-INFINITY"/>
</constraints>
"""


@pytest.fixture
def location_constraints_string():
    """
    Fixture for providing a sample location constraints XML.

    :return: A sample location constraints XML.
    :rtype: str
    """
    return LC_STR


@pytest.fixture
def location_constraints_xml():
    """
    Fixture for providing a sample location constraints XML.

    :return: A sample location constraints XML.
    :rtype: list[xml.etree.ElementTree.Element]
    """
    return ET.fromstring(LC_STR).findall(".//rsc_location")


@pytest.fixture
def location_constraints_manager():
    """
    Fixture for creating a LocationConstraintsManager instance.

    :return: LocationConstraintsManager instance
    :rtype: LocationConstraintsManager
    """
    return LocationConstraintsManager(ansible_os_family="SUSE")


class TestLocationConstraints:
    """
    Test cases for the LocationConstraintsManager class.
    """

    def test_location_constraints_exists_success(
        self,
        mocker,
        location_constraints_manager,
        location_constraints_string,
        location_constraints_xml,
    ):
        """
        Test the location_constraints_exists method for finding constraints successfully.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param location_constraints_manager: LocationConstraintsManager instance.
        :type location_constraints_manager: LocationConstraintsManager
        :param location_constraints_string: _sample location constraints XML.
        :type location_constraints_string: str
        :param location_constraints_xml: _sample location constraints XML.
        :type location_constraints_xml: list[xml.etree.ElementTree.Element]
        """
        mock_run_command = mocker.patch.object(
            location_constraints_manager, "execute_command_subprocess"
        )
        mock_run_command.return_value = location_constraints_string
        loc_constraints = location_constraints_manager.location_constraints_exists()

        assert loc_constraints[0].attrib["id"] == location_constraints_xml[0].attrib["id"]

    def test_location_constraints_exists_failure(self, mocker, location_constraints_manager):
        """
        Test the location_constraints_exists method for not finding constraints.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param location_constraints_manager: LocationConstraintsManager instance.
        :type location_constraints_manager: LocationConstraintsManager
        """
        mock_run_command = mocker.patch.object(
            location_constraints_manager, "execute_command_subprocess"
        )
        mock_run_command.return_value = None
        loc_constraints = location_constraints_manager.location_constraints_exists()

        assert loc_constraints == []

    def test_remove_location_constraints_success(
        self, mocker, location_constraints_manager, location_constraints_xml
    ):
        """
        Test the remove_location_constraints method for successfully removing constraints.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param location_constraints_manager: LocationConstraintsManager instance.
        :type location_constraints_manager: LocationConstraintsManager
        :param location_constraints_xml: _sample location constraints XML.
        :type location_constraints_xml: list[xml.etree.ElementTree.Element]
        """
        mock_run_command = mocker.patch.object(
            location_constraints_manager, "execute_command_subprocess"
        )
        mock_run_command.return_value = "Deleted: loc_azure"
        location_constraints_manager.remove_location_constraints(location_constraints_xml)

        assert location_constraints_manager.result["location_constraint_removed"] is False

    def test_main_module(self, monkeypatch):
        """
        Test the main function of the module.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class for Ansible
            """

            def __init__(self, argument_spec, supports_check_mode):
                self.params = {"action": "remove", "ansible_os_family": "SUSE"}
                self.check_mode = False

            def exit_json(self, **kwargs):
                """
                Mock exit_json method.
                """
                mock_result.update(kwargs)

        with monkeypatch.context() as m:
            m.setattr("src.modules.location_constraints.AnsibleModule", MockAnsibleModule)
            main()
            assert mock_result["status"] == "INFO"
