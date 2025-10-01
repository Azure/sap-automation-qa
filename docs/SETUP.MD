
# Setup Guide for SAP Testing Automation Framework

## Technical Requirements for running Automation Framework

To run the SAP Testing Automation Framework, you must meet certain prerequisites and follow technical requirements.

### SAP System Deployment on Microsoft Azure

- The SAP system must be hosted on Microsoft Azure Infrastructure-as-a-Service (IaaS).
- The SAP system deployed should follow SAP on Azure best practices as outlined in:
  - [SAP HANA high availability on Azure Virtual Machine](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start).
  - [SAP Netweaver high availability on Azure Virtual Machine](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start)

### Management server

The SAP Testing Automation Framework requires a jumpbox or management server with the following setup:

- **Operating System**: Supported (Ubuntu 22.04 LTS, SLES 15 SP4, 15 SP6, REDHAT 9.4).
- **Location**: Must be deployed on Azure.

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

1.4. **Run the initial setup script**:

```bash
./scripts/setup.sh
```

1.5. **Activate the python environment**:

```bash
source .venv/bin/activate
```
