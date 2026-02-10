# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the send_telemetry_data module.
"""

import base64
import json
import pytest
from src.modules.send_telemetry_data import TelemetryDataSender, main


class TestTelemetryDataSender:
    """
    Test cases for the TelemetryDataSender class.
    """

    @pytest.fixture
    def module_params(self):
        """
        Fixture for providing sample module parameters.

        :return: Sample module parameters.
        :rtype: dict
        """
        return {
            "test_group_json_data": {"TestGroupInvocationId": "12345"},
            "telemetry_data_destination": "azureloganalytics",
            "laws_workspace_id": "workspace_id",
            "laws_shared_key": base64.b64encode(b"shared_key").decode("utf-8"),
            "telemetry_table_name": "telemetry_table",
            "adx_database_name": "adx_database",
            "adx_cluster_fqdn": "adx_cluster",
            "adx_client_id": "adx_client",
            "workspace_directory": "/tmp",
        }

    @pytest.fixture
    def module_params_adx(self):
        """
        Fixture for providing sample module parameters.

        :return: Sample module parameters.
        :rtype: dict
        """
        return {
            "test_group_json_data": {"TestGroupInvocationId": "12345"},
            "telemetry_data_destination": "azuredataexplorer",
            "laws_workspace_id": "workspace_id",
            "laws_shared_key": base64.b64encode(b"shared_key").decode("utf-8"),
            "telemetry_table_name": "telemetry_table",
            "adx_database_name": "adx_database",
            "adx_cluster_fqdn": "adx_cluster",
            "adx_client_id": "adx_client",
            "workspace_directory": "/tmp",
        }

    @pytest.fixture
    def module_params_list(self):
        """
        Fixture providing a list payload for batched telemetry.

        :return: Sample module parameters with list payload.
        :rtype: dict
        """
        return {
            "test_group_json_data": [
                {
                    "TestGroupInvocationId": "12345",
                    "TestCaseInvocationId": "c1",
                    "TestCaseName": "check1",
                },
                {
                    "TestGroupInvocationId": "12345",
                    "TestCaseInvocationId": "c2",
                    "TestCaseName": "check2",
                },
            ],
            "telemetry_data_destination": "azureloganalytics",
            "laws_workspace_id": "workspace_id",
            "laws_shared_key": base64.b64encode(b"shared_key").decode("utf-8"),
            "telemetry_table_name": "telemetry_table",
            "adx_database_name": "adx_database",
            "adx_cluster_fqdn": "adx_cluster",
            "adx_client_id": "adx_client",
            "workspace_directory": "/tmp",
        }

    @pytest.fixture
    def telemetry_data_sender(self, module_params):
        """
        Fixture for creating a TelemetryDataSender instance.

        :param module_params: Sample module parameters.
        :type module_params: dict
        :return: TelemetryDataSender instance.
        :rtype: TelemetryDataSender
        """
        return TelemetryDataSender(module_params)

    @pytest.fixture
    def telemetry_data_sender_adx(self, module_params_adx):
        """
        Fixture for creating a TelemetryDataSender instance.

        :param module_params_adx: Sample module parameters.
        :type module_params_adx: dict
        :return: TelemetryDataSender instance.
        :rtype: TelemetryDataSender
        """
        return TelemetryDataSender(module_params_adx)

    def test_send_telemetry_data_to_azuredataexplorer(self, mocker, telemetry_data_sender):
        """
        Test the send_telemetry_data_to_azuredataexplorer method.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: _azure.kusto.ingest.QueuedIngestClient
        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        mock_kusto = mocker.patch("azure.kusto.ingest.QueuedIngestClient.ingest_from_dataframe")
        mock_kusto.return_value = "response"

        response = telemetry_data_sender.send_telemetry_data_to_azuredataexplorer(
            telemetry_json_data=json.dumps({"key": "value"})
        )
        assert response == "response"

    def test_send_telemetry_data_to_azureloganalytics(self, mocker, telemetry_data_sender):
        """
        Test the send_telemetry_data_to_azureloganalytics method.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: _azure.kusto.ingest.QueuedIngestClient
        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        mock_requests = mocker.patch("requests.post")
        mock_requests.return_value.status_code = 200

        response = telemetry_data_sender.send_telemetry_data_to_azureloganalytics(
            telemetry_json_data=json.dumps({"key": "value"})
        )
        assert response.status_code == 200

    def test_validate_params(self, telemetry_data_sender):
        """
        Test the validate_params method.

        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        assert telemetry_data_sender.validate_params() is True

    def test_validate_params_adx(self, telemetry_data_sender_adx):
        """
        Test the validate_params method for ADX.

        :param telemetry_data_sender_adx: TelemetryDataSender instance.
        :type telemetry_data_sender_adx: TelemetryDataSender
        """
        assert telemetry_data_sender_adx.validate_params() is True

    def test_write_log_file(self, mocker, telemetry_data_sender):
        """
        Test the write_log_file method.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        mock_open = mocker.patch("builtins.open", mocker.mock_open())
        telemetry_data_sender.write_log_file()
        mock_open.assert_called_once_with("/tmp/logs/12345.log", "a", encoding="utf-8")

    def test_write_log_file_with_list_payload(self, mocker, module_params_list):
        """
        Ensure write_log_file handles list payloads and writes each entry on its own line.
        This is critical because render_html_report expects newline-delimited JSON.
        """
        sender = TelemetryDataSender(module_params_list)
        mock_file = mocker.mock_open()
        mocker.patch("builtins.open", mock_file)
        mocker.patch("os.makedirs")
        sender.write_log_file()

        mock_file.assert_called_once_with("/tmp/logs/12345.log", "a", encoding="utf-8")
        handle = mock_file()
        write_calls = handle.write.call_args_list
        assert (
            len(write_calls) == 4
        ), f"Expected 4 write calls (2 entries × 2), got {len(write_calls)}"
        import json

        json_writes = [call[0][0] for call in write_calls if call[0][0] != "\n"]
        assert len(json_writes) == 2, "Should have 2 JSON entries"
        for json_str in json_writes:
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict), "Each line should be a dict, not a list"
            assert "TestGroupInvocationId" in parsed

    def test_validate_params_accepts_list_payload(self, module_params_list):
        """
        validate_params should return True for list payloads when required params exist.
        """
        sender = TelemetryDataSender(module_params_list)
        assert sender.validate_params() is True

    def test_send_telemetry_data_with_list_calls_laws(self, mocker, module_params_list):
        """
        When provided a list payload and LAWS destination, ensure the module calls requests.post.
        """
        sender = TelemetryDataSender(module_params_list)
        mock_validate = mocker.patch.object(sender, "validate_params")
        mock_validate.return_value = True
        mock_post = mocker.patch("requests.post")
        mock_post.return_value.status_code = 200

        sender.send_telemetry_data()
        assert mock_post.call_count == 1

    def test_fetch_laws_shared_key_success(self, mocker, telemetry_data_sender):
        """
        Test successful shared key retrieval using Azure SDK per Microsoft documentation.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        mock_credential = mocker.patch("src.modules.send_telemetry_data.DefaultAzureCredential")
        mock_credential.return_value = mocker.Mock()
        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client

        mock_response = mocker.Mock()
        mock_response.primary_shared_key = "fetched_key_abc"
        mock_client.shared_keys.get_shared_keys.return_value = mock_response

        key = telemetry_data_sender._fetch_laws_shared_key()
        assert key == "fetched_key_abc"
        mock_client.shared_keys.get_shared_keys.assert_called_once_with(
            resource_group_name="rg-test", workspace_name="ws-test"
        )

    def test_fetch_laws_shared_key_missing_subscription_id(self, mocker, telemetry_data_sender):
        """
        Test that missing subscription_id raises ValueError.
        """
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        with pytest.raises(ValueError, match="laws_subscription_id"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_missing_resource_group(self, mocker, telemetry_data_sender):
        """
        Test that missing resource_group raises ValueError.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        with pytest.raises(ValueError, match="laws_resource_group"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_missing_workspace_name(self, mocker, telemetry_data_sender):
        """
        Test that missing workspace_name raises ValueError.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"

        with pytest.raises(ValueError, match="laws_workspace_name"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_credential_failure(self, mocker, telemetry_data_sender):
        """
        Test that DefaultAzureCredential failure is handled properly.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        mock_credential = mocker.patch("src.modules.send_telemetry_data.DefaultAzureCredential")
        mock_credential.side_effect = Exception("Credential acquisition failed")

        with pytest.raises(Exception, match="Credential acquisition failed"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_api_call_failure(self, mocker, telemetry_data_sender):
        """
        Test that API call failure is handled properly.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        mock_credential = mocker.patch("src.modules.send_telemetry_data.DefaultAzureCredential")
        mock_credential.return_value = mocker.Mock()

        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client
        mock_client.shared_keys.get_shared_keys.side_effect = Exception("API call failed")

        with pytest.raises(Exception, match="API call failed"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_no_primary_key_in_response(self, mocker, telemetry_data_sender):
        """
        Test that missing primary_shared_key in response raises ValueError.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        mock_credential = mocker.patch("src.modules.send_telemetry_data.DefaultAzureCredential")
        mock_credential.return_value = mocker.Mock()

        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client
        mock_response = mocker.Mock()
        mock_response.primary_shared_key = None
        mock_client.shared_keys.get_shared_keys.return_value = mock_response

        with pytest.raises(ValueError, match="Primary shared key not found"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_empty_key_in_response(self, mocker, telemetry_data_sender):
        """
        Test that empty primary_shared_key in response raises ValueError.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"

        mock_credential = mocker.patch("src.modules.send_telemetry_data.DefaultAzureCredential")
        mock_credential.return_value = mocker.Mock()

        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client
        mock_response = mocker.Mock()
        mock_response.primary_shared_key = ""
        mock_client.shared_keys.get_shared_keys.return_value = mock_response

        with pytest.raises(ValueError, match="Primary shared key not found"):
            telemetry_data_sender._fetch_laws_shared_key()

    def test_fetch_laws_shared_key_with_user_assigned_identity(self, mocker, telemetry_data_sender):
        """
        Test that user-assigned managed identity is used when client_id is provided.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"
        telemetry_data_sender.module_params["user_assigned_identity_client_id"] = (
            "user-mi-client-id"
        )

        mock_mi_credential = mocker.patch(
            "src.modules.send_telemetry_data.ManagedIdentityCredential"
        )
        mock_mi_credential.return_value = mocker.Mock()
        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client

        mock_response = mocker.Mock()
        mock_response.primary_shared_key = "fetched_key_with_user_mi"
        mock_client.shared_keys.get_shared_keys.return_value = mock_response

        key = telemetry_data_sender._fetch_laws_shared_key()
        mock_mi_credential.assert_called_once_with(client_id="user-mi-client-id")
        assert key == "fetched_key_with_user_mi"

    def test_fetch_laws_shared_key_empty_user_assigned_identity_uses_default(
        self, mocker, telemetry_data_sender
    ):
        """
        Test that DefaultAzureCredential is used when user_assigned_identity_client_id is empty string.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"
        telemetry_data_sender.module_params["user_assigned_identity_client_id"] = ""
        mock_default_credential = mocker.patch(
            "src.modules.send_telemetry_data.DefaultAzureCredential"
        )
        mock_default_credential.return_value = mocker.Mock()
        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client

        mock_response = mocker.Mock()
        mock_response.primary_shared_key = "fetched_key_default"
        mock_client.shared_keys.get_shared_keys.return_value = mock_response

        key = telemetry_data_sender._fetch_laws_shared_key()
        mock_default_credential.assert_called_once()
        assert key == "fetched_key_default"

    def test_fetch_laws_shared_key_whitespace_user_assigned_identity_uses_default(
        self, mocker, telemetry_data_sender
    ):
        """
        Test that DefaultAzureCredential is used when user_assigned_identity_client_id is whitespace.
        """
        telemetry_data_sender.module_params["laws_subscription_id"] = "sub123"
        telemetry_data_sender.module_params["laws_resource_group"] = "rg-test"
        telemetry_data_sender.module_params["laws_workspace_name"] = "ws-test"
        telemetry_data_sender.module_params["user_assigned_identity_client_id"] = "   "
        mock_default_credential = mocker.patch(
            "src.modules.send_telemetry_data.DefaultAzureCredential"
        )
        mock_default_credential.return_value = mocker.Mock()
        mock_client_class = mocker.patch(
            "src.modules.send_telemetry_data.LogAnalyticsManagementClient"
        )
        mock_client = mocker.Mock()
        mock_client_class.return_value = mock_client

        mock_response = mocker.Mock()
        mock_response.primary_shared_key = "fetched_key_default"
        mock_client.shared_keys.get_shared_keys.return_value = mock_response

        key = telemetry_data_sender._fetch_laws_shared_key()
        mock_default_credential.assert_called_once()
        assert key == "fetched_key_default"

    def test_validate_params_auto_fetches_shared_key(self, mocker):
        """
        Test that validate_params auto-fetches shared key when not provided.
        """
        params = {
            "test_group_json_data": {"TestGroupInvocationId": "12345"},
            "telemetry_data_destination": "azureloganalytics",
            "laws_workspace_id": "workspace_id",
            "laws_subscription_id": "sub123",
            "laws_resource_group": "rg-test",
            "laws_workspace_name": "ws-test",
            "telemetry_table_name": "telemetry_table",
            "workspace_directory": "/tmp",
        }
        sender = TelemetryDataSender(params)

        mock_fetch = mocker.patch.object(sender, "_fetch_laws_shared_key")
        mock_fetch.return_value = "auto_fetched_key"

        result = sender.validate_params()
        assert result is True
        assert sender.module_params["laws_shared_key"] == "auto_fetched_key"
        mock_fetch.assert_called_once()

    def test_send_telemetry_data(self, mocker, telemetry_data_sender):
        """
        Test the send_telemetry_data method.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        mock_validate_params = mocker.patch.object(telemetry_data_sender, "validate_params")
        mock_validate_params.return_value = True
        mock_send_telemetry_data_to_azureloganalytics = mocker.patch.object(
            telemetry_data_sender, "send_telemetry_data_to_azureloganalytics"
        )
        mock_send_telemetry_data_to_azureloganalytics.return_value = "response"

        telemetry_data_sender.send_telemetry_data()
        assert telemetry_data_sender.result["status"] == "PASSED"

    def test_get_result(self, telemetry_data_sender):
        """
        Test the get_result method.

        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        result = telemetry_data_sender.get_result()
        assert "start" in result
        assert "end" in result

    def test_main_method(self, monkeypatch):
        """
        Test the main function of the send_telemetry_data module.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class to simulate AnsibleModule behavior.
            """

            def __init__(self, *args, **kwargs):
                self.params = {
                    "test_group_json_data": {"TestGroupInvocationId": "12345"},
                    "telemetry_data_destination": "azureloganalyticss",
                    "laws_workspace_id": "workspace_id",
                    "laws_shared_key": base64.b64encode(b"shared_key").decode("utf-8"),
                    "telemetry_table_name": "telemetry_table",
                    "adx_database_name": "adx_database",
                    "adx_cluster_fqdn": "adx_cluster",
                    "adx_client_id": "adx_client",
                    "workspace_directory": "/tmp",
                }

            def exit_json(self, **kwargs):
                mock_result.update(kwargs)

        mock_ansible_module = MockAnsibleModule(
            argument_spec={},
            supports_check_mode=False,
        )
        monkeypatch.setattr(
            "src.modules.send_telemetry_data.AnsibleModule",
            lambda *args, **kwargs: mock_ansible_module,
        )

        main()

        assert mock_result["status"] == "PASSED"

    @pytest.fixture
    def base_entry(self):
        """Sample base telemetry entry for parameter expansion tests."""
        return {
            "TestCaseInvocationId": "HA-HANA-001",
            "TestCaseStartTime": "2026-01-07T10:00:00",
            "TestCaseEndTime": "2026-01-07T10:00:01",
            "TestCaseStatus": "INFO",
            "TestCaseName": "HANA Cluster Configuration",
            "TestCaseDescription": "Check HANA cluster parameters",
            "TestGroupInvocationId": "group-123",
            "TestGroupStartTime": "2026-01-07T09:00:00",
            "TestGroupName": "ConfigurationChecks",
            "OsVersion": "SUSE 15.4",
            "TestCaseMessage": "Actual=config Expected=",
            "DurationSeconds": "1",
            "StorageType": "ANF",
            "PackageVersions": "{}",
            "Tags": "ha,db",
            "TestExecutionStartTime": "2026-01-07T10:00:00",
            "TestExecutionEndTime": "2026-01-07T10:00:01",
            "TestCaseHostname": "host01",
            "TestCaseLogMessagesFromSap": "{}",
        }

    @pytest.fixture
    def module_params_simple(self):
        """Simple module params for parameter expansion tests."""
        return {
            "test_group_json_data": [],
            "telemetry_data_destination": "azureloganalytics",
            "workspace_directory": "/tmp",
        }

    def test_expand_no_parameters(self, module_params_simple, base_entry):
        """Test that entries without parameters are kept as-is."""
        entry_no_params = base_entry.copy()
        entry_no_params["TestCaseDetails"] = json.dumps({"message": "No params"})

        module_params_simple["test_group_json_data"] = [entry_no_params]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 1
        assert result[0]["TestCaseInvocationId"] == "HA-HANA-001"

    def test_expand_with_parameters(self, module_params_simple, base_entry):
        """Test that entries with parameters are expanded correctly."""
        details = {
            "parameters": [
                {
                    "name": "stonith-enabled",
                    "category": "CRM_CONFIG",
                    "value": "true",
                    "expected_value": "true",
                    "status": "PASSED",
                },
                {
                    "name": "migration-threshold",
                    "category": "RSC_DEFAULTS",
                    "value": "5000",
                    "expected_value": "5000",
                    "status": "PASSED",
                },
            ]
        }

        entry_with_params = base_entry.copy()
        entry_with_params["TestCaseDetails"] = json.dumps(details)

        module_params_simple["test_group_json_data"] = [entry_with_params]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 2
        assert result[0]["TestCaseInvocationId"] == "HA-HANA-001-CRM_CONFIG"
        assert result[0]["TestCaseName"] == "stonith-enabled"
        assert result[0]["TestCaseStatus"] == "PASSED"
        assert result[0]["TestCaseMessage"] == "Actual=true Expected=true"

        assert result[1]["TestCaseInvocationId"] == "HA-HANA-001-RSC_DEFAULTS"
        assert result[1]["TestCaseName"] == "migration-threshold"

    def test_expand_skipped_parameters_filtered(self, module_params_simple, base_entry):
        """Test that SKIPPED parameters are filtered out."""
        details = {
            "parameters": [
                {
                    "name": "param1",
                    "category": "CRM_CONFIG",
                    "value": "val1",
                    "expected_value": "val1",
                    "status": "PASSED",
                },
                {
                    "name": "param2",
                    "category": "CRM_CONFIG",
                    "value": "val2",
                    "expected_value": "val2",
                    "status": "SKIPPED",
                },
                {
                    "name": "param3",
                    "category": "RSC_DEFAULTS",
                    "value": "val3",
                    "expected_value": "val3",
                    "status": "WARNING",
                },
            ]
        }

        entry_with_params = base_entry.copy()
        entry_with_params["TestCaseDetails"] = json.dumps(details)

        module_params_simple["test_group_json_data"] = [entry_with_params]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 2
        assert result[0]["TestCaseName"] == "param1"
        assert result[1]["TestCaseName"] == "param3"
        assert all(r["TestCaseName"] != "param2" for r in result)

    def test_expand_empty_parameters_list(self, module_params_simple, base_entry):
        """Test that entries with empty parameters list are kept as-is."""
        details = {"parameters": []}

        entry_empty_params = base_entry.copy()
        entry_empty_params["TestCaseDetails"] = json.dumps(details)

        module_params_simple["test_group_json_data"] = [entry_empty_params]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 1
        assert result[0]["TestCaseInvocationId"] == "HA-HANA-001"

    def test_expand_mixed_entries(self, module_params_simple, base_entry):
        """Test batch with mixed parameter and non-parameter entries."""
        entry1 = base_entry.copy()
        entry1["TestCaseInvocationId"] = "CHECK-001"
        entry1["TestCaseDetails"] = json.dumps({"message": "Simple check"})

        entry2 = base_entry.copy()
        entry2["TestCaseInvocationId"] = "HA-HANA-001"
        entry2["TestCaseDetails"] = json.dumps(
            {
                "parameters": [
                    {
                        "name": "param1",
                        "category": "CRM_CONFIG",
                        "value": "val1",
                        "expected_value": "val1",
                        "status": "PASSED",
                    },
                    {
                        "name": "param2",
                        "category": "RSC_DEFAULTS",
                        "value": "val2",
                        "expected_value": "val2",
                        "status": "WARNING",
                    },
                ]
            }
        )

        entry3 = base_entry.copy()
        entry3["TestCaseInvocationId"] = "CHECK-002"
        entry3["TestCaseDetails"] = json.dumps({"another": "check"})

        module_params_simple["test_group_json_data"] = [entry1, entry2, entry3]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 4
        assert result[0]["TestCaseInvocationId"] == "CHECK-001"
        assert result[1]["TestCaseInvocationId"] == "HA-HANA-001-CRM_CONFIG"
        assert result[2]["TestCaseInvocationId"] == "HA-HANA-001-RSC_DEFAULTS"
        assert result[3]["TestCaseInvocationId"] == "CHECK-002"

    def test_expand_single_dict_entry(self, module_params_simple, base_entry):
        """Test that single dict (non-list) is handled correctly."""
        details = {
            "parameters": [
                {
                    "name": "test-param",
                    "category": "TEST",
                    "value": "value",
                    "expected_value": "value",
                    "status": "PASSED",
                }
            ]
        }

        entry_with_params = base_entry.copy()
        entry_with_params["TestCaseDetails"] = json.dumps(details)
        module_params_simple["test_group_json_data"] = entry_with_params
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 1
        assert result[0]["TestCaseInvocationId"] == "HA-HANA-001-TEST"
        assert result[0]["TestCaseName"] == "test-param"

    def test_expand_parameter_without_status(self, module_params_simple, base_entry):
        """Test parameters without status field are included."""
        details = {
            "parameters": [
                {
                    "name": "param-no-status",
                    "category": "CRM_CONFIG",
                    "value": "value",
                    "expected_value": "value",
                }
            ]
        }

        entry_with_params = base_entry.copy()
        entry_with_params["TestCaseDetails"] = json.dumps(details)

        module_params_simple["test_group_json_data"] = [entry_with_params]
        sender = TelemetryDataSender(module_params_simple)
        result = sender.result["telemetry_data"]
        assert len(result) == 1
        assert result[0]["TestCaseName"] == "param-no-status"
        assert result[0]["TestCaseStatus"] == "INFO"

    def test_expand_preserves_common_fields(self, module_params_simple, base_entry):
        """Test that common fields are preserved in expanded entries."""
        details = {
            "parameters": [
                {
                    "name": "param1",
                    "category": "CRM_CONFIG",
                    "value": "val1",
                    "expected_value": "val1",
                    "status": "PASSED",
                }
            ]
        }

        entry_with_params = base_entry.copy()
        entry_with_params["TestCaseDetails"] = json.dumps(details)

        module_params_simple["test_group_json_data"] = [entry_with_params]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        expanded = result[0]
        assert expanded["TestGroupInvocationId"] == "group-123"
        assert expanded["TestGroupName"] == "ConfigurationChecks"
        assert expanded["OsVersion"] == "SUSE 15.4"
        assert expanded["TestCaseHostname"] == "host01"
        assert expanded["StorageType"] == "ANF"
        assert expanded["DurationSeconds"] == "1"

    def test_expand_invalid_json_details(self, module_params_simple, base_entry):
        """Test that invalid JSON in TestCaseDetails is handled gracefully."""
        entry_invalid_json = base_entry.copy()
        entry_invalid_json["TestCaseDetails"] = "not valid json {{"

        module_params_simple["test_group_json_data"] = [entry_invalid_json]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 1
        assert result[0]["TestCaseInvocationId"] == "HA-HANA-001"

    def test_expand_large_parameter_list(self, module_params_simple, base_entry):
        """Test expansion with large number of parameters."""
        parameters = [
            {
                "name": f"param{i}",
                "category": f"CATEGORY{i % 3}",
                "value": f"val{i}",
                "expected_value": f"val{i}",
                "status": "PASSED" if i % 2 == 0 else "WARNING",
            }
            for i in range(50)
        ]

        details = {"parameters": parameters}
        entry_with_params = base_entry.copy()
        entry_with_params["TestCaseDetails"] = json.dumps(details)

        module_params_simple["test_group_json_data"] = [entry_with_params]
        sender = TelemetryDataSender(module_params_simple)

        result = sender.result["telemetry_data"]
        assert len(result) == 50
        for i, expanded in enumerate(result):
            assert expanded["TestCaseName"] == f"param{i}"
            assert "CATEGORY" in expanded["TestCaseInvocationId"]

    def test_is_check_results_format_true(self, module_params_simple):
        """Test detection of check results format."""
        check_results = [
            {
                "id": "check_001",
                "name": "Test Check",
                "check": {"id": "check_001", "name": "Test Check"},
                "status": "PASSED",
                "hostname": "host01",
                "timestamp": "2024-01-01 10:00:00",
            }
        ]

        sender = TelemetryDataSender(module_params_simple)
        assert sender._is_check_results_format(check_results) is True

    def test_is_check_results_format_false_telemetry(self, module_params_simple):
        """Test detection rejects telemetry format."""
        telemetry_data = [
            {
                "TestCaseInvocationId": "check_001",
                "TestCaseStatus": "PASSED",
                "TestGroupName": "ConfigurationChecks",
            }
        ]

        sender = TelemetryDataSender(module_params_simple)
        assert sender._is_check_results_format(telemetry_data) is False

    def test_is_check_results_format_invalid_data(self, module_params_simple):
        """Test detection with invalid data."""
        sender = TelemetryDataSender(module_params_simple)
        assert sender._is_check_results_format("not a list or dict") is False
        assert sender._is_check_results_format([]) is False
        assert sender._is_check_results_format([123, 456]) is False

    def test_build_telemetry_batch_from_results(self):
        """Test building telemetry batch from check results."""
        check_results = [
            {
                "id": "check_001",
                "name": "HA Config Check",
                "check": {
                    "id": "check_001",
                    "name": "HA Config Check",
                    "description": "Verify HA configuration",
                },
                "status": "PASSED",
                "hostname": "host01",
                "timestamp": "2024-01-01 10:00:00",
                "actual_value": "true",
                "expected_value": "true",
                "execution_time": 5,
                "details": {"info": "check passed"},
            },
            {
                "id": "check_002",
                "name": "Network Check",
                "check": {"id": "check_002", "name": "Network Check"},
                "status": "SKIPPED",
                "hostname": "host02",
                "timestamp": "2024-01-01 10:01:00",
            },
        ]

        module_params = {
            "test_group_json_data": check_results,
            "telemetry_data_destination": "none",
            "workspace_directory": "/tmp",
            "common_vars": {
                "test_group_invocation_id": "group123",
                "group_start_time": "2024-01-01 09:00:00",
                "group_name": "ConfigurationChecks",
                "NFS_provider": "ANF",
                "package_versions": "v1.0",
                "execution_tags": "prod",
            },
            "system_context_map": {
                "host01": {
                    "os_type": "SLES",
                    "os_version": "15.4",
                    "database_type": "HANA",
                    "database_sid": "HDB",
                    "sap_sid": "S4H",
                    "high_availability_agent": "fence_azure_arm",
                    "role": "Database",
                }
            },
        }

        sender = TelemetryDataSender(module_params)
        result = sender.result["telemetry_data"]
        assert len(result) == 1

        entry = result[0]
        assert entry["TestCaseInvocationId"] == "check_001"
        assert entry["TestCaseStatus"] == "PASSED"
        assert entry["TestCaseName"] == "HA Config Check"
        assert entry["TestCaseDescription"] == "Verify HA configuration"
        assert entry["TestGroupInvocationId"] == "group123"
        assert entry["TestGroupName"] == "ConfigurationChecks"
        assert entry["OsVersion"] == "SLES 15.4"
        assert "Actual=true" in entry["TestCaseMessage"]
        assert "Expected=true" in entry["TestCaseMessage"]
        assert entry["DurationSeconds"] == 5
        assert entry["StorageType"] == "ANF"
        assert entry["TestCaseHostname"] == "host01"
        assert entry["DBType"] == "HANA"
        assert entry["DbSid"] == "HDB"
        assert entry["SapSid"] == "S4H"
        assert entry["DbFencingType"] == "fence_azure_arm"
        assert entry["ScsFencingType"] == "fence_azure_arm"

    def test_build_telemetry_batch_with_parameters(self):
        """Test building telemetry batch from check results with parameters."""
        check_results = [
            {
                "id": "check_ha_params",
                "name": "HA Parameters",
                "check": {"id": "check_ha_params", "name": "HA Parameters"},
                "status": "INFO",
                "hostname": "host01",
                "timestamp": "2024-01-01 10:00:00",
                "details": {
                    "parameters": [
                        {
                            "name": "stonith-enabled",
                            "category": "STONITH",
                            "value": "true",
                            "expected_value": "true",
                            "status": "PASSED",
                        },
                        {
                            "name": "stonith-timeout",
                            "category": "STONITH",
                            "value": "900",
                            "expected_value": "900",
                            "status": "PASSED",
                        },
                    ]
                },
            }
        ]

        module_params = {
            "test_group_json_data": check_results,
            "telemetry_data_destination": "none",
            "workspace_directory": "/tmp",
            "common_vars": {
                "test_group_invocation_id": "group123",
                "group_start_time": "2024-01-01 09:00:00",
                "group_name": "ConfigurationChecks",
            },
            "system_context_map": {
                "host01": {
                    "os_type": "SLES",
                    "os_version": "15.4",
                }
            },
        }

        sender = TelemetryDataSender(module_params)
        result = sender.result["telemetry_data"]
        assert len(result) == 2
        assert result[0]["TestCaseName"] == "stonith-enabled"
        assert "STONITH" in result[0]["TestCaseInvocationId"]
        assert result[0]["TestCaseStatus"] == "PASSED"
        assert "Actual=true" in result[0]["TestCaseMessage"]
        assert result[1]["TestCaseName"] == "stonith-timeout"
        assert "STONITH" in result[1]["TestCaseInvocationId"]
        assert result[1]["TestCaseStatus"] == "PASSED"
        assert "Actual=900" in result[1]["TestCaseMessage"]
