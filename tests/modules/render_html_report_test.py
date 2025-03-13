# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the render_html_report module.
"""

import pytest
from src.modules.render_html_report import HTMLReportRenderer, main


class TestHTMLReportRenderer:
    """
    Test cases for the HTMLReportRenderer class.
    """

    @pytest.fixture
    def module_params(self):
        """
        Fixture for providing sample module parameters.

        :return: Sample module parameters.
        :rtype: dict
        """
        return {
            "test_group_invocation_id": "12345",
            "test_group_name": "test_group",
            "report_template": "report_template.html",
            "workspace_directory": "/tmp",
        }

    @pytest.fixture
    def html_report_renderer(self, module_params):
        """
        Fixture for creating an HTMLReportRenderer instance.

        :param module_params: Sample module parameters.
        :type module_params: dict
        :return: HTMLReportRenderer instance.
        :rtype: HTMLReportRenderer
        """
        return HTMLReportRenderer(
            module_params["test_group_invocation_id"],
            module_params["test_group_name"],
            module_params["report_template"],
            module_params["workspace_directory"],
        )

    def test_render_report(self, mocker, html_report_renderer):
        """
        Test the render_report method of the HTMLReportRenderer class.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param html_report_renderer: HTMLReportRenderer instance.
        :type html_report_renderer: HTMLReportRenderer
        """
        mock_open = mocker.patch(
            "builtins.open",
            mocker.mock_open(
                read_data="""
<!DOCTYPE html>
<html>
<head>
    <title>Test Report</title>
</head>
<body>
    <h1>Test Report</h1>
    <p>This is a test report.</p>
    <table>
        <tr>
            <td>Test 1</td>
            <td>Pass</td>
        </tr>
        <tr>
            <td>Test 2</td>
            <td>Fail</td>
        </tr>
    </table>
</body>
</html>
"""
            ),
        )

        html_report_renderer.render_report(
            [
                {"test_name": "Test 1", "test_result": "Pass"},
                {"test_name": "Test 2", "test_result": "Fail"},
            ]
        )
        mock_open.assert_called_with(
            "/tmp/quality_assurance/test_group_12345.html", "w", encoding="utf-8"
        )
        handle = mock_open()
        handle.write.assert_called()

    def test_main(self, monkeypatch):
        """
        Test the main function of the render_html_report module.

        :param monkeypatch: Monkeypatch fixture for mocking.
        :type monkeypatch: pytest.MonkeyPatch
        """
        mock_result = {}

        class MockAnsibleModule:
            """
            Mock class for Ansible  Module.
            """

            def __init__(self, argument_spec, supports_check_mode):
                self.params = {
                    "test_group_invocation_id": "12345",
                    "test_group_name": "test_group",
                    "report_template": "report_template.html",
                    "workspace_directory": "/tmp",
                }
                self.check_mode = False

            def exit_json(self, **kwargs):
                mock_result.update(kwargs)

        monkeypatch.setattr("src.modules.render_html_report.AnsibleModule", MockAnsibleModule)
        main()
        assert mock_result["status"] == "PASSED"
