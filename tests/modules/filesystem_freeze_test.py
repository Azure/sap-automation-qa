"""
Unit tests for the filesystem_freeze module.
"""

import io
import pytest
from src.modules.filesystem_freeze import FileSystemFreeze


def fake_open_factory(file_content):
    """
    Factory function to create a fake open function that returns a StringIO object with the content.
    """

    def fake_open(*args, **kwargs):
        return io.StringIO("\n".join(file_content))

    return fake_open


@pytest.fixture
def filesystem_freeze():
    """
    Fixture for creating a FileSystemFreeze instance.

    :return: FileSystemFreeze instance
    :rtype: FileSystemFreeze
    """
    return FileSystemFreeze()


class TestFileSystemFreeze:
    """
    Class to test the FileSystemFreeze class.
    """

    def test_file_system_exists(self, monkeypatch, filesystem_freeze):
        """
        Test the run method when the filesystem exists.
        """

        with monkeypatch.context() as m:
            m.setattr(
                "builtins.open", fake_open_factory(["/dev/sda1 /hana/shared ext4 rw,relatime 0 0"])
            )
            m.setattr(filesystem_freeze, "execute_command_subprocess", lambda x: "output")
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
        """

        with monkeypatch.context() as m:
            m.setattr(
                "builtins.open", fake_open_factory(["/dev/sda1 /hana/log ext4 rw,relatime 0 0"])
            )
            filesystem_freeze.run()
            result = filesystem_freeze.get_result()

            assert result["status"] == "FAILED"
            assert result["message"] == "The filesystem mounted on /hana/shared was not found."
            assert result["changed"] is False
