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
| SAP HANA | Scale-up | Azure Fencing Agent | Azure Managed Disk or ANF |
| SAP HANA | Scale-up | ISCSI (SBD device) | Azure Managed Disk or ANF |

For SAP Central Services on SLES, both the simple mount approach and the classic method are supported.

## Technical Requirements for running Automation Framework

To run the SAP Testing Automation Framework, you must meet certain prerequisites and follow techincal requirements.

### SAP System Deployment on Microsoft Azure

- The SAP system must be hosted on Microsoft Azure Infrastructure-as-a-Service (IaaS).
- The SAP system deploymed should follow SAP on Azure best practices as outlined in:
  - [SAP HANA high availability on Azure Virtual Machine](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start).
  - [SAP Netweaver high availability on Azure Virtual Machine](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start)

### Enabling Cluster Services on Boot
    
Before executing the tests, ensure that the cluster services are configured to start automatically during system boot. Run the following command on one of the cluster nodes to enable this setting. The `--all` option ensures that the cluster services are enabled on all nodes within the cluster.

```bash
crm cluster enable --all  # for SUSE virtual machines
pcs cluster enable --all  # for RedHat virtual machine
```

### Management server

The SAP Testing Automation Framework requires a jumpbox or management server with the following setup:

- **Operating System**: Ubuntu 22.04 LTS.
- **Location**: Must be deployed on Azure.
  
> [!NOTE]
> Currently, only Ubuntu 22.04 LTS is supported for running the SAP Testing Automation Framework.

### Azure RBAC

For the framework to access the properties of the Azure Load Balancer in a high availability SAP system on Azure, the management server must have a Reader role assigned to the Load Balancer. This can be done using either a system-assigned or user-assigned managed identity.

#### Configuring access using system-assigned managed identity

1. Enable system managed identity on the management server by following the steps in [Configure managed identities on Azure VMs](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-to-configure-managed-identities?pivots=qs-configure-portal-windows-vm#system-assigned-managed-identity).
1. Open the Azure Load Balancer used for the high availability deployment of your SAP system on Azure.
1. In the Azure Load Balancer panel, go to Access control (IAM).
1. Follow steps from [Use managed identity to access Azure Resource](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-portal) to complete the configuration.

#### Configuring access using user-assigned managed identity

1. Create user-assigned managed identity as described in [manage user-assigned managed identities](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-manage-user-assigned-managed-identities?pivots=identity-mi-methods-azp#create-a-user-assigned-managed-identity)
1. Assign user-assigned managed identity to management server as described in [configure managed identities on Azure VMs](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-to-configure-managed-identities?pivots=qs-configure-portal-windows-vm#assign-a-user-assigned-managed-identity-to-an-existing-vm)
1. Open the Azure Load Balancer used for the high availability deployment of your SAP system on Azure.
1. In the Azure Load Balancer panel, go to Access control (IAM).
1. Assign the required role to the user-assigned managed identity by following the steps in [assign roles using Azure portal](https://learn.microsoft.com/azure/role-based-access-control/role-assignments-portal).

### Network Connectivity

The management server must have network connectivity to the SAP system to perform tests and validations. You can establish this connection by peering the networks as outlined in [manage a virtual network peering](https://learn.microsoft.com/azure/virtual-network/virtual-network-manage-peering?tabs=peering-portal).

### Analytics Integration (optional)

- **Analytics Integration** [Telemetry Setup Information](./TELEMETRY_SETUP.md)
  - Azure Log Analytics
  - Azure Data Explorer

## Getting Started

### 1. Environment Setup

To set up your enviroment in management server, follow these steps:

1.1. **Login to the Ubuntu management server**:

Ensure you are logged into the Ubuntu management server that is connected to the SAP system's virtual network.

1.2. **Fork and clone the repository**:

```bash
# sudo to root
sudo su -

# First, visit https://github.com/Azure/sap-automation-qa in your browser
# Click the "Fork" button in the top-right corner to create a fork in your GitHub account

# Clone your fork of the repository (replace GITHUB-USERNAME with your GitHub username)
git clone https://github.com/GITHUB-USERNAME/sap-automation-qa.git
cd sap-automation-qa
```

1.3. **Run the initial setup script**:

```bash
./scripts/setup.sh
```

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
db_high_availability: true

# The high availability configuration of the SCS and DB instance. Supported values are:
# - AFA (for Azure Fencing Agent)
# - ISCSI (for SBD devices)
scs_cluster_type: "AFA"  # or "ISCSI"
database_cluster_type: "AFA"  # or "ISCSI"

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

# If you've the SSHKEY or VMPASSWORD stored in the an Azure Key Vault as Secret:
#  - Enter the Azure Key Vault Resource ID in key_vault_id parameter and the Secrete ID in secret_id paramter.
#  - You can find the Resource ID of Key Vault in Azure Portal → Key Vaults → Your Key Vault → JSON view → Copy the Resource ID
#  - You can find the Resource ID of Secret in Your Key Vault → Secrets → Select Secret → Current Version → Copy the Secrete Identifier  
# If you're creating SSHKEY or VMPASSWORD file locally:
#  - Remove the following two parameters
key_vault_id:                  /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.KeyVault/vaults/<key-vault-name>
secret_id:                     https://<key-vault-name>.vault.azure.net/secrets/<secret-name>/<id>
```

2.2.3. Credential Files

The required credential files depend on the authentication method used to connect to the SAP system:

1. SSH Key Authentication: If connecting via SSH key, place the private key inside `WORKSPACE/SYSTEM/<DIRECTORY>` and name the file "ssh_key.ppk".
1. Username and Password Authentication: If connecting using a username and password, create a password file by running the following command. It takes the username from hosts.yaml file. 

  ```bash
  echo "password" > WORKSPACES/SYSTEM/<DIRECTORY>/password
  ```

### 3. Test Execution

To execute the script, run following command:

```bash
./scripts/sap_automation_qa.sh
```

### 4. Viewing Test Reports

After the test execution completes, a detailed report is generated. This report summarizes the PASS/FAIL status of each test case and includes detailed execution logs for every step of the automation run.

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
