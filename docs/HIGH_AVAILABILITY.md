# SAP High Availability Testing

A key component of the SAP Testing Automation framework is the SAP High Availability (HA) Testing. This helps in ensuring that an SAP system deployment complies to SAP on Azure best practices and guidelines.

The SAP High Availability Testing scenario executes a series of tests designed to simulate real-world failures, ensuring the system's recovery capabilities. Leveraging Ansible, the framework orchestrates various test cases, including node crashes, network disruptions, and storage failures, to validate the effectiveness of recovery mechanisms. Additionally, the framework captures comprehensive logs and generates detailed reports on the test outcomes.

## Supported Configurations

### Linux distribution

Currently SAP Testing Automation Framework is supported for below Linux distros and version.

| Distribution | Supported Release |  
|--------------|-------------------|
| SUSE Linux Enterpise Server (SLES) | 15 SP4, 15 SP5, 15 SP6 |
| Red Hat Enterprise Linux (RHEL) | 8.8, 8.10, 9.2, 9.4 |

### High Availability configuration pattern

| Component | Type | Cluster Type | Storage |
|-----------|------|--------------|---------|
| SAP Central Services | ENSA1 or ENSA2 | Azure Fencing Agent | Azure Files or ANF |
| SAP Central Services | ENSA1 or ENSA2 | ISCSI (SBD device) | Azure Files or ANF |
| SAP Central Services | ENSA1 or ENSA2 | Azure Shared Disks (SBD device) | Azure Files or ANF |
| SAP HANA | Scale-up | Azure Fencing Agent | Azure Managed Disk or ANF |
| SAP HANA | Scale-up | ISCSI (SBD device) | Azure Managed Disk or ANF |
| SAP HANA | Scale-up | Azure Shared Disks (SBD device) | Azure Managed Disk or ANF |

For SAP Central Services on SLES, both the simple mount approach and the classic method are supported.


### Enabling Cluster Services on Boot

Before executing the tests, ensure that the cluster services are configured to start automatically during system boot. Run the following command on one of the cluster nodes to enable this setting. The `--all` option ensures that the cluster services are enabled on all nodes within the cluster.

```bash
crm cluster enable --all  # for SUSE virtual machines
pcs cluster enable --all  # for RedHat virtual machine
```

### 1. Setup Configuration

Follow the steps in [Setup Guide for SAP Testing Automation Framework](./SETUP.MD) to set up the framework on a management server.

### 2. Configuration

#### 2.1. Test Environment Configuration

2.1.1. Navigate to the root directory

```bash
cd sap-automation-qa
```

2.1.2. Update `vars.yaml` with your test parameters. This file contains the variables used in the test cases:

```yaml
# The type of test to be executed. Supported values are:
# - SAPFunctionalTests
TEST_TYPE: "SAPFunctionalTests"

# The type of SAP functional test to be executed. Supported values are:
# - DatabaseHighAvailability
# - CentralServicesHighAvailability
sap_functional_test_type: "DatabaseHighAvailability"  # or "CentralServicesHighAvailability"

# The name of the SAP system configuration for which you want to execute the test cases.
# It would be the name of the folder under 'WORKSPACE/SYSTEM/' where it could find hosts.yaml, sap-parameters.yaml files of the SAP system configuration
SYSTEM_CONFIG_NAME: "DEV-WEEU-SAP01-X00"

# The type of authentication to be used for the telemetry data destination. Supported values are: VMPASSWORD and SSHKEY
AUTHENTICATION_TYPE: 

# The destination of the telemetry data. Supported values are:
# - azureloganalytics
# - azuredataexplorer (only recommended for long-term storage)
telemetry_data_destination: "azureloganalytics"

# The name of the telemetry table in the telemetry data destination.
telemetry_table_name: "your-telemetry-table-name"

# The workspace id, shared key of the Log Analytics workspace.
laws_shared_key: "your-log-analytics-shared-key"
laws_workspace_id: "your-log-analytics-workspace-id"

# The cluster name, data ingestion URI, and client ID of the Azure Data Explorer.
adx_cluster_fqdn: "your-adx-cluster-fqdn"
adx_database_name: "your-adx-database-name"
ade_client_id: "your-adx-client-id"
```

#### 2.2. System Configuration (WORKSPACES)

Create your system workspace. This directory contains the configuration files specific to your SAP system, necessary for connecting to the system and executing test scenarios. The `WORKSPACE/SYSTEM/` directory holds sub-directories, each representing a different [SAP system](./WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00).

