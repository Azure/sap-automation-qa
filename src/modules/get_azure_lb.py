# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for getting Azure Load Balancer details
"""

from ansible.module_utils.basic import AnsibleModule
from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient
from ansible.module_utils.cluster_constants import PROBES, RULES


class AzureLoadBalancer:
    """
    Class to get the details of the DB/SCS/ERS load balancers in a specific resource group.
    """

    def __init__(self, module: AnsibleModule):
        self.result = {
            "details": [],
            "status": None,
            "error": None,
        }
        self.credential = None
        self.module = module
        self.network_client = None

    def _create_network_client(self):
        """
        Get the network client object.

        :rtype: NetworkManagementClient
        """
        try:
            self.credential = ManagedIdentityCredential()
            self.network_client = NetworkManagementClient(
                self.credential, self.module.params["subscription_id"]
            )
        except Exception as e:
            self.result["error"] = (
                "Failed to get the MSI credential object or network client. " + str(e)
            )

    def get_load_balancers(self) -> list:
        """
        Get all load balancers in a specific resource group.

        :rtype: list
        """
        try:
            return [
                lb.as_dict()
                for lb in self.network_client.load_balancers.list(
                    self.module.params["resource_group_name"]
                )
            ]
        except Exception as e:
            self.result["error"] = str(e)
            return []

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

        if self.result["error"]:
            return self.result

        load_balancers = self.get_load_balancers()

        if self.result["error"]:
            return self.result

        required_load_balancer_ip = self.module.params["load_balancer_ip"]
        required_load_balancer = None

        required_load_balancer = next(
            (
                lb
                for lb in load_balancers
                if lb["frontend_ip_configurations"][0]["private_ip_address"]
                == required_load_balancer_ip
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
                "PASSED"
                if all(param["status"] == "PASSED" for param in parameters)
                else "FAILED"
            )
            self.result["details"] = {"parameters": parameters}
        except Exception as e:
            self.result["error"] = str(e)

        return self.result


def run_module():
    """
    Entry point of the script.
    """
    module_args = dict(
        subscription_id=dict(type="str", required=True),
        resource_group_name=dict(type="str", required=True),
        load_balancer_ip=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    load_balancer = AzureLoadBalancer(module)
    result = load_balancer.get_load_balancers_details()

    if result["error"]:
        module.fail_json(msg=result["error"], **result)
    else:
        module.exit_json(
            msg="Load balancer details are fetched successfully.", **result
        )


def main():
    """
    Entry point
    """
    run_module()


if __name__ == "__main__":
    main()
