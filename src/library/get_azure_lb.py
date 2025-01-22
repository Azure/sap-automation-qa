# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for getting Azure Load Balancer details
"""

from ansible.module_utils.basic import AnsibleModule
from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient
from collections import defaultdict

PROBES = {
    "probe_threshold": 2,
    "interval_in_seconds": 5,
    "number_of_probes": 2,
}

RULES = {
    "idle_timeout_in_minutes": 4,
    "enable_floating_ip": True,
    "enable_tcp_reset": False,
}


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
        drift_parameters = defaultdict(lambda: defaultdict(list))
        valid_parameters = defaultdict(lambda: defaultdict(list))

        def check_parameters(
            entity, entity_name, parameters, drift_parameters, valid_parameters
        ):
            for key, value in parameters.items():
                if entity[key] != value:
                    drift_parameters[entity_name][key].append(
                        self._format_parameter_result(key, entity[key], value)
                    )
                else:
                    valid_parameters[entity_name][key].append(
                        self._format_parameter_result(key, entity[key], value)
                    )

        try:
            if required_load_balancer:
                for rule in required_load_balancer["load_balancing_rules"]:
                    check_parameters(
                        rule, rule["name"], RULES, drift_parameters, valid_parameters
                    )

                for probe in required_load_balancer["probes"]:
                    check_parameters(
                        probe, probe["name"], PROBES, drift_parameters, valid_parameters
                    )

            if drift_parameters:
                self.result["status"] = "FAILED"
            self.result["status"] = "PASSED"
            self.result["details"] = {**drift_parameters, **valid_parameters}
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
