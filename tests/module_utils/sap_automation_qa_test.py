# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the sap_automation_qa module.
"""

import xml.etree.ElementTree as ET
from src.module_utils.sap_automation_qa import SapAutomationQA
from src.module_utils.enums import TestStatus


class MockLogger:
    """
    Mock logger class.
    """

    def __init__(self, name):
        self.name = name

    def setLevel(self, level):  # noqa: N805
        """
        Mock setLevel method.

        :param level: _logging level
        :type level: int
        """
        pass  # noqa: E501

    def addHandler(self, handler):  # noqa: N805
        """
        Mock addHandler method.

        :param handler: _logging handler
        :type handler: logging.Handler
        """
        pass  # noqa: E501

    def log(self, level, msg):  # noqa: N805
        """
        Mock log method.

        :param level: _logging level
        :type level: int
        :param msg: _logging message
        :type msg: str
        """
        pass  # noqa: E501

    def error(self, msg):  # noqa: N805
        """
        Mock error method.

        :param msg: _logging message
        :type msg: str
        """
        pass  # noqa: E501


class TestSapAutomationQA:
    """
    Test class for the SapAutomationQA class.
    """

    def test_init(self):
        """
        Test the initialization of the SapAutomationQA class.
        """
        sap_qa = SapAutomationQA()
        assert sap_qa.result["message"] == ""
        assert not sap_qa.result["details"]
        assert not sap_qa.result["logs"]
        assert sap_qa.result["changed"] is False

    def test_setup_logger(self, monkeypatch):
        """
        Test the setup_logger method.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def mock_get_logger(name):
            """
            Mock getLogger method.

            :param name: _logging name
            :type name: str
            :return: _mock logger
            :rtype: MockLogger
            """
            return MockLogger(name)

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "src.module_utils.sap_automation_qa.logging.getLogger", mock_get_logger
            )
            sap_qa = SapAutomationQA()
            assert sap_qa.logger.name == "sap-automation-qa"

    def test_add_log(self, monkeypatch):
        """
        Test the add_log method.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def mock_get_logger(name):
            """
            Mock getLogger method.

            :param name: _logging name
            :type name: str
            :return: _mock logger
            :rtype: MockLogger
            """
            return MockLogger(name)

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "src.module_utils.sap_automation_qa.logging.getLogger", mock_get_logger
            )
            sap_qa = SapAutomationQA()
            sap_qa.log(1, "Test log")
            assert sap_qa.result["logs"] == ["Test log"]

    def test_handle_error(self, monkeypatch):
        """
        Test the handle_error method.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def mock_get_logger(name):
            """
            Mock getLogger method.

            :param name: _logging name
            :type name: str
            :return: _mock logger
            :rtype: MockLogger
            """
            return MockLogger(name)

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "src.module_utils.sap_automation_qa.logging.getLogger", mock_get_logger
            )
            sap_qa = SapAutomationQA()
            sap_qa.handle_error(FileNotFoundError("Test error"))
            assert sap_qa.result["status"] == TestStatus.ERROR.value
            assert "Test error" in sap_qa.result["message"]
            assert sap_qa.result["changed"] is False

    def test_execute_command_subprocess(self, monkeypatch):
        """
        Test the execute_command_subprocess method.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def mock_get_logger(name):
            """
            Mock getLogger method.

            :param name: _logging name
            :type name: str
            :return: _mock logger
            :rtype: MockLogger
            """
            return MockLogger(name)

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "src.module_utils.sap_automation_qa.logging.getLogger", mock_get_logger
            )
            sap_qa = SapAutomationQA()
            command = "echo 'Hello World'"
            result = sap_qa.execute_command_subprocess(command)
            assert result == ""

    def test_parse_xml_output(self, monkeypatch):
        """
        Test the parse_xml_output method.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def mock_get_logger(name):
            """
            Mock getLogger method.

            :param name: _logging name
            :type name: str
            :return: _mock logger
            :rtype: MockLogger
            """
            return MockLogger(name)

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "src.module_utils.sap_automation_qa.logging.getLogger", mock_get_logger
            )
            sap_qa = SapAutomationQA()
            xml_output = "<root></root>"
            result = sap_qa.parse_xml_output(xml_output=xml_output)
            assert isinstance(result, ET.Element)

    def test_get_test_status(self, monkeypatch):
        """
        Test the get_test_status method.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """

        def mock_get_logger(name):
            """
            Mock getLogger method.

            :param name: _logging name
            :type name: str
            :return: _mock logger
            :rtype: MockLogger
            """
            return MockLogger(name)

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr(
                "src.module_utils.sap_automation_qa.logging.getLogger", mock_get_logger
            )
            sap_qa = SapAutomationQA()
            result = sap_qa.get_result()
            assert isinstance(result, dict)
