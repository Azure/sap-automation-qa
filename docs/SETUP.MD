
# Setup Guide for SAP Testing Automation Framework

The SAP Testing Automation Framework allows you to execute:

1. High Availability (HA) functional test suites (HANA database, Central Services).
2. Configuration / compliance checks against an SAP on Azure deployment.

Execution is driven by Ansible-based playbooks and Python helpers, using metadata defined in YAML files under a per‑system workspace.

## Pre-requisites

### 1. SAP System Deployment on Microsoft Azure

- The SAP system must be hosted on Microsoft Azure Infrastructure-as-a-Service (IaaS).
- The SAP system deployed should follow SAP on Azure best practices as outlined in:
  - [SAP HANA high availability on Azure Virtual Machine](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start).
  - [SAP Netweaver high availability on Azure Virtual Machine](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start)

### 2. Management (Jump) server

The SAP Testing Automation Framework requires a management server, which must run one of the supported operating system versions listed in [Supported distributions for the management server](https://learn.microsoft.com/en-us/azure/sap/automation/testing-framework-supportability#supported-distributions-for-management-server). 

### 3. Network Connectivity

The management server must have network connectivity to the SAP system to perform tests and validations. If your management server is in a separate network from your SAP system, you must establish the connection by peering the networks as outlined in [manage a virtual network peering](https://learn.microsoft.com/azure/virtual-network/virtual-network-manage-peering?tabs=peering-portal).

### 4. Identity and authorization

The framework requires a managed identity to securely access Azure resources (like Load Balancers, Storage). You must configure **one** of the following two options.

#### Option 1: User-Assigned Managed Identity

1.  **Create a User-Assigned Managed Identity**:
    
    *   Follow the guide to [manage user-assigned managed identities](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-manage-user-assigned-managed-identities).
    *   After creation, navigate to the identity's **Overview** page and copy the **Client ID**. You will need this for `sap-parameters.yaml`.
    
2.  **Assign the Identity to the Management VM**:
    *   Navigate to your management server VM in the Azure Portal.
    *   Under **Settings**, select **Identity**.
    *   Go to the **User assigned** tab and click **+ Add**.
    *   Select the user-assigned identity you created.
    *   For detailed steps, see [configure managed identities on Azure VMs](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-to-manage-ua-identity-vm).

3.  **Assign Roles to the User-Assigned Identity**:
    
    This is a critical step to grant the identity permissions. We recommend to grant permission at the resource group level. 
    
    **Method 1: Assign roles from the managed identity.**
    
    1. Navigate to the user-assigned identity resource in the Azure Portal.
    2. Go to Azure role assignments to grant it the necessary permissions on other resources. The scope available here is limited to **Subscription**, **Resource group**, and a few other options. But if you want to assign roles per-resource like Azure load balancer, Azure NetApp Files etc., then follow method 2. 
    
    **Method 2: Assign roles from the target resource.**
    
    1. Navigate to the specific resource you want the identity to access (e.g., the Azure Load Balancer, Azure NetApp Files).
    2. Go to its **Access control (IAM)** blade.
    3. Click **Add > Add role assignment**.
    4. Select the required role (e.g., `Reader`\).
    5. For **Assign access to**, choose **Managed identity**.
    6. Click **+ Select members**, choose your subscription, and under **Managed identity**, select the user-assigned identity you created.
    7. Click **Review + assign**.
    8. Repeat this for every resource listed in the permissions table below. For detailed guidance, see [Assign Azure roles using the Azure portal](https://learn.microsoft.com/azure/role-based-access-control/role-assignments-portal).
    
4.  **Configure `sap-parameters.yaml`**:
    
    *   Paste the **Client ID** you copied in step 1 into the `user_assigned_identity_client_id` field.

#### Option 2: System-Assigned Managed Identity

A system-assigned identity is tied directly to the management server VM. It is created and deleted with the VM.

1.  **Enable System-Assigned Identity on the Management VM**:
    *   Navigate to your management server VM in the Azure Portal.
    *   Under **Settings**, select **Identity**.
    *   Under the **System assigned** tab, switch the **Status** to **On** and click **Save**.
    *   For detailed steps, follow the guide: [Configure managed identities on Azure VMs](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-to-manage-ua-identity-vm).

2. **Assign Roles to the Management VM's Identity**:

   This is a critical step to grant the management server VM permissions. We recommend to grant permission at the resource group level. 

   **Method 1: Assign roles from management server VM identity.**

   1. Navigate to the management server VM, select **identity** in the Azure Portal.
   2. Go to Azure role assignments to grant it the necessary permissions on other resources. The scope available here is limited to **Subscription**, **Resource group**, and a few other options. But if you want to assign roles per-resource like Azure load balancer, Azure NetApp Files etc., then follow method 2. 

   **Method 2: Assign roles from the target resource.**

   1. Navigate to the specific resource you want the identity to access (e.g., the Azure Load Balancer, Azure NetApp Files).
   2. Go to its **Access control (IAM)** blade.
   3. Click **Add > Add role assignment**.
   4. Select the required role (e.g., `Reader`\).
   5. For **Assign access to**, choose **Managed identity**.
   6. Click **+ Select members**, choose your subscription, and under **Managed identity**, select the system-assigned identity of management server.
   7. Click **Review + assign**.
   8. Repeat this for every resource listed in the permissions table below. For detailed guidance, see [Assign Azure roles using the Azure portal](https://learn.microsoft.com/azure/role-based-access-control/role-assignments-portal).

3.  **Configure `sap-parameters.yaml`**:
    *   When using a system-assigned identity, the `user_assigned_identity_client_id` parameter in `sap-parameters.yaml` must be left blank or set to an empty string (`""`).

### 5. Analytics Integration (optional)

- **Analytics Integration** [Telemetry Setup Information](./TELEMETRY_SETUP.md)
  - Azure Log Analytics
  - Azure Data Explorer

## Getting Started

### 1. Environment Setup

To set up your environment in management server, follow these steps:

1.1. **Login to the management server**:

Ensure you are logged into the management server that is connected to the SAP system's virtual network.

1.2. **Install git on management server**:

```bash
# Debian/Ubuntu
sudo su -
apt-get install git

# RHEL/CentOS
sudo su -
yum install git

# SUSE
sudo su -
zypper install git
```

1.3. **Fork and clone the repository**:

```bash
# sudo to root
sudo su -

# First, visit https://github.com/Azure/sap-automation-qa in your browser
# Click the "Fork" button in the top-right corner to create a fork in your GitHub account

# Clone your fork of the repository (replace GITHUB-USERNAME with your GitHub username)
git clone https://github.com/GITHUB-USERNAME/sap-automation-qa.git
cd sap-automation-qa
```

1.4. **Setup**

The framework supports two setup methods. You can set it up locally to run test playbooks from the command line, or deploy it as a Docker container that provides a REST API for automated test execution. Choose the method that best fits your workflow.
The containerized setup does not require the local setup, as it builds its own isolated environment.

#### 1.4.1. Local Setup

To set up the framework locally on the management server, run the following setup script. This script installs the necessary system packages (`python3-pip`, `sshpass`, `python3-venv`), Azure CLI (if not already installed), and creates a Python virtual environment with all required dependencies.

```bash
./scripts/setup.sh
```

Once the setup completes, activate the Python virtual environment:

```bash
source .venv/bin/activate
```

#### 1.4.2. Container Setup (Preview)

As an alternative to the local setup, the framework can also run as a Docker container on the management server. The containerized deployment exposes a REST API that allows you to execute tests, schedule recurring test runs, and monitor job status. For detailed information on API usage, scheduling, and troubleshooting, see [SAP QA Service](./SAP_QA_SERVICE.md).

The container builds its own isolated environment, so the local setup (step 1.4.1) is not required when using this approach. However, the system configuration described in section 2 must still be completed, as the container reads workspace configuration files from `WORKSPACES/SYSTEM/`.

To get started, run the following command to build and start the container:

```bash
./scripts/setup.sh container start
```

You can verify that the service is running and healthy by executing:

```bash
curl http://localhost:8000/healthz
```

Once the service is running, the API is available at `http://localhost:8000` and interactive API documentation can be accessed at `http://localhost:8000/docs`.

**Container Management:**

The following commands are available for managing the container lifecycle:

| Command | Description |
|---------|-------------|
| `./scripts/setup.sh container start` | Build and start the service |
| `./scripts/setup.sh container update` | Rebuild the image and restart the service |
| `./scripts/setup.sh container stop` | Stop the service |
| `./scripts/setup.sh container remove` | Remove the container, network, and volumes |

By default, `container start` builds the Docker image locally from source. To skip the local build and pull a pre-built image from an Azure Container Registry (ACR), you can pass the full image reference using the `--image` flag:

```bash
./scripts/setup.sh container start --image <acr-name>.azurecr.io/sap-automation-qa:latest
```

> [!NOTE]
> Using `--image` requires access to the ACR. The script attempts `az acr login` first. If that fails, set the `ACR_USERNAME` and `ACR_PASSWORD` environment variables before running the command.


### 2. System Configuration

#### 2.1. Test Environment Configuration

2.1.1. Navigate to the root directory

```bash
cd sap-automation-qa
```

2.1.2. Update `vars.yaml` with your test parameters. This file contains the variables used in the test cases:

```yaml
# The type of test to be executed. Supported values are:
# - SAPFunctionalTests
# - ConfigurationChecks
TEST_TYPE: "SAPFunctionalTests"

# The type of SAP functional test to be executed. Supported values are:
# - DatabaseHighAvailability
# - CentralServicesHighAvailability
# - Not required for ConfigurationChecks test type
SAP_FUNCTIONAL_TEST_TYPE: "DatabaseHighAvailability"  # or "CentralServicesHighAvailability"

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
# If laws_shared_key is not provided, it will be auto-fetched from Azure using the parameters below.
laws_shared_key: "your-log-analytics-shared-key"
laws_workspace_id: "your-log-analytics-workspace-id"

# Optional: Azure subscription and resource details for auto-fetching Log Analytics shared key.
# Required when laws_shared_key is not provided.
laws_subscription_id: "your-laws-subscription-id"
laws_resource_group: "your-laws-resource-group"
laws_workspace_name: "your-laws-workspace-name"

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
database_scale_out : false  # true if database high availability is configured as scale-out

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
NFS_provider: "AFS"  # or "ANF"

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

# ANF specific parameters (if NFS_provider is set to ANF)
# You can find these values in the Azure Portal → Your NetApp Account → Overview page
# ANF_account_rg: The resource group where the Azure NetApp Files account is located
# ANF_account_name: The name of the Azure NetApp Files account
ANF_account_rg:                "ANF-RESOURCE-GROUP"
ANF_account_name:              "ANF-ACCOUNT-NAME"
```

2.2.3. **Credential Files** (Available locally)

The required credential files depend on the authentication method used to connect to the SAP system:

1. **SSH Key Authentication**: If connecting via SSH key, place the private key inside `WORKSPACE/SYSTEM/<DIRECTORY>` and name the file "ssh_key.ppk".

1. **Password Authentication**: If connecting using a username and password, create a password file by running the following command. It takes the username from hosts.yaml file. 

   ```bash
   echo "password" > WORKSPACES/SYSTEM/<DIRECTORY>/password
   chmod 600 WORKSPACES/SYSTEM/<DIRECTORY>/password
   ```

> [!NOTE]
>
> If you are using a credential file locally, then you need to comment `key_vault_id` and `secret_id` in `sap-parameters.yaml`

2.2.4. **Credential Files** (From Azure Key Vault)

When using Azure Key Vault to store credentials, the framework retrieves authentication details directly from the key vault using the configured managed identity.

**Authentication Methods:**

    1. **SSH Key Authentication**: Store the private SSH key content in Azure Key Vault as a secret.
    2. **Password Authentication**: Store the password in Azure Key Vault as a secret. The username is taken from the `hosts.yaml` file. 

**Setup:**

  1. Ensure the managed identity has "Key Vault Secrets User" role on the key vault.

  2. Configure `key_vault_id` and `secret_id` parameters in `sap-parameters.yaml` as shown in section 2.2.2.

**Important**: When using Key Vault authentication, do NOT create local credential files (`ssh_key.ppk` or `password` files).

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
- [Container Deployment — SAP QA Service](./SAP_QA_SERVICE.md)
