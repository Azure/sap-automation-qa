"""
Unit tests for the get_azure_lb module.
"""

import pytest
from src.modules.get_azure_lb import AzureLoadBalancer, main


class LoadBalancer:
    """
    Mock class to simulate Azure Load Balancer.
    """

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
        """
        Convert the LoadBalancer instance to a dictionary.

        :return: Dictionary representation of the LoadBalancer instance.
        :rtype: dict
        """
        return {
            "name": self.name,
            "location": self.location,
            "frontend_ip_configurations": self.frontend_ip_configurations,
            "load_balancing_rules": self.load_balancing_rules,
            "probes": self.probes,
        }


class TestAzureLoadBalancer:
    """
    Test cases for the AzureLoadBalancer class.
    """

    @pytest.fixture
    def azure_lb(self, mocker):
        """
        Fixture for creating an AzureLoadBalancer instance.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock

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

    def test_get_load_balancers(self, azure_lb):
        """
        Test the get_load_balancers method.

        :param azure_lb: AzureLoadBalancer instance
        :type azure_lb: AzureLoadBalancer
        """
        azure_lb._create_network_client()
        assert len(azure_lb.get_load_balancers()) == 1

    def test_get_load_balancers_details(self, azure_lb):
        """
        Test the get_load_balancers_details method.

        :param azure_lb: AzureLoadBalancer instance
        :type azure_lb: AzureLoadBalancer
        """
        azure_lb.get_load_balancers_details()
        assert azure_lb.result["status"] == "PASSED"
        assert azure_lb.result["details"]["parameters"] is not None

    def test_main(self, monkeypatch):
        """
        Test the main function.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class for AnsibleModule.
            """

            def __init__(self, *args, **kwargs):
                self.params = {
                    "subscription_id": "test",
                    "region": "test",
                    "inbound_rules": repr([{}]),
                    "constants": {},
                }

            def exit_json(self, **kwargs):
                """
                Mock exit_json method.
                """
                nonlocal mock_result
                mock_result = kwargs

        with monkeypatch.context() as monkey_patch:
            monkey_patch.setattr("src.modules.get_azure_lb.AnsibleModule", MockAnsibleModule)
            main()
            assert mock_result["status"] == "FAILED"
