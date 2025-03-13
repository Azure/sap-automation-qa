# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the check_indexserver module.
"""

import io
from src.modules.check_indexserver import IndexServerCheck, main
from src.module_utils.sap_automation_qa import TestStatus


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


class TestIndexServerCheck:
    """
    Class to test the IndexServerCheck class and main function.
    """

    def test_redhat_indexserver_success(self, monkeypatch):
        """
        Simulate a global.ini file with correct redhat configuration.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        file_lines = [
            "[ha_dr_provider_chksrv]",
            "provider=ChkSrv",
            "path=/usr/share/SAPHanaSR/srHook",
            "dummy=dummy",
        ]
        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("builtins.open", fake_open_factory(file_lines))
            checker = IndexServerCheck(database_sid="TEST", os_distribution="redhat")
            checker.check_indexserver()
            result = checker.get_result()

            assert result["status"] == TestStatus.SUCCESS.value
            assert result["message"] == "Indexserver is configured."
            assert result["indexserver_enabled"] == "yes"
            assert "provider" in result["details"]
            assert "path" in result["details"]

    def test_suse_indexserver_success(self, monkeypatch):
        """
        Simulate a global.ini file with correct suse configuration.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        file_lines = [
            "[ha_dr_provider_suschksrv]",
            "provider=susChkSrv",
            "path=/usr/share/SAPHanaSR",
            "dummy=dummy",
        ]
        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("builtins.open", fake_open_factory(file_lines))
            checker = IndexServerCheck(database_sid="TEST", os_distribution="suse")
            checker.check_indexserver()
            result = checker.get_result()

            assert result["status"] == TestStatus.SUCCESS.value
            assert result["message"] == "Indexserver is configured."
            assert result["indexserver_enabled"] == "yes"
            assert "provider" in result["details"]
            assert "path" in result["details"]

    def test_unsupported_os(self):
        """
        Test unsupported OS distribution.
        """
        with io.StringIO() as _:
            checker = IndexServerCheck(database_sid="TEST", os_distribution="windows")
            checker.check_indexserver()
            result = checker.get_result()

            assert result["status"] == TestStatus.ERROR.value
            assert "Unsupported OS distribution" in result["message"]
            assert result["indexserver_enabled"] == "no"

    def test_indexserver_not_configured(self, monkeypatch):
        """
        Simulate a global.ini file with incorrect configuration.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        file_lines = [
            "[some_other_section]",
            "provider=Wrong",
            "path=WrongPath",
            "dummy=dummy",
        ]
        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("builtins.open", fake_open_factory(file_lines))
            index_server_check = IndexServerCheck(database_sid="HDB", os_distribution="redhat")
            index_server_check.check_indexserver()
            result = index_server_check.get_result()

            assert result["status"] == TestStatus.ERROR.value
            assert result["message"] == "Indexserver is not configured."
            assert result["indexserver_enabled"] == "no"

    def test_file_missing(self, monkeypatch):
        """
        Simulate a missing global.ini file.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def fake_open(*args, **kwargs):
            """
            Fake open function that raises FileNotFoundError.

            :raises FileNotFoundError: Simulate file not found error.
            """
            raise FileNotFoundError("File not found")

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("builtins.open", fake_open)
            index_server_check = IndexServerCheck(database_sid="HDB", os_distribution="redhat")
            index_server_check.check_indexserver()
            result = index_server_check.get_result()

            assert result["status"] == TestStatus.ERROR.value
            assert "Exception occurred" in result["message"]
            assert result["indexserver_enabled"] == "no"

    def test_main_method(self, monkeypatch):
        """
        Test the main method of the check_indexserver module.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}
        file_lines = [
            "[some_other_section]",
            "provider=Wrong",
            "path=WrongPath",
            "dummy=dummy",
        ]

        class MockAnsibleModule:
            """
            Mock AnsibleModule for testing.
            """

            def __init__(self, *args, **kwargs):
                self.params = {
                    "database_sid": "TEST",
                    "ansible_os_family": "redhat",
                }

            def exit_json(self, **kwargs):
                """
                Mock exit_json method.
                """
                nonlocal mock_result
                mock_result = kwargs

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.check_indexserver.AnsibleModule", MockAnsibleModule)
            monkey_patch.setattr("builtins.open", fake_open_factory(file_lines))
            main()
            assert mock_result["status"] == TestStatus.ERROR.value
