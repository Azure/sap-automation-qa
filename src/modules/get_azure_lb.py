# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for getting Azure Load Balancer details
"""

import logging
import ast
from typing import Dict
from ansible.module_utils.basic import AnsibleModule
from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient

try:
    from ansible.module_utils.sap_automation_qa import (
        SapAutomationQA,
        TestStatus,
        Parameters,
    )
except ImportError:
    from src.module_utils.sap_automation_qa import (
        SapAutomationQA,
        TestStatus,
        Parameters,
    )


class AzureLoadBalancer(SapAutomationQA):
    """
    Class to get the details of the DB/SCS/ERS load balancers in a specific resource group.
    """

    def __init__(self, module_params: Dict):
        super().__init__()
        self.credential = None
        self.module_params = module_params
        self.network_client = None
        self.constants = module_params["constants"].get("AZURE_LOADBALANCER", {})

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
            self.result["message"] += f"Failed to create network client object. {e} \n"

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
            self.result["message"] += f"Failed to create network client object. {e} \n"

    def get_load_balancers_details(self) -> dict:
        """
        Get the details of the DB/SCS/ERS load balancers in a specific resource group.

        :rtype: dict
        """
        self._create_network_client()

        if self.result["status"] == TestStatus.ERROR.value:
            return self.result

        load_balancers = self.get_load_balancers()

        if self.result["status"] == TestStatus.ERROR.value:
            return self.result

        inbound_rules = ast.literal_eval(self.module_params["inbound_rules"])
        load_balancer_ips = list(
            inbound_rule["privateIpAddress"]
            for inbound_rule in inbound_rules
            if "privateIpAddress" in inbound_rule
        )
        found_load_balancer = None

        found_load_balancer = next(
            (
                lb
                for lb in load_balancers
                for frontend_ip_config in lb["frontend_ip_configurations"]
                if frontend_ip_config["private_ip_address"] in load_balancer_ips
            ),
            None,
        )
        parameters = []

        def check_parameters(entity, parameters_dict, entity_type):
            for key, expected_value in parameters_dict.items():
                parameters.append(
                    Parameters(
                        category=entity_type,
                        id=entity["name"],
                        name=key,
                        value=str(entity[key]),
                        expected_value=str(expected_value),
                        status=(
                            TestStatus.SUCCESS.value
                            if entity[key] == expected_value
                            else TestStatus.ERROR.value
                        ),
                    ).to_dict()
                )

        try:
            if found_load_balancer:
                self.result[
                    "message"
                ] += (
                    f"Validating load balancer parameters {found_load_balancer['name']}"
                )
                for rule in found_load_balancer["load_balancing_rules"]:
                    try:
                        check_parameters(
                            rule,
                            self.constants["RULES"],
                            "load_balancing_rule",
                        )
                    except Exception as e:
                        self.handle_error(e)
                        self.result[
                            "message"
                        ] += f"Failed to validate load balancer rule parameters. {e} \n"
                        continue

                for probe in found_load_balancer["probes"]:
                    try:
                        check_parameters(
                            probe,
                            self.constants["PROBES"],
                            "probes",
                        )
                    except Exception as e:
                        self.handle_error(e)
                        self.result[
                            "message"
                        ] += (
                            f"Failed to validate load balancer probe parameters. {e} \n"
                        )
                        continue

                failed_parameters = [
                    param
                    for param in parameters
                    if param.get("status", TestStatus.ERROR.value)
                    == TestStatus.ERROR.value
                ]
                self.result.update(
                    {
                        "details": {"parameters": parameters},
                        "status": (
                            TestStatus.ERROR.value
                            if failed_parameters
                            else TestStatus.SUCCESS.value
                        ),
                    }
                )
                self.result[
                    "message"
                ] += "Successfully validated load balancer parameters"
            else:
                self.result["message"] += "No load balancer found"

        except Exception as e:
            self.handle_error(e)


def run_module():
    """
    Entry point of the script.
    """
    module_args = dict(
        subscription_id=dict(type="str", required=True),
        region=dict(type="str", required=True),
        inbound_rules=dict(type="str", required=True),
        constants=dict(type="dict", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    load_balancer = AzureLoadBalancer(module_params=module.params)
    load_balancer.get_load_balancers_details()

    module.exit_json(**load_balancer.get_result())


def main():
    """
    Entry point
    """
    run_module()


if __name__ == "__main__":
    main()
