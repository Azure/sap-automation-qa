# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for getting Azure Load Balancer details
"""

import logging
import ast
from typing import Dict
from azure.identity import ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import TestStatus, Parameters
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import TestStatus, Parameters

DOCUMENTATION = r"""
---
module: get_azure_lb
short_description: Gets and validates Azure Load Balancer details
description:
    - This module retrieves Azure Load Balancer details for DB/SCS/ERS in a specific resource group.
    - Validates load balancer rules and health probe configurations against expected values.
    - Uses Azure SDK to interact with Azure Network resources.
options:
    subscription_id:
        description:
            - The Azure subscription ID.
        type: str
        required: true
    region:
        description:
            - Azure region where the resources are deployed.
        type: str
        required: true
    inbound_rules:
        description:
            - JSON string containing inbound rule configurations to check for.
            - Must include privateIpAddress fields to match load balancers.
        type: str
        required: true
    constants:
        description:
            - Dictionary containing expected configuration values for validation.
            - Must include AZURE_LOADBALANCER.RULES and AZURE_LOADBALANCER.PROBES.
        type: dict
        required: true
    msi_client_id:
        description:
            - Managed Identity Client ID for authentication.
            - Optional; if not provided, the default Managed Identity will be used.
        type: str
        required: false
author:
    - Microsoft Corporation
notes:
    - Requires Azure SDK for Python.
    - Uses Managed Identity for authentication.
    - Must be run on a machine with Managed Identity credentials configured.
requirements:
    - python >= 3.6
    - azure-identity
    - azure-mgmt-network
"""

EXAMPLES = r"""
- name: Get and validate Azure Load Balancer configuration
  get_azure_lb:
    subscription_id: "{{ azure_subscription_id }}"
    region: "{{ azure_region }}"
    inbound_rules: "{{ inbound_rules | to_json }}"
    constants:
      AZURE_LOADBALANCER:
        RULES:
          idle_timeout_in_minutes: 30
          load_distribution: "Default"
          enable_floating_ip: True
        PROBES:
          interval_in_seconds: 15
          number_of_probes: 3
  register: lb_result

- name: Display load balancer validation results
  debug:
    var: lb_result

- name: Use Managed Identity Client ID for authentication
  get_azure_lb:
    subscription_id: "{{ azure_subscription_id }}"
    region: "{{ azure_region }}"
    inbound_rules: "{{ inbound_rules | to_json }}"
    constants:
      AZURE_LOADBALANCER:
        RULES:
          idle_timeout_in_minutes: 30
          load_distribution: "Default"
          enable_floating_ip: True
        PROBES:
          interval_in_seconds: 15
          number_of_probes: 3
    msi_client_id: "{{ managed_identity_client_id }}"
  register: lb_result
"""

RETURN = r"""
status:
    description: Status of the validation.
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Descriptive message about the operation and validation results.
    returned: always
    type: str
    sample: "Successfully validated load balancer parameters."
details:
    description: Detailed validation results for each parameter.
    returned: always
    type: dict
    contains:
        parameters:
            description: List of parameters validated.
            returned: always
            type: list
            elements: dict
            contains:
                category:
                    description: Parameter category (load_balancing_rule or probe).
                    type: str
                    sample: "load_balancing_rule"
                id:
                    description: Name/identifier of the entity.
                    type: str
                    sample: "lbRuleSAPILP"
                name:
                    description: Name of the parameter.
                    type: str
                    sample: "idle_timeout_in_minutes"
                value:
                    description: Actual value found.
                    type: str
                    sample: "30"
                expected_value:
                    description: Expected value for comparison.
                    type: str
                    sample: "30"
                status:
                    description: Result of the comparison.
                    type: str
                    sample: "SUCCESS"
