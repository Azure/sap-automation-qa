"""
Unit tests for the log_parser module.
"""

import json
import pytest
from src.library.log_parser import LogParser
from datetime import datetime


PCMK_KEYWORDS = {
    "LogAction",
    "LogNodeActions",
    "pacemaker-fenced",
}
SYS_KEYWORDS = {
    "SAPHana",
    "SAPHanaController",
}


@pytest.fixture
def log_parser():
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


def test_parse_logs_success(mocker, log_parser):
    """
    Test the parse_logs method for successful log parsing.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param log_parser: The LogParser instance
    :type log_parser: LogParser
    """
    mock_open = mocker.patch(
        "builtins.open",
        mocker.mock_open(
            read_data="""
2023-01-01 12:00:00.000000 LogAction: Action performed
2023-01-01 13:00:00.000000 SAPHana: SAP HANA action
2023-01-01 14:00:00.000000 Some other log entry
"""
        ),
    )

    log_parser.parse_logs()
    result = log_parser.get_result()
    expected_filtered_logs = [
        "2023-01-01 12:00:00.000000 LogAction: Action performed",
        "2023-01-01 13:00:00.000000 SAPHana: SAP HANA action",
    ]
    filtered_logs = [log.strip() for log in json.loads(result["filtered_logs"])]
    assert filtered_logs == expected_filtered_logs
    assert result["error"] == ""


def test_parse_logs_failure(mocker, log_parser):
    """
    Test the parse_logs method for log parsing failure.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    :param log_parser: The LogParser instance
    :type log_parser: LogParser
    """
    mock_open = mocker.patch(
        "builtins.open",
        side_effect=FileNotFoundError("File not found"),
    )

    log_parser.parse_logs()

    result = log_parser.get_result()
    print(f"Result: {result}")
    assert result["filtered_logs"] == []
    assert result["error"] == "File not found"


def test_main(mocker):
    """
    Test the main function of the log_parser module.

    :param mocker: The mocker fixture
    :type mocker: pytest_mock.MockerFixture
    """
    mock_ansible_module = mocker.patch("src.library.log_parser.AnsibleModule")
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
