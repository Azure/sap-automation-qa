# define all the models here

"""
This is the models file for the module_utils collection.
"""

from enum import Enum


class TestStatus(Enum):
    """
    Enum for the status of the test case/step.
    """

    SUCCESS = "PASSED"
    ERROR = "FAILED"
    WARNING = "WARNING"
    INFO = "INFO"
    NOT_STARTED = "NOT_STARTED"
