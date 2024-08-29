# HA Testing Framework User Guide

## What is HA Testing Framework
#### HA Testing Framework is a ansible based framework that is used to test the High Availability of an SAP system. It is a generic framework that can be used to test any SAP system that is designed to be highly available. The framework is designed to be modular and extensible. It is easy to add new test cases and new test scenarios. The framework is designed to be easy to use and easy to understand.

## Components of HA Testing Framework
#### The HA Testing Framework is made up of the following components:
# 1. Ansible Playbooks and Roles
# 2. Scripts that help in the execution of the test cases
# 3. WORKSPACES: SAP system specific configuration files, which include inventory file, configuration file, and connection keys that are required to connect to the SAP system. Please refer to the WORKSPACES section for more details.

## WORKSPACES
#### WORKSPACES/SYSTEM/SYSTEM_CONFIG_NAME are SAP system specific configuration files that are required to connect to the SAP system. A WORKSPACE is a directory that contains the following files:
# 1. hosts.yaml file: This file contains the IP addresses of the SAP system hosts in the following format:
# ```
# X00_DB:
#   hosts:
#     x00dhdb00l01f:
#       ansible_host        : 127.0.0.1
#       ansible_user        : azureadm
#       ansible_connection  : ssh
#       connection_type     : key
#       virtual_host        : x00dhdb00l01f
#       become_user         : root
#       os_type             : linux
#       vm_name             : AZURE_VM_NAME

#     x00dhdb00l11f:
#       ansible_host        : 127.0.0.1
#       ansible_user        : azureadm
#       ansible_connection  : ssh
#       connection_type     : key
#       virtual_host        : x00dhdb00l11f
#       become_user         : root
#       os_type             : linux
#       vm_name             : AZURE_VM_NAME_2
# ```
# `
# X00 is the SAP SID of the SAP system afollowed by the hosts type (DB, ASCS, PAS, etc.). The hosts.yaml file contains the following information:

# The hosts.yaml file contains the following information:
# ansible_host: The IP address of the host.
# ansible_user: The user to connect to the host.
# ansible_connection: The connection type.
# connection_type: The type of connection.
# virtual_host: The virtual host name of the SCS/DB host.
# become_user: The user that has root privileges.
# os_type: The operating system type linux/windows.
# vm_name: The computer name of the Azure VM.

# Please refer to an example hosts.yaml in the WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/hosts.yaml file.

# 2. sap-parameters.yaml file: This file contains the configuration details of the SAP system:
# sap_sid: The SAP SID of the SAP system.
# scs_high_availability: The high availability configuration of the SCS instance. The value depends on the high availability configuration of the SCS instance. Supported values are:
# - AFA (Azure Fencing Agent)


# db_sid: The database SID of the SAP system.
# db_high_availability: The high availability configuration of the DB instance. The value depends on the high availability configuration of the DB instance.