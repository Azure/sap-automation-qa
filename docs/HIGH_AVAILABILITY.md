# SAP High Availability Testing

The SAP on Azure Automation framework includes a High Availability (HA) testing component designed to validate that SAP deployments on Azure adhere to established best practices. This component executes a series of automated tests that simulate real-world failure scenarios to ensure the resilience and recovery capabilities of the SAP system.

Leveraging Ansible, the framework orchestrates these failure scenarios and validates the system's automated recovery processes. This document provides guidance on configuring and executing these HA tests.

## Supported Configurations

Azure offers various deployment options for SAP workloads on different operating system distributions. The SAP Testing Automation Framework executes its test scenarios on the SAP system configurations running on Linux distribution. You can find the support matrix on supported Linux distribution version, and high availability configuration pattern in [SAP Testing Automation Framework Supported Platforms and Features](https://learn.microsoft.com/azure/sap/automation/testing-framework-supportability#supported-sap-system-configurations).

## Pre-requisites

Before executing the HA tests, complete the following prerequisite steps.

### 1. Enable Cluster Services on Boot

Ensure that cluster services are configured to start automatically on system boot. Execute the appropriate command for your Linux distribution on one of the cluster nodes:

```bash
# For SUSE Linux Enterprise Server (SLES)
crm cluster enable --all

# For Red Hat Enterprise Linux (RHEL)
pcs cluster enable --all
```

### 2. Configure the Automation Framework

Follow the steps in the [Setup Guide for SAP Testing Automation Framework](./SETUP.MD) to prepare the framework on a designated management server.

### 3. Configure the System for HA Testing

1.  Update the `TEST_TYPE` parameter in the `vars.yaml` file to `SAPFunctionalTests` to enable the High Availability test scenarios.
2.  Follow the steps in the [System Configuration section of the Setup Guide](./SETUP.MD#2-system-configuration) to provide the details of your SAP system.


## Test Execution

Execute the tests using the `sap_automation_qa.sh` script from the `scripts` directory. You can run all tests or specify a subset of test cases.

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

## Viewing Test Results

Upon completion, the framework generates a detailed HTML report that summarizes the PASS/FAIL status of each test case and provides detailed execution logs.

1.  **Navigate to the workspace directory for your SAP system.**

    Replace `<SYSTEM_CONFIG_NAME>` with the name of your SAP system configuration (e.g., `DEV-WEEU-SAP01-X00`).

    ```bash
    cd WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/quality_assurance/
    ```

2.  **Identify the report file.**

    The report file name follows this format:
    `HA_{SAP_TIER}_{DATABASE_TYPE}_{OS_DISTRO_NAME}_{INVOCATION_ID}.html`

    *   `SAP_TIER`: The SAP tier tested (e.g., DB, SCS).
    *   `DATABASE_TYPE`: The database type (e.g., HANA).
    *   `OS_DISTRO_NAME`: The operating system (e.g., SLES15SP4).
    *   `INVOCATION_ID`: A unique identifier for the test run, which is logged at the end of the test execution.

    ![Test Execution Completion Screenshot](./images/execution_screenshot.png)

3.  **View the report.**

    Open the HTML file in any web browser to review the test results and logs.
