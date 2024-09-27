from datetime import datetime
from ansible.module_utils.basic import AnsibleModule
import json


def filter_logs(
    start_time, end_time, keywords, ansible_os_family, log_file="/var/log/messages"
):
    """
    Filters logs from the specified log file based on start time, end time, and keywords.

    :param start_time: Start time in the format 'YYYY-MM-DD HH:MM:SS'
    :param end_time: End time in the format 'YYYY-MM-DD HH:MM:SS'
    :param keywords: Set of keywords to filter logs
    :param ansible_os_family: The OS family of the target host
    :param log_file: Path to the log file
    :return: List of filtered log lines
    """
    date_format = (
        "%Y-%m-%dT%H:%M:%S" if ansible_os_family == "SUSE" else "%Y-%m-%d %H:%M:%S"
    )

    start_dt = datetime.strptime(
        datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").strftime(date_format),
        date_format,
    )
    end_dt = datetime.strptime(
        datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S").strftime(date_format),
        date_format,
    )

    filtered_logs = []

    with open(log_file, "r") as file:
        for line in file:
            try:
                if ansible_os_family == "REDHAT":
                    log_time = datetime.strptime(
                        " ".join(line.split()[:3]), "%b %d %H:%M:%S"
                    )
                    log_time = log_time.replace(year=start_dt.year)
                elif ansible_os_family == "SUSE":
                    log_time = datetime.strptime(line.split(".")[0], date_format)
                else:
                    continue

                if start_dt <= log_time <= end_dt and any(
                    keyword in line for keyword in keywords
                ):
                    filtered_logs.append(
                        line.translate(str.maketrans({"\\": "", '"': "", "'": ""}))
                    )
            except ValueError:
                continue

    return json.dumps(filtered_logs)


def run_module():
    """
    Sets up and runs the log parsing module with the specified arguments.

    :param start_time: The start time for log parsing. This is a required parameter.
    :type start_time: str
    :param end_time: The end time for log parsing. This is a required parameter.
    :type end_time: str
    :param log_file: The path to the log file to be parsed. Defaults to "/var/log/messages".
    :type log_file: str, optional
    :param keywords: A list of keywords to filter the log entries. Defaults to empty list.
    :type keywords: list, optional
    """
    module_args = dict(
        start_time=dict(type="str", required=True),
        end_time=dict(type="str", required=True),
        log_file=dict(type="str", required=False, default="/var/log/messages"),
        keywords=dict(type="list", required=False, default=[]),
        ansible_os_family=dict(type="str", required=True),
    )

    result = dict(
        start="",
        end="",
        log_file="",
        start_time="",
        end_time="",
        keywords="",
        filtered_logs="",
        error="",
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    ansible_os_family = module.params["ansible_os_family"]

    start_time = module.params["start_time"]
    end_time = module.params["end_time"]
    pacemaker_keywords = {
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
    system_keywords = {
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
    keywords = pacemaker_keywords | system_keywords

    try:
        result["start"] = datetime.now()
        result["start_time"] = start_time
        result["end_time"] = end_time
        result["keywords"] = list(keywords)
        result["filtered_logs"] = filter_logs(
            start_time, end_time, keywords, ansible_os_family
        )
        result["end"] = datetime.now()
        module.exit_json(**result)
    except Exception as e:
        result["msg"] = str(e)
        module.fail_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
