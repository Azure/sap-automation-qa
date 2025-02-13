"""
Unit tests for the get_azure_lb module.
"""

import pytest
import json
from src.modules.get_azure_lb import AzureLoadBalancer


class LoadBalancer:
    def __init__(self, location, ip_addr):
        self.name = "test"
        self.location = location
        self.frontend_ip_configurations = [{"private_ip_address": ip_addr}]
        self.load_balancing_rules = [
            {
                "name": "test1",
                "idle_timeout_in_minutes": 4,
                "enable_floating_ip": False,
            }
        ]
        self.probes = [
            {
                "name": "test1",
                "interval_in_seconds": 5,
                "number_of_probes": 3,
                "timeout_in_seconds": 4,
            }
        ]

    def as_dict(self):
        return {
            "name": self.name,
            "location": self.location,
            "frontend_ip_configurations": self.frontend_ip_configurations,
            "load_balancing_rules": self.load_balancing_rules,
            "probes": self.probes,
        }


@pytest.fixture
def azure_lb(mocker):
    """
    Fixture for creating an AzureLoadBalancer instance.

    :return: AzureLoadBalancer instance
    :rtype: AzureLoadBalancer
    """
    patched_client = mocker.patch("src.modules.get_azure_lb.NetworkManagementClient")
    patched_client.return_value.load_balancers.list_all.return_value = [
        LoadBalancer("test1", "127.0.0.0"),
        LoadBalancer("test", "127.0.0.1"),
    ]
    return AzureLoadBalancer(
        module_params={
            "subscription_id": "test",
            "region": "test",
            "inbound_rules": repr(
                [
                    {
                        "backendPort": "0",
                        "frontendPort": "0",
                        "protocol": "All",
                        "privateIpAddress": "127.0.0.1",
                    }
                ]
            ),
            "constants": {
                "AZURE_LOADBALANCER": {
                    "RULES": {"idle_timeout_in_minutes": 4, "enable_floating_ip": False},
                    "PROBES": {
                        "interval_in_seconds": 5,
                        "number_of_probes": 3,
                        "timeout_in_seconds": 4,
                    },
                }
            },
        }
    )


class TestAzureLoadBalancer:
    def test_get_load_balancers(self, mocker, azure_lb):
        """
        Test the get_load_balancers method.
        """
        azure_lb._create_network_client()
        assert len(azure_lb.get_load_balancers()) == 1

    def test_get_load_balancers_details(self, mocker, azure_lb):
        """
        Test the get_load_balancers_details method.
        """
        azure_lb.get_load_balancers_details()
        azure_lb.result["status"] == "PASSED"
        azure_lb.result["details"]["parameters"] is not None
