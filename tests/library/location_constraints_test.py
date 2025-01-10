"""
Unit tests for the location_constraints module.
"""

import pytest
import subprocess
import xml.etree.ElementTree as ET
from ansible_src.library.location_constraints import LocationConstraintsManager

LC_STR = """
<constraints>
    <rsc_location id="loc_azure_health" rsc-pattern="!health-.*">
        <rule score-attribute="#health-azure" id="loc_azure_health-rule">
        <expression operation="defined" attribute="#uname" id="loc_azure_health-rule-expression"/>
        </rule>
    </rsc_location>
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
    return ET.fromstring(LC_STR).findall("rsc_location")


@pytest.fixture
def location_constraints_manager():
    """
    Fixture for creating a LocationConstraintsManager instance.

    :return: LocationConstraintsManager instance
    :rtype: LocationConstraintsManager
    """
    return LocationConstraintsManager(ansible_os_family="SUSE")


def test_remove_location_constraint_success(
    mocker, location_constraints_manager, location_constraints_xml
):
    """
    Test the remove_location_constraint method for successful constraint removal.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param location_constraints_manager: The LocationConstraintsManager instance
    :type location_constraints_manager: LocationConstraintsManager
    :param location_constraints_xml: The location constraints XML fixture
    :type location_constraints_xml: str
    """
    mock_run_command = mocker.patch.object(location_constraints_manager, "_run_command")
    mock_run_command.return_value = "Constraint removed"

    location_constraints_manager.remove_location_constraints(location_constraints_xml)
    expected_result = {
        "changed": False,
        "location_constraint_removed": True,
        "stdout": "",
        "msg": "",
    }
    assert location_constraints_manager.result == expected_result


def test_remove_location_constraint_failure(mocker, location_constraints_manager):
    """
    Test the remove_location_constraint method for failed constraint removal.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param location_constraints_manager: The LocationConstraintsManager instance
    :type location_constraints_manager: LocationConstraintsManager
    """
    mock_run_command = mocker.patch.object(location_constraints_manager, "_run_command")
    mock_run_command.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["crm", "configure", "delete", "test-constraint"],
        output="",
        stderr="Error",
    )

    location_constraints_manager.remove_location_constraint("test-constraint")
    expected_result = {
        "changed": False,
        "location_constraint_removed": False,
        "stdout": "",
        "msg": "Command '['crm', 'configure', 'delete', 'test-constraint']' returned non-zero exit status 1.",
    }
    assert location_constraints_manager.result == expected_result


def test_main(mocker):
    """
    Test the main function of the location_constraints module.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    """
    mock_ansible_module = mocker.patch(
        "ansible_src.library.location_constraints.AnsibleModule"
    )
    mock_ansible_module.return_value.params = {
        "ansible_os_family": "SUSE",
        "constraint_id": "test-constraint",
    }

    manager = LocationConstraintsManager(ansible_os_family="SUSE")
    manager.remove_location_constraints("test-constraint")
    expected_result = {
        "changed": True,
        "location_constraint_removed": True,
        "stdout": "Constraint removed",
        "msg": "",
    }
    assert manager.result == expected_result
