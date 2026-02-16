# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the log_parser module.
"""

import json
import pytest
from src.modules.log_parser import LogParser, PCMK_KEYWORDS, SYS_KEYWORDS, main
from src.module_utils.enums import OperatingSystemFamily


class TestLogParser:
    """
    Test cases for the LogParser class.
    """

    @pytest.fixture
    def log_parser_redhat(self):
        """
        Fixture for creating a LogParser instance.

        :return: LogParser instance
        :rtype: LogParser
        """
        return LogParser(
            start_time="2025-01-01 00:00:00",
            end_time="2025-01-01 23:59:59",
            log_file="test_log_file.log",
            ansible_os_family=OperatingSystemFamily.REDHAT,
        )

    @pytest.fixture
    def log_parser_suse(self):
        """
        Fixture for creating a LogParser instance.

        :return: LogParser instance
        :rtype: LogParser
        """
        return LogParser(
            start_time="2023-01-01 00:00:00",
            end_time="2023-01-01 23:59:59",
            log_file="test_log_file.log",
            ansible_os_family=OperatingSystemFamily.SUSE,
        )

    def test_parse_logs_success(self, mocker, log_parser_redhat):
        """
        Test the parse_logs method for successful log parsing.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param log_parser_redhat: LogParser instance.
        :type log_parser_redhat: LogParser
        """
        mocker.patch(
            "builtins.open",
            mocker.mock_open(read_data="""Jan 01 23:17:30 nodename LogAction: Action performed
                    Jan 01 23:17:30 nodename SAPHana: SAP HANA action
                    Jan 01 23:17:30 nodename Some other log entry"""),
        )

        log_parser_redhat.parse_logs()
        result = log_parser_redhat.get_result()
        expected_filtered_logs = [
            "Jan 01 23:17:30 nodename LogAction: Action performed",
            "Jan 01 23:17:30 nodename SAPHana: SAP HANA action",
        ]
        filtered_logs = [log.strip() for log in json.loads(result["filtered_logs"])]
        assert filtered_logs == expected_filtered_logs
        assert result["status"] == "PASSED"

    def test_parse_logs_failure(self, mocker, log_parser_suse):
        """
        Test the parse_logs method for failed log parsing.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param log_parser_suse: LogParser instance.
        :type log_parser_suse: LogParser
        """
        mocker.patch(
            "builtins.open",
            side_effect=FileNotFoundError("File not found"),
        )

        log_parser_suse.parse_logs()
        result = log_parser_suse.get_result()
        assert result["filtered_logs"] == []

    def test_main(self, mocker):
        """
        Test the main function of the log_parser module.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        """
        mock_ansible_module = mocker.patch("src.modules.log_parser.AnsibleModule")
        mock_ansible_module.return_value.params = {
            "start_time": "2023-01-01 00:00:00",
            "end_time": "2023-01-01 23:59:59",
            "log_file": "test_log_file.log",
            "ansible_os_family": "SUSE",
        }

        parser = LogParser(
            start_time="2023-01-01 00:00:00",
            end_time="2023-01-01 23:59:59",
            log_file="test_log_file.log",
            ansible_os_family="SUSE",
        )
        parser.parse_logs()

        result = parser.get_result()
        expected_result = {
            "start_time": "2023-01-01 00:00:00",
            "end_time": "2023-01-01 23:59:59",
            "log_file": "test_log_file.log",
            "keywords": list(PCMK_KEYWORDS | SYS_KEYWORDS),
            "filtered_logs": [],
            "error": "",
        }
        assert result["filtered_logs"] == expected_result["filtered_logs"]

    def test_main_redhat(self, monkeypatch):
        """
        Test the main function of the log_parser module for RedHat.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock AnsibleModule for testing.
            """

            def __init__(self, argument_spec, supports_check_mode):
                self.params = {
                    "start_time": "2023-01-01 00:00:00",
                    "end_time": "2023-01-01 23:59:59",
                    "log_file": "test_log_file.log",
                    "ansible_os_family": "REDHAT",
                    "function": "parse_logs",
                }
                self.check_mode = False

            def exit_json(self, **kwargs):
                mock_result.update(kwargs)

        def mock_ansible_facts(module):
            """
            Mock function to return Ansible facts for RedHat.

            :param module: Mock Ansible module instance.
            :type module: MockAnsibleModule
            :return: Dictionary with Ansible facts.
            :rtype: dict
            """
            return {"os_family": "RedHat"}

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.log_parser.AnsibleModule", MockAnsibleModule)
            monkey_patch.setattr("src.modules.log_parser.ansible_facts", mock_ansible_facts)
            main()
            assert mock_result["status"] == "FAILED"

    def test_merge_logs_success(self, log_parser_redhat):
        """
        Test the merge_logs method for successful log merging.

        :param log_parser_redhat: LogParser instance.
        :type log_parser_redhat: LogParser
        """
        log_parser_redhat.logs = [
            '["Jan 01 12:34:56 server1 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_00 started"]',
            '["Jan 01 12:35:00 server2 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_01 started"]',
            '["Jan 01 12:36:00 server3 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_02 started"]',
        ]

        log_parser_redhat.merge_logs()
        result = log_parser_redhat.get_result()

        filtered_logs = [log.strip() for log in json.loads(result["filtered_logs"])]
        assert len(filtered_logs) == len(log_parser_redhat.logs)
        assert result["status"] == "PASSED"

    def test_merge_logs_success_suse(self, log_parser_suse):
        """
        Test the merge_logs method for successful log merging.

        :param log_parser_suse: LogParser instance.
        :type log_parser_suse: LogParser
        """
        log_parser_suse.logs = [
            '["Jan 01 12:34:56 server1 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_00 started"]',
            '["Jan 01 12:35:00 server2 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_01 started"]',
            '["Jan 01 12:36:00 server3 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_02 started"]',
        ]

        log_parser_suse.merge_logs()
        result = log_parser_suse.get_result()

        filtered_logs = [log.strip() for log in json.loads(result["filtered_logs"])]
        assert len(filtered_logs) == len(log_parser_suse.logs)
        assert result["status"] == "PASSED"

    def test_merge_logs_empty_input(self, log_parser_redhat):
        """
        Test the merge_logs method with empty input.

        :param log_parser_redhat: LogParser instance.
        :type log_parser_redhat: LogParser
        """
        log_parser_redhat.logs = []

        log_parser_redhat.merge_logs()
        result = log_parser_redhat.get_result()

        assert json.loads(result["filtered_logs"]) == []
        assert result["status"] == "PASSED"
        assert result["message"] == "No logs provided to merge"

    def test_merge_logs_invalid_json(self, log_parser_redhat):
        """
        Test the merge_logs method with invalid JSON strings.

        :param log_parser_redhat: LogParser instance.
        :type log_parser_redhat: LogParser
        """
        log_parser_redhat.logs = [
            '["Jan 01 12:34:56 server1 pacemaker-controld: Notice: '
            'Resource SAPHana_HDB_00 started"]',
            "Invalid JSON string",
        ]

        log_parser_redhat.merge_logs()
        result = log_parser_redhat.get_result()

        filtered_logs = [log.strip() for log in json.loads(result["filtered_logs"])]
        assert len(filtered_logs) == 2
        assert result["status"] == "PASSED"

    def test_merge_logs_suse_timestamp_parsing(self, log_parser_suse):
        """
        Test the merge_logs method with SUSE timestamp format.
        """
        log_parser_suse.logs = [
            '["2023-01-01T12:34:56.123456789+01:00 server1 pacemaker-controld: Notice: Resource SAPHana_HDB_00 started"]',
            '["2023-01-01T12:35:00.987654321+01:00 server2 pacemaker-controld: Notice: Resource SAPHana_HDB_01 started"]',
        ]
        log_parser_suse.merge_logs()
        result = log_parser_suse.get_result()
        filtered_logs = json.loads(result["filtered_logs"])
        assert len(filtered_logs) == 2
        assert result["status"] == "PASSED"

    def test_merge_logs_unknown_os_family(self, monkeypatch):
        """
        Test the merge_logs method with unknown OS family.
        """

        def mock_execute_command(*args, **kwargs):
            return ""

        monkeypatch.setattr(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess",
            mock_execute_command,
        )
        log_parser_unknown = LogParser(
            start_time="2023-01-01 00:00:00",
            end_time="2023-01-01 23:59:59",
            log_file="test_log_file.log",
            ansible_os_family=OperatingSystemFamily.DEBIAN,
        )

        log_parser_unknown.logs = [
            '["Jan 01 12:34:56 server1 pacemaker-controld: Notice: Resource SAPHana_HDB_00 started"]',
        ]

        log_parser_unknown.merge_logs()
        result = log_parser_unknown.get_result()

        filtered_logs = json.loads(result["filtered_logs"])
        assert len(filtered_logs) == 1
        assert result["status"] == "PASSED"

    def test_parse_logs_suse_timestamp_format(self, mocker, log_parser_suse):
        """
        Test the parse_logs method with SUSE timestamp format.
        """
        mocker.patch(
            "builtins.open",
            mocker.mock_open(
                read_data="""2023-01-01T12:34:56.123456789+01:00 nodename SAPHana: SAP HANA action
