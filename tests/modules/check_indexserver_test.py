"""
Unit tests for the check_indexserver module.
"""

import io
from src.modules.check_indexserver import IndexServerCheck
from src.module_utils.sap_automation_qa import TestStatus


def fake_open_factory(file_content):
    """
    Factory function to create a fake open function that returns a StringIO object with the content.
    """

    def fake_open(*args, **kwargs):
        return io.StringIO("\n".join(file_content))

    return fake_open


class TestIndexServerCheck:
    def test_redhat_indexserver_success(self, monkeypatch):
        """
        Simulate a global.ini file with correct redhat configuration.
        """
        file_lines = [
            "[ha_dr_provider_chksrv]",
            "provider=ChkSrv",
            "path=/usr/share/SAPHanaSR/srHook",
            "dummy=dummy",
        ]
        monkeypatch.setattr("builtins.open", fake_open_factory(file_lines))
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
        """
        file_lines = [
            "[ha_dr_provider_suschksrv]",
            "provider=susChkSrv",
            "path=/usr/share/SAPHanaSR",
            "dummy=dummy",
        ]
        monkeypatch.setattr("builtins.open", fake_open_factory(file_lines))
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
        With unsupported os, no file open is needed.
        """
        checker = IndexServerCheck(database_sid="TEST", os_distribution="ubuntu")
        checker.check_indexserver()
        result = checker.get_result()

        assert result["status"] == TestStatus.ERROR.value
        assert "Unsupported OS distribution" in result["message"]
        assert result["indexserver_enabled"] == "no"

    def test_indexserver_not_configured(self, monkeypatch):
        """
        Simulate a global.ini file that does not contain the expected section for redhat.
        """
        file_lines = [
            "[some_other_section]",
            "provider=Wrong",
            "path=WrongPath",
            "dummy=dummy",
        ]
        monkeypatch.setattr("builtins.open", fake_open_factory(file_lines))
        checker = IndexServerCheck(database_sid="TEST", os_distribution="redhat")
        checker.check_indexserver()
        result = checker.get_result()

        assert result["status"] == TestStatus.ERROR.value
        assert result["message"] == "Indexserver is not configured."
        assert result["indexserver_enabled"] == "no"

    def test_exception_during_file_open(self, monkeypatch):
        """
        Patch open to raise an Exception and check the result.
        """

        def fake_open_fail(*args, **kwargs):
            raise Exception("File error")

        monkeypatch.setattr("builtins.open", fake_open_fail)
        checker = IndexServerCheck(database_sid="TEST", os_distribution="redhat")
        checker.check_indexserver()
        result = checker.get_result()

        assert result["status"] == TestStatus.ERROR.value
        assert (
            "Exception occurred while checking indexserver configuration: File error"
            in result["message"]
        )
        assert result["indexserver_enabled"] == "no"
