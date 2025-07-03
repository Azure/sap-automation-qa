# SAP Automation QA - Offline Validation

## Overview

The offline validation feature enables robust validation of SAP HANA and SAP Central Services High Availability cluster configurations without requiring live cluster access or without connecting to the SAP virtual machines. This capability allows you to analyze cluster configurations from previously collected CIB (Cluster Information Base) XML files, making it ideal for post-incident analysis, compliance auditing, and troubleshooting scenarios.
Offline validation provides a powerful capability for maintaining and auditing SAP HANA cluster configurations without impacting production systems.

## How Offline Validation Works

### Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CIB XML       │    │   Validation     │    │   HTML Report   │
│   Output        │───▶│   Engine        │───▶│   Generation    │
│   (In files)    │    │                  │    │   (with Tables) │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```


### Prerequisites

- SAP Testing Automation Framework (STAF) setup on a management server. Detailed setup instructions can be found in the [STAF Setup Guide](./HIGH_AVAILABILITY.md).
- Previously collected CIB XML files stored in the `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/offline_validation/` directory.

### Required Files Structure
```file
WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/
├── hosts.yaml                   # Ansible inventory
├── sap-parameters.yaml          # SAP system parameters
└── offline_validation/          # Output of commands for offline validation
    ├── <hostname1>/
    │   └── cib                  # CIB XML file for node 1
    └── <hostname2>/
        └── cib                  # CIB XML file for node 2
```

## How to Perform Offline Validation

### Step 1: Initial Setup

This setup is defined in the Getting Started section of the [High Availability Guide](./HIGH_AVAILABILITY.md). Ensure you have the following:

- Ansible inventory file (`hosts.yaml`) with the SAP system configuration.
- SAP system parameters file (`sap-parameters.yaml`).
- Updated vars.yaml file with the necessary parameters.

### Step 2: Collect CIB XML Files and copy to management server

#### 2.1 Collect CIB XML Files

  Before performing offline validation, you need to collect High Availability cluster configuration files (CIB XML files) from the SAP system nodes. This can be done by executing the following command on each node:

  ```bash
  cibadmin --query | tee cib
  ```

  This command will create a file named `cib` in the current directory, which contains the cluster configuration in XML format.

#### 2.2 Create the Required Directory Structure

  Copy these files to the management server under the `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/offline_validation/` directory, maintaining the structure as shown above. Ensure the directory structure is created as follows:

  ```bash
  mkdir -p WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/offline_validation/<hostname>/
  ```

  Place the `cib` file in the respective `<hostname>/` directory.

### Step 3: Run Offline Validation

  Execute the sap_automation_qa script for offline validation with the `--offline` flag. The target OS family is a requirement parameter (`target_os_family`) and must be specified using the `--extra-vars` option.

  ```bash
  ./scripts/sap_automation_qa.sh --offline --extra-vars='target_os_family=SUSE'
  # or
  ./scripts/sap_automation_qa.sh --offline --extra-vars='target_os_family=RHEL'
  ```

  Enable verbose logging for troubleshooting:
  ```bash
  ./scripts/sap_automation_qa.sh --extra-vars='target_os_family=<os_family>' --offline -vvv
  ```

### Step 4: View Results

  The validation results will be available in `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/quality_assurance/` directory. Open the HTML file in a web browser to view the detailed parameter validation table with PASSED/INFO/FAILED statuses.