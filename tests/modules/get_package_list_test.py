# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_package_list module.
"""

import pytest
from src.modules.get_package_list import PackageListFormatter, main


class TestPackageListFormatter:
    """
    Test cases for the PackageListFormatter class.
    """

    @pytest.fixture
    def package_facts_list(self):
        """
        Fixture for creating a package_facts_list.

        :return: package_facts_list
        :rtype: dict
        """
        return {
            "corosynclib": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
            "corosync": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
        }

    def test_format_packages(self, mocker, package_facts_list):
        """
        Test the format_packages method of the PackageListFormatter class.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param package_facts_list: Fixture for creating a package_facts_list.
        :type package_facts_list: dict
        """
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
        assert result["details"] == expected_details
        assert result["status"] == "PASSED"

    def test_format_packages_no_packages(self, mocker):
        """
        Test the format_packages method with no packages and no rpm fallback.
        """
        mocker.patch.object(
            PackageListFormatter,
            "_collect_packages_via_rpm",
            return_value={},
        )
        empty_facts = {}
        formatter = PackageListFormatter(empty_facts)
        result = formatter.format_packages()
        assert result.get("details") == []
        assert result["status"] == "PASSED"
        assert result.get("changed") is False
        assert result.get("message") == ""

    def test_format_packages_rpm_fallback(self, mocker):
        """
        Test that rpm subprocess fallback is used when package_facts_list is empty.
        """
        rpm_output = "corosync\t2.4.5\t1.el7\tx86_64\n" "pacemaker\t2.1.0\t3.el8\tx86_64\n"
        mocker.patch.object(
            PackageListFormatter,
            "execute_command_subprocess",
            return_value=rpm_output,
        )
        formatter = PackageListFormatter({})
        result = formatter.format_packages()
        assert result["status"] == "PASSED"
        names = [list(d.keys())[0] for d in result["details"]]
        assert "Corosync" in names
        assert "Pacemaker" in names

    def test_main_method(self, monkeypatch):
        """
        Test the main method of the get_package_list module.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class to simulate AnsibleModule behavior.
            """

            def __init__(self, *args, **kwargs):
                self.params = {
                    "package_facts_list": {
                        "corosynclib": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
                        "corosync": [{"version": "2.4.5", "release": "1.el7", "arch": "x86_64"}],
                    }
                }

            def exit_json(self, **kwargs):
                nonlocal mock_result
                mock_result = kwargs

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.get_package_list.AnsibleModule", MockAnsibleModule)
            main()
            assert mock_result["status"] == "PASSED"
            assert len(mock_result["details"]) == 2
