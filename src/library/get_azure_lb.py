# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for getting Azure Load Balancer details
"""

from ansible.module_utils.basic import AnsibleModule
from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient


class AzureLoadBalancer:
    """
    Class to get the details of the DB/SCS/ERS load balancers in a specific resource group.
    """

    def __init__(self, module: AnsibleModule):
        self.result = {
            "load_balancer": [],
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
        except Exception:
            self.result["error"] = "Failed to get the MSI credential object."

    def get_load_balancers(self) -> list:
        """
        Get all load balancers in a specific resource group.

        :rtype: list
        """
        try:
            load_balancers = self.network_client.load_balancers.list(
                self.module.params["resource_group_name"]
            )
            return [lb.as_dict() for lb in load_balancers]
        except Exception as e:
            self.result["error"] = str(e)
            return []

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
        try:
            if required_load_balancer:
                self.result["load_balancer"].append(
                    {
                        "name": required_load_balancer["name"],
                        "resource_group": required_load_balancer["resource_group"],
                        "location": required_load_balancer["location"],
                        "frontend_ip_configurations": required_load_balancer.get(
                            "frontend_ip_configurations", []
                        ),
                        "probes": [
                            {
                                "name": probe["name"],
                                "protocol": probe["protocol"],
                                "port": probe["port"],
                                "interval_in_seconds": probe["interval_in_seconds"],
                                "number_of_probes": probe["number_of_probes"],
                            }
                            for probe in required_load_balancer.get("probes", [])
                        ],
                        "rules": [
                            {
                                "name": rule["name"],
                                "protocol": rule["protocol"],
                                "frontend_port": rule["frontend_port"],
                                "backend_port": rule["backend_port"],
                                "idle_timeout_in_minutes": rule[
                                    "idle_timeout_in_minutes"
                                ],
                                "enable_floating_ip": rule["enable_floating_ip"],
                            }
                            for rule in required_load_balancer.get(
                                "load_balancing_rules", []
                            )
                        ],
                    }
                )
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
        module.exit_json(**result)


def main():
    """
    Entry point
    """
    run_module()


if __name__ == "__main__":
    main()
