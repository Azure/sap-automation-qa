# SAP High Availability Testing Framework
## Overview
The SAP High Availability (HA) Testing Framework is a comprehensive, Ansible-based solution designed to validate the high availability configuration of SAP systems. This testing framework helps organizations ensure their SAP deployments meet reliability and availability requirements through automated testing, monitoring, and cluster validation processes.

The framework operates by executing a series of carefully designed test scenarios that simulate real-world failure conditions and validate system recovery capabilities. By leveraging Ansible's powerful automation capabilities, it can orchestrate complex test scenarios across multiple components while maintaining detailed logs and generating comprehensive reports of test outcomes.

### Purpose
High availability testing is crucial for maintaining business continuity in SAP environments. This framework addresses several critical needs:

**Risk Mitigation**: 
The framework provides systematic testing of failure scenarios, helping organizations identify and address potential issues before they impact production systems. It simulates various failure modes, including node failures, network interruptions, and storage issues, ensuring that recovery mechanisms function as designed.

**Compliance**: 
Organizations must often demonstrate that their SAP systems meet specific availability requirements. This framework provides documented evidence of HA testing, including detailed logs and reports that can be used for audit purposes. It helps ensure that HA implementations align with organizational standards and regulatory requirements.

**Quality Assurance**: 
Through automated and consistent testing procedures, the framework helps maintain high quality standards across SAP infrastructure components. It validates that all HA mechanisms, including clustering software, storage replication, and application-level failover, work together seamlessly.

**Automation**: 
Manual testing of HA configurations is time-consuming and prone to human error. This framework automates the entire testing process, from setup to execution and reporting, significantly reducing the operational overhead of HA testing while improving accuracy and consistency.

## Key Components
### Core Framework
- **Ansible Playbooks**: Automated test execution and system validation
- **Test Scripts**: Helper utilities for test case management
- **WORKSPACES**: System-specific configuration and credentials management
- **Reporting Engine**: Generates detailed HTML test reports

### System Requirements
#### Required Components
1. **SAP System on Azure Cloud**
   - The SAP system must be deployed on Azure infrastructure.
   - Configured with supported high availability patterns to ensure system reliability.
   - Network connectivity to the testing infrastructure must be established.

2. **Ubuntu Jump Host**
   - **Operating System**: Ubuntu 22.04 LTS.
   - **Location**: Deployed in Azure.
   - **Network**: Must be connected to the SAP system's virtual network.
   - **Permissions**: Requires a System Assigned/User Assigned managed identity with Reader Role at the subscription level.

#### Optional Components
- **Analytics Integration**
  - Azure Log Analytics
  - Azure Data Explorer

## Getting Started
### 1. Environment Setup
To set up your environment, follow these steps:

A. **Login to the Ubuntu Jump Host**:
Ensure you are logged into the Ubuntu Jump Host that is connected to the SAP system's virtual network.


B. **Clone the repository**:
  ```bash
  git clone https://github.com/devanshjainms/sap-automaiton-qa.git
  cd sap-automation-qa
  ```

C. **Run the initial setup script**:
  ```bash
  ./scripts/setup.sh
  ```

### 2. Configuration
#### A. Test Environment Configuration
1. Navigate to the root directory
```bash
cd sap-automation-qa
```

2. Update `vars.yaml` with your test parameters. This file contains the variables used in the test cases:

```yaml
# The type of test to be executed. Supported values are:
# - SAPFunctionalTests
TEST_TYPE: "SAPFunctionalTests"

# The type of SAP functional test to be executed. Supported values are:
# - DatabaseHighAvailability
# - CentralServicesHighAvailability
sap_functional_test_type: "DatabaseHighAvailability"  # or "CentralServicesHighAvailability"

# The name of the SAP system configuration for which you want to execute the test cases.
SYSTEM_CONFIG_NAME: "DEV-WEEU-SAP01-X00"

# Boolean indicating if the SSH key is stored in Azure Key Vault.
ssh_key_from_kv: false

# The destination of the telemetry data. Supported values are:
# - azureloganalytics
# - azuredataexplorer
telemetry_data_destination: "azureloganalytics"

# The name of the telemetry table in the telemetry data destination.
telemetry_table_name: "your-telemetry-table-name"

# The shared key of the Log Analytics workspace.
laws_shared_key: "your-log-analytics-shared-key"

# The workspace ID of the Log Analytics workspace.
laws_workspace_id: "your-log-analytics-workspace-id"

# The cluster name of the Azure Data Explorer.
adx_cluster_fqdn: "your-adx-cluster-fqdn"

# The database name of the Azure Data Explorer.
adx_database_name: "your-adx-database-name"

# The client ID of the Azure Data Explorer.
ade_client_id: "your-ade-client-id"
```

