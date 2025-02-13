"""
Expanded unit tests for the get_package_list module.
"""

import pytest
from src.modules.get_package_list import PackageListFormatter


@pytest.fixture
def package_facts_list():
    """
    Fixture for providing a sample package facts list.
    """
    return {
        "corosynclib": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
        "corosync": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
    }


class TestPackageListFormatter:
    def test_format_packages(self, mocker, package_facts_list):
        """
        Test the format_packages method of the PackageListFormatter class.
        """
        # Patch AnsibleModule to avoid side effects.
        mock_ansible_module = mocker.patch("src.modules.get_package_list.AnsibleModule")
        mock_ansible_module.return_value.params = {"package_facts_list": package_facts_list}

        formatter = PackageListFormatter(package_facts_list)
        result = formatter.format_packages()
        expected_details = [
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
        ]
        # Assert formatted output.
        assert result["details"] == expected_details
        assert result["status"] == "PASSED"

    def test_format_packages_no_packages(self, monkeypatch):
        """
        Test format_packages when package_facts_list does not contain any of the expected packages.
        """
        empty_facts = {}
        formatter = PackageListFormatter(empty_facts)
        result = formatter.format_packages()
        # Expect details list to be empty, while other result keys remain unchanged.
        assert result.get("details") == []
        # Assuming default values are set in the parent, for instance:
        assert result["status"] == "PASSED"
        assert result.get("changed") is False
        assert result.get("message") == ""
