"""
This module defines various enumerations and data classes used throughout the sap-automation-qa
"""

from enum import Enum
from typing import Dict, Any, List


class TelemetryDataDestination(Enum):
    """
    Enum for the destination of the telemetry data.
    """

    KUSTO = "azuredataexplorer"
    LOG_ANALYTICS = "azureloganalytics"


class TestStatus(Enum):
    """
    Enum for the status of the test case/step.
    """

    SUCCESS = "PASSED"
    ERROR = "FAILED"
    WARNING = "WARNING"
    INFO = "INFO"
    NOT_STARTED = "NOT_STARTED"


class OperatingSystemFamily(Enum):
    """
    Enum for the operating system family.
    """

    REDHAT = "REDHAT"
    SUSE = "SUSE"
    DEBIAN = "DEBIAN"
    WINDOWS = "WINDOWS"


class HanaSRProvider(Enum):
    """
    Enum for the SAP HANA SR provider type.
    """

    SAPHANASR = "SAPHanaSR"
    ANGI = "SAPHanaSR-angi"


class Parameters:
    """
    This class stores the parameters for the test case.

    :param category: The category of the parameter
    :type category: str
    :param id: Unique identifier for the parameter
    :type id: str
    :param name: Name of the parameter
    :type name: str
    :param value: Current value of the parameter
    :type value: Any
    :param expected_value: Expected value for validation
    :type expected_value: Any
    :param status: Current status of the parameter validation
    :type status: str
    """

    def __init__(
        self, category: str, id: str, name: str, value: Any, expected_value: Any, status: str
    ):
        self.category = category
        self.id = id
        self.name = name
        self.value = value
        self.expected_value = expected_value
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the parameters to a dictionary.

        return: Dictionary containing the parameters
        rtype: Dict[str, Any]
        """
        return {
            "category": self.category,
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "expected_value": self.expected_value,
            "status": self.status,
        }


class Result:
    """
    This class stores the result of the test case.

    :param status: Current status of the test
    :type status: str
    :param message: Descriptive message about the result
    :type message: str
    :param details: List of detailed information
    :type details: List[Any]
    :param logs: List of log messages
    :type logs: List[str]
    :param changed: Whether the test caused any changes
    :type changed: bool
    """

    def __init__(
        self,
        status: str = "",
        message: str = "",
        details: List[Any] = list(),
        logs: List[str] = list(),
        changed: bool = False,
    ):
        self.status = status if status is not None else TestStatus.NOT_STARTED.value
        self.message = message
        self.details = details if details is not None else []
        self.logs = logs if logs is not None else []
        self.changed = changed

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the result to a dictionary.

        return: Dictionary containing the result
        rtype: Dict[str, Any]
        """
        return {
            "status": self.status,
            "message": self.message,
            "details": self.details.copy(),
            "logs": self.logs.copy(),
            "changed": self.changed,
        }
