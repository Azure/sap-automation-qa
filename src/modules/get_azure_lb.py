# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for getting Azure Load Balancer details
"""

import logging
from typing import Dict
from ansible.module_utils.basic import AnsibleModule
from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.db_cluster_constants import PROBES, RULES
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.db_cluster_constants import PROBES, RULES


class AzureLoadBalancer(SapAutomationQA):
    """
    Class to get the details of the DB/SCS/ERS load balancers in a specific resource group.
    """

    def __init__(self, module_params: Dict):
        super().__init__()
        self.credential = None
        self.module_params = module_params
        self.network_client = None

    def _create_network_client(self):
        """
        Get the network client object.

        :rtype: NetworkManagementClient
        """
        try:
            self.credential = ManagedIdentityCredential()
            self.network_client = NetworkManagementClient(
                self.credential, self.module_params["subscription_id"]
            )
        except Exception as e:
            self.handle_error(e)

    def get_load_balancers(self) -> list:
        """
        Get all load balancers in a specific resource group.

        :rtype: list
        """
        try:
            load_balancers = self.network_client.load_balancers.list_all()
            return [
                lb.as_dict()
                for lb in load_balancers
                if lb.location.lower() == self.module_params["region"].lower()
            ]

        except Exception as e:
            self.handle_error(e)

    def _format_parameter_result(self, name: str, value: str, expected: str) -> str:
        """
        Formats the parameter result for reporting.
        """
        return f"Name: {name}, Value: {value}, Expected Value: {expected}"

    def get_load_balancers_details(self) -> dict:
        """
        Get the details of the DB/SCS/ERS load balancers in a specific resource group.

        :rtype: dict
        """
        self._create_network_client()

        if self.result["status"] == "FAILED":
            return self.result

        load_balancers = self.get_load_balancers()

        if self.result["status"] == "FAILED":
            return self.result

        self.log(
            logging.INFO,
            f"Load balancers: {load_balancers} Type, {type(load_balancers)}",
        )

        load_balancer_ips = [
            inbound_rule.get("privateIpAddress", "")
            for inbound_rule in self.module_params["inbound_rules"]
        ]
        required_load_balancer = None

        required_load_balancer = next(
            (
                lb
                for lb in load_balancers
                for frontend_ip_config in lb["frontend_ip_configurations"]
                if frontend_ip_config["private_ip_address"] in load_balancer_ips
            ),
            None,
        )
        parameters = []

        def check_parameters(entity, entity_name, parameters_dict, entity_type):
            for key, value in parameters_dict.items():
                status = "PASSED" if entity[key] == value else "FAILED"
                parameters.append(
                    {
                        "category": entity_name,
                        "type": entity_type,
                        "name": key,
                        "value": str(entity[key]),
                        "expected value": str(value),
                        "status": status,
                    }
                )

        try:
            if required_load_balancer:
                for rule in required_load_balancer["load_balancing_rules"]:
                    check_parameters(
                        rule,
                        required_load_balancer["name"],
                        RULES,
                        "load_balancing_rule",
                    )

                for probe in required_load_balancer["probes"]:
                    check_parameters(
                        probe, required_load_balancer["name"], PROBES, "probes"
                    )

            self.result["status"] = (
                TestStatus.SUCCESS.value
                if all(param["status"] == "PASSED" for param in parameters)
                else TestStatus.ERROR.value
            )
            self.result["details"] = {"parameters": parameters}
        except Exception as e:
            self.handle_error(e)

        return self.result


def run_module():
    """
    Entry point of the script.
    """
    module_args = dict(
        subscription_id=dict(type="str", required=True),
        region=dict(type="str", required=True),
        inbound_rules=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    load_balancer = AzureLoadBalancer(module_params=module.params)
    result = load_balancer.get_load_balancers_details()

    module.exit_json(msg="Load balancer details are fetched successfully.", **result)


def main():
    """
    Entry point
    """
    run_module()


if __name__ == "__main__":
    main()