2023-01-01T12:35:00.987654321+01:00 nodename pacemaker-controld: Pacemaker action"""
            ),
        )

        log_parser_suse.parse_logs()
        result = log_parser_suse.get_result()

        filtered_logs = json.loads(result["filtered_logs"])
        assert len(filtered_logs) == 2
        assert result["status"] == "PASSED"

    def test_run_module_merge_logs_function(self, monkeypatch):
        """
        Test the run_module function with merge_logs function parameter.
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock AnsibleModule for testing merge_logs function.
            """

            def __init__(self, argument_spec, supports_check_mode):
                self.params = {
                    "start_time": "2023-01-01 00:00:00",
                    "end_time": "2023-01-01 23:59:59",
                    "log_file": "test_log_file.log",
                    "function": "merge_logs",
                    "logs": ['["Jan 01 12:34:56 server1 test log"]'],
                }
                self.check_mode = False

            def exit_json(self, **kwargs):
                mock_result.update(kwargs)

        def mock_ansible_facts(module):
            """
            Mock function to return Ansible facts.
            """
            return {"os_family": "RedHat"}

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.log_parser.AnsibleModule", MockAnsibleModule)
            monkey_patch.setattr("src.modules.log_parser.ansible_facts", mock_ansible_facts)
            from src.modules.log_parser import run_module

            run_module()
            assert mock_result["status"] == "PASSED"
