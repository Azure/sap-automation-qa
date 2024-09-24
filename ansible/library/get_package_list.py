"""Custom ansible module for formatting the packages list"""

from ansible.module_utils.basic import AnsibleModule

PACKAGE_LIST = [
    {"name": "Pacemaker", "key": "pacemaker"},
    {"name": "Resource Agent", "key": "resource-agents"},
    {"name": "Fencing Agent", "key": "fence-agents"},
    {"name": "SAPHanaSR", "key": "SAPHanaSR"},
]


def run_module():
    """
    Sets up and runs the package list module with the specified arguments.

    :param package_facts_list: The package facts list from the target host.
    """
    module_args = dict(
        package_facts_list=dict(type="dict", required=True),
    )
    result = dict(packages_list=[])
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    package_list = module.params["package_facts_list"]

    for package in PACKAGE_LIST:
        if package["key"] in package_list:
            properties = package_list[package["key"]][0]
            result["packages_list"].append(
                {
                    package["name"]: {
                        "version": properties.get("version"),
                        "release": properties.get("release"),
                        "architecture": properties.get("arch"),
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
