# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the status of a HANA cluster.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.facts.compat import ansible_facts

try:
    from ansible.module_utils.get_cluster_status import BaseClusterStatusChecker
    from ansible.module_utils.enums import (
        OperatingSystemFamily,
        HanaSRProvider,
        HanaTopology,
    )
    from ansible.module_utils.commands import AUTOMATED_REGISTER, PRIORITY_FENCING_DELAY
except ImportError:
    from src.module_utils.get_cluster_status import BaseClusterStatusChecker
    from src.module_utils.commands import AUTOMATED_REGISTER, PRIORITY_FENCING_DELAY
    from src.module_utils.enums import (
        OperatingSystemFamily,
        HanaSRProvider,
        HanaTopology,
    )


DOCUMENTATION = r"""
---
module: get_cluster_status_db
short_description: Checks the status of a SAP HANA database cluster
description:
    - This module checks the status of a pacemaker cluster in a SAP HANA environment
    - Identifies primary and secondary nodes in the cluster
    - Retrieves operation mode, replication mode, and other cluster attributes
    - Validates if the cluster is ready and stable
options:
    operation_step:
        description:
            - The current operation step being executed
        type: str
        required: true
    database_sid:
        description:
            - SAP HANA database SID
        type: str
        required: true
    saphanasr_provider:
        description:
            - The SAP HANA system replication provider type
        type: str
        required: true
    db_instance_number:
        description:
            - The instance number of the SAP HANA database
        type: str
        required: true
    hana_topology:
        description:
            - The SAP HANA topology type
            - For scale_out_standby (no Pacemaker), this module does not apply
        type: str
        required: false
        default: scale_up
        choices:
            - scale_up
            - scale_out_hsr
author:
    - Microsoft Corporation
notes:
    - This module requires root privileges to access pacemaker cluster information
    - Depends on crm_mon and crm_attribute commands being available
    - Validates the cluster status by checking node attributes
requirements:
    - python >= 3.6
    - pacemaker cluster environment
"""

EXAMPLES = r"""
- name: Check SAP HANA cluster status
  get_cluster_status_db:
    operation_step: "check_cluster"
    database_sid: "HDB"
    saphanasr_provider: "SAPHanaSR"
  register: cluster_result

- name: Display cluster status
  debug:
    msg: "Primary node: {{ cluster_result.primary_node }}, Secondary node: {{ cluster_result.secondary_node }}"

- name: Fail if cluster is not stable
  fail:
    msg: "HANA cluster is not properly configured"
  when: cluster_result.primary_node == '' or cluster_result.secondary_node == ''
"""

RETURN = r"""
status:
    description: Status of the cluster check
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Descriptive message about the cluster status
    returned: always
    type: str
    sample: "Cluster is stable and ready"
primary_node:
    description: Name of the primary node in the HANA cluster
    returned: always
    type: str
    sample: "hanadb1"
secondary_node:
    description: Name of the secondary node in the HANA cluster
    returned: always
    type: str
    sample: "hanadb2"
operation_mode:
    description: HANA system replication operation mode
    returned: always
    type: str
    sample: "logreplay"
replication_mode:
    description: HANA system replication mode
    returned: always
    type: str
    sample: "sync"
primary_site_name:
    description: Name of the primary site in HANA system replication
    returned: always
    type: str
    sample: "Site1"
AUTOMATED_REGISTER:
    description: Status of automated registration
    returned: always
    type: str
    sample: "true"
primary_site_nodes:
    description: List of node names on the primary site (scale-out HSR only)
    returned: when hana_topology is scale_out_hsr
    type: list
    sample: ["hanadb1", "hanadb2"]
secondary_site_nodes:
    description: List of node names on the secondary site (scale-out HSR only)
    returned: when hana_topology is scale_out_hsr
    type: list
    sample: ["hanadb3", "hanadb4"]
majority_maker_node:
    description: Name of the majority maker node (scale-out HSR only)
    returned: when hana_topology is scale_out_hsr
    type: str
    sample: "hanadb5"
secondary_site_name:
    description: Name of the secondary site in HANA system replication
    returned: when hana_topology is scale_out_hsr
    type: str
    sample: "Site2"
hana_topology:
    description: The configured HANA topology type
    returned: always
    type: str
    sample: "scale_up"
cluster_status:
    description: Detailed cluster attributes for each node
    returned: always
    type: dict
    contains:
        primary:
            description: Attributes of the primary node (scale-up) or dict of nodes (scale-out)
            type: dict
        secondary:
            description: Attributes of the secondary node (scale-up) or dict of nodes (scale-out)
            type: dict
worker_node_scores_valid:
    description: Whether all worker node scores match expected values (scale-out HSR only)
    returned: when hana_topology is scale_out_hsr
    type: bool
    sample: true
worker_node_score_details:
    description: Per-worker-node score validation details (scale-out HSR only)
    returned: when hana_topology is scale_out_hsr
    type: list
    elements: dict
    sample:
        - node: "hanadb2"
          site_role: "primary"
          actual_score: "150"
          expected_score: "150"
          valid: true
"""


