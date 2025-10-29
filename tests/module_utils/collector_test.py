# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the collector module.
"""

import pytest
import json
from typing import Any, Dict


from src.module_utils.collector import (
    AzureDataParser,
    Collector,
    CommandCollector,
    ModuleCollector,
)


class MockCheck:
    """
    Mock Check object for testing
    """

    def __init__(self, collector_args: Dict[str, Any] | None = None):
        self.collector_args = collector_args or {}
        self.command = None


class MockParent:
    """
    Mock SapAutomationQA parent for testing
    """

    def __init__(self):
        self.logs = []
        self.errors = []

    def log(self, level: int, message: str) -> None:
        """
        Mock log method
        """
        self.logs.append({"level": level, "message": message})

    def handle_error(self, error: Exception) -> None:
        """
        Mock handle_error method
        """
        self.errors.append(error)

    def execute_command_subprocess(self, command: str, shell_command: bool = True) -> str:
        """
        Mock execute_command_subprocess method
        """
        return "mock_output"


class TestCollector:
    """
    Test suite for Collector base class
    """

    def test_collector_abstract_collect(self):
        """
        Test that Collector is abstract and cannot be instantiated directly
        """
        parent = MockParent()
        with pytest.raises(TypeError, match="abstract"):
            _ = Collector(parent)  # type: ignore

    def test_sanitize_command_valid_and_dangerous(self):
        """
        Test sanitize_command with valid and dangerous patterns
        """
        collector = CommandCollector(MockParent())
        assert collector.sanitize_command("ls -la") == "ls -la"
        assert collector.sanitize_command("ps aux | grep java") == "ps aux | grep java"
        with pytest.raises(ValueError, match="dangerous pattern"):
            collector.sanitize_command("sudo rm -rf /var/log")
        with pytest.raises(ValueError, match="maximum length"):
            collector.sanitize_command("a" * 3001)

    def test_substitute_context_vars(self):
        """
        Test context variable substitution in commands
        """
        collector = CommandCollector(MockParent())
        result = collector.substitute_context_vars(
            "ssh {{ CONTEXT.user }}@{{ CONTEXT.host }}", {"user": "admin", "host": "192.168.1.1"}
        )
        assert result == "ssh admin@192.168.1.1"
        result = collector.substitute_context_vars(
            "echo {{ CONTEXT.exists }} {{ CONTEXT.missing }}", {"exists": "value"}
        )
        assert result == "echo value {{ CONTEXT.missing }}"


class TestCommandCollector:
    """
    Test suite for CommandCollector
    """

    def test_collect_success_with_substitution(self):
        """
        Test successful command collection with context substitution
        """
        collector = CommandCollector(MockParent())
        check = MockCheck({"command": "cat {{ CONTEXT.file }}", "shell": True})
        context = {"file": "/etc/hosts"}
        result = collector.collect(check, context)
        assert result == "mock_output"
        assert check.command == "cat /etc/hosts"

    def test_collect_error_cases(self):
        """
        Test command collection error paths
        """
        collector = CommandCollector(MockParent())
        assert "ERROR: No command specified" in collector.collect(MockCheck({}), {})
        check = MockCheck({"command": "rm -rf /tmp"})
        assert "ERROR: Command sanitization failed" in collector.collect(check, {})
        check = MockCheck({"command": "{{ CONTEXT.cmd }} -rf /tmp"})
        assert "ERROR: Command sanitization failed after substitution" in collector.collect(
            check, {"cmd": "rm"}
        )
        check = MockCheck({"command": "whoami", "user": "user;malicious"})
        assert "ERROR: Invalid user parameter" in collector.collect(check, {})

    def test_collect_user_handling(self):
        """
        Test user parameter handling in command collection
        """
        collector = CommandCollector(MockParent())
        check = MockCheck({"command": "whoami", "user": "sapuser", "shell": True})
        result = collector.collect(check, {})
        assert result == "mock_output"
        check = MockCheck({"command": "ls /root", "user": "root", "shell": True})
        result = collector.collect(check, {})
        assert check.command == "ls /root"

    def test_collect_exception_handling(self, monkeypatch):
        """
        Test collect handles exceptions properly
        """
        parent = MockParent()
        collector = CommandCollector(parent)

        def mock_execute_failing(command: str, shell_command: bool = True) -> str:
            raise Exception("Command failed")

        monkeypatch.setattr(parent, "execute_command_subprocess", mock_execute_failing)
        result = collector.collect(MockCheck({"command": "failing_command", "shell": True}), {})
        assert "ERROR: Command execution failed" in result
        assert len(parent.errors) == 1


class TestAzureDataParser:
    """
    Test suite for AzureDataParser
    """

    def test_parse_azure_disks_vars(self):
        """
        Test parsing Azure disks variables
        """
        parser = AzureDataParser(MockParent())
        assert (
            parser.parse_azure_disks_vars(MockCheck({}), {"azure_disks_info": "disk_data"})
            == "disk_data"
        )
        assert parser.parse_azure_disks_vars(MockCheck({}), {}) == "N/A"

        assert (
            parser.parse_anf_volumes_vars(MockCheck({}), {"anf_volumes_info": "anf_volume_data"})
            == "anf_volume_data"
        )
        assert (
            parser.parse_lvm_groups_vars(MockCheck({}), {"lvm_groups_info": "lvm_groups_data"})
            == "lvm_groups_data"
        )
        assert (
            parser.parse_lvm_volumes_vars(MockCheck({}), {"lvm_volumes_info": "lvm_volumes_data"})
            == "lvm_volumes_data"
        )
        assert (
            parser.parse_filesystem_vars(
                MockCheck({}), {"formatted_filesystem_info": "filesystem_data"}
            )
            == "filesystem_data"
        )

    def test_parse_anf_vars_success(self):
        """
        Test successful ANF property parsing with JSON string metadata
        """
        parser = AzureDataParser(MockParent())

        anf_volume = {"ip": "10.0.0.1", "throughput": "1000"}
        filesystem = {"target": "/hana/shared", "source": "10.0.0.1:/volume1", "nfs_type": "ANF"}
        check = MockCheck({"mount_point": "/hana/shared", "property": "throughput"})
        context = {"filesystems": [filesystem], "anf_storage_metadata": [anf_volume]}
        assert parser.parse_anf_vars(check, context) == "1000"
        context["anf_storage_metadata"] = json.dumps([anf_volume])
        assert parser.parse_anf_vars(check, context) == "1000"

    def test_parse_anf_vars_mount_not_found(self):
        """
        Test ANF parsing when mount point not found
        """
        parser = AzureDataParser(MockParent())
        check = MockCheck({"mount_point": "/missing", "property": "throughput"})
        assert (
            parser.parse_anf_vars(check, {"filesystems": [], "anf_storage_metadata": []}) == "N/A"
        )

        filesystem = {"target": "/hana/shared", "source": "/dev/sdb1", "nfs_type": "NFS"}
        check = MockCheck({"mount_point": "/hana/shared", "property": "throughput"})

        assert (
            parser.parse_anf_vars(check, {"filesystems": [filesystem], "anf_storage_metadata": []})
            == "N/A"
        )
        filesystem = {"target": "/hana/shared", "source": "invalid_source", "nfs_type": "ANF"}
        check = MockCheck({"mount_point": "/hana/shared", "property": "throughput"})

        assert (
            parser.parse_anf_vars(check, {"filesystems": [filesystem], "anf_storage_metadata": []})
            == "N/A"
        )

    def test_parse_anf_vars_ip_not_found(self):
        """
        Test ANF parsing when IP not found in metadata
        """
        parser = AzureDataParser(MockParent())
        anf_volume = {"ip": "10.0.0.2", "throughput": "1000"}
        filesystem = {"target": "/hana/shared", "source": "10.0.0.1:/volume1", "nfs_type": "ANF"}
        assert (
            parser.parse_anf_vars(
                MockCheck({"mount_point": "/hana/shared", "property": "throughput"}),
                {"filesystems": [filesystem], "anf_storage_metadata": [anf_volume]},
            )
            == "N/A"
        )

        anf_volume = {"ip": "10.0.0.1", "size": "4096"}
        filesystem = {"target": "/hana/shared", "source": "10.0.0.1:/volume1", "nfs_type": "ANF"}

        assert (
            parser.parse_anf_vars(
                MockCheck({"mount_point": "/hana/shared", "property": "throughput"}),
                {"filesystems": [filesystem], "anf_storage_metadata": [anf_volume]},
            )
            == "N/A"
        )

    def test_parse_anf_vars_invalid_json(self):
        """
        Test ANF parsing with invalid JSON string
        """
        parser = AzureDataParser(MockParent())
        filesystem = {"target": "/hana/shared", "source": "10.0.0.1:/volume1", "nfs_type": "ANF"}

        assert (
            parser.parse_anf_vars(
                MockCheck({"mount_point": "/hana/shared", "property": "throughput"}),
                {"filesystems": [filesystem], "anf_storage_metadata": "invalid json {"},
            )
            == "N/A"
        )

        filesystem = {"target": "/hana/shared", "source": "10.0.0.1:/volume1", "nfs_type": "ANF"}

        assert (
            parser.parse_anf_vars(
                MockCheck({"mount_point": "/hana/shared", "property": "throughput"}),
                {"filesystems": [filesystem], "anf_storage_metadata": 12345},
            )
            == "N/A"
        )
        result = parser.parse_anf_vars(
            MockCheck({"mount_point": "/hana/shared", "property": "throughput"}),
            {"filesystems": None, "anf_storage_metadata": []},
        )
        assert "ERROR: ANF property parsing failed" in result

    def test_parse_disks_vars_property_in_filesystem(self):
        """
        Test disk parsing when property exists in filesystem entry
        """
        assert (
            AzureDataParser(MockParent()).parse_disks_vars(
                MockCheck({"mount_point": "/hana/data", "property": "iops"}),
                {
                    "filesystems": [{"target": "/hana/data", "iops": "5000"}],
                    "azure_disks_metadata": [],
                },
            )
            == "5000"
        )

    def test_parse_disks_vars_lvm_aggregation(self):
        """
        Test disk parsing with LVM striped volume aggregation and JSON strings
        """
        parser = AzureDataParser(MockParent())

        disk1 = {"name": "disk1", "iops": 2000}
        disk2 = {"name": "disk2", "iops": 2000}
        filesystem = {"target": "/hana/data", "azure_disk_names": ["disk1", "disk2"]}
        check = MockCheck({"mount_point": "/hana/data", "property": "iops"})
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": [disk1, disk2]}
            )
            == "4000"
        )
        disk1_json = '{"name": "disk1", "iops": 1500}'
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": [disk1_json, disk2]}
            )
            == "3500"
        )

    def test_parse_disks_vars_single_disk(self):
        """
        Test disk parsing for single disk with device name matching
        """
        parser = AzureDataParser(MockParent())
        disk = {"name": "/dev/sdc", "iops": 3000}
        filesystem = {"target": "/hana/log", "source": "/dev/sdc"}
        check = MockCheck({"mount_point": "/hana/log", "property": "iops"})
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": [disk]}
            )
            == "3000"
        )
        disk_fallback = {"name": "sdc", "iops": 3000}
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": [disk_fallback]}
            )
            == "3000"
        )

    def test_parse_disks_vars_mount_not_found(self):
        """
        Test disk parsing when mount point not found
        """
        assert (
            AzureDataParser(MockParent()).parse_disks_vars(
                MockCheck({"mount_point": "/missing", "property": "iops"}),
                {"filesystems": [], "azure_disks_metadata": []},
            )
            == "N/A"
        )

    def test_parse_disks_vars_no_disk_metadata(self):
        """
        Test disk parsing with no disk metadata or not found
        """
        parser = AzureDataParser(MockParent())
        filesystem = {"target": "/hana/data", "source": "/dev/sdc"}
        check = MockCheck({"mount_point": "/hana/data", "property": "iops"})
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": []}
            )
            == "N/A"
        )
        disk = {"name": "other_disk", "iops": 3000}
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": [disk]}
            )
            == "N/A"
        )

    def test_parse_disks_vars_property_not_found(self):
        """
        Test disk parsing when property not in disk metadata
        """
        assert (
            AzureDataParser(MockParent()).parse_disks_vars(
                MockCheck({"mount_point": "/hana/log", "property": "iops"}),
                {
                    "filesystems": [{"target": "/hana/log", "source": "/dev/sdc"}],
                    "azure_disks_metadata": [{"name": "/dev/sdc", "size": "512"}],
                },
            )
            == "N/A"
        )

    def test_parse_disks_vars_invalid_disk_value(self):
        """
        Test disk parsing with non-numeric disk values
        """
        parser = AzureDataParser(MockParent())
        disk1 = {"name": "disk1", "iops": "invalid"}
        disk2 = {"name": "disk2", "iops": 2000}
        filesystem = {"target": "/hana/data", "azure_disk_names": ["disk1", "disk2"]}
        check = MockCheck({"mount_point": "/hana/data", "property": "iops"})
        assert (
            parser.parse_disks_vars(
                check, {"filesystems": [filesystem], "azure_disks_metadata": [disk1, disk2]}
            )
            == "2000"
        )

    def test_parse_disks_vars_no_matching_disks(self):
        """
        Test disk parsing when no disks match
        """
        assert (
            AzureDataParser(MockParent()).parse_disks_vars(
                MockCheck({"mount_point": "/hana/data", "property": "iops"}),
                {
                    "filesystems": [
                        {"target": "/hana/data", "azure_disk_names": ["disk1", "disk2"]}
                    ],
                    "azure_disks_metadata": [{"name": "other_disk", "iops": 2000}],
                },
            )
            == "N/A"
        )

        # Test disk parsing with invalid JSON string in metadata
        assert (
            AzureDataParser(MockParent()).parse_disks_vars(
                MockCheck({"mount_point": "/hana/data", "property": "iops"}),
                {
                    "filesystems": [{"target": "/hana/data", "azure_disk_names": ["disk1"]}],
                    "azure_disks_metadata": ["invalid json {"],
                },
            )
            == "N/A"
        )

        # Test disk parsing with unexpected metadata type
        assert (
            AzureDataParser(MockParent()).parse_disks_vars(
                MockCheck({"mount_point": "/hana/data", "property": "iops"}),
                {
                    "filesystems": [{"target": "/hana/data", "azure_disk_names": ["disk1"]}],
                    "azure_disks_metadata": [12345],
                },
            )
            == "N/A"
        )

        # Test disk parsing handles exceptions
        result = AzureDataParser(MockParent()).parse_disks_vars(
            MockCheck({"mount_point": "/hana/data", "property": "iops"}),
            {"filesystems": None, "azure_disks_metadata": []},
        )
        assert "ERROR: Parsing failed" in result

        # Test AzureDataParser.collect delegates to CommandCollector
        result = AzureDataParser(MockParent()).collect(
            MockCheck({"command": "echo test", "shell": True}), {}
        )
        assert result == "mock_output"


class TestModuleCollector:
    """
    Test suite for ModuleCollector
    """

    def test_collect_with_context_key(self):
        """
        Test collecting module data with explicit context_key
        """
        result = ModuleCollector(MockParent()).collect(
            MockCheck({"module_name": "test_module", "context_key": "test_data"}),
            {"test_data": {"result": "success"}},
        )
        assert result == {"result": "success"}

        # Test collecting module data using default context key mapping
        result = ModuleCollector(MockParent()).collect(
            MockCheck({"module_name": "get_pcmk_properties_db"}),
            {"ha_db_config": {"config": "value"}},
        )
        assert result == {"config": "value"}

        # Test collecting module data for unmapped module

        result = ModuleCollector(MockParent()).collect(
            MockCheck({"module_name": "custom_module"}), {"custom_module": {"data": "value"}}
        )
        assert result == {"data": "value"}

    def test_collect_no_module_name(self):
        """
        Test collect with no module_name specified
        """
        assert "ERROR: No module_name specified" in ModuleCollector(MockParent()).collect(
            MockCheck({}), {}
        )

        result = ModuleCollector(MockParent()).collect(
            MockCheck({"module_name": "test_module", "context_key": "missing_key"}),
            {"other_key": "value"},
        )
        assert "ERROR: Module result 'missing_key' not found in context" in result

    def test_collect_all_mapped_modules(self):
        """
        Test collect with all pre-mapped module names
        """
        mappings = {
            "get_pcmk_properties_db": "ha_db_config",
            "get_pcmk_properties_scs": "ha_scs_config",
            "get_azure_lb": "ha_loadbalancer_config",
        }

        for module_name, context_key in mappings.items():
            result = ModuleCollector(MockParent()).collect(
                MockCheck({"module_name": module_name}), {context_key: {"test": "data"}}
            )
            assert result == {"test": "data"}