```bash
cd WORKSPACES/SYSTEM
mkdir ENV-REGION-VNET-SID
cd ENV-REGION-VNET-SID
```

The system workspace should include the following files, containing all necessary details about the SAP system.

2.2.1. **hosts.yaml** - System [Inventory file](https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html) (required)

This file contains the connection details for the SAP system hosts and is used as an inventory file by the Ansible framework to connect to the SAP system. You can find the inventory file in the path [hosts.yaml](../WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/hosts.yaml).

Here is an example of the hosts.yaml file format:

```yaml
X00_DB:
  hosts:
    hostname0:
      ansible_host: "IP_ADDRESS0"
      ansible_user: "USERNAME"
      ansible_connection: "ssh"
      connection_type: "key"
      virtual_host: "VIRTUAL_HOSTNAME0"
      become_user: "USERNAME1" #Username with root privilege
      os_type: "linux"
      vm_name: "AZURE_VM_NAME0"
    hostname1:
      ansible_host: "IP_ADDRESS1"
      ansible_user: "USERNAME"
      ansible_connection: "ssh"
      connection_type: "key"
      virtual_host: "VIRTUAL_HOSTNAME1"
      become_user: "USERNAME1" #Username with root privilege
      os_type: "linux"
      vm_name: "AZURE_VM_NAME1"
  vars:
    node_tier: "hana"  # or "ers", "scs"
```

In the file:

- X00 represents the SAP SID (System ID) of the SAP system, followed by the host type (e.g., DB, ASCS, PAS). You must provide the SAP SID of the system, regardless of whether you are testing Database High Availability or Central Services High Availability.

The file includes the following details:

- **ansible_host**: The IP address of the host.
- **ansible_user**: The user for connecting to the host.
- **ansible_connection**: The connection type (usually "ssh").
- **connection_type**: The connection type, used when connecting via SSH key (not needed for password-based connections).
- **virtual_host**: The virtual host name of the SCS/DB host.
- **become_user**: The user with root privileges. For example, user "azureadm" must be able to change to root without password.
- **os_type**: The operating system type (e.g., Linux or Windows).
- **vm_name**: The computer name of the Azure VM.
- **node_tier**: The type of node tier. Supported values: hana, ers, scs.

2.2.2. **sap-parameters.yaml** - SAP Configuration (required)

This file contains the SAP system configuration parameters. The parameters are used by the test scenarios to validate the system's high availability configuration. You can find the inventory file in the path [sap-parameters.yaml](../WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/sap-parameters.yaml).

Here is an example of the sap-parameters.yaml file format:

```yaml
# The SAP and Database SID of the SAP system.
sap_sid: "your-sap-sid"
db_sid: "your-db-sid"

# Boolean indicating if the SCS and database is configured as highly available.
scs_high_availability: true
database_high_availability: true

# The high availability configuration of the SCS and DB instance. Supported values are:
# - AFA (for Azure Fencing Agent)
# - ISCSI (for SBD devices with ISCSI target servers)
# - ASD (for SBD devices with Azure Shared Disks)
scs_cluster_type: "AFA"  # or "ISCSI" or "ASD"
database_cluster_type: "AFA"  # or "ISCSI" or "ASD"

# The instance number of the SCS, ERS and DB instance.
scs_instance_number: "00"
ers_instance_number: "01"
db_instance_number: "00"

# The type of database. Supported values are:
# - HANA
platform: "HANA"

# The NFS provider used for shared storage. Supported values are:
# - ANF (for Azure NetApp Files)
# - AFS (for Azure File Share)
NFS_provider: "ANF"  # or "AFS"

# If you're using a user-assigned managed identity (as explained in "Azure RBAC" section above):
#  - Enter the client ID of that identity here
#  - You can find this ID in Azure Portal → Managed Identities → Your Identity → Properties → Client ID
# If you're using system-assigned managed identity instead:
#  - Leave this blank or set to empty string ""
user_assigned_identity_client_id: "000000-00000-00000-00000-000000"

# If you have the SSH key or VM password stored in an Azure Key Vault as a secret:
#  - Enter the Azure Key Vault Resource ID in the key_vault_id parameter and the Secret ID in the secret_id parameter.
#  - You can find the Resource ID of the Key Vault in Azure Portal → Key Vaults → Your Key Vault → JSON view → Copy the Resource ID  
#  - You can find the Resource ID of the Secret in Your Key Vault → Secrets → Select Secret → Current Version → Copy the Secret Identifier  
# If you're creating SSHKEY or VMPASSWORD file locally:
#  - Remove the following two parameters
key_vault_id:                  /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.KeyVault/vaults/<key-vault-name>
secret_id:                     https://<key-vault-name>.vault.azure.net/secrets/<secret-name>/<id>
```

