"""
Unit tests for the log_parser module.
"""

import json
import pytest
from src.modules.log_parser import LogParser, PCMK_KEYWORDS, SYS_KEYWORDS


@pytest.fixture
def log_parser_redhat():
    """
    Fixture for creating a LogParser instance.

    :return: LogParser instance
    :rtype: LogParser
    """
    return LogParser(
        start_time="2025-01-01 00:00:00",
        end_time="2025-01-01 23:59:59",
        log_file="test_log_file.log",
        ansible_os_family="REDHAT",
    )


@pytest.fixture
def log_parser_suse():
    """
    Fixture for creating a LogParser instance.

    :return: LogParser instance
    :rtype: LogParser
    """
    return LogParser(
        start_time="2023-01-01 00:00:00",
        end_time="2023-01-01 23:59:59",
        log_file="test_log_file.log",
        ansible_os_family="SUSE",
    )


class TestLogParser:
    def test_parse_logs_success(self, mocker, log_parser_redhat):
        """
        Test the parse_logs method for successful log parsing.
        """
        mocker.patch(
            "builtins.open",
            mocker.mock_open(
                read_data="""Jan 01 23:17:30 nodename LogAction: Action performed
                    Jan 01 23:17:30 nodename SAPHana: SAP HANA action
                    Jan 01 23:17:30 nodename Some other log entry"""
            ),
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
        Test the parse_logs method for log parsing failure.
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
