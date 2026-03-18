# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the render_html_report module.
"""

import os
import pytest
from src.modules.render_html_report import (
    HTMLReportRenderer,
    main,
)


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
            "framework_version": "1.0.0",
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
            framework_version=module_params["framework_version"],
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
            mocker.mock_open(read_data="""
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
"""),
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
                    "framework_version": "1.0.0",
                    "execution_log_path": "",
                }
                self.check_mode = False

            def exit_json(self, **kwargs):
                mock_result.update(kwargs)

        monkeypatch.setattr("src.modules.render_html_report.AnsibleModule", MockAnsibleModule)
        main()
        assert mock_result["status"] == "PASSED"

    def test_read_execution_log_returns_content(self, tmp_path):
        """
        Test that read_execution_log reads an existing log file.

        :param tmp_path: Temporary directory provided by pytest.
        :type tmp_path: pathlib.Path
        """
        log_file = tmp_path / "execution.log"
        log_content = "TASK [setup] ***\\nok: [host1]\\nTASK [test] ***\\nchanged: [host1]"
        log_file.write_text(log_content)

        renderer = HTMLReportRenderer(
            test_group_invocation_id="test-id",
            test_group_name="test_group",
            report_template="",
            workspace_directory=str(tmp_path),
            execution_log_path=str(log_file),
        )
        assert renderer.read_execution_log() == log_content

    def test_read_execution_log_missing_file(self):
        """
        Test that read_execution_log returns empty string for missing file.
        """
        renderer = HTMLReportRenderer(
            test_group_invocation_id="test-id",
            test_group_name="test_group",
            report_template="",
            workspace_directory="/tmp",
            execution_log_path="/nonexistent/path/execution.log",
        )
        assert renderer.read_execution_log() == ""

    def test_read_execution_log_empty_path(self):
        """
        Test that read_execution_log returns empty string when no path set.
        """
        renderer = HTMLReportRenderer(
            test_group_invocation_id="test-id",
            test_group_name="test_group",
            report_template="",
            workspace_directory="/tmp",
        )
        assert renderer.read_execution_log() == ""

    def test_render_report_includes_execution_log(self, tmp_path):
        """
        Test that render_report passes execution log to the template.

        :param tmp_path: Temporary directory provided by pytest.
        :type tmp_path: pathlib.Path
        """
        log_file = tmp_path / "execution.log"
        log_file.write_text("TASK [test] ***\\nok: [host1]")

        template = (
            "{% if execution_log %}LOG:{{ execution_log }}{% endif %}"
            "RESULTS:{{ test_case_results | length }}"
        )
        renderer = HTMLReportRenderer(
            test_group_invocation_id="abc",
            test_group_name="grp",
            report_template=template,
            workspace_directory=str(tmp_path),
            execution_log_path=str(log_file),
        )
        renderer.render_report([{"test": "data"}])

        report_path = tmp_path / "quality_assurance" / "grp_abc.html"
        content = report_path.read_text()
        assert "LOG:TASK [test]" in content
        assert "RESULTS:1" in content

    def test_render_report_without_execution_log(self, tmp_path):
        """
        Test that render_report works without execution log.

        :param tmp_path: Temporary directory provided by pytest.
        :type tmp_path: pathlib.Path
        """
        template = (
            "{% if execution_log %}LOG:{{ execution_log }}{% endif %}"
            "RESULTS:{{ test_case_results | length }}"
        )
        renderer = HTMLReportRenderer(
            test_group_invocation_id="abc",
            test_group_name="grp",
            report_template=template,
            workspace_directory=str(tmp_path),
        )
        renderer.render_report([])

        report_path = tmp_path / "quality_assurance" / "grp_abc.html"
        content = report_path.read_text()
        assert "LOG:" not in content
        assert "RESULTS:0" in content

    def test_read_execution_log_strips_ansi_codes(self, tmp_path):
        """
        Test that ANSI escape sequences are stripped from execution log.

        :param tmp_path: Temporary directory provided by pytest.
        :type tmp_path: pathlib.Path
        """
        log_file = tmp_path / "execution.log"
        log_file.write_text("\x1b[0;32mok: [host1]\x1b[0m\n\x1b[0;31mfailed: [host2]\x1b[0m")

        renderer = HTMLReportRenderer(
            test_group_invocation_id="test-id",
            test_group_name="test_group",
            report_template="",
            workspace_directory=str(tmp_path),
            execution_log_path=str(log_file),
        )
        result = renderer.read_execution_log()
        assert "\x1b[" not in result
        assert "ok: [host1]" in result
        assert "failed: [host2]" in result

    def test_read_execution_log_truncates_large_files(self, tmp_path):
        """
        Test that logs exceeding the size limit are truncated.

        :param tmp_path: Temporary directory provided by pytest.
        :type tmp_path: pathlib.Path
        """
        log_file = tmp_path / "large_execution.log"
        log_file.write_text("X" * (2 * 1024 * 1024 + 1000))

        renderer = HTMLReportRenderer(
            test_group_invocation_id="test-id",
            test_group_name="test_group",
            report_template="",
            workspace_directory=str(tmp_path),
            execution_log_path=str(log_file),
        )
        result = renderer.read_execution_log()
        assert "--- Log truncated" in result
        assert len(result) < 2 * 1024 * 1024 + 200

    def test_render_report_html_escapes_execution_log(self, tmp_path):
        """
        Test that HTML special characters in execution log are escaped.

        :param tmp_path: Temporary directory provided by pytest.
        :type tmp_path: pathlib.Path
        """
        log_file = tmp_path / "execution.log"
        log_file.write_text('<script>alert("xss")</script> & <b>bold</b>')

        template = "{% if execution_log %}<pre>{{ execution_log | e }}</pre>{% endif %}"
        renderer = HTMLReportRenderer(
            test_group_invocation_id="abc",
            test_group_name="grp",
            report_template=template,
            workspace_directory=str(tmp_path),
            execution_log_path=str(log_file),
        )
        renderer.render_report([])

        report_path = tmp_path / "quality_assurance" / "grp_abc.html"
        content = report_path.read_text()
        assert "<script>" not in content
        assert "&lt;script&gt;" in content
        assert "&amp;" in content