2.2.3. **Credential Files** (Available locally)

The required credential files depend on the authentication method used to connect to the SAP system:

1. **SSH Key Authentication**: If connecting via SSH key, place the private key inside `WORKSPACE/SYSTEM/<DIRECTORY>` and name the file "ssh_key.ppk".
1. **Password Authentication**: If connecting using a username and password, create a password file by running the following command. It takes the username from hosts.yaml file. 

  ```bash
  echo "password" > WORKSPACES/SYSTEM/<DIRECTORY>/password
  ```

2.2.4. **Credential Files** (From Azure Key Vault)

When using Azure Key Vault to store credentials, the framework retrieves authentication details directly from the key vault using the configured managed identity.

  **Authentication Methods:**

  1. **SSH Key Authentication**: Store the private SSH key content in Azure Key Vault as a secret.
  2. **Password Authentication**: Store the password in Azure Key Vault as a secret. The username is taken from the `hosts.yaml` file.

  **Setup:**

  1. Ensure the managed identity has "Key Vault Secrets User" role on the key vault.

  2. Configure `key_vault_id` and `secret_id` parameters in `sap-parameters.yaml` as shown in section 2.2.2.

  **Important**: When using Key Vault authentication, do NOT create local credential files (`ssh_key.ppk` or `password` files).


### 3. Test Execution

To execute the script, run following command:

```bash
# Run all the tests with default parameters
./scripts/sap_automation_qa.sh

# Run specific test cases from HA_DB_HANA group
./scripts/sap_automation_qa.sh --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash]

# Run specific test cases from HA_SCS group
./scripts/sap_automation_qa.sh --test_groups=HA_SCS --test_cases=[ha-config]

# Run with verbose output
./scripts/sap_automation_qa.sh --test_groups=HA_DB_HANA --test_cases=[primary-node-crash] -vvv
```

### 4. Viewing Test Results

After the test execution completes, a detailed HTML report is generated that summarizes the PASS/FAIL status of each test case and includes detailed execution logs for every step of the automation run.

**To locate and view your test report:**

1. **Navigate to your SAP system’s workspace directory:**

   Replace `<SYSTEM_CONFIG_NAME>` with the name of your SAP system configuration (for example, `DEV-WEEU-SAP01-X00`):

   ```bash
   cd WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/quality_assurance/
   ```
2. **Find your report file:**

   The report file is named using the following format:

   ```
   HA_{SAP_TIER}_{DATABASE_TYPE}_{OS_DISTRO_NAME}_{INVOCATION_ID}.html
   ```

   - `SAP_TIER`: The SAP tier tested (e.g., DB, SCS)
   - `DATABASE_TYPE`: The database type (e.g., HANA)
   - `OS_DISTRO_NAME`: The operating system distribution (e.g., SLES15SP4)
   - `INVOCATION_ID`: A unique identifier (Group invocation ID) for the test run which is logged at the end of test execution. Find example screenshot below:

      ![Test Execution Completion Screenshot](./images/execution_screenshot.png)

3. **View the report**

   You can open the HTML report in any web browser to review the results and logs.

## Update the framework

To ensure you have the latest features and fixes, it's important to keep your fork of the SAP Testing Automation Framework up to date. You can do this by pulling the latest changes from the original repository into your fork.

### Steps to update your fork

1. **Ensure you have the upstream repository configured**:

    ```bash
    # Check if you already have the upstream remote
    git remote -v

    # If you don't see an 'upstream' entry, add it
    git remote add upstream https://github.com/Azure/sap-automation-qa.git
    ```

2. **Fetch the latest changes from the upstream repository**:

    ```bash
    git fetch upstream
    ```

3. **Ensure you're on your main branch**:

    ```bash
    git checkout main
    ```

4. **Merge the changes from upstream into your local fork**:

    ```bash
    git merge upstream/main
    ```

5. **Push the updated code to your GitHub fork**:

    ```bash
    git push origin main
    ```

This process will update your fork with all the latest features, bug fixes, and improvements from the original SAP Testing Automation Framework repository.

> **NOTE**
> If you've made local changes to your fork, you might encounter merge conflicts during step 4. In that case, you'll need to resolve these conflicts before proceeding with the push in step 5.

## Additional Resources

- [Azure SAP Documentation](https://docs.microsoft.com/azure/sap)
