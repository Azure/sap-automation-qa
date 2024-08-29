# HA Testing Framework User Guide

## What is HA Testing Framework
HA Testing Framework is a ansible based framework that is used to test the High Availability of an SAP system. It is a generic framework that can be used to test any SAP system that is designed to be highly available. The framework is designed to be modular and extensible. It is easy to add new test cases and new test scenarios. The framework is designed to be easy to use and easy to understand.

## Components of HA Testing Framework
The HA Testing Framework is made up of the following components:
1. Ansible Playbooks and Roles
2. Scripts that help in the execution of the test cases
3. WORKSPACES: SAP system specific configuration files, which include inventory file, configuration file, and connection keys that are required to connect to the SAP system. Please refer to the WORKSPACES section for more details.

## How to execute the test cases?
1. Clone the HA Testing Framework repository.
```
git clone https://github.com/devanshjainms/sap-automaiton-qa.git
```
2. Navigate to the WORKSPACES/SYSTEM directory and update the SAP system configuration based on the details mentioned below in WORKSPACES section. You can refer to an example configuration in the WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00 directory.
```
cd WORKSPACES/SYSTEM
mkdir SYSTEM_CONFIG_NAME
cd SYSTEM_CONFIG_NAME
```
3. Navigate to the scripts directory and execute the run_tests.sh script.
```
cd scripts
./sap_automation_qa.sh
After the test execution completes, a HTML reqport is generated in the WORKSPACES/SYSETEM/CONFIG_NAME/quality_assurance/ directory. You can copy and view this report in a web browser. You can also optionally choose to send data to Azure Log Analytics or Azure Data Explorer by setting the telemetry_data_destination variable in the vars.yaml file.

## WORKSPACES
WORKSPACES/SYSTEM/SYSTEM_CONFIG_NAME are SAP system specific configuration files that are required to connect to the SAP system. A WORKSPACE is a directory that contains the following files:
### 1. hosts.yaml file: This file contains the IP addresses of the SAP system hosts in the following format:
```
X00_DB:
  hosts:
    x00dhdb00l01f:
      ansible_host        : 127.0.0.1
      ansible_user        : azureadm
      ansible_connection  : ssh
      connection_type     : key
      virtual_host        : x00dhdb00l01f
      become_user         : root
      os_type             : linux
      vm_name             : AZURE_VM_NAME

    x00dhdb00l11f:
      ansible_host        : 127.0.0.1
      ansible_user        : azureadm
      ansible_connection  : ssh
      connection_type     : key
      virtual_host        : x00dhdb00l11f
      become_user         : root
      os_type             : linux
      vm_name             : AZURE_VM_NAME_2
```
`
X00 is the SAP SID of the SAP system afollowed by the hosts type (DB, ASCS, PAS, etc.). The hosts.yaml file contains the following information:

The hosts.yaml file contains the following information:
ansible_host: The IP address of the host.
ansible_user: The user to connect to the host.
ansible_connection: The connection type.
connection_type: The type of connection.
virtual_host: The virtual host name of the SCS/DB host.
become_user: The user that has root privileges.
os_type: The operating system type linux/windows.
vm_name: The computer name of the Azure VM.

Please refer to an example hosts.yaml in the WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/hosts.yaml file.

### 2. sap-parameters.yaml file: This file contains the configuration details of the SAP system:
i. sap_sid: The SAP SID of the SAP system.
ii. scs_high_availability: Boolean indicating if the SCS is configured as highly available.
iii. scs_cluster_type: The high availability configuration of the SCS instance. The value depends on the high availability configuration of the SCS instance. Supported values are:
- AFA (Azure Fencing Agent)

iv. db_sid: The database SID of the SAP system.
v. db_instance_number: The instance number of the DB instance.
vi. platform: The type of database: Supported values are"
- HANA
vii. db_high_availability: Boolean indicating if the database is configured as highly available.
viii. database_cluster_type: The high availability configuration of the DB instance. The value depends on the high availability configuration of the DB instance. Supported values are:
- AFA (Azure Fencing Agent)

ix. use_key_vault: Boolean indicating if the ssh key is stored in Azure Key Vault.
x. keyvault_resource_id: The resource ID of the Azure Key Vault where the ssh key is stored. The jumpbox should have the system assigned managed identity enabled, and the managed identity should have access to the Azure Key Vault secrets.
xi. keyvault_secret_name: The name of the secret in the Azure Key Vault where the ssh key is stored.

### 3. ssh_key.ppk file: This file contains the private key that is used to connect to the SAP system hosts. The private key is stored in the ppk format. If you use_key_vault as false, the private key is stored in the ssh_key.ppk file. If you use_key_vault as true, the private key is stored in the Azure Key Vault.


### 4. vars.yaml file: This file contains the variables that are used in the test cases. The vars.yaml file contains the following information:
i. TEST_TYPE: The type of test to be executed. Supported values are:
- SAPFunctionalTests
ii. sap_functional_test_type: The type of SAP functional test to be executed. Supported values are:
- DatabaseHighAvailability
- CentralServicesHighAvailability
iii. SYSTEM_CONFIG_NAME: The name of the SAP system configuration that you want to execute the test cases for. 
iv. ssh_key_from_kv: Boolean indicating if the ssh key is stored in Azure Key Vault.
v. telemetry_data_destination: The destination of the telemetry data. Supported values are: azureloganalytics, azuredataexplorer
vi. telemetry_table_name: The name of the telemetry table in the telemetry data destination.
vii. laws_shared_key: The shared key of the Log Analytics workspace.
viii. laws_workspace_id: The workspace ID of the Log Analytics workspace.
ix. adx_cluster_fqdn: The cluster name of the Azure Data Explorer.
x. adx_database_name: The database name of the Azure Data Explorer.
xi. ade_client_id: The client ID of the Azure Data Explorer. 

