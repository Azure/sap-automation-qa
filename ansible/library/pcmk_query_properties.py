#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import xml.etree.ElementTree as ET
import subprocess


def run_module():
    """
    This function is the entry point for the Ansible module.
    It takes in two parameters: 'path' and 'resource_type'.
    'path' specifies the path to the executable that will be used to query properties.
    'resource_type' specifies the type of resource to query properties for.
    The function executes the specified path with the '--query' argument,
    parses the output XML, and extracts the IDs of the resources of the specified type.
    The function returns a dictionary with the 'changed' flag set to False and
    a list of resource IDs in the 'resources' field.
    If an exception occurs during the execution, the function fails with an error message.
    """

    module_args = dict(
        path=dict(type="str", required=True),
        resource_type=dict(type="str", required=True),
    )

    result = dict(changed=False, resources=[])

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    path = module.params["path"]
    resource_type = module.params["resource_type"]

    try:
        output = subprocess.check_output([path, "--query"])
        root = ET.fromstring(output)
        resources = root.findall(".//primitive[@class='{}']".format(resource_type))
        for resource in resources:
            result["resources"].append(resource.attrib["id"])
    except Exception as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