"""


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

    def _create_network_client(self) -> bool:
        """
        Create the network client object.
        """
        try:
            if self.module_params.get("msi_client_id"):
                self.credential = ManagedIdentityCredential(
                    client_id=self.module_params["msi_client_id"]
                )
            else:
                self.credential = ManagedIdentityCredential()
            self.network_client = NetworkManagementClient(
                self.credential, self.module_params["subscription_id"]
            )
            return True
        except Exception as ex:
            self.handle_error(ex)
            self.result["message"] += (
                " Failed to authenticate to Azure to read the Load " + f"Balancer Details. {ex} \n"
            )
            return False

    def get_load_balancers(self) -> list:
        """
        Get the list of load balancers in a specific resource group.

        :return: List of load balancers
        :rtype: list
        """
        try:
            if self.network_client is None:
                return []

            load_balancers = self.network_client.load_balancers.list_all()
            return [
                lb.as_dict()
                for lb in load_balancers
                if str(lb.location).lower() == self.module_params["region"].lower()
            ]

        except Exception as ex:
            self.handle_error(ex)
            self.result["message"] += f" Failed to get load balancers. {ex} \n"
        return []

    def get_load_balancers_details(self) -> None:
        """
        Get the details of the load balancers in a specific resource group.
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

        self.log(logging.INFO, f"Looking for load balancers with IPs: {load_balancer_ips}")

        found_load_balancer = None

        def get_private_ip_from_config(config):
            """
            Extract private IP from frontend config, handling different key variations.
            Azure SDK might return different structures based on authentication context.
            """
            private_ip = config.get("private_ip_address") or config.get("privateIpAddress")
            return private_ip

        found_load_balancer = next(
            (
                lb
                for lb in load_balancers
                for frontend_ip_config in lb.get("frontend_ip_configurations", [])
                if get_private_ip_from_config(frontend_ip_config) in load_balancer_ips
            ),
            None,
        )

        if not found_load_balancer and load_balancers:
            available_ips = []
            self.log(
                logging.WARNING, f"No matching load balancer found for IPs: {load_balancer_ips}"
            )
            for lb in load_balancers:
                lb_name = lb.get("name", "unknown")
                for config in lb.get("frontend_ip_configurations", []):
                    private_ip = get_private_ip_from_config(config)
                    if private_ip:
                        available_ips.append(f"{lb_name}:{private_ip}")
                    else:
                        self.log(
                            logging.DEBUG,
                            f"Frontend config structure for {lb_name}: {list(config.keys())}",
                        )
            self.log(logging.WARNING, f"Available load balancers and private IPs: {available_ips}")
        parameters = []

        def check_parameters(entity, parameters_dict, entity_type):
            for key, value_object in parameters_dict.items():
                entity_value = entity.get(key, "N/A")
                expected_value = value_object.get("value", "")

                parameters.append(
                    Parameters(
                        category=entity_type,
                        id=entity.get("name", "unknown"),
                        name=key,
                        value=str(entity_value),
                        expected_value=str(expected_value),
                        status=(
                            TestStatus.SUCCESS.value
                            if entity_value == expected_value
                            else TestStatus.ERROR.value
                        ),
                    ).to_dict()
                )

        try:
            if found_load_balancer:
                self.log(
                    logging.INFO,
                    f"Found load balancer {found_load_balancer['name']}",
                )
                self.result[
                    "message"
                ] += f"Validating load balancer parameters {found_load_balancer['name']}"
                for rule in found_load_balancer["load_balancing_rules"]:
                    try:
                        check_parameters(
                            rule,
                            self.constants["RULES"],
                            "load_balancing_rule",
                        )
                    except Exception as ex:
                        self.handle_error(ex)
                        self.result[
                            "message"
                        ] += f"Failed to validate load balancer rule parameters. {ex} \n"
                        continue

                for probe in found_load_balancer["probes"]:
                    try:
                        check_parameters(
                            probe,
                            self.constants["PROBES"],
                            "probes",
                        )
                    except Exception as ex:
                        self.handle_error(ex)
                        self.result[
                            "message"
                        ] += f"Failed to validate load balancer probe parameters. {ex} \n"
                        continue

                failed_parameters = [
                    param
                    for param in parameters
                    if param.get("status", TestStatus.ERROR.value) == TestStatus.ERROR.value
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
                self.result["message"] += "Successfully validated load balancer parameters"
            else:
                self.result.update(
                    {
                        "details": {"parameters": []},
                        "status": TestStatus.ERROR.value,
                    }
                )
                self.result["message"] += (
                    "Load Balancer details not fetched."
                    " Ensure that the Managed Identity (MSI) has sufficient permissions "
                    "to access the load balancer details."
                )

        except Exception as ex:
            self.handle_error(ex)


def run_module():
    """
    Entry point of the script.
    """
    module_args = dict(
        subscription_id=dict(type="str", required=True),
        region=dict(type="str", required=True),
        inbound_rules=dict(type="str", required=True),
        constants=dict(type="dict", required=True),
        msi_client_id=dict(type="str", required=False),
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
