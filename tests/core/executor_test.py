# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for AnsibleExecutor."""

import json
import subprocess
from pathlib import Path
import pytest
from pytest_mock import MockerFixture
from src.core.execution.executor import (
    AnsibleExecutor,
    _describe_exit_code,
    _tail_file,
)


def _make_mock_popen(
    mocker: MockerFixture,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
):
    """Create a mock mimicking subprocess.Popen."""
    proc = mocker.MagicMock()
    proc.returncode = returncode
    proc.pid = 12345
    proc.wait.return_value = returncode
    proc.communicate.return_value = (stdout, stderr)
    return proc


class TestAnsibleExecutor:
    """Tests for the AnsibleExecutor module."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> AnsibleExecutor:
        """
        Create executor with a valid playbook stub.
        """
        playbook_dir = tmp_path / "src"
        playbook_dir.mkdir()
        (playbook_dir / "ansible.cfg").write_text("")
        playbook = playbook_dir / "playbook_00_configuration_checks.yml"
        playbook.write_text("---\n- hosts: all\n")
        return AnsibleExecutor(playbook_dir=playbook_dir)

    @pytest.fixture
    def executor_with_input_api(self, tmp_path: Path) -> AnsibleExecutor:
        """
        Create executor with input-api.yaml for filter tests.
        """
        playbook_dir = tmp_path / "src"
        playbook_dir.mkdir(exist_ok=True)
        (playbook_dir / "ansible.cfg").write_text("")
        playbook = playbook_dir / "playbook_00_ha_db_functional_tests.yml"
        playbook.write_text("---\n- hosts: all\n")
        vars_dir = playbook_dir / "vars"
        vars_dir.mkdir()
        (vars_dir / "input-api.yaml").write_text(
            "test_groups:\n"
            "  - name: HA_DB_HANA\n"
            "    test_cases:\n"
            "      - name: HA Config\n"
            "        task_name: ha-config\n"
            "        enabled: true\n"
            "      - name: Resource Migration\n"
            "        task_name: resource-migration\n"
            "        enabled: true\n"
            "      - name: Primary Node Crash\n"
            "        task_name: primary-node-crash\n"
            "        enabled: true\n"
        )
        return AnsibleExecutor(playbook_dir=playbook_dir)

    def test_zero_exit_code(self) -> None:
        """
        Verify exit code 0 description.
        """
        assert "code 0" in _describe_exit_code(0)

    def test_normal_failure_exit_code(self) -> None:
        """
        Verify non-signal failure description.
        """
        assert "code 2" in _describe_exit_code(2)

    def test_sigkill_decoded(self) -> None:
        """
        Verify SIGKILL is decoded as OOM/forced.
        """
        result = _describe_exit_code(-9)
        assert "SIGKILL" in result
        assert "OOM" in result or "forced" in result

    def test_sigterm_decoded(self) -> None:
        """
        Verify SIGTERM is decoded as container stop.
        """
        assert "SIGTERM" in _describe_exit_code(-15)

    def test_sigsegv_decoded(self) -> None:
        """
        Verify SIGSEGV is decoded as segfault.
        """
        result = _describe_exit_code(-11)
        assert "SIGSEGV" in result
        assert "segmentation" in result.lower()

    def test_sigabrt_decoded(self) -> None:
        """
        Verify SIGABRT is decoded.
        """
        assert "SIGABRT" in _describe_exit_code(-6)

    def test_unknown_signal_decoded(self) -> None:
        """
        Verify unknown signal number still produces output.
        """
        assert "signal" in _describe_exit_code(-99).lower()

    def test_sigkill_empty_stderr(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify SIGKILL with empty stderr produces useful msg.
        """
        mock_popen = mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
        )
        mock_popen.return_value = _make_mock_popen(
            mocker,
            returncode=-9,
        )
        result = executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
        )
        assert result["status"] == "failed"
        assert "SIGKILL" in result["error"]
        assert result["return_code"] == -9

    def test_stderr_preferred_over_signal_msg(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify stderr is used when available, not signal msg.
        """
        mock_popen = mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
        )
        mock_popen.return_value = _make_mock_popen(
            mocker,
            returncode=-11,
            stderr="fatal: SSH connection lost",
        )
        result = executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
        )
        assert result["status"] == "failed"
        assert "SSH connection lost" in result["error"]
        assert "SIGSEGV" not in result["error"]

    def test_stdout_fallback_when_no_stderr(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify last stdout is appended when stderr is empty.
        """
        mock_popen = mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
        )
        mock_popen.return_value = _make_mock_popen(
            mocker,
            returncode=-9,
            stdout="TASK [check_hana] ok\nTASK [fencing]",
        )
        result = executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
        )
        assert result["status"] == "failed"
        assert "SIGKILL" in result["error"]
        assert "last output" in result["error"]

    def test_tail_small_file(self, tmp_path: Path) -> None:
        """
        Reads entire file when smaller than max_chars.
        """
        f = tmp_path / "small.log"
        f.write_text("line1\nline2\n")
        assert _tail_file(f) == "line1\nline2"

    def test_tail_large_file_truncated(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Returns only last max_chars of a large file.
        """
        f = tmp_path / "big.log"
        f.write_text("A" * 5000)
        assert len(_tail_file(f, max_chars=100)) < 100

    def test_tail_missing_file(self, tmp_path: Path) -> None:
        """
        Returns empty string for missing file.
        """
        assert _tail_file(tmp_path / "missing.log") == ""

    def test_success_writes_log_file(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
        tmp_path: Path,
    ) -> None:
        """
        Verify successful run creates a log file.
        """
        log_file = tmp_path / "logs" / "job.log"

        def fake_popen(cmd, stdout, stderr, **kw):
            stdout.write("TASK [ok] ***\n")
            proc = mocker.MagicMock()
            proc.returncode = 0
            proc.pid = 99
            proc.wait.return_value = 0
            return proc

        mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
            side_effect=fake_popen,
        )
        result = executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
            log_file=log_file,
        )
        assert result["status"] == "success"
        assert log_file.exists()
        assert "TASK [ok]" in log_file.read_text()
        assert "stdout" not in result

    def test_failure_reads_tail_from_log(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
        tmp_path: Path,
    ) -> None:
        """
        Verify failed run includes log tail in error.
        """
        log_file = tmp_path / "logs" / "fail.log"

        def fake_popen(cmd, stdout, stderr, **kw):
            stdout.write("TASK [fatal error here]\n")
            proc = mocker.MagicMock()
            proc.returncode = 2
            proc.pid = 99
            proc.wait.return_value = 2
            return proc

        mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
            side_effect=fake_popen,
        )
        result = executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
            log_file=log_file,
        )
        assert result["status"] == "failed"
        assert "fatal error here" in result["error"]
        assert result["return_code"] == 2

    def test_no_log_file_uses_capture(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify no log_file falls back to in-memory capture.
        """
        mock_popen = mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
        )
        mock_popen.return_value = _make_mock_popen(
            mocker,
            returncode=0,
            stdout="output here",
        )
        result = executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
        )
        assert result["status"] == "success"
        assert "stdout" in result

    def test_terminate_unknown_job(
        self,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify terminate returns False if no process.
        """
        assert executor.terminate_process("no-such") is False

    def test_terminate_sends_sigterm(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify terminate sends SIGTERM to tracked process.
        """
        proc = mocker.MagicMock()
        proc.pid = 1001
        proc.wait.return_value = 0
        executor._processes["job-1"] = proc
        assert executor.terminate_process("job-1") is True
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once_with(timeout=5)

    def test_terminate_escalates_to_sigkill(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify SIGKILL sent when SIGTERM times out.
        """
        proc = mocker.MagicMock()
        proc.pid = 1002
        proc.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 5),
            0,
        ]
        executor._processes["job-2"] = proc

        assert executor.terminate_process("job-2") is True
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    def test_process_tracked_during_execution(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify job_id is registered in _processes during run.
        """
        captured_keys: list[list[str]] = []

        def fake_popen(cmd, **kw):
            proc = mocker.MagicMock()
            proc.returncode = 0
            proc.pid = 42

            def fake_communicate(**kw2):
                captured_keys.append(list(executor._processes.keys()))
                return ("ok", "")

            proc.communicate = fake_communicate
            return proc

        mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
            side_effect=fake_popen,
        )
        executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
            job_id="track-me",
        )
        assert "track-me" in captured_keys[0]
        assert "track-me" not in executor._processes

    def test_job_id_injected_as_extra_var(
        self,
        mocker: MockerFixture,
        executor: AnsibleExecutor,
    ) -> None:
        """
        Verify job_id is passed as Ansible extra var.
        """
        captured_cmd: list[str] = []

        def fake_popen(cmd, **kw):
            captured_cmd.extend(cmd)
            proc = mocker.MagicMock()
            proc.returncode = 0
            proc.pid = 42
            proc.communicate.return_value = ("", "")
            return proc

        mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
            side_effect=fake_popen,
        )
        executor.run_test(
            workspace_id="WS",
            test_id="t1",
            test_group="CONFIG_CHECKS",
            inventory_path="/fake/hosts",
            job_id="jid-123",
        )
        assert json.loads(captured_cmd[captured_cmd.index("-e") + 1])["job_id"] == "jid-123"

    def test_test_id_applies_filter(
        self,
        mocker: MockerFixture,
        executor_with_input_api: AnsibleExecutor,
    ) -> None:
        """
        Verify test_id filters test_groups so only the
        matching test case is enabled.
        """
        captured_cmd: list[str] = []

        def fake_popen(cmd, **kw):
            captured_cmd.extend(cmd)
            proc = mocker.MagicMock()
            proc.returncode = 0
            proc.pid = 42
            proc.communicate.return_value = ("", "")
            return proc

        mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
            side_effect=fake_popen,
        )
        executor_with_input_api.run_test(
            workspace_id="WS",
            test_id="resource-migration",
            test_group="HA_DB_HANA",
            inventory_path="/fake/hosts",
        )

        extra = json.loads(captured_cmd[captured_cmd.index("-e") + 1])
        assert "test_groups" in extra
        groups = extra["test_groups"]
        ha_group = next(g for g in groups if g["name"] == "HA_DB_HANA")
        enabled = [c["task_name"] for c in ha_group["test_cases"] if c.get("enabled")]
        assert enabled == ["resource-migration"]

    def test_empty_test_id_no_filter(
        self,
        mocker: MockerFixture,
        executor_with_input_api: AnsibleExecutor,
    ) -> None:
        """
        Verify empty test_id does NOT inject test_groups filter.
        """
        captured_cmd: list[str] = []

        def fake_popen(cmd, **kw):
            captured_cmd.extend(cmd)
            proc = mocker.MagicMock()
            proc.returncode = 0
            proc.pid = 42
            proc.communicate.return_value = ("", "")
            return proc

        mocker.patch(
            "src.core.execution.executor.subprocess.Popen",
            side_effect=fake_popen,
        )
        executor_with_input_api.run_test(
            workspace_id="WS",
            test_id="",
            test_group="HA_DB_HANA",
            inventory_path="/fake/hosts",
        )

        extra = json.loads(captured_cmd[captured_cmd.index("-e") + 1])
        assert "test_groups" not in extra
