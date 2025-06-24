# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for log parsing
"""

import json
from datetime import datetime
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.facts.compat import ansible_facts

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.enums import OperatingSystemFamily
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.enums import OperatingSystemFamily

DOCUMENTATION = r"""
---
module: log_parser
short_description: Parses and merges system logs for SAP-related keywords
description:
    - This module parses system log files for specific SAP and cluster-related keywords.
    - Filters log entries within a specified time range.
    - Supports merging multiple log files and sorting them chronologically.
    - Handles different log formats based on the operating system family.
    - Returns filtered or merged log entries containing predefined or custom keywords.
options:
    start_time:
        description:
            - Start time for log filtering in format "YYYY-MM-DD HH:MM:SS".
        type: str
        required: false
    end_time:
        description:
            - End time for log filtering in format "YYYY-MM-DD HH:MM:SS".
        type: str
        required: false
    log_file:
        description:
            - Path to the log file to be parsed.
            - Default is system messages log.
        type: str
        required: false
        default: /var/log/messages
    keywords:
        description:
            - Additional keywords to filter logs by.
            - These are combined with the predefined SAP and Pacemaker keywords.
        type: list
        required: false
        default: []
    function:
        description:
            - Specifies the function to execute: "parse_logs" or "merge_logs".
        type: str
        required: true
        choices: ["parse_logs", "merge_logs"]
    logs:
        description:
            - List of log entries or JSON strings to merge and sort.
            - Used only when the function is set to "merge_logs".
        type: list
        required: false
        default: []
author:
    - Microsoft Corporation
notes:
    - Predefined keyword sets are included for Pacemaker and SAP system logs.
    - Log entries are filtered by both time range and keyword presence.
    - All entries containing backslashes or quotes will have these characters removed.
    - Merging logs requires proper timestamp formats based on the OS family.
requirements:
    - python >= 3.6
"""

EXAMPLES = r"""
- name: Parse SAP HANA cluster logs for the last hour
  log_parser:
    start_time: "{{ (ansible_date_time.iso8601 | to_datetime - '1 hour') | to_datetime('%Y-%m-%d %H:%M:%S') }}"
    end_time: "{{ ansible_date_time.iso8601 | to_datetime('%Y-%m-%d %H:%M:%S') }}"
    log_file: "/var/log/messages"
  register: parse_result

- name: Display filtered log entries
  debug:
    var: parse_result.filtered_logs

- name: Merge and sort multiple log files
  log_parser:
    function: "merge_logs"
    logs:
      - "[\"Jan 01 12:34:56 server1 pacemaker-controld: Notice: Resource SAPHana_HDB_00 started\"]"
      - "[\"Jan 01 12:35:00 server2 pacemaker-controld: Notice: Resource SAPHana_HDB_01 started\"]"
  register: merge_result

- name: Display merged log entries
  debug:
    var: merge_result.filtered_logs
"""

RETURN = r"""
status:
    description: Status of the log parsing or merging operation.
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Error message in case of failure.
    returned: on failure
    type: str
    sample: "Could not open file /var/log/messages: No such file or directory."
start_time:
    description: Start time used for filtering.
    returned: when function is "parse_logs".
    type: str
    sample: "2023-01-01 00:00:00"
end_time:
    description: End time used for filtering.
    returned: when function is "parse_logs".
    type: str
    sample: "2023-01-02 00:00:00"
log_file:
    description: Path to the log file that was parsed.
    returned: when function is "parse_logs".
    type: str
    sample: "/var/log/messages"
keywords:
    description: List of keywords used for filtering.
    returned: when function is "parse_logs".
    type: list
    sample: ["SAPHana", "pacemaker-fenced", "reboot"]
filtered_logs:
    description: JSON string containing filtered or merged log entries.
    returned: always
    type: str
    sample: "[\"Jan 01 12:34:56 server1 pacemaker-controld: Notice: Resource SAPHana_HDB_00 started\"]"
