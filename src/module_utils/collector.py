# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Collectors for data collection in SAP Automation QA
"""
import json
from abc import ABC, abstractmethod
import logging
import re
import shlex
import ipaddress
from typing import Any

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.commands import DANGEROUS_COMMANDS
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.commands import DANGEROUS_COMMANDS


class Collector(ABC):
    """
    Base class for data collection
    """

    def __init__(self, parent: SapAutomationQA):
        """
        Initialize with parent module for logging

        :param parent: Parent module with logging capability
        :type parent: SapAutomationQA
        """
        self.parent = parent

    @abstractmethod
    def collect(self, check, context) -> Any:
        """
        Collect data for validation

        :param check: Check object
        :type check: Check
        :param context: Context object
        :type context: Context
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def sanitize_command(self, command: str) -> str:
        """
        Sanitize command to prevent injection attacks

        :param command: Raw command string
        :type command: str
        :return: Sanitized command or None if dangerous
        :rtype: str
        :raises ValueError: If command contains dangerous patterns
        """

        for pattern in DANGEROUS_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                self.parent.log(logging.ERROR, f"Dangerous command pattern detected: {pattern}")
                raise ValueError(f"Command contains potentially dangerous pattern: {pattern}")
        if len(command) > 3000:
            self.parent.log(logging.ERROR, f"Command too long: {len(command)} chars")
            raise ValueError("Command exceeds maximum length of 1000 characters")

        return command

    def substitute_context_vars(self, command: str, context: dict) -> str:
        """
        Substitute context variables in the command string.

        :param command: Command string with placeholders
        :type command: str
        :param context: Context variables to substitute
        :type context: dict
        :return: Command string with substituted values
        :rtype: str
        """
        self.parent.log(logging.INFO, f"Substituting context variables in command {command}")
        for key, value in context.items():
            placeholder = "{{ CONTEXT." + key + " }}"
            if placeholder in command:
                self.parent.log(
                    logging.INFO,
                    f"Substituting {placeholder} with {value} in command: {command}",
                )
                command = command.replace(placeholder, str(value))
        return command


class CommandCollector(Collector):
    """Collects data by executing shell commands"""

    def collect(self, check, context) -> str:
        """
        Execute a command and return the output.

        :param check: _Description of the check to be performed_
        :type check: Check
        :param context: Context variables to substitute in the command
        :type context: Dict[str, Any]
        :return: The output of the command
        :rtype: str
        """
        try:
            command = check.collector_args.get("command", "")
            user = check.collector_args.get("user", "")
            if not command:
                return "ERROR: No command specified"
            try:
                command = self.sanitize_command(command)
            except ValueError as e:
                self.parent.log(logging.ERROR, f"Command sanitization failed: {e}")
                return f"ERROR: Command sanitization failed: {e}"
            command = self.substitute_context_vars(command, context)
            try:
                command = self.sanitize_command(command)
            except ValueError as e:
                self.parent.log(
                    logging.ERROR, f"Command sanitization failed after substitution: {e}"
                )
                return f"ERROR: Command sanitization failed after substitution: {e}"

            check.command = command
            if user and user != "root":
                if not re.match(r"^[a-zA-Z0-9_-]+$", user):
                    self.parent.log(logging.ERROR, f"Invalid user parameter: {user}")
                    return f"ERROR: Invalid user parameter: {user}"

                if user == "db2sid":
                    user = f"db2{context.get('database_sid', '').lower()}"

                command = f"sudo -u {shlex.quote(user)} {command}"

            return self.parent.execute_command_subprocess(
                command, shell_command=check.collector_args.get("shell", True)
            ).strip()
        except Exception as ex:
            self.parent.handle_error(ex)
            return f"ERROR: Command execution failed: {str(ex)}"


