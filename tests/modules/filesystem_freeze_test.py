# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the filesystem_freeze module.
"""

import io
import pytest
from src.modules.filesystem_freeze import FileSystemFreeze, main


def fake_open_factory(file_content):
    """
    Factory function to create a fake open function that returns a StringIO object with the content.

    :param file_content: Content to be returned by the fake open function.
    :type file_content: list
    :return: Fake open function.
    :rtype: function
    """

    def fake_open(*args, **kwargs):
        """
        Fake open function that returns a StringIO object.

        :return: StringIO object with the content.
        :rtype: io.StringIO
        """
        return io.StringIO("\n".join(file_content))

    return fake_open


class TestFileSystemFreeze:
    """
    Class to test the FileSystemFreeze class.
    """

    @pytest.fixture
    def filesystem_freeze(self):
        """
        Fixture for creating a FileSystemFreeze instance.

        :return: FileSystemFreeze instance
        :rtype: FileSystemFreeze
        """
        return FileSystemFreeze()

    def test_file_system_exists(self, monkeypatch, filesystem_freeze):
        """
        Test the run method when the filesystem exists.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        :param filesystem_freeze: FileSystemFreeze instance.
        :type filesystem_freeze: FileSystemFreeze
        """
        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "builtins.open", fake_open_factory(["/dev/sda1 /hana/shared ext4 rw,relatime 0 0"])
            )
            monkey_patch.setattr(
                filesystem_freeze, "execute_command_subprocess", lambda x: "output"
            )
            filesystem_freeze.run()
            result = filesystem_freeze.get_result()

            assert result["status"] == "PASSED"
            assert (
                result["message"]
                == "The file system (/hana/shared) was successfully mounted read-only."
            )
            assert result["changed"] is True

    def test_file_system_not_exists(self, monkeypatch, filesystem_freeze):
        """
        Test the run method when the filesystem does not exist.

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        :param filesystem_freeze: FileSystemFreeze instance.
        :type filesystem_freeze: FileSystemFreeze
        """

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "builtins.open", fake_open_factory(["/dev/sda1 /hana/log ext4 rw,relatime 0 0"])
            )
            filesystem_freeze.run()
            result = filesystem_freeze.get_result()

            assert result["status"] == "FAILED"
            assert result["message"] == "The filesystem mounted on /hana/shared was not found."
            assert result["changed"] is False

    def test_main_method_anf_provider(self, monkeypatch):
        """
        Test the main method when NFS provider is ANF

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class for Ansible
            """

            def __init__(self, *args, **kwargs):
                self.params = {"nfs_provider": "ANF"}

            def exit_json(self, **kwargs):
                """
                Mock exit_json method.
                """
                nonlocal mock_result
                mock_result = kwargs

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.filesystem_freeze.AnsibleModule", MockAnsibleModule)
            monkey_patch.setattr(
                "builtins.open", fake_open_factory(["/dev/sda1 /hana/shared ext4 rw,relatime 0 0"])
            )
            monkey_patch.setattr(
                "src.modules.filesystem_freeze.FileSystemFreeze.execute_command_subprocess",
                lambda self, cmd: "command output",
            )

            main()

            assert mock_result["changed"] is True
            assert mock_result["status"] == "PASSED"
            assert (
                mock_result["message"]
                == "The file system (/hana/shared) was successfully mounted read-only."
            )

    def test_main_method_non_anf_provider(self, monkeypatch):
        """
        Test the main method when NFS provider is not ANF

        :param monkeypatch: Monkeypatch fixture for modifying built-in functions.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            def __init__(self, *args, **kwargs):
                self.params = {"nfs_provider": "non-anf"}

            def exit_json(self, **kwargs):
                nonlocal mock_result
                mock_result = kwargs

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.filesystem_freeze.AnsibleModule", MockAnsibleModule)

            main()

            assert mock_result["changed"] is False
