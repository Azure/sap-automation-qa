# SAP Automation QA - Offline Validation

The offline validation feature for SAP High Availability (HA) clusters within the SAP Testing Automation Framework allows for the robust validation of SAP HANA and SAP Central Services HA cluster configurations without requiring direct access to the live cluster environment. By using cluster configuration files (CIB XML), you can audit and validate your cluster setup, ensuring it meets the required standards and best practices. Offline validation provides the capability for maintaining configuration integrity, performing regular audits, and troubleshooting without connecting to the production systems.

## How Offline Validation Works

The offline validation process relies on cluster configuration information extracted into CIB (Cluster Information Base) XML files. The validation engine processes these files to analyze the cluster's configuration against a set of predefined rules and best practices.

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CIB XML       │    │   Validation     │    │   HTML Report   │
│   Output        │───▶│   Engine        │───▶│   Generation    │
│   (In files)    │    │                  │    │   (with Tables) │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

1.  **CIB XML Files**: These files contain a snapshot of the Pacemaker cluster configuration from each node.
2.  **Validation Engine**: The engine parses the CIB XML files and evaluates the configuration parameters, resource settings, and constraints.
3.  **HTML Report**: The results are compiled into a detailed HTML report, which presents the validation checks in a clear, tabular format.

### Prerequisites

Before performing offline validation, ensure the following requirements are met:

- SAP Testing Automation Framework (STAF) setup on a management server. Detailed setup instructions can be found in the [STAF Setup Guide](./SETUP.md).
- You must collect CIB XML files from each node in the SAP HA cluster. These files must be stored in the appropriate directory structure `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/offline_validation/` on the management server.

### Required Files Structure

The offline validation process requires a specific directory structure on the management server. The CIB XML files must be placed within the workspace of the system being validated.

```file
WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/
├── hosts.yaml                   # Ansible inventory file for the SAP system.
├── sap-parameters.yaml          # SAP system parameters file.
└── offline_validation/          # Directory for offline validation artifacts.
    ├── <hostname1>/
    │   └── cib                  # CIB XML file from the first node.
    └── <hostname2>/
        └── cib                  # CIB XML file from the second node.
```

## How to Perform Offline Validation

Follow these steps to conduct an offline validation of your SAP HA cluster configuration.

### Step 1: Initial Setup

This setup is defined in the Getting Started section of the [High Availability Guide](./HIGH_AVAILABILITY.md). Ensure you have the following:

- Ansible inventory file (`hosts.yaml`) with the SAP system configuration.
- SAP system parameters file (`sap-parameters.yaml`).
- Updated vars.yaml file with the necessary parameters.

### Step 2: Collect CIB XML Files

First, collect the cluster configuration from each node in your SAP system.

1. Log in to each node of the HA cluster.

2. Execute the following command to export the cluster configuration to a file named `cib`:

   ```bash
   # Execute below command on both nodes
   cibadmin --query | tee cib
   ```

   This command captures the complete cluster configuration in XML format.

### Step 3: Transfer and Organize CIB Files

Next, transfer the `cib` files to your management server and organize them into the required directory structure.

1.  For each node, create a corresponding directory on the management server:

    ```bash
    mkdir -p WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/offline_validation/<hostname>/
    ```

    Replace `<SYSTEM_CONFIG_NAME>` with the name of your SAP system configuration and `<hostname>` with the hostname of the node from which the `cib` file was collected.

2.  Copy each `cib` file into its respective `<hostname>` directory.

### Step 4: Run Offline Validation

Once the CIB files are in place, execute the offline validation script.

1.  Navigate to the scripts directory of the SAP Automation QA framework.
2.  Run the `sap_automation_qa.sh` script with the `--offline` flag. You must also specify the target OS family using the `--extra-vars` parameter.

    For SUSE-based systems:
    ```bash
    ./scripts/sap_automation_qa.sh --offline --extra-vars='target_os_family=SUSE'
    ```

    For RHEL-based systems:
    ```bash
    ./scripts/sap_automation_qa.sh --offline --extra-vars='target_os_family=RHEL'
    ```

> [!TIP]
> For troubleshooting or detailed logging, you can run the script in verbose mode by adding the `-vvv` flag:
> ```bash
> ./scripts/sap_automation_qa.sh --offline --extra-vars='target_os_family=<os_family>' -vvv
> ```

### Step 5: View Results

After the script completes, the validation results are stored in an HTML file.

1.  Navigate to the quality assurance directory for your system configuration:

    `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/quality_assurance/`

2.  Open the HTML file in a web browser to view the detailed validation report. The report includes tables that show each parameter checked, its expected value, and its actual configured value, with clear pass/fail indicators.