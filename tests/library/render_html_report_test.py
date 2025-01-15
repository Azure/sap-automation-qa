"""
Unit tests for the render_html_report module.
"""

import pytest
from ansible.module_utils.basic import AnsibleModule
from src.library.render_html_report import HTMLReportRenderer


@pytest.fixture
def module_params():
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
def html_report_renderer(module_params):
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


def test_render_report(mocker, html_report_renderer):
    """
    Test the render_report method.

    :param html_report_renderer: The HTMLReportRenderer instance.
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
