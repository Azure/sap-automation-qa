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


def check_node(node, database_sid):
    """Checks the attributes of a node and returns the corresponding action based on the attribute value.

    Args:
        node (xml.etree.ElementTree.Element): The XML element representing a node.

    Returns:
        dict: A dictionary containing the action to be taken based on the attribute value.

    """
    node_states = {}

    attribute_actions = {
        f"hana_{database_sid}_clone_state": lambda node, value: node_states.update(
            {"clone_state": value}
        ),
        f"hana_{database_sid}_sync_state": lambda node, value: node_states.update(
            {"sync_state": value}
        ),
    }

    for attribute in node:
        action = attribute_actions.get(attribute.attrib["name"])
        if action:
            action(node, attribute.attrib["value"])

    if (
        node_states.get("clone_state") == "PROMOTED"
        and node_states.get("sync_state") == "PRIM"
    ):
        return {"primary_node": node.attrib["name"]}
    elif (
        node_states.get("clone_state") == "DEMOTED"
        and node_states.get("sync_state") == "SOK"
    ):
        return {"secondary_node": node.attrib["name"]}

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
        database_sid=dict(type="str", required=True),
    )

    result = {
        "changed": False,
        "status": None,
        "cluster_status": None,
        "primary_node": "",
        "secondary_node": "",
        "start": datetime.now(),
        "end": datetime.now(),
        "msg": "",
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    database_sid = module.params["database_sid"]

    try:
        while result["primary_node"] is "":
            cluster_status = subprocess.check_output(["crm_mon", "--output-as=xml"])
            result["cluster_status"] = cluster_status.decode("utf-8").strip()
            cluster_status_xml = ET.fromstring(cluster_status)
            pacemaker_status = subprocess.check_output(
                ["systemctl", "is-active", "pacemaker"]
            )
            if pacemaker_status.decode("utf-8").strip() == "active":
                result["status"] = "running"
            else:
                result["msg"] = "pacemaker service is not running"

            if (
                int(
                    cluster_status_xml.find("summary")
                    .find("nodes_configured")
                    .attrib["number"]
                )
                < 2
            ):
                result["msg"] = (
                    "Pacemaker cluster is not stable and does not have primary node or secondary node"
                )

            nodes = cluster_status_xml.find("nodes")
            for node in nodes:
                if node.attrib["online"] != "true":
                    return {
                        "error": "Node {} is not online".format(node.attrib["name"])
                    }

            node_attributes = cluster_status_xml.find("node_attributes")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(check_node, node, database_sid)
                    for node in node_attributes
                ]
                for future in concurrent.futures.as_completed(futures):
                    result.update(future.result())

        if result["primary_node"] == "" or result["secondary_node"] == "":
            result["msg"] = (
                "Pacemaker cluster is not stable and does not have primary node or secondary node"
            )
            module.fail_json(**result)
    except Exception as e:
        result["msg"] = str(e)
        module.fail_json(**result)
    result["end"] = datetime.now()
    module.exit_json(**result)


def main():
    """Entry point of the script."""
    run_module()


if __name__ == "__main__":
    main()
