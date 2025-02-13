# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the send_telemetry_data module.
"""

import base64
import json
import pytest
from src.modules.send_telemetry_data import TelemetryDataSender, main


@pytest.fixture
def module_params():
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
def module_params_adx():
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
def telemetry_data_sender(module_params):
    """
    Fixture for creating a TelemetryDataSender instance.

    :param module_params: Sample module parameters.
    :type module_params: dict
    :return: TelemetryDataSender instance.
    :rtype: TelemetryDataSender
    """
    return TelemetryDataSender(module_params)


@pytest.fixture
def telemetry_data_sender_adx(module_params_adx):
    """
    Fixture for creating a TelemetryDataSender instance.

    :param module_params_adx: Sample module parameters.
    :type module_params_adx: dict
    :return: TelemetryDataSender instance.
    :rtype: TelemetryDataSender
    """
    return TelemetryDataSender(module_params_adx)


class TestTelemetryDataSender:

    def test_send_telemetry_data_to_azuredataexplorer(self, mocker, telemetry_data_sender):
        """
        Test the send_telemetry_data_to_azuredataexplorer method.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: _azure.kusto.ingest.QueuedIngestClient
        :param telemetry_data_sender: TelemetryDataSender instance.
        :type telemetry_data_sender: TelemetryDataSender
        """
        mock_pandas = mocker.patch("pandas.DataFrame")
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
            def __init__(self, argument_spec, supports_check_mode):
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
