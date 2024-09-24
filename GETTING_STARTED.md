# HA Testing Framework User Guide
## What is the HA Testing Framework?
The HA Testing Framework is an Ansible-based framework used to test the High Availability of an SAP system. It is a generic framework that can be used to test any SAP system designed to be highly available. The framework is modular and extensible, making it easy to add new test cases and scenarios. It is designed to be user-friendly and easy to understand.

## Components of the HA Testing Framework
The HA Testing Framework consists of the following components:

- Ansible playbooks and roles
- Scripts to help execute the test cases
- WORKSPACES: SAP system-specific configuration files, including inventory files, configuration files, and connection keys required to connect to the SAP system. Please refer to the [WORKSPACES](#workspaces) section for more details.

## Pre-requisites to run the HA Testing Framework
- SAP System on Azure Cloud (Required):
Your SAP system must be hosted on the Azure cloud and configured with high availability. For supported high availability configurations, please refer to the supported scenarios. 

- Ubuntu Jump Host (Required):
A Ubuntu OS based jump host must be running on Azure with connectivity to the SAP system's virtual network. This host will facilitate secure management and access to the SAP environment.

- Data Storage for Test Results (Optional):
Optionally, configure a data factory, such as Azure Log Analytics or Azure Data Explorer, where test results can be stored in a tabular structure for further analysis.

## How to run the test cases for you SAP system?
1. Log in to the Virtual Machine (jump box):
Access the virtual machine (jump box) that has connectivity to your SAP systems and log in as the root user.

2. Clone the HA Testing Framework Repository:
On the logged-in Linux machine, clone the HA Testing Framework repository:
```
git clone https://github.com/devanshjainms/sap-automaiton-qa.git
cd sap-automation-qa
```
3. Run the setup script (one time setup):
This script sets up the test environment by installing the necessary dependencies for the test framework to execute the tests. In addition to these dependencies, the setup script also creates a Python virtual environment. This virtual environment will later be utilized by the Ansible playbooks to install Python dependencies.
```
# installs "python3-pip" "ansible" "sshpass" "python3-venv"
cd scripts
./setup.sh
``` 
4. Configure the Test Environment:
Update the test configuration file vars.yaml located in the root directory to set up the test environment. Detailed information about the parameters defined in this file can be found in the [Test Configuration File](#test-configuration-file) section.

5. Set Up SAP System Configuration:
Navigate to the WORKSPACES/SYSTEM directory and configure your SAP system based on the specifications outlined in the [WORKSPACES](#workspaces) section. You can reference an example configuration in the [WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00](./WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/) directory:
```
cd WORKSPACES/SYSTEM
mkdir ENV-REGION-VNET-SID
cd ENV-REGION-VNET-SID
```
6. Execute the Test Script:
Navigate to the scripts directory and run the sap_automation_qa.sh script:
```
cd scripts
./sap_automation_qa.sh
```
7. View Test Results:
After the test execution completes, an HTML report will be generated in the WORKSPACES/SYSTEM/SYSTEM_CONFIG_NAME/quality_assurance/ directory. You can copy and view this report in a web browser. Additionally, if you wish to send data to Azure Log Analytics or Azure Data Explorer, set the telemetry_data_destination variable in the vars.yaml file. More details on this can be found in the [WORKSPACES](#workspaces) section.

## Test configuration file

`vars.yaml` File
This file contains the variables used in the test cases. The vars.yaml file contains the following information:
- TEST_TYPE: The type of test to be executed. Supported values are:
  - SAPFunctionalTests
- sap_functional_test_type: The type of SAP functional test to be executed. Supported values are:
  - DatabaseHighAvailability
  - CentralServicesHighAvailability
- SYSTEM_CONFIG_NAME: The name of the SAP system configuration for which you want to execute the test cases.
- ssh_key_from_kv: Boolean indicating if the SSH key is stored in Azure Key Vault.
- telemetry_data_destination: The destination of the telemetry data. Supported values are:
  - azureloganalytics
  - azuredataexplorer
- telemetry_table_name: The name of the telemetry table in the telemetry data destination.
- laws_shared_key: The shared key of the Log Analytics workspace.
- laws_workspace_id: The workspace ID of the Log Analytics workspace.
- adx_cluster_fqdn: The cluster name of the Azure Data Explorer.
- adx_database_name: The database name of the Azure Data Explorer.
- ade_client_id: The client ID of the Azure Data Explorer.

## WORKSPACES
This directory contains the configuration files specific to your SAP system, necessary for connecting to the system and executing test scenarios. The WORKSPACE/SYSTEM/ directory holds sub-directories, each representing a different SAP system. Each of these system-specific directories should have the following files:

1. `hosts.yaml` File (required)
This file contains the connection properties of the SAP system hosts. This file acts as a [inventory file](https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html) for the ansible framework to connect to the SAP system. Example of a inventory file:
```yaml
X00_DB:
  hosts:
    x00dhdb00l01f:
      ansible_host: 127.0.0.1
      ansible_user: azureadm
      ansible_connection: ssh
      connection_type: key
      virtual_host: x00dhdb00l01f
      become_user: root
      os_type: linux
      vm_name: AZURE_VM_NAME

    x00dhdb00l11f:
      ansible_host: 127.0.0.1
      ansible_user: azureadm
      ansible_connection: ssh
      connection_type: key
      virtual_host: x00dhdb00l11f
      become_user: root
      os_type: linux
      vm_name: AZURE_VM_NAME_2
  vars:
    node_tier: hana
```
`X00` is the SAP SID of the SAP system, followed by the host type (DB, ASCS, PAS, etc.). You should provide the SAP SID of the SAP system, regardless of whether you are testing Database High Availability or Central Services High Availability. The `hosts.yaml` file contains the following information:
- `ansible_host`: The IP address of the host.
- `ansible_user`: The user to connect to the host.
- `ansible_connection`: The connection type.
- `connection_type`: The type of connection. Applicable only when using ssh key for connection, while using password, this should not be specified.
- `virtual_host`: The virtual host name of the SCS/DB host.
- `become_user`: The user with root privileges.
- `os_type`: The operating system type (Linux/Windows).
- `vm_name`: The computer name of the Azure VM.
- `node_tier`: This defines the type of node tier. Supported values: hana, ers, scs

Please refer to an example `hosts.yaml` in the `WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/hosts.yaml` file.

2. `sap-parameters.yaml` File (required)
This file contains the configuration details of the SAP system:

  - sap_sid: The SAP SID of the SAP system.
  - scs_high_availability: Boolean indicating if the SCS is configured as highly available.
  - scs_cluster_type: The high availability configuration of the SCS instance. Supported values are:
    - AFA (Azure Fencing Agent) 
  - db_sid: The database SID of the SAP system.
  - db_instance_number: The instance number of the DB instance.
  - platform: The type of database. Supported values are:
    - HANA
  - db_high_availability: Boolean indicating if the database is configured as highly available.
  - database_cluster_type: The high availability configuration of the DB instance. Supported values are:
    - AFA (Azure Fencing Agent)
  - use_key_vault: Boolean indicating if the SSH key is stored in Azure Key Vault.
  - keyvault_resource_id: The resource ID of the Azure Key Vault where the SSH key is stored. The jumpbox should have the system-assigned managed identity enabled, and the managed identity should have access to the Azure Key Vault secrets.
  - keyvault_secret_name: The name of the secret in the Azure Key Vault where the SSH key is stored.

3. `ssh_key.ppk` File (optional)
This file contains the private key used to connect to the SAP system hosts. The private key is stored in the PPK format. If use_key_vault is false, the private key is stored in the ssh_key.ppk file. If use_key_vault is true, the private key is stored in the Azure Key Vault.

4. `password` File (optional)
This contains of the password, in plain text, for the SAP system hosts.

### Supported scenarios

| SAP Tier | SAP Tier Type  | Cluster Type | High Availability |
| :----------- | :------------ | :------------ | :------------- |
| Central Services       |     NA     | Azure Fencing Agent         | Yes |
| Database       |      HANA    | Azure Fencing Agent         | Yes |