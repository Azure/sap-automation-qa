#!/usr/bin/env python3

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test Filter Module

This module provides functionality to filter test groups and test cases
from the input-api.yaml configuration based on command line arguments.
"""

import sys
import json
from typing import Dict, List, Optional, Any
import yaml


class TestFilter:
    """Filter test configuration based on specified groups and cases."""

    def __init__(self, input_file: str):
        """
        Initialize the TestFilter with the input YAML file.

        :param input_file: Path to the input YAML file
        :type input_file: str
        """
        self.input_file = input_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load the configuration from the input YAML file.

        :return: Loaded configuration
        :rtype: Dict[str, Any]
        """
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file {self.input_file} not found", file=sys.stderr)
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {self.input_file}: {e}", file=sys.stderr)
            sys.exit(1)

    def filter_tests(
        self, test_group: Optional[str] = None, test_cases: Optional[List[str]] = None
    ) -> str:
        """
        Filter the test configuration based on the specified test group and test cases.

        :param test_group: Name of the test group to filter, defaults to None
        :type test_group: Optional[str], optional
        :param test_cases: List of test case task names to include, defaults to None
        :type test_cases: Optional[List[str]], optional
        :return: JSON string representation of the filtered test configuration
        :rtype: str
        """
        filtered_config = self.config.copy()

        if test_group or test_cases:
            for group in filtered_config["test_groups"]:
                if test_group and group["name"] == test_group:
                    if test_cases:
                        filtered_cases = []
                        for case in group["test_cases"]:
                            if case["task_name"] in test_cases:
                                case["enabled"] = True
                                filtered_cases.append(case)
                        group["test_cases"] = filtered_cases
                elif test_group and group["name"] != test_group:
                    for case in group["test_cases"]:
                        case["enabled"] = False
                elif test_cases and not test_group:
                    for case in group["test_cases"]:
                        if case["task_name"] in test_cases:
                            case["enabled"] = True
                        else:
                            case["enabled"] = False

        return json.dumps(filtered_config, indent=2)

    def get_ansible_vars(
        self, test_group: Optional[str] = None, test_cases: Optional[List[str]] = None
    ) -> str:
        """
        Get Ansible variables from the filtered test configuration.

        :param test_group: Name of the test group to filter, defaults to None
        :type test_group: Optional[str], optional
        :param test_cases: List of test case task names to include, defaults to None
        :type test_cases: Optional[List[str]], optional
        :return: JSON string representation of the Ansible variables
        :rtype: str
        """
        filtered_json = self.filter_tests(test_group, test_cases)
        filtered_config = json.loads(filtered_json)
        return json.dumps({"test_groups": filtered_config["test_groups"]})


def main():
    """
    Command line interface for the test filter.
    """
    if len(sys.argv) < 2:
        print(
            "Usage: python filter_tests.py <input_file> [test_group] [test_cases...]",
            file=sys.stderr,
        )
        print(
            "Example: "
            + "python filter_tests.py input-api.yaml HA_DB_HANA ha-config,primary-node-crash",
            file=sys.stderr,
        )
        sys.exit(1)

    input_file = sys.argv[1]
    test_group = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "null" else None
    test_cases_str = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "null" else None

    test_cases = None
    if test_cases_str:
        test_cases = [case.strip() for case in test_cases_str.split(",")]

    filter_obj = TestFilter(input_file)
    result = filter_obj.get_ansible_vars(test_group, test_cases)
    print(result)


if __name__ == "__main__":
    main()
