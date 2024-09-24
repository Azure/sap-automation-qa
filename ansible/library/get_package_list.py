"""Custom ansible module for formatting the packages list"""

from ansible.module_utils.basic import AnsibleModule

PACKAGE_LIST = [
    {"name": "Corosync Lib", "key": "corosynclib"},
    {"name": "Corosync", "key": "corosync"},
    {"name": "Fence Agents Common", "key": "fence-agents-common"},
    {"name": "Fencing Agent", "key": "fence-agents-azure-arm"},
    {"name": "Pacemaker CLI", "key": "pacemaker-cli"},
    {"name": "Pacemaker Libs", "key": "pacemaker-libs"},
    {"name": "Pacemaker Schemas", "key": "pacemaker-schemas"},
    {"name": "Pacemaker", "key": "pacemaker"},
    {"name": "Resource Agent", "key": "resource-agents"},
    {"name": "SAP Cluster Connector", "key": "sap-cluster-connector"},
    {"name": "SAPHanaSR", "key": "SAPHanaSR"},
    {"name": "Socat", "key": "socat"},
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

    result["packages_list"] = [
        {
            package["name"]: {
                "version": package_list[package["key"]][0].get("version"),
                "release": package_list[package["key"]][0].get("release"),
                "architecture": package_list[package["key"]][0].get("arch"),
            }
        }
        for package in PACKAGE_LIST
        if package["key"] in package_list
    ]

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
