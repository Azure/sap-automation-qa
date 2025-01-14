"""Custom ansible module for log parsing"""

import json
from datetime import datetime
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule


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


class LogParser:
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
        self.start_time = start_time
        self.end_time = end_time
        self.log_file = log_file
        self.keywords = list(PCMK_KEYWORDS | SYS_KEYWORDS)
        self.ansible_os_family = ansible_os_family
        self.result = {
            "start_time": start_time,
            "end_time": end_time,
            "log_file": log_file,
            "keywords": self.keywords,
            "filtered_logs": [],
            "error": "",
        }

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
        except FileNotFoundError as ex:
            self.result["error"] = str(ex)
        except Exception as e:
            self.result["error"] = str(e)

    def get_result(self) -> Dict[str, Any]:
        """
        Returns the result dictionary.

        :return: The result dictionary containing the filtered logs and other details.
        :rtype: dict
        """
        return self.result


def main() -> None:
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
    if result["error"]:
        module.fail_json(msg=result["error"], **result)
    else:
        module.exit_json(**result)


if __name__ == "__main__":
    main()
