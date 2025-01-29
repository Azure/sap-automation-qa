# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
This module is used to check if SAP HANA indexserver is configured.
"""

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus


class IndexServerCheck(SapAutomationQA):
    """
    This class is used to check if SAP HANA indexserver is configured.

    :param SapAutomationQA: Base class for SAP Automation QA.
    :type SapAutomationQA: class
    """

    def __init__(
        self,
        database_sid: str,
    ):
        super().__init__()
        self.database_sid = database_sid

    def check_indexserver(self) -> None:
        """
        Checks if the indexserver is configured.
        """
        # read global.ini file to check if indexserver is configured
        # If any of the three lines are not there,
        # [ha_dr_provider_chksrv]
        # provider = ChkSrv
        # path = /usr/share/SAPHanaSR/srHook
        # then consider chksrv is not set

        expected_properties = {
            "provider": "ChkSrv",
            "path": "/usr/share/SAPHanaSR/srHook",
        }

        global_ini_path = (
            f"/usr/sap/{self.database_sid}/SYS/global/hdb/custom/config/global.ini"
        )
        with open(global_ini_path, "r", encoding="utf-8") as file:
            global_ini = [line.strip() for line in file.readlines()]

        try:
            section_start = global_ini.index("[ha_dr_provider_chksrv]")
            properties_slice = global_ini[section_start + 1 : section_start + 4]

            extracted_properties = {
                prop.split("=")[0].strip(): prop.split("=")[1].strip()
                for prop in properties_slice
            }

            # check if expected properties are present in the extracted properties

            if not all(
                [
                    extracted_properties.get(key) == value
                    for key, value in expected_properties.items()
                ]
            ):
                self.result.update(
                    {
                        "status": TestStatus.SUCCESS.value,
                        "message": "Indexserver is not configured.",
                        "details": extracted_properties,
                        "indexserver_enabled": "no",
                    }
                )

            self.result.update(
                {
                    "status": TestStatus.SUCCESS.value,
                    "message": "Indexserver is configured.",
                    "details": extracted_properties,
                    "indexserver_enabled": "yes",
                }
            )
        except Exception as e:
            self.result.update(
                {
                    "status": TestStatus.ERROR.value,
                    "message": f"Exception occurred while checking indexserver configuration. {e}",
                    "details": {},
                    "indexserver_enabled": "no",
                }
            )


def main():
    """
    Main function to check if SAP HANA indexserver is configured.
    """
    module = AnsibleModule(
        argument_spec=dict(
            database_sid=dict(type="str", required=True),
        )
    )

    database_sid = module.params["database_sid"]

    index_server_check = IndexServerCheck(database_sid)
    index_server_check.check_indexserver()

    module.exit_json(**index_server_check.get_result())


if __name__ == "__main__":
    main()
