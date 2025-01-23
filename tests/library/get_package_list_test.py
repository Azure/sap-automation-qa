"""
Unit tests for the get_package_list module.
"""

import pytest
from src.modules.get_package_list import PackageListFormatter


@pytest.fixture
def package_facts_list():
    """
    Fixture for providing a sample package facts list.

    :return: A sample package facts list.
    :rtype: dict
    """
    return {
        "corosynclib": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
        "corosync": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
    }


def test_main(mocker, package_facts_list):
    """
    Test the main function of the get_package_list module.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param package_facts_list: The sample package facts list fixture.
    :type package_facts_list: dict
    """
    mock_ansible_module = mocker.patch(
        "src.library.get_package_list.AnsibleModule"
    )
    mock_ansible_module.return_value.params = {"package_facts_list": package_facts_list}

    formatter = PackageListFormatter(package_facts_list)
    result = formatter.format_packages()
    expected_result = {
        "changed": False,
        "packages_list": [
            {
                "Corosync Lib": {
                    "version": "2.4.5",
                    "release": "1.el7",
                    "architecture": "x86_64",
                }
            },
            {
                "Corosync": {
                    "version": "2.4.5",
                    "release": "1.el7",
                    "architecture": "x86_64",
                }
            },
        ],
        "msg": "",
    }
    assert result == expected_result
