# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for formatting the packages list
"""

import logging
from typing import Dict, Any, Tuple
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.commands import FREEZE_FILESYSTEM
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.commands import FREEZE_FILESYSTEM

DOCUMENTATION = r"""
---
module: filesystem_freeze
short_description: Freezes the filesystem mounted on /hana/shared
description:
    - This module freezes (mounts as read-only) the filesystem mounted on /hana/shared
    - Identifies the device that is mounted on /hana/shared automatically
    - Only proceeds with the operation if NFS provider is Azure NetApp Files (ANF)
options:
    nfs_provider:
        description:
            - The NFS provider type
            - Module only executes if this is set to "ANF"
        type: str
        required: true
author:
    - Microsoft Corporation
notes:
    - This module requires root permissions to execute filesystem commands
    - Uses /proc/mounts to identify the filesystem device
    - Only works with Azure NetApp Files as the NFS provider
"""

EXAMPLES = r"""
- name: Freeze the filesystem on /hana/shared
  filesystem_freeze:
    nfs_provider: "ANF"
  register: freeze_result

- name: Display freeze operation results
  debug:
    msg: "{{ freeze_result.message }}"

- name: Skip freezing for non-ANF providers
  filesystem_freeze:
    nfs_provider: "Other"
  register: freeze_result
"""

RETURN = r"""
changed:
    description: Whether the module made any changes
    returned: always
    type: bool
    sample: true
message:
    description: Status message describing the result
    returned: always
    type: str
    sample: "The file system (/hana/shared) was successfully mounted read-only."
status:
    description: Status code of the operation
    returned: always
    type: str
    sample: "SUCCESS"
details:
    description: Command output from the freeze operation
    returned: on success
    type: str
    sample: "filesystem /dev/mapper/vg_hana-shared successfully frozen"
"""


class FileSystemFreeze(SapAutomationQA):
    """
    Class to run the test case when the filesystem is frozen.
    """

    def __init__(self, database_sid: str) -> None:
        """
        Initialize the FileSystemFreeze class.

        :param database_sid: The database SID.
        :type database_sid: str
        """
        super().__init__()
        self.database_sid = database_sid

    def _find_filesystem(self) -> Tuple[str, str]:
        """
        Find the filesystem mounted on /hana/shared.

        :return: The filesystem mounted on /hana/shared.
        :rtype: Tuple[str, str]
        """
        try:
            with open("/proc/mounts", "r", encoding="utf-8") as mounts_file:
                for line in mounts_file:
                    parts = line.split()
                    if len(parts) > 1 and parts[1] == "/hana/shared":
                        return parts[0], parts[1]
        except FileNotFoundError as ex:
            self.handle_error(ex)
        return None, None

    def run(self) -> Dict[str, Any]:
        """
        Run the test case when the filesystem is frozen.

        :return: A dictionary containing the result of the test case.
        :rtype: Dict[str, Any]
        """
        file_system, mount_point = self._find_filesystem()

        if file_system and mount_point:
            self.log(
                logging.INFO,
                f"Found the filesystem mounted on: {file_system} at {mount_point}",
            )
            read_only_output = self.execute_command_subprocess(
                FREEZE_FILESYSTEM(file_system, mount_point)
            )
            self.log(logging.INFO, read_only_output)
            self.result.update(
                {
                    "changed": True,
                    "message": f"The file system ({mount_point}) was mounted read-only.",
                    "status": TestStatus.SUCCESS.value,
                    "details": read_only_output,
                    "mount_point": mount_point,
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
        database_sid=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    if module.params["nfs_provider"] != "ANF":
        module.exit_json(changed=False, message="The NFS provider is not ANF. Skipping")
    formatter = FileSystemFreeze(database_sid=module.params["database_sid"])
    result = formatter.run()

    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
