#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import xml.etree.ElementTree as ET
import subprocess

def run_module():
    module_args = dict(
        path=dict(type='str', required=True),
        resource_type=dict(type='str', required=True),
    )

    result = dict(
        changed=False,
        resources=[]
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    path = module.params['path']
    resource_type = module.params['resource_type']

    try:
        output = subprocess.check_output([path, '--query'])
        root = ET.fromstring(output)
        resources = root.findall(".//primitive[@class='{}']".format(resource_type))
        for resource in resources:
            result['resources'].append(resource.attrib['id'])
    except Exception as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()

