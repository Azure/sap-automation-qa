"""Custom ansible module for location constraints"""

import subprocess
from ansible.module_utils.basic import AnsibleModule
import xml.etree.ElementTree as ET


def run_command(cmd):
    try:
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        ) as proc:
            return proc.stdout.read()
    except subprocess.CalledProcessError as e:
        raise Exception(str(e))


def remove_location_constraints(location_constraints):
    for location_constraint in location_constraints:
        run_command(["crm", "resource", "clear", location_constraint.attrib["rsc"]])


def location_constraints_exists():
    xml_output = run_command(["cibadmin", "--query", "--scope", "constraints"])
    constraints = ET.fromstring(xml_output).findall(".//rsc_location")
    return constraints if constraints is not None else []


def run_module():
    module_args = dict(
        action=dict(type="str", required=True),
    )
    result = dict(changed=False, location_constraint_removed=False)
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    if module.check_mode:
        module.exit_json(**result)
    try:
        location_constraints = location_constraints_exists()
        if location_constraints and module.params.get("action") == "remove":
            remove_location_constraints(location_constraints)
            result["location_constraint_removed"] = True
            module.exit_json(msg="Location constraints removed", **result)
        else:
            module.exit_json(
                msg="Location constraints do not exist or was removed. Number of location constraints.",
                **result
            )
    except Exception as e:
        module.fail_json(msg=str(e), **result)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