"""


PCMK_KEYWORDS = {
    "LogAction",
    "LogNodeActions",
    "pacemaker-fenced",
    "check_migration_threshold",
    "corosync",
    "Result of",
    "reboot",
    "cannot run anywhere",
    "attrd_peer_update",
    "High CPU load detected",
    "cli-ban",
    "cli-prefer",
    "cib-bootstrap-options-maintenance-mode",
    "-is-managed",
    "-maintenance",
    "-standby",
    "sbd",
    "pacemaker-controld",
    "pacemaker-execd",
    "pacemaker-based",
    "pacemaker-attrd",
}
SYS_KEYWORDS = {
    "SAPHana",
    "SAPHanaController",
    "SAPHanaTopology",
    "SAPInstance",
    "fence_azure_arm",
    "rsc_st_azure",
    "rsc_ip_",
    "rsc_nc_",
    "rsc_Db2_",
    "rsc_HANA_",
    "corosync",
    "Result of",
    "reboot",
}


class LogParser(SapAutomationQA):
    """
    Class to parse logs based on provided parameters.
    """

    def __init__(
        self,
        start_time: str,
        end_time: str,
        log_file: str,
        ansible_os_family: OperatingSystemFamily,
        logs: list = list(),
    ):
        super().__init__()
        self.start_time = start_time
        self.end_time = end_time
        self.log_file = log_file
        self.keywords = list(PCMK_KEYWORDS | SYS_KEYWORDS)
        self.ansible_os_family = ansible_os_family
        self.logs = logs if logs else []
        self.result.update(
            {
                "start_time": start_time,
                "end_time": end_time,
                "log_file": log_file,
                "keywords": self.keywords,
                "filtered_logs": [],
            }
        )

    def merge_logs(self) -> None:
        """
        Merges multiple log files into a single list for processing.
        """
        try:
            all_logs = []
            parsed_logs = []
            if not self.logs:
                self.result.update(
                    {
                        "filtered_logs": json.dumps([]),
                        "status": TestStatus.SUCCESS.value,
                        "message": "No logs provided to merge",
                    }
                )
                return

            for logs in self.logs:
                if isinstance(logs, str):
                    try:
                        parsed = json.loads(logs)
                        parsed_logs.extend(parsed)
                    except json.JSONDecodeError:
                        parsed_logs.append(logs)
                else:
                    parsed_logs.extend(logs)

            for log in parsed_logs:
                try:
                    if self.ansible_os_family == OperatingSystemFamily.REDHAT:
                        timestamp_str = " ".join(log.split()[:3])
                        log_time = datetime.strptime(timestamp_str, "%b %d %H:%M:%S")
                        log_time = log_time.replace(year=datetime.now().year)
                        all_logs.append((log_time, log))

                    elif self.ansible_os_family == OperatingSystemFamily.SUSE:
                        timestamp_str = log.split(".")[0]
                        log_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                        all_logs.append((log_time, log))

                    else:
                        all_logs.append((datetime.min, log))
                except (ValueError, IndexError):
                    all_logs.append((datetime.min, log))

            sorted_logs = [log for _, log in sorted(all_logs, key=lambda x: x[0])]

            self.result.update(
                {
                    "filtered_logs": json.dumps(sorted_logs),
                    "status": TestStatus.SUCCESS.value,
                }
            )
        except Exception as ex:
            self.handle_error(ex)

    def parse_logs(self) -> None:
        """
        Parses the logs based on the provided parameters.
        """
        try:
            start_dt = datetime.strptime(self.start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(self.end_time, "%Y-%m-%d %H:%M:%S")

            with open(self.log_file, "r", encoding="utf-8") as file:
                for line in file:
                    try:
                        if self.ansible_os_family == OperatingSystemFamily.REDHAT:
                            log_time = datetime.strptime(
                                " ".join(line.split()[:3]), "%b %d %H:%M:%S"
                            )
                            log_time = log_time.replace(year=start_dt.year)
                        elif self.ansible_os_family == OperatingSystemFamily.SUSE:
                            log_time = datetime.strptime(line.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                        else:
                            continue

                        if start_dt <= log_time <= end_dt and any(
                            keyword in line for keyword in self.keywords
                        ):
                            self.result["filtered_logs"].append(
                                line.translate(str.maketrans({"\\": "", '"': "", "'": ""}))
                            )
                    except ValueError:
                        continue

            self.result.update(
                {
                    "filtered_logs": json.dumps(self.result["filtered_logs"]),
                    "status": TestStatus.SUCCESS.value,
                }
            )
        except FileNotFoundError as ex:
            self.handle_error(ex)
        except Exception as ex:
            self.handle_error(ex)


def run_module() -> None:
    """
    Entry point of the script.
    Sets up and runs the log parsing module with the specified arguments.
    """
    module_args = dict(
        start_time=dict(type="str", required=False),
        end_time=dict(type="str", required=False),
        log_file=dict(type="str", required=False, default="/var/log/messages"),
        keywords=dict(type="list", required=False, default=[]),
        function=dict(type="str", required=True, choices=["parse_logs", "merge_logs"]),
        logs=dict(type="list", required=False, default=[]),
        filter=dict(type="str", required=False, default="os_family"),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    parser = LogParser(
        start_time=module.params.get("start_time"),
        end_time=module.params.get("end_time"),
        log_file=module.params.get("log_file"),
        ansible_os_family=OperatingSystemFamily(
            str(ansible_facts(module).get("os_family", "SUSE")).upper()
        ),
        logs=module.params.get("logs"),
    )
    if module.params["function"] == "parse_logs":
        parser.parse_logs()
    elif module.params["function"] == "merge_logs":
        parser.merge_logs()

    result = parser.get_result()
    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
