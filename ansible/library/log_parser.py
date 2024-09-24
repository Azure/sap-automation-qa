import datetime
from ansible.module_utils.basic import AnsibleModule
import json


def filter_logs(start_time, end_time, keywords, log_file="/var/log/messages"):
    """
    Filters logs from the specified log file based on start time, end time, and keywords.

    :param start_time: Start time in the format 'YYYY-MM-DD HH:MM:SS'
    :param end_time: End time in the format 'YYYY-MM-DD HH:MM:SS'
    :param keywords: List of keywords to filter logs
    :param log_file: Path to the log file
    :return: List of filtered log lines
    """
    start_dt = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    filtered_logs = []

    with open(log_file, "r") as file:
        for line in file:
            try:
                log_time_str = " ".join(line.split()[:3])
                log_time = datetime.datetime.strptime(log_time_str, "%b %d %H:%M:%S")
                log_time = log_time.replace(year=start_dt.year)

                if start_dt <= log_time <= end_dt:
                    if any(keyword in line for keyword in keywords):
                        line.replace("\\n", "").replace("'", "").replace('"', "")
                        filtered_logs.append(line)
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

    start_time = module.params["start_time"]
    end_time = module.params["end_time"]
    pacemaker_keywords = [
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
    ]
    system_keywords = [
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
    ]
    keywords = pacemaker_keywords + system_keywords

    try:
        result["start"] = datetime.datetime.now()
        result["start_time"] = start_time
        result["end_time"] = end_time
        result["keywords"] = keywords
        result["filtered_logs"] = filter_logs(start_time, end_time, keywords)
        result["end"] = datetime.datetime.now()
        module.exit_json(**result)
    except Exception as e:
        result["error"] = str(e)
        module.fail_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