#### B. System Configuration (WORKSPACES)
Create your system workspace. This directory contains the configuration files specific to your SAP system, necessary for connecting to the system and executing test scenarios. The `WORKSPACE/SYSTEM/` directory holds sub-directories, each representing a different [SAP system](./WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00).

```bash
cd WORKSPACES/SYSTEM
mkdir ENV-REGION-VNET-SID
cd ENV-REGION-VNET-SID
```

#### Required Files
1. **hosts.yaml** - System [Inventory file](https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html) (required)
his file contains the connection properties of the SAP system hosts. This file acts as a inventory file for the ansible framework to connect to the SAP system. [Example of a inventory file](./WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/hosts.yaml):
```yaml
X00_DB:
  hosts:
    hostname0:
      ansible_host: "IP_ADDRESS0"
      ansible_user: "USERNAME"
      ansible_connection: "ssh"
      connection_type: "key"
      virtual_host: "VIRTUAL_HOSTNAME0"
      become_user: "root"
      os_type: "linux"
      vm_name: "AZURE_VM_NAME0"
    hostname1:
      ansible_host: "IP_ADDRESS1"
      ansible_user: "USERNAME"
      ansible_connection: "ssh"
      connection_type: "key"
      virtual_host: "VIRTUAL_HOSTNAME1"
      become_user: "root"
      os_type: "linux"
      vm_name: "AZURE_VM_NAME1"
  vars:
    node_tier: "hana"  # or "ers", "scs"
```

X00 is the SAP SID of the SAP system, followed by the host type (DB, ASCS, PAS, etc.). You should provide the SAP SID of the SAP system, regardless of whether you are testing Database High Availability or Central Services High Availability. The `hosts.yaml` file contains the following information:

- **ansible_host**: The IP address of the host.
- **ansible_user**: The user to connect to the host.
- **ansible_connection**: The connection type.
- **connection_type**: The type of connection. Applicable only when using SSH key for connection; when using a password, this should not be specified.
- **virtual_host**: The virtual host name of the SCS/DB host.
- **become_user**: The user with root privileges.
- **os_type**: The operating system type (Linux/Windows).
- **vm_name**: The computer name of the Azure VM.
- **node_tier**: This defines the type of node tier. Supported values: hana, ers, scs.


2. **sap-parameters.yaml** - SAP Configuration (required)
This file contains the SAP system configuration parameters. The parameters are used by the test scenarios to validate the system's high availability configuration. [Example of a SAP parameters file](./WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/sap-parameters.yaml):
```yaml
# The SAP SID of the SAP system.
sap_sid: "your-sap-sid"

# Boolean indicating if the SCS is configured as highly available.
scs_high_availability: false

# The high availability configuration of the SCS instance. Supported values are:
# - AFA (for Azure Fencing Agent)
# - ISCSI (for SBD devices)
scs_cluster_type: "AFA"  # or "ISCSI"

# The database SID of the SAP system.
db_sid: "your-db-sid"

# The instance number of the DB instance.
db_instance_number: "00"

# The type of database. Supported values are:
# - HANA
platform: "HANA"

# Boolean indicating if the database is configured as highly available.
db_high_availability: false

# The NFS provider used for shared storage. Supported values are:
# - ANF (for Azure NetApp Files)
# - AFS (for Azure File Share)
NFS_provider: "ANF"  # or "AFS"

# The high availability configuration of the DB instance. Supported values are:
# - AFA (for Azure Fencing Agent)
# - ISCSI (for SBD devices)
database_cluster_type: "AFA"  # or "ISCSI"
```

#### Optional Files
- **ssh_key.ppk**: SSH private key (if not using Key Vault)
- **password**: Host credentials (if not using SSH keys)

### 3. Test Execution
```bash
./scripts/sap_automation_qa.sh
```

## Supported Configurations
### High Availability Patterns
| Component | Database | Cluster Type | Storage |
|-----------|----------|--------------|----------|
| Central Services | N/A | Azure Fencing Agent | ANF/AFS |
| HANA Database | HANA | Azure Fencing Agent | ANF/AFS |
| HANA Database | HANA | SBD | ANF/AFS |

### Storage Solutions
- **ANF**: Azure NetApp Files
- **AFS**: Azure File Share

### Cluster Types
- **AFA**: Azure Fencing Agent
- **ISCSI**: SBD devices

## Troubleshooting
Test results and logs can be found in:
```
WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/quality_assurance/
```

## Additional Resources
- [Azure SAP Documentation](https://docs.microsoft.com/azure/sap)