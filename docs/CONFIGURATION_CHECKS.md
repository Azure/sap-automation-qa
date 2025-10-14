# SAP Configuration Checks

## Overview

SAP Configuration Checks is an integral part of the SAP Testing Automation framework, providing comprehensive validation of SAP system configurations on Azure infrastructure. This module ensures that SAP Database and SAP Central Services deployments meet enterprise requirements for compliance before entering production. This tool is designed to identify misconfigurations, deviations from best practices, and potential issues that could impact system's stability and performance.

This tool is a new version of the existing [Quality Checks scripts](https://github.com/Azure/SAP-on-Azure-Scripts-and-Utilities/tree/main/QualityCheck), re-architected to provide a extensible, and maintainable solution. It leverages Python for core logic and Ansible for orchestration.

## Purpose

Configuration validation serves as a critical quality gate in the SAP deployment lifecycle by:

- **Validating Azure Infrastructure**: Ensuring compute, storage, and network configurations align with SAP best practices
- **Verifying SAP Parameters**: Checking critical SAP HANA and application server settings
- **Assessing Cluster Health**: Validating Pacemaker configurations and resource constraints
- **Ensuring Compliance**: Confirming adherence to organizational and SAP security standards

## Configuration Check Categories

**Azure Compute**
- VM SKU appropriateness for SAP workloads
- Accelerated Networking enablement
- Availability Set/Zone configuration
- Proximity Placement Group setup

**Storage Configuration**
- Premium SSD/Ultra Disk usage for critical paths
- Write Accelerator for log volumes
- Storage account redundancy settings
- Disk caching policies

**SAP HANA Configuration**
- Memory allocation
- System replication parameters

**Pacemaker Cluster**
- Resource agent versions and parameters
- Fencing (STONITH) configuration
- Resource constraints and colocation rules
- Cluster communication settings

**SAP HA Resources**
- Virtual hostname configuration
- File system mount options
- Service startup ordering
- Failover timeout values


### 1. Setup Configuration

Follow the steps (1.1 - 1.5) in [Setup Guide for SAP Testing Automation Framework](./SETUP.MD) to set up the framework on a management server.

### 2. System Configuration

Update the `TEST_TYPE` parameter in [`vars.yaml`](./../vars.yaml) file to `ConfigurationChecks` to enable the Configuration Checks test scenarios.

Follow the steps (2.1 - 2.2) in [Setup Guide for SAP Testing Automation Framework](./SETUP.MD#2-system-configuration) to configure your system details.


### 3. Test Execution

To execute the script, run following command:

```bash
# Help option
./scripts/sap_automation_qa.sh --help

# Run all the configuration checks with default parameters
./scripts/sap_automation_qa.sh

# Run checks with verbose logging
./scripts/sap_automation_qa.sh -vv

# Run only Database (HANA) configuration checks
./scripts/sap_automation_qa.sh --extra-vars='{"configuration_test_type":"Database"}'

# Run only ASCS/ERS configuration checks
./scripts/sap_automation_qa.sh --extra-vars='{"configuration_test_type":"CentralServiceInstances"}'

# Run only Application Server configuration checks
./scripts/sap_automation_qa.sh --extra-vars='{"configuration_test_type":"ApplicationInstances"}'
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