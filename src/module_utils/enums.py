"""
This module defines various enumerations and data classes used throughout the sap-automation-qa
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

try:
    from ansible.module_utils.collector import ApplicabilityRule
except ImportError:
    from src.module_utils.collector import ApplicabilityRule


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
    SKIPPED = "SKIPPED"


class TestSeverity(Enum):
    """
    Enum for the severity of the test/config case/step.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    WARNING = "WARNING"
    LOW = "LOW"
    INFO = "INFO"


class OperatingSystemFamily(Enum):
    """
    Enum for the operating system family.
    """

    REDHAT = "REDHAT"
    SUSE = "SUSE"
    DEBIAN = "DEBIAN"
    WINDOWS = "WINDOWS"
    UNKNOWN = "UNKNOWN"


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


@dataclass
class Check:
    """
    Represents a configuration check

    :param id: Unique identifier for the check
    :type id: str
    :param name: Name of the check
    :type name: str
    :param description: Description of the check
    :type description: str
    :param category: Category of the check
    :type category: str
    :param workload: Workload type (e.g., SAP, Non-SAP)
    :type workload: str
    :param TestSeverity: TestSeverity level of the check
    :type TestSeverity: TestSeverity
    :param collector_type: Type of collector to use (e.g., command, azure)
    :type collector_type: str
    :param collector_args: Arguments for the collector
    :type collector_args: Dict[str, Any]
    :param validator_type: Type of validator to use (e.g., string, range)
    :type validator_type: str
    :param validator_args: Arguments for the validator
    :type validator_args: Dict[str, Any]
    :param tags: Tags associated with the check
    :type tags: List[str]
    :param applicability: List of applicability rules
    :type applicability: List[ApplicabilityRule]
    :param references: References for the check
    :type references: Dict[str, str]
    :param report: Report type (e.g., check, section)
    :type report: Optional[str]
    """

    id: str
    name: str
    description: str
    category: str
    workload: str
    ConfigCheckSeverity: TestSeverity = TestSeverity.WARNING
    collector_type: str = "command"
    collector_args: Dict[str, Any] = field(default_factory=dict)
    validator_type: str = "string"
    validator_args: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    applicability: List[ApplicabilityRule] = field(default_factory=list)
    references: Dict[str, str] = field(default_factory=dict)
    report: Optional[str] = "check"

    def is_applicable(self, context: Dict[str, Any]) -> bool:
        """
        Check if the check is applicable based on the context

        :param context: Context dictionary containing properties
        :type context: Dict[str, Any]
        :return: True if applicable, False otherwise
        :rtype: bool
        """

        for rule in self.applicability:
            context_value = context[rule.property]
            if not rule.is_applicable(context_value):
                return False

        return True


@dataclass
class CheckResult:
    """
    Represents the result of a check execution

    :param check: The check that was executed
    :type check: Check
    :param status: Status of the check execution
    :type status: TestStatus
    :param hostname: Hostname of the system where the check was executed
    :type hostname: str
    :param expected_value: Expected value from the check
    :type expected_value: Any
    :param actual_value: Actual value collected during the check
    :type actual_value: Any
    :param execution_time: Time taken to execute the check
    :type execution_time: float
    :param timestamp: Timestamp of the check execution
    :type timestamp: datetime
    :param details: Additional details about the check execution
    :type details: Optional[str]
    """

    check: Check
    status: TestStatus
    hostname: str
    expected_value: Any
    actual_value: Any
    execution_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    details: Optional[str] = None
