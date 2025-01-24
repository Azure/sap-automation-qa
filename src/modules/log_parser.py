# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for log parsing
"""
from enum import Enum
import json
from datetime import datetime
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.cluster_constants import PCMK_KEYWORDS, SYS_KEYWORDS
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.cluster_constants import PCMK_KEYWORDS, SYS_KEYWORDS


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
            date_format = "%Y-%m-%d %H:%M:%S"

            with open(self.log_file, "r", encoding="utf-8") as file:
                for line in file:
                    try:
                        if self.ansible_os_family == "REDHAT":
                            log_time = datetime.strptime(
                                " ".join(line.split()[:3]), "%b %d %H:%M:%S"
                            )
                            log_time = log_time.replace(year=start_dt.year)
                        elif self.ansible_os_family == "SUSE":
                            log_time = datetime.strptime(
                                line.split(".")[0], date_format
                            )
                        else:
                            continue

                        if start_dt <= log_time <= end_dt and any(
                            keyword in line for keyword in self.keywords
                        ):
                            self.result["filtered_logs"].append(
                                line.translate(
                                    str.maketrans({"\\": "", '"': "", "'": ""})
                                )
                            )
                    except ValueError:
                        continue

            self.result["filtered_logs"] = json.dumps(self.result["filtered_logs"])
            self.result["status"] = TestStatus.SUCCESS
        except FileNotFoundError as ex:
            self.handle_error(ex)
        except Exception as e:
            self.handle_error(e)

    def get_result(self) -> Dict[str, Any]:
        """
        Returns the result dictionary.

        :return: The result dictionary containing the filtered logs and other details.
        :rtype: dict
        """
        return self.result


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
    if result["status"] == "FAILED":
        module.fail_json(msg=result["message"], **result)
    else:
        module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
