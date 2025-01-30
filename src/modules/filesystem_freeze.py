# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for formatting the packages list
"""
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus


class FileSystemFreeze(SapAutomationQA):
    """
    Class to run the test case when the filesystem is frozen.
    """

    def __init__(
        self,
    ):
        super().__init__()

    def _find_filesystem(self) -> str:
        """
        Find the filesystem mounted on /hana/shared.

        :return: The filesystem mounted on /hana/shared.
        """
        try:
            with open("/proc/mounts", "r", encoding="utf-8") as mounts_file:
                for line in mounts_file:
                    parts = line.split()
                    if len(parts) > 1 and parts[1] == "/hana/shared":
                        return parts[0]
        except FileNotFoundError as e:
            self.handle_error(e)
        return None

    def run(self) -> Dict[str, Any]:
        """
        Run the test case when the filesystem is frozen.

        :return: A dictionary containing the result of the test case.
        """
        file_system = self._find_filesystem()

        if file_system:
            read_only_output = self.execute_command_subprocess(
                ["mount", "-o", "ro", file_system, "/hana/shared"]
            )
            self.result.update(
                {
                    "changed": True,
                    "message": "The file system (/hana/shared) was successfully mounted as read-only.",
                    "status": TestStatus.SUCCESS.value,
                    "details": read_only_output,
                }
            )
        else:
            self.result.update(
                {
                    "message": "The filesystem mounted on /hana/shared was not found.",
                    "status": TestStatus.ERROR.value,
                }
            )

        return self.result


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        nfs_provider=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    if module.params["nfs_provider"] != "ANF":
        module.exit_json(changed=False, message="The NFS provider is not ANF. Skipping")
    formatter = FileSystemFreeze()
    result = formatter.run()

    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