class AzureDataParser(Collector):
    """
    Parses data from Azure resources
    """

    def __init__(self, parent: SapAutomationQA):
        super().__init__(parent)

    def parse_azure_disks_vars(self, check, context) -> str:
        """
        Parse Azure disks variables from the given data.

        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Parsed Azure disks variables
        :rtype: str
        """
        return context.get("azure_disks_info", "N/A")

    def parse_anf_vars(self, check, context) -> str:
        """
        Parse required property for Azure NetApp Files (ANF) from from filesystem data.

        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Parsed ANF properties variables
        :rtype: str
        """
        filesystem_data = context.get("filesystems", [])
        anf_storage_data = context.get("anf_storage_metadata", [])
        mount_point = check.collector_args.get("mount_point", "")
        property_name = check.collector_args.get("property", "")
        value = "N/A"

        try:
            parsed_anf_volumes = []
            if isinstance(anf_storage_data, str):
                try:
                    parsed_anf_volumes = json.loads(anf_storage_data)
                except json.JSONDecodeError:
                    self.parent.log(
                        logging.WARNING,
                        f"Failed to parse ANF storage metadata JSON: {anf_storage_data[:100]}",
                    )
            elif isinstance(anf_storage_data, list):
                parsed_anf_volumes = anf_storage_data
            else:
                self.parent.log(
                    logging.WARNING, f"Unexpected ANF storage data type: {type(anf_storage_data)}"
                )
                return value

            fs_entry = None
            for fs in filesystem_data:
                if fs.get("target") == mount_point:
                    fs_entry = fs
                    break

            if not fs_entry:
                self.parent.log(
                    logging.WARNING, f"Mount point {mount_point} not found in filesystem data"
                )
                return value

            if fs_entry.get("nfs_type") != "ANF":
                self.parent.log(
                    logging.WARNING,
                    f"Mount point {mount_point} is not an ANF volume (type: {fs_entry.get('nfs_type')})",
                )
                return value
            source = fs_entry.get("source", "")
            if ":" not in source:
                self.parent.log(
                    logging.WARNING, f"Invalid NFS source format for {mount_point}: {source}"
                )
                return value

            nfs_ip = source.split(":")[0]
            for anf_volume in parsed_anf_volumes:
                if anf_volume.get("ip") == nfs_ip:
                    if property_name in anf_volume:
                        value = str(anf_volume.get(property_name, "N/A"))
                        self.parent.log(
                            logging.INFO,
                            f"Found {property_name}={value} for ANF volume at {mount_point} (IP: {nfs_ip})",
                        )
                    else:
                        self.parent.log(
                            logging.WARNING,
                            f"Property '{property_name}' not found in ANF volume for {mount_point}",
                        )
                    break
            else:
                self.parent.log(
                    logging.WARNING,
                    f"No ANF volume found with IP {nfs_ip} for mount point {mount_point}",
                )

        except Exception as ex:
            self.parent.handle_error(ex)
            value = f"ERROR: ANF property parsing failed: {str(ex)}"

        return value

    def parse_anf_volumes_vars(self, check, context) -> str:
        """
        Parse Azure NetApp Files (ANF) volumes variables from the given data.

        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Parsed ANF volumes variables
        :rtype: str
        """
        return context.get("anf_volumes_info", "N/A")

    def parse_lvm_groups_vars(self, check, context) -> str:
        """
        Parse LVM group info from the given data.

        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Parsed LVM group variables
        :rtype: str
        """
        return context.get("lvm_groups_info", "N/A")

    def parse_lvm_volumes_vars(self, check, context) -> str:
        """
        Parse LVM volume info from the given data.
        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Parsed LVM volume variables
        :rtype: str
        """
        return context.get("lvm_volumes_info", "N/A")

    def parse_filesystem_vars(self, check, context) -> str:
        """
        Parse filesystem variables from the given data.

        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Parsed filesystem variables
        :rtype: str
        """
        return context.get("formatted_filesystem_info", "N/A")

    def parse_disks_vars(self, check, context) -> str:
        """
        Parse the required property for given mount point from filesystem data and disks metadata.

        For LVM striped volumes, this aggregates metrics across all underlying disks.
        For single disks, returns the metric for that disk.

        :param check: Check object with collector arguments
        :type check: Check
        :param context: Context object containing all required data
        :type context: Dict[str, Any]
        :return: Aggregated property value or "N/A" if not found
        :rtype: str
        """
        filesystem_data = context.get("filesystems", [])
        disks_metadata = context.get("azure_disks_metadata", {})
        mount_point = check.collector_args.get("mount_point", "")
        property = check.collector_args.get("property", "")
        value = "N/A"
        try:
            parsed_disks = []
            for disk in disks_metadata:
                if isinstance(disk, str):
                    try:
                        parsed_disks.append(json.loads(disk))
                    except json.JSONDecodeError:
                        self.parent.log(
                            logging.WARNING,
                            f"Failed to parse disk metadata JSON string: {disk[:100]}",
                        )
                        continue
                elif isinstance(disk, dict):
                    parsed_disks.append(disk)
                else:
                    self.parent.log(logging.WARNING, f"Unexpected disk metadata type: {type(disk)}")

            fs_entry = None
            for fs in filesystem_data:
                if fs.get("target") in (
                    mount_point,
                    f"{mount_point}/{context.get('database_sid', '').upper()}",
                    f"{mount_point}/{context.get('sap_sid', '').upper()}",
                ):
                    fs_entry = fs
                    break

            if not fs_entry:
                self.parent.log(
                    logging.WARNING, f"Mount point {mount_point} not found in filesystem data"
                )
                return value
            if property in fs_entry and fs_entry.get(property) is not None:
                value = str(fs_entry[property])
                self.parent.log(
                    logging.INFO,
                    f"Found {property}='{value}' for {mount_point} from filesystem data",
                )
                return value
            if not parsed_disks:
                self.parent.log(logging.WARNING, "No valid disk metadata found")
                return value

            if "azure_disk_names" in fs_entry and fs_entry["azure_disk_names"]:
                total_value, matched_disks = 0, 0

                for disk_name in fs_entry["azure_disk_names"]:
                    disk = next((d for d in parsed_disks if d.get("name") == disk_name), None)
                    if disk and property in disk:
                        disk_value = disk.get(property, 0)
                        try:
                            total_value += float(disk_value) if disk_value else 0
                            matched_disks += 1
                        except (ValueError, TypeError):
                            self.parent.log(
                                logging.WARNING,
                                f"Could not convert {property}={disk_value} to number for disk {disk_name}",
                            )

                if matched_disks > 0:
                    value = str(int(total_value))
                    self.parent.log(
                        logging.INFO,
                        f"Aggregated {property} for {mount_point}: {value} (from {matched_disks} disks)",
                    )
                else:
                    self.parent.log(
                        logging.WARNING,
                        f"No matching disks found for {mount_point} with property {property}",
                    )
            else:
                disk_name = fs_entry.get("source")
                disk = next((d for d in parsed_disks if d.get("name") == disk_name), None)
                if not disk:
                    device_name = disk_name.split("/")[-1] if "/" in disk_name else disk_name
                    disk = next((d for d in parsed_disks if device_name in d.get("name", "")), None)
                if disk and property in disk:
                    value = str(disk.get(property, "N/A"))
                    self.parent.log(
                        logging.INFO,
                        f"Found {property}={value} for {mount_point} from disk {disk.get('name')}",
                    )
                else:
                    self.parent.log(
                        logging.WARNING,
                        f"Property '{property}' not found for mount point '{mount_point}' (source: {disk_name})",
                    )

        except Exception as ex:
            self.parent.handle_error(ex)
            value = f"ERROR: Parsing failed: {str(ex)}"

        return value

    def collect(self, check, context) -> Any:
        """
        Collect and parse Azure resource data

        This method delegates to azure_resource_collector module to get raw data,
        then parses it according to the check requirements.
        """
        try:
            command = check.collector_args.get("command", "")
            if command:
                return CommandCollector(self.parent).collect(check, context)

            resource_type = check.collector_args.get("resource_type", "")
            method_name = f"parse_{resource_type}_vars"
            parameters = {
                "context": context,
                "check": check,
            }
            return (
                getattr(self, method_name)(**parameters)
                if hasattr(self, method_name)
                else "ERROR: Unsupported resource type"
            )

        except Exception as ex:
            self.parent.handle_error(ex)
            return f"ERROR: Azure data collection failed: {str(ex)}"


class ModuleCollector(Collector):
    """
    Collects data from Ansible module results stored in context
    """

    def collect(self, check, context) -> Any:
        """
        Retrieve module result data from context.

        The module should have been executed by the playbook before calling
        the configuration check, and its result stored in the context.

        :param check: Check object with module information
        :type check: Check
        :param context: Context variables containing module results
        :type context: Dict[str, Any]
        :return: The data from the module result
        :rtype: Any
        """
        try:
            module_name = check.collector_args.get("module_name", "")
            context_key = check.collector_args.get("context_key", "")

            if not module_name:
                return "ERROR: No module_name specified"

            if not context_key:
                module_context_map = {
                    "get_pcmk_properties_db": "ha_db_config",
                    "get_pcmk_properties_scs": "ha_scs_config",
                    "get_azure_lb": "ha_loadbalancer_config",
                }
                context_key = module_context_map.get(module_name, module_name)

            return context.get(
                context_key, f"ERROR: Module result '{context_key}' not found in context"
            )

        except Exception as ex:
            self.parent.handle_error(ex)
            return f"ERROR: Module data retrieval failed: {str(ex)}"
