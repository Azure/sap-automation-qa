"""Custom ansible module for formatting the packages list"""

import subprocess
from ansible.module_utils.basic import AnsibleModule

PACKAGE_LIST = [
    {"name": "Pacemaker", "key": "pacemaker"},
    {"name": "Resource Agent", "key": "resource-agents"},
    {"name": "Fencing Agent", "key": "fence-agents"},
    {"name": "SAPHanaSR", "key": "SAPHanaSR"},
]


def run_module():
    """
    Runs the ansible module for location constraints.
    """
    module_args = dict(
        package_facts_list=dict(type="dict", required=True),
    )
    result = dict(packages_list=[])
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    package_list = module.params["package_facts_list"]

    for package in PACKAGE_LIST:
        if package["key"] in package_list:
            result["packages_list"].append(
                {
                    package["name"]: {
                        "version": package_list[package["key"]].get("version"),
                        "release": package_list[package["key"]].get("release"),
                        "architecture": package_list[package["key"]].get("arch"),
                    }
                }
            )
        else:
            result["packages_list"].append({package["name"]: "Not Found"})

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
