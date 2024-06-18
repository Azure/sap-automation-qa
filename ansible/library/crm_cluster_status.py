"""Python script to get and validate the status of a cluster.
"""

import subprocess
import concurrent.futures
from ansible.module_utils.basic import AnsibleModule
import xml.etree.ElementTree as ET
import time
from datetime import datetime

attribute_actions = {
    ("hana_hdb_clone_state", "PROMOTED"): lambda node: {
        "primary_node": node.attrib["name"]
    },
    ("hana_hdb_sync_state", "PRIM"): lambda node: {"primary_node": node.attrib["name"]},
    ("hana_hdb_clone_state", "DEMOTED"): lambda node: {
        "secondary_node": node.attrib["name"]
    },
    ("hana_hdb_sync_state", "SOK"): lambda node: {
        "secondary_node": node.attrib["name"]
    },
}


def check_node(node):
    for attribute in node:
        action = attribute_actions.get(
            (attribute.attrib["name"], attribute.attrib["value"])
        )
        if action:
            return action(node)
    return {}


def run_module():
    module_args = dict(
        operation_step=dict(type="str", required=True),
    )

    result = {
        "changed": False,
        "status": None,
        "cluster_status": None,
        "primary_node": None,
        "secondary_node": None,
        "count": 0,
        "start": datetime.now(),
        "end": datetime.now(),
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    try:
        count = 0
        while result["primary_node"] is None and count < 5:
            crm_status = subprocess.check_output(["crm", "status", "xml"])
            count += 1
            result["count"] = count
            result["cluster_status"] = crm_status.decode("utf-8").strip()
            crm_status_xml = ET.fromstring(crm_status)
            if crm_status_xml.find("pacemakerd").attrib["state"] != "running":
                return {"error": "pacemakerd is not running"}
            else:
                result["status"] = "running"

            if (
                int(
                    crm_status_xml.find("summary")
                    .find("nodes_configured")
                    .attrib["number"]
                )
                < 2
            ):
                return {"error": "Minimum 2 nodes are required in the cluster"}

            nodes = crm_status_xml.find("nodes")
            for node in nodes:
                if node.attrib["online"] != "true":
                    return {
                        "error": "Node {} is not online".format(node.attrib["name"])
                    }

            node_attributes = crm_status_xml.find("node_attributes")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(check_node, node) for node in node_attributes
                ]
                for future in concurrent.futures.as_completed(futures):
                    result.update(future.result())

        if not result["primary_node"]:
            module.fail_json(msg="crm status did not respond.", **result)
    except Exception as e:
        module.fail_json(msg=str(e), **result)
    result["end"] = datetime.now()
    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()
