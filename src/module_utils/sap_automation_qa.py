"""
This module is used to setup the context for the test cases
and setup base variables for the test case running in the sap-automation-qa
"""

from abc import ABC
from enum import Enum
import sys
import logging
import subprocess
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET


class TestStatus(Enum):
    """
    Enum for the status of the test case/step.
    """

    SUCCESS = "PASSED"
    ERROR = "FAILED"
    WARNING = "WARNING"
    INFO = "INFO"
    NOT_STARTED = "NOT_STARTED"


class SapAutomationQA(ABC):
    """
    This class is used to setup the context for the test cases
    and setup base variables for the test case running in the sap-automation-qa
    """

    def __init__(self):
        self.logger = self.setup_logger()
        self.result = {
            "status": TestStatus.NOT_STARTED.value,
            "message": "",
            "details": [],
            "logs": [],
            "changed": False,
        }

    def setup_logger(self) -> logging.Logger:
        """
        This method is used to setup the logger for the test case

        :return: Configured logger instance
        :rtype: logging.Logger
        """
        logger = logging.getLogger("sap-automation-qa")
        logger.setLevel(logging.INFO)
        log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(log_format)
        logger.addHandler(stream_handler)
        return logger

    def log(self, level: int, message: str):
        """
        Logs a message and adds it to the result logs.

        :param level: Logging level (e.g., logging.INFO, logging.ERROR)
        :type level: int
        :param message: Message to log
        :type message: str
        """
        self.logger.log(level, message)
        message.replace("\n", " ")
        self.result["logs"].append(message)

    def handle_error(self, exception: Exception, stderr: str = None):
        """
        Handles command execution errors by logging and updating the result dictionary.

        :param exception: Exception raised during command execution
        :type exception: Exception
        :param stderr: Standard error output from the command
        :type stderr: str
        """
        error_message = f"Error executing command: {exception}. More errors: {stderr}"
        self.log(logging.ERROR, error_message)
        self.logger.error(error_message)
        self.result["status"] = TestStatus.ERROR.value
        self.result["message"] = error_message
        self.result["logs"].append(error_message)

    def execute_command_subprocess(
        self, command: str, shell_command: bool = False
    ) -> str:
        """
        Executes a shell command using subprocess with a timeout and logs output or errors.

        :param command: Shell command to execute
        :type command: str
        :param shell_command: Whether the command is a shell command
        :type shell_command: bool
        :return: Standard output from the command
        :rtype: str
        """
        command_string = (
            command if isinstance(command, str) else " ".join(command).replace("'", "")
        )
        self.log(
            logging.INFO,
            f"Executing command: {command_string}",
        )
        try:
            command_output = subprocess.run(
                command,
                timeout=30,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell_command,
            )
            stdout = command_output.stdout.decode("utf-8")
            stderr = command_output.stderr.decode("utf-8")
            return stdout if not stderr else stderr
        except subprocess.TimeoutExpired as e:
            self.handle_error(e, "Command timed out")
        except subprocess.CalledProcessError as e:
            self.handle_error(e, e.stderr.decode("utf-8").strip())
        except Exception as e:
            self.handle_error(e, "")
        return ""

    def parse_xml_output(self, xml_output: str) -> Optional[ET.Element]:
        """
        Parses the XML output of a command.
        """
        if xml_output.startswith("<"):
            return ET.fromstring(xml_output)
        return None

    def get_result(self) -> Dict[str, Any]:
        """
        Returns the result dictionary.

        :return: The result dictionary containing the status, message, details, and logs.
        :rtype: dict
        """
        return self.result
