# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for log parsing
"""

DOCUMENTATION = r"""
---
module: log_parser
short_description: Parses system logs for SAP-related keywords
description:
    - This module parses system log files for specific SAP and cluster-related keywords
    - Filters log entries within a specified time range
    - Supports different log formats based on operating system family
    - Returns filtered log entries containing predefined or custom keywords
options:
    start_time:
        description:
            - Start time for log filtering in format "YYYY-MM-DD HH:MM:SS"
        type: str
        required: true
    end_time:
        description:
            - End time for log filtering in format "YYYY-MM-DD HH:MM:SS"
        type: str
        required: true
    log_file:
        description:
            - Path to the log file to be parsed
            - Default is system messages log
        type: str
        required: false
        default: /var/log/messages
    keywords:
        description:
            - Additional keywords to filter logs by
            - These are combined with the predefined SAP and Pacemaker keywords
        type: list
        required: false
        default: []
    ansible_os_family:
        description:
            - Operating system family (REDHAT, SUSE, etc.)
            - Used to determine the appropriate log timestamp format
        type: str
        required: true
author:
    - Microsoft Corporation
notes:
    - Predefined keyword sets are included for Pacemaker and SAP system logs
    - Log entries are filtered by both time range and keyword presence
    - All entries containing backslashes or quotes will have these characters removed
requirements:
    - python >= 3.6
"""

EXAMPLES = r"""
- name: Parse SAP HANA cluster logs for the last hour
  log_parser:
    start_time: "{{ (ansible_date_time.iso8601 | to_datetime - '1 hour') | to_datetime('%Y-%m-%d %H:%M:%S') }}"
    end_time: "{{ ansible_date_time.iso8601 | to_datetime('%Y-%m-%d %H:%M:%S') }}"
    log_file: "/var/log/messages"
    ansible_os_family: "{{ ansible_os_family|upper }}"
  register: parse_result

- name: Display filtered log entries
  debug:
    var: parse_result.filtered_logs

- name: Parse custom log file with additional keywords
  log_parser:
    start_time: "2023-01-01 00:00:00"
    end_time: "2023-01-02 00:00:00"
    log_file: "/var/log/pacemaker.log"
    keywords:
      - "SAPHana_HDB_00"
      - "error"
      - "failure"
    ansible_os_family: "SUSE"
  register: custom_logs
"""

RETURN = r"""
status:
    description: Status of the log parsing operation
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Error message in case of failure
    returned: on failure
    type: str
    sample: "Could not open file /var/log/messages: No such file or directory"
start_time:
    description: Start time used for filtering
    returned: always
    type: str
    sample: "2023-01-01 00:00:00"
end_time:
    description: End time used for filtering
    returned: always
    type: str
    sample: "2023-01-02 00:00:00"
log_file:
    description: Path to the log file that was parsed
    returned: always
    type: str
    sample: "/var/log/messages"
keywords:
    description: List of keywords used for filtering
    returned: always
    type: list
    sample: ["SAPHana", "pacemaker-fenced", "reboot"]
filtered_logs:
    description: JSON string containing filtered log entries
    returned: always
    type: str
    sample: "[\"Jan 01 12:34:56 server1 pacemaker-controld: Notice: Resource SAPHana_HDB_00 started\"]"
"""

import json
from datetime import datetime
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus

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
        ansible_os_family: str,
    ):
        super().__init__()
        self.start_time = start_time
        self.end_time = end_time
        self.log_file = log_file
        self.keywords = list(PCMK_KEYWORDS | SYS_KEYWORDS)
        self.ansible_os_family = ansible_os_family
        self.result.update(
            {
                "start_time": start_time,
                "end_time": end_time,
                "log_file": log_file,
                "keywords": self.keywords,
                "filtered_logs": [],
            }
        )

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
                        if self.ansible_os_family == "REDHAT":
                            log_time = datetime.strptime(
                                " ".join(line.split()[:3]), "%b %d %H:%M:%S"
                            )
                            log_time = log_time.replace(year=start_dt.year)
                        elif self.ansible_os_family == "SUSE":
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
        start_time=dict(type="str", required=True),
        end_time=dict(type="str", required=True),
        log_file=dict(type="str", required=False, default="/var/log/messages"),
        keywords=dict(type="list", required=False, default=[]),
        ansible_os_family=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    parser = LogParser(
        start_time=module.params["start_time"],
        end_time=module.params["end_time"],
        log_file=module.params["log_file"],
        ansible_os_family=module.params["ansible_os_family"],
    )
    parser.parse_logs()

    result = parser.get_result()
    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