class HanaClusterStatusChecker(BaseClusterStatusChecker):
    """
    Class to check the status of a pacemaker cluster in a SAP HANA environment.
    """

    def __init__(
        self,
        database_sid: str,
        db_instance_number: str,
        saphanasr_provider: HanaSRProvider,
        ansible_os_family: OperatingSystemFamily,
        hana_topology: HanaTopology = HanaTopology.SCALE_UP,
        hana_clone_resource_name: str = "",
        hana_primitive_resource_name: str = "",
    ):
        super().__init__(ansible_os_family)
        self.database_sid = database_sid
        self.saphanasr_provider = saphanasr_provider
        self.db_instance_number = db_instance_number
        self.hana_topology = hana_topology
        self.hana_clone_resource_name = hana_clone_resource_name
        self.hana_primitive_resource_name = hana_primitive_resource_name
        self.result.update(
            {
                "primary_node": "",
                "secondary_node": "",
                "primary_site_nodes": [],
                "secondary_site_nodes": [],
                "majority_maker_node": "",
                "operation_mode": "",
                "replication_mode": "",
                "primary_site_name": "",
                "secondary_site_name": "",
                "hana_topology": hana_topology.value,
                "AUTOMATED_REGISTER": "false",
                "PRIORITY_FENCING_DELAY": "",
                "worker_node_scores_valid": True,
                "worker_node_score_details": [],
            }
        )

    def _get_cluster_parameters(self) -> None:
        """
        Retrieves the values of the AUTOMATED_REGISTER and PRIORITY_FENCING_DELAY attributes.
        """
        param_commands = {
            "AUTOMATED_REGISTER": (
                AUTOMATED_REGISTER(self.hana_primitive_resource_name)
                if self.hana_primitive_resource_name
                else AUTOMATED_REGISTER(self.hana_clone_resource_name)
            ),
        }
        if self.hana_topology != HanaTopology.SCALE_OUT_HSR:
            param_commands["PRIORITY_FENCING_DELAY"] = PRIORITY_FENCING_DELAY

        for param_name, command in param_commands.items():
            try:
                self.result[param_name] = self.execute_command_subprocess(command).strip()
            except Exception:
                self.result[param_name] = "unknown"

    def _process_node_attributes(self, cluster_status_xml: ET.Element) -> Dict[str, Any]:
        """
        Dispatches node attribute processing based on HANA topology.

        :param cluster_status_xml: XML element containing node attributes.
        :type cluster_status_xml: ET.Element
        :return: Dictionary with node information.
        :rtype: Dict[str, Any]
        """
        if self.hana_topology == HanaTopology.SCALE_OUT_HSR:
            return self._process_scale_out_hsr_attributes(cluster_status_xml)
        return self._process_scale_up_attributes(cluster_status_xml)

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Returns provider-specific attribute names and expected values.

        :return: Provider configuration dictionary with clone/sync
            attribute names and expected primary/secondary values.
        :rtype: Dict[str, Any]
        """
        scaleout_score_attr = (
            f"master-{self.hana_primitive_resource_name}"
            if self.hana_primitive_resource_name
            else f"master-rsc_SAPHana_{self.database_sid.upper()}"
            + f"_HDB{self.db_instance_number}"
        )
        angi_score_attr = (
            f"master-{self.hana_primitive_resource_name}"
            if self.hana_primitive_resource_name
            else "master-rsc_SAPHanaCon_"
            + f"{self.database_sid.upper()}"
            + f"_HDB{self.db_instance_number}"
        )

        providers = {
            HanaSRProvider.SAPHANASR: {
                "clone_attr": (f"hana_{self.database_sid}_clone_state"),
                "sync_attr": (f"hana_{self.database_sid}_sync_state"),
                "score_attr": scaleout_score_attr,
                "primary": {"clone": "PROMOTED", "sync": "PRIM"},
                "secondary": {"clone": "DEMOTED", "sync": "SOK"},
                "worker_scores": {
                    "primary": "-10000",
                    "secondary": "-12200",
                },
            },
            HanaSRProvider.ANGI: {
                "clone_attr": (f"hana_{self.database_sid}_clone_state"),
                "sync_attr": angi_score_attr,
                "score_attr": angi_score_attr,
                "primary": {"clone": "PROMOTED", "sync": "150"},
                "secondary": {
                    "clone": "DEMOTED",
                    "sync": "100",
                },
                "worker_scores": {
                    "primary": "101",
                    "secondary": "-12200",
                },
            },
            HanaSRProvider.SCALEOUT: {
                "clone_attr": f"hana_{self.database_sid}_clone_state",
                "sync_attr": scaleout_score_attr,
                "score_attr": scaleout_score_attr,
                "primary": {"clone": "PROMOTED", "sync": "150"},
                "secondary": {"clone": "DEMOTED", "sync": "100"},
                "worker_scores": {
                    "primary": "-10000",
                    "secondary": "-12200",
                },
            },
        }

        return providers.get(
            self.saphanasr_provider,
            providers[HanaSRProvider.SAPHANASR],
        )

    def _process_scale_up_attributes(self, cluster_status_xml: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes for a scale-up (2-node) HANA cluster.

        :param cluster_status_xml: XML element containing node attributes.
        :type cluster_status_xml: ET.Element
        :return: Dictionary with primary and secondary node information.
        :rtype: Dict[str, Any]
        """
        result: Dict[str, Any] = {
            "primary_node": "",
            "secondary_node": "",
            "cluster_status": {"primary": {}, "secondary": {}},
            "operation_mode": "",
            "replication_mode": "",
            "primary_site_name": "",
            "secondary_site_name": "",
        }
        node_attributes = cluster_status_xml.find("node_attributes")
        if node_attributes is None:
            self.log(
                logging.ERROR,
                "No node attributes found in the cluster status XML.",
            )
            return result

        provider_config = self._get_provider_config()

        for node in node_attributes:
            node_name = node.attrib["name"]
            attrs = {attr.attrib["name"]: attr.attrib["value"] for attr in node}
            result["operation_mode"] = attrs.get(
                f"hana_{self.database_sid}_op_mode",
                result["operation_mode"],
            )
            result["replication_mode"] = attrs.get(
                f"hana_{self.database_sid}_srmode",
                result["replication_mode"],
            )
            clone_state = attrs.get(provider_config["clone_attr"], "")
            sync_state = attrs.get(provider_config["sync_attr"], "")
            if (
                clone_state == provider_config["primary"]["clone"]
                and sync_state == provider_config["primary"]["sync"]
            ):
                result.update(
                    {
                        "primary_node": node_name,
                        "primary_site_name": attrs.get(
                            f"hana_{self.database_sid}_site",
                            "",
                        ),
                    }
                )
                result["cluster_status"]["primary"] = attrs

            elif (
                clone_state == provider_config["secondary"]["clone"]
                and sync_state == provider_config["secondary"]["sync"]
            ):
                result["secondary_node"] = node_name
                result["secondary_site_name"] = attrs.get(
                    f"hana_{self.database_sid}_site",
                    "",
                )
                result["cluster_status"]["secondary"] = attrs

        self.result.update(result)
        return result

    def _process_scale_out_hsr_attributes(self, cluster_status_xml: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes for a scale-out HSR HANA cluster.

        :param cluster_status_xml: XML element containing node
        :type cluster_status_xml: ET.Element
        :return: Dictionary with scale-out HSR cluster information
        :rtype: Dict[str, Any]
        """
        result: Dict[str, Any] = {
            "primary_node": "",
            "secondary_node": "",
            "primary_site_nodes": [],
            "secondary_site_nodes": [],
            "majority_maker_node": "",
            "cluster_status": {"primary": {}, "secondary": {}},
            "operation_mode": "",
            "replication_mode": "",
            "primary_site_name": "",
            "secondary_site_name": "",
            "worker_node_scores_valid": True,
            "worker_node_score_details": [],
        }
        node_attributes = cluster_status_xml.find("node_attributes")
        if node_attributes is None:
            self.log(
                logging.ERROR,
                "No node attributes found in the cluster status XML.",
            )
            return result

        provider_config = self._get_provider_config()
        clone_attr = provider_config["clone_attr"]

        nodes_by_site: Dict[str, List[tuple]] = {}
        majority_maker_candidates: List[str] = []

        for node in node_attributes:
            node_name = node.attrib["name"]
            attrs = {attr.attrib["name"]: attr.attrib["value"] for attr in node}
            result["operation_mode"] = attrs.get(
                f"hana_{self.database_sid}_op_mode",
                result["operation_mode"],
            )
            result["replication_mode"] = attrs.get(
                f"hana_{self.database_sid}_srmode",
                result["replication_mode"],
            )
            site = attrs.get(f"hana_{self.database_sid}_site", "")
            clone_state = attrs.get(clone_attr, "")

            if not site and not clone_state:
                majority_maker_candidates.append(node_name)
                continue

            nodes_by_site.setdefault(site, []).append((node_name, attrs))

        primary_site = ""
        for site, nodes in nodes_by_site.items():
            for node_name, attrs in nodes:
                clone_state = attrs.get(clone_attr, "")
                sync_state = attrs.get(provider_config["sync_attr"], "")
                if (
                    clone_state == provider_config["primary"]["clone"]
                    and sync_state == provider_config["primary"]["sync"]
                ):
                    primary_site = site
                    result["primary_node"] = node_name
                    result["primary_site_name"] = site
                    break
            if primary_site:
                break

        for site, nodes in nodes_by_site.items():
            node_names = [n for n, _ in nodes]
            node_attrs = {n: a for n, a in nodes}
            if site == primary_site:
                result["primary_site_nodes"] = node_names
                result["cluster_status"]["primary"] = node_attrs
                self._validate_worker_scores(nodes, provider_config, "primary", result)
            else:
                result["secondary_site_name"] = site
                result["secondary_site_nodes"] = node_names
                result["cluster_status"]["secondary"] = node_attrs
                for node_name, attrs in nodes:
                    clone_state = attrs.get(clone_attr, "")
                    sync_state = attrs.get(
                        provider_config["sync_attr"],
                        "",
                    )
                    if (
                        clone_state == provider_config["secondary"]["clone"]
                        and sync_state == provider_config["secondary"]["sync"]
                    ):
                        result["secondary_node"] = node_name
                        break
                self._validate_worker_scores(nodes, provider_config, "secondary", result)

        if majority_maker_candidates:
            result["majority_maker_node"] = majority_maker_candidates[0]

        self.result.update(result)
        return result

    def _validate_worker_scores(
        self,
        nodes: List[tuple],
        provider_config: Dict[str, Any],
        site_role: str,
        result: Dict[str, Any],
    ) -> None:
        """
        Validates that worker node scores match expected values for the site role.

        Workers are identified by exclusion: nodes whose roles attribute
        4th field is NOT 'master' are treated as workers. This handles
        formats like "slave::worker:" where the 4th field may be empty.
        Scores are read from the master promotable score attribute (score_attr).

        :param nodes: List of (node_name, attrs) tuples for a site.
        :type nodes: List[tuple]
        :param provider_config: Provider configuration dictionary.
        :type provider_config: Dict[str, Any]
        :param site_role: Either "primary" or "secondary".
        :type site_role: str
        :param result: Result dictionary to update with validation details.
        :type result: Dict[str, Any]
        """
        worker_scores = provider_config.get("worker_scores")
        if not worker_scores:
            return

        score_attr = provider_config["score_attr"]
        expected_score = worker_scores[site_role]
        roles_attr = f"hana_{self.database_sid}_roles"

        for node_name, attrs in nodes:
            roles = attrs.get(roles_attr, "")
            role_parts = roles.split(":")
            if len(role_parts) < 4 or role_parts[3] == "master":
                continue

            score = attrs.get(score_attr, "")
            if not score:
                result["worker_node_score_details"].append(
                    {
                        "node": node_name,
                        "site_role": site_role,
                        "actual_score": "missing",
                        "expected_score": expected_score,
                        "valid": False,
                    }
                )
                result["worker_node_scores_valid"] = False
                self.log(
                    logging.WARNING,
                    f"Worker node {node_name} on {site_role} site has "
                    f"no score attribute '{score_attr}'",
                )
                continue

            is_valid = score == expected_score
            result["worker_node_score_details"].append(
                {
                    "node": node_name,
                    "site_role": site_role,
                    "actual_score": score,
                    "expected_score": expected_score,
                    "valid": is_valid,
                }
            )
            if not is_valid:
                result["worker_node_scores_valid"] = False
                self.log(
                    logging.WARNING,
                    f"Worker node {node_name} on {site_role} site has "
                    f"unexpected score: {score} (expected "
                    f"{expected_score})",
                )

    def _is_cluster_ready(self) -> bool:
        """
        Check if the primary node has been identified.

        :return: True if the primary node is identified, False otherwise.
        :rtype: bool
        """
        return self.result["primary_node"] != ""

    def _is_cluster_stable(self) -> bool:
        """
        Check if the cluster is in a stable state.

        :return: True if the cluster is stable, False otherwise.
        :rtype: bool
        """
        if self.hana_topology == HanaTopology.SCALE_OUT_HSR:
            return (
                self.result["primary_node"] != ""
                and self.result["secondary_node"] != ""
                and len(self.result["secondary_site_nodes"]) > 0
                and self.result["majority_maker_node"] != ""
                and self.result["worker_node_scores_valid"]
            )
        return self.result["primary_node"] != "" and self.result["secondary_node"] != ""

    def run(self) -> Dict[str, str]:
        """
        Main function that runs the cluster status checks.

        :return: Dictionary with the result of the checks.
        :rtype: Dict[str, str]
        """
        result = super().run()
        self._get_cluster_parameters()
        self._get_replication_params()
        return result

    def _get_replication_params(self) -> None:
        """
        Retrieves replication_mode and operation_mode when not available from CIB node attributes
        """
        if self.result["operation_mode"] and self.result["replication_mode"]:
            return

        try:
            output = self.execute_command_subprocess(
                [
                    "su",
                    "-",
                    f"{self.database_sid}adm",
                    "-c",
                    f"/usr/sap/{self.database_sid.upper()}/HDB{ self.db_instance_number}"
                    f"/exe/hdbnsutil -sr_state --sapcontrol=1",
                ]
            )
        except Exception as exc:
            self.log(
                logging.WARNING,
                "Failed to query hdbnsutil -sr_state: %s",
                str(exc),
            )
            return

        for line in output.splitlines():
            line = line.strip()
            if not self.result["replication_mode"] and line.startswith("siteReplicationMode/"):
                value = line.split("=", 1)[1]
                if value != "primary":
                    self.result["replication_mode"] = value

            if not self.result["operation_mode"] and line.startswith("siteOperationMode/"):
                value = line.split("=", 1)[1]
                if value != "primary":
                    self.result["operation_mode"] = value


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        operation_step=dict(type="str", required=True),
        database_sid=dict(type="str", required=True),
        saphanasr_provider=dict(type="str", required=True),
        db_instance_number=dict(type="str", required=True),
        hana_topology=dict(
            type="str",
            required=False,
            default="scale_up",
            choices=["scale_up", "scale_out_hsr"],
        ),
        hana_clone_resource_name=dict(type="str", required=False),
        hana_primitive_resource_name=dict(type="str", required=False),
        filter=dict(type="str", required=False, default="os_family"),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    checker = HanaClusterStatusChecker(
        database_sid=module.params["database_sid"],
        saphanasr_provider=HanaSRProvider(module.params["saphanasr_provider"]),
        ansible_os_family=OperatingSystemFamily(
            str(ansible_facts(module).get("os_family", "UNKNOWN")).upper()
        ),
        db_instance_number=module.params["db_instance_number"],
        hana_topology=HanaTopology(module.params["hana_topology"]),
        hana_clone_resource_name=module.params.get("hana_clone_resource_name", ""),
        hana_primitive_resource_name=module.params.get("hana_primitive_resource_name", ""),
    )
    checker.run()

    module.exit_json(**checker.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
