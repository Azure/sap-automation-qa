# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test executor interface and implementations.
"""

import json
import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any, Optional, Protocol
from src.module_utils.filter_tests import TestFilter
from src.core.observability import get_logger

logger = get_logger(__name__)


def _describe_exit_code(returncode: int) -> str:
    """Produce a human-readable description of a process exit code.

    :param returncode: Process exit code.
    :returns: Human-readable description.
    """
    if returncode >= 0:
        return f"Process exited with code {returncode}"
    sig_num = -returncode
    try:
        sig_name = signal.Signals(sig_num).name
    except ValueError:
        sig_name = f"signal {sig_num}"
    well_known: dict[int, str] = {
        signal.SIGKILL: "(likely OOM-killed or forced termination)",
        signal.SIGTERM: "(terminated — container stop or shutdown)",
        signal.SIGSEGV: "(segmentation fault)",
        signal.SIGABRT: "(aborted)",
    }
    detail = well_known.get(sig_num, "")
    return f"Process killed by {sig_name} {detail}".strip()


TEST_GROUP_PLAYBOOKS = {
    "CONFIG_CHECKS": "playbook_00_configuration_checks.yml",
    "HA_DB_HANA": "playbook_00_ha_db_functional_tests.yml",
    "HA_SCS": "playbook_00_ha_scs_functional_tests.yml",
    "HA_OFFLINE": "playbook_01_ha_offline_tests.yml",
}


def _tail_file(
    path: Path,
    max_chars: int = 2000,
) -> str:
    """Read the last *max_chars* characters from a file.

    :param path: File to read.
    :param max_chars: Maximum characters to return.
    :returns: Tail content, or empty string if unreadable.
    """
    try:
        size = path.stat().st_size
        with open(path, "r", encoding="utf-8") as fh:
            if size > max_chars:
                fh.seek(size - max_chars)
                fh.readline()  # skip partial line
            return fh.read().strip()
    except OSError:
        return ""


class ExecutorProtocol(Protocol):
    """
    Protocol for test execution.
    """

    def run_test(
        self,
        workspace_id: str,
        test_id: str,
        test_group: str,
        inventory_path: str,
        extra_vars: Optional[dict[str, Any]] = None,
        log_file: Optional[Path | str] = None,
        job_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        ssh_password: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run a test.

        :param workspace_id: Workspace identifier
        :param test_id: Test ID to run (or empty for full playbook)
        :param test_group: Test group (CONFIG_CHECKS, HA_DB_HANA, etc.)
        :param inventory_path: Path to Ansible inventory
        :param extra_vars: Additional variables to pass
        :param log_file: Path to file for combined stdout/stderr
        :param job_id: Job correlation ID for process tracking
        :param private_key_path: Path to SSH private key file
        :param ssh_password: SSH password for VMPASSWORD auth
        :returns: Execution result
        """
        ...

    def terminate_process(
        self,
        job_id: str,
    ) -> bool:
        """Terminate the subprocess for a running job.

        :param job_id: Job ID whose process to terminate.
        :returns: True if a process was terminated.
        """
        ...


