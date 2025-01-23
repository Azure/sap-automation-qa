# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for formatting the packages list
"""
import subprocess
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule


class FileSystemFreeze:
    """
    Class to run the test case when the filesystem is frozen.
    """

    def __init__(
        self,
    ):
        self.result = {
            "changed": False,
            "msg": "",
        }

    def _run_command(self, filesystem_path: str) -> None:
        """
        Run the command to change the filesystem to read only.
        mount -o ro filesystem_path /hana/shared

        :param filesystem_path: The path of the filesystem to change.
        """
        command = f"mount -o ro {filesystem_path} /hana/shared"
        try:
            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                encoding="utf-8",
            ) as proc:
                return proc.stdout.read()
        except subprocess.CalledProcessError as e:
            return str(e)

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
        except FileNotFoundError:
            self.result["msg"] = "The /proc/mounts file was not found."
        return None

    def run(self) -> Dict[str, Any]:
        """
        Run the test case when the filesystem is frozen.

        :return: A dictionary containing the result of the test case.
        """
        file_system = self._find_filesystem()

        if file_system:
            read_only_output = self._run_command(file_system)
            self.result["changed"] = True
            self.result["msg"] = read_only_output
        else:
            self.result["msg"] = "The filesystem mounted on /hana/shared was not found."

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
        module.exit_json(changed=False, msg="The NFS provider is not ANF. Skipping")
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
