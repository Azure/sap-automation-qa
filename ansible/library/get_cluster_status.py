"""Python script to get and validate the status of a cluster.

This script uses the `crm_mon` command-line tool to retrieve the status of a cluster and performs various validations on the cluster status.

Methods:
- check_node: Checks the attributes of a node and returns the corresponding action based on the attribute value.
- run_module: Main function that runs the Ansible module and performs the cluster status checks.
- main: Entry point of the script.

"""

import subprocess
import concurrent.futures
from ansible.module_utils.basic import AnsibleModule
import xml.etree.ElementTree as ET
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
    """Checks the attributes of a node and returns the corresponding action based on the attribute value.

    Args:
        node (xml.etree.ElementTree.Element): The XML element representing a node.

    Returns:
        dict: A dictionary containing the action to be taken based on the attribute value.

    """
    for attribute in node:
        action = attribute_actions.get(
            (attribute.attrib["name"], attribute.attrib["value"])
        )
        if action:
            return action(node)
    return {}


def run_module():
    """Main function that runs the Ansible module and performs the cluster status checks.

    This function retrieves the operation step from the module arguments and performs the following checks:
    - Checks the status of the cluster using the `crm_mon` command.
    - Validates the cluster status and checks if pacemakerd is running.
    - Checks if the minimum required number of nodes are configured in the cluster.
    - Checks if all nodes in the cluster are online.
    - Checks the attributes of each node in the cluster.

    """
    module_args = dict(
        operation_step=dict(type="str", required=True),
    )

    result = {
        "changed": False,
        "status": None,
        "cluster_status": None,
        "primary_node": "",
        "secondary_node": "",
        "count": 0,
        "start": datetime.now(),
        "end": datetime.now(),
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    try:
        count = 0
        while result["primary_node"] is "" and count < 5:
            cluster_status = subprocess.check_output(["crm_mon", "--output-as=xml"])
            count += 1
            result["count"] = count
            result["cluster_status"] = cluster_status.decode("utf-8").strip()
            cluster_status_xml = ET.fromstring(cluster_status)
            if cluster_status_xml.find("pacemakerd") is None:
                pacemakerd_state = (
                    cluster_status_xml.find("summary")
                    .find("stack")
                    .attrib.get("pacemakerd-state")
                )
            else:
                pacemakerd_state = cluster_status_xml.find("pacemakerd").attrib.get(
                    "state"
                )

            if pacemakerd_state != "running":
                return {"error": "pacemakerd is not running"}
            else:
                result["status"] = "running"

            if (
                int(
                    cluster_status_xml.find("summary")
                    .find("nodes_configured")
                    .attrib["number"]
                )
                < 2
            ):
                return {"error": "Minimum 2 nodes are required in the cluster"}

            nodes = cluster_status_xml.find("nodes")
            for node in nodes:
                if node.attrib["online"] != "true":
                    return {
                        "error": "Node {} is not online".format(node.attrib["name"])
                    }

            node_attributes = cluster_status_xml.find("node_attributes")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(check_node, node) for node in node_attributes
                ]
                for future in concurrent.futures.as_completed(futures):
                    result.update(future.result())

        if result["primary_node"] == "" or result["secondary_node"] == "":
            module.fail_json(
                msg="Pacemaker cluster is not stable and does not have primary node or secondary node",
                **result
            )
    except Exception as e:
        module.fail_json(msg=str(e), **result)
    result["end"] = datetime.now()
    module.exit_json(**result)


def main():
    """Entry point of the script."""
    run_module()


if __name__ == "__main__":
    main()
