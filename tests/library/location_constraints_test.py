"""
Unit tests for the location_constraints module.
"""

import pytest
import subprocess
import xml.etree.ElementTree as ET
from src.library.location_constraints import LocationConstraintsManager

LC_STR = """
<constraints>
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
    :rtype: str
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


def test_location_constraints_exists_success(
    mocker,
    location_constraints_manager,
    location_constraints_string,
    location_constraints_xml,
):
    """
    Test the location_constraints_exists method for finding constraint success.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param location_constraints_manager: The LocationConstraintsManager instance
    :type location_constraints_manager: LocationConstraintsManager
    :param location_constraints_str: The location constraints string
    :type location_constraints_str: str
    :param location_constraints_xml: The location constraints XML
    :type location_constraints_xml: xml.etree.ElementTree.Element
    """
    mock_run_command = mocker.patch.object(location_constraints_manager, "_run_command")
    mock_run_command.return_value = location_constraints_string
    loc_constraints = location_constraints_manager.location_constraints_exists()

    assert loc_constraints[0].attrib["id"] == location_constraints_xml[0].attrib["id"]


def test_location_constraints_exists_failure(mocker, location_constraints_manager):
    """
    Test the location_constraints_exists method for finding no constraints.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param location_constraints_manager: The LocationConstraintsManager instance
    :type location_constraints_manager: LocationConstraintsManager
    """
    mock_run_command = mocker.patch.object(location_constraints_manager, "_run_command")
    mock_run_command.return_value = None
    loc_constraints = location_constraints_manager.location_constraints_exists()

    assert loc_constraints == []


def test_remove_location_constraints_success(
    mocker, location_constraints_manager, location_constraints_xml
):
    """
    Test the remove_location_constraints method for removing constraints successfully.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param location_constraints_manager: The LocationConstraintsManager instance
    :type location_constraints_manager: LocationConstraintsManager
    :param location_constraints_xml: The location constraints XML
    :type location_constraints_xml: xml.etree.ElementTree.Element
    """
    mock_run_command = mocker.patch.object(location_constraints_manager, "_run_command")
    mock_run_command.return_value = "Deleted: loc_azure"
    location_constraints_manager.remove_location_constraints(location_constraints_xml)

    assert location_constraints_manager.result["location_constraint_removed"] is True