class AnsibleExecutor:
    """Executes tests using Ansible playbooks directly."""

    def __init__(
        self,
        playbook_dir: Path | str = "src",
        ansible_cfg: Optional[Path | str] = None,
    ) -> None:
        """Initialize the executor.

        :param playbook_dir: Directory containing playbooks
        :param ansible_cfg: Path to ansible.cfg
        """
        self.playbook_dir = Path(playbook_dir)
        self.ansible_cfg = Path(ansible_cfg) if ansible_cfg else self.playbook_dir / "ansible.cfg"
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    def run_test(
        self,
        workspace_id: str,
        test_id: str,
        test_group: str,
        inventory_path: str,
        extra_vars: Optional[dict[str, Any]] = None,
        log_file: Optional[Path | str] = None,
        job_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        ssh_password: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run a test using ansible-playbook.

        :param workspace_id: Workspace identifier
        :param test_id: Test ID to run (or empty for full playbook)
        :param test_group: Test group
        :param inventory_path: Path to Ansible inventory
        :param extra_vars: Additional variables
        :param log_file: Path to file for combined stdout/stderr
        :param job_id: Job correlation ID for process tracking
        :param private_key_path: Path to SSH private key file
        :param ssh_password: SSH password for VMPASSWORD auth
        :returns: Execution result dict
        """
        playbook_name = TEST_GROUP_PLAYBOOKS.get(test_group)
        if not playbook_name:
            return {
                "status": "failed",
                "error": f"Unknown test group: {test_group}",
            }

        playbook_path = self.playbook_dir / playbook_name
        if not playbook_path.exists():
            return {
                "status": "failed",
                "error": f"Playbook not found: {playbook_path}",
            }

        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i",
            inventory_path,
        ]

        if private_key_path:
            cmd.extend(["--private-key", private_key_path])
        all_vars = extra_vars or {}
        all_vars["workspace_id"] = workspace_id
        if job_id:
            all_vars["job_id"] = job_id

        if ssh_password:
            all_vars["ansible_ssh_pass"] = ssh_password
        if test_id:
            all_vars["test_id"] = test_id
            input_api = self.playbook_dir / "vars" / "input-api.yaml"
            if input_api.exists():
                try:
                    filtered = json.loads(
                        TestFilter(str(input_api)).get_ansible_vars(
                            test_cases=[test_id],
                        )
                    )
                    all_vars.update(filtered)
                    logger.info(
                        "Applied test filter: only '%s' enabled",
                        test_id,
                    )
                except (Exception, SystemExit):
                    logger.warning(
                        "Test filter unavailable; playbook will "
                        "run all enabled tests (test_id=%s)",
                        test_id,
                    )

        if all_vars:
            cmd.extend(["-e", json.dumps(all_vars)])

        env = {"ANSIBLE_CONFIG": str(self.ansible_cfg)}

        logger.info(
            f"Running test: workspace={workspace_id}, "
            f"test_id={test_id or 'all'}, group={test_group}"
        )

        try:
            return self._run_with_logging(
                cmd=cmd,
                env=env,
                test_id=test_id,
                test_group=test_group,
                workspace_id=workspace_id,
                log_file=log_file,
                job_id=job_id,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error": "Test execution timed out after 1 hour",
                "test_id": test_id,
                "test_group": test_group,
            }
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "test_id": test_id,
                "test_group": test_group,
            }

    def _run_with_logging(
        self,
        cmd: list[str],
        env: dict[str, str],
        test_id: str,
        test_group: str,
        workspace_id: str,
        log_file: Optional[Path | str] = None,
        job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute subprocess, streaming output to log file.

        :param cmd: Command list for subprocess.
        :param env: Extra environment variables.
        :param test_id: Test identifier.
        :param test_group: Test group.
        :param workspace_id: Workspace identifier.
        :param log_file: Optional path for combined output.
        :param job_id: Job correlation ID for process tracking.
        :returns: Execution result dict.
        """
        merged_env = {**os.environ, **env}

        if log_file is None:
            return self._run_capture(
                cmd,
                merged_env,
                test_id,
                test_group,
                workspace_id,
                job_id,
            )

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a", encoding="utf-8") as fh:
            proc = subprocess.Popen(
                cmd,
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                env=merged_env,
            )
            if job_id:
                with self._lock:
                    self._processes[job_id] = proc
            try:
                proc.wait(timeout=3600)
            finally:
                if job_id:
                    with self._lock:
                        self._processes.pop(job_id, None)

        if proc.returncode == 0:
            return {
                "status": "success",
                "test_id": test_id,
                "test_group": test_group,
                "workspace_id": workspace_id,
            }

        error_msg = _describe_exit_code(proc.returncode)
        tail = _tail_file(log_path, max_chars=2000)
        if tail:
            error_msg += f" | last output: {tail}"

        return {
            "status": "failed",
            "test_id": test_id,
            "test_group": test_group,
            "workspace_id": workspace_id,
            "error": error_msg,
            "return_code": proc.returncode,
        }

    def _run_capture(
        self,
        cmd: list[str],
        env: dict[str, str],
        test_id: str,
        test_group: str,
        workspace_id: str,
        job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fallback: capture stdout/stderr in memory.

        Used when no log_file is supplied (e.g. in tests).
        """
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if job_id:
            with self._lock:
                self._processes[job_id] = proc
        try:
            stdout, stderr = proc.communicate(
                timeout=3600,
            )
        finally:
            if job_id:
                with self._lock:
                    self._processes.pop(job_id, None)

        if proc.returncode == 0:
            return {
                "status": "success",
                "test_id": test_id,
                "test_group": test_group,
                "workspace_id": workspace_id,
                "stdout": (stdout[-5000:] if stdout else ""),
            }

        error_msg = _describe_exit_code(proc.returncode)
        if stderr:
            error_msg = stderr[-2000:]
        elif stdout:
            error_msg += f" | last output: " f"{stdout[-500:]}"

        return {
            "status": "failed",
            "test_id": test_id,
            "test_group": test_group,
            "workspace_id": workspace_id,
            "error": error_msg,
            "return_code": proc.returncode,
        }

    def terminate_process(
        self,
        job_id: str,
    ) -> bool:
        """Terminate the subprocess for a running job.

        Sends SIGTERM first, then SIGKILL after 5 seconds
        if the process hasn't exited.

        :param job_id: Job ID whose process to terminate.
        :returns: True if a process was terminated.
        """
        with self._lock:
            proc = self._processes.get(job_id)
        if proc is None:
            return False

        logger.info(f"Terminating subprocess for job {job_id}, " f"pid={proc.pid}")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"SIGTERM timed out for job {job_id}, " f"sending SIGKILL")
                proc.kill()
                proc.wait(timeout=5)
        except OSError as exc:
            logger.warning(f"Failed to terminate process for " f"job {job_id}: {exc}")
            return False
        return True
