# SAP Testing Automation Framework with SAP Deployment Automation Framework ([SDAF](https://github.com/Azure/sap-automation))

## Overview

The SAP Testing Automation Framework started as an addition to the SAP Deployment Automation Framework (SDAF) to provide a comprehensive testing solution for SAP systems on Azure. The framework is designed to validate the configuration and performance of SAP systems under a wide array of scenarios, bringing confidence and assurance by simulating real-world conditions.

This guide will help you set up your existing SAP Deployment Automation Framework environment to include the SAP Testing Automation Framework. The integration will allow you to run automated tests on your SAP systems, ensuring that they meet strict reliability and availability requirements.

## Prerequisites

- Existing SAP Deployment Automation Framework (SDAF) workspace set up on Azure DevOps with deployed SAP system.
- Permissions to create and manage pipelines in Azure DevOps.
- Forked version of the [SDAF](https://github.com/Azure/sap-automation) repository in GitHub or Azure DevOps.

## Steps

1. **Set Up the SDAF Feature Branch**

   The SAP Testing Automation Framework requires the latest features from the `qa-preview` branch of the SAP Deployment Automation Framework repository.

   Execute the following commands in your local repository to incorporate these changes:

   ```bash
   # Add the official Azure repository as a remote source
   git remote add azure https://github.com/Azure/sap-automation

   # Fetch and checkout the qa-preview branch containing testing framework features
   git pull azure qa-preview

   # Push the branch to your forked repository for use with your pipelines
   git push origin qa-preview
   ```

2. **Create Pipeline in Azure DevOps:**

    - Create a new pipeline in Azure DevOps named SAP Automation QA in your Azure DevOps project.
    - Steps:
        1. Create a new file (13-sap-quality-assurance.yml) in the pipelines directory in the root of the Azure DevOps project. Add the content from the file in the [template](../src/templates/azure-pipeline.yml) of this repository as the pipeline configuration.

        2. Navigate to the Pipelines page in Azure DevOps and click on **New Pipeline**. Answer the questions to create a new pipeline as follows:
            - **Where is your code?**: Azure DevOps
            - **Repository**: Your ADO project name
            - **Classify the pipeline** Non-production
            - Click on Configure Pipeline
            - **Configure your pipeline**: Existing Azure Pipelines YAML file
            - **Path**: /pipelines/13-sap-quality-assurance.yml
            - **Run**: Save (not save and run)

3. **Run the pipeline**:
    1. Navigate to the Pipelines page in Azure DevOps and click on the **All** tab
    2. Select the pipeline you just created (SAP Automation QA)
    3. Click on **Run Pipeline**.

4. **Input Parameters**: The pipeline requires the following parameters:

   | Parameter | Description | Required | Example Value |
   |-----------|-------------|:--------:|---------------|
   | **SAP System configuration name** | Follows format: ENV-LOCA-VNET-SID | Yes | DEV-WEU-SAP01-S4H |
   | **Workload Environment** | Environment type | Yes | DEV |
   | **SAP Functional Tests Type** | Test category to run | Yes | DatabaseHighAvailability |
   | **Telemetry Data Destination** | Where to send test data | No | AzureLogAnalytics |

   **Providing Telemetry Data Destination Parameters**
   
   To configure the Telemetry Data Destination for the SAP Testing Automation Framework, you need to specify the required parameters in the Extra Parameters input field. This allows the pipeline to send telemetry data to the desired destination, such as Azure Log Analytics or Azure Data Explorer.

   **How to Specify Telemetry Parameters**

   Use the following format in the Extra Parameters field:

   ```bash
   --extra-vars "laws_workspace_id=<workspace-id>,laws_shared_key=<shared-key>,telemetry_table_name=<table-name>"
   ```

   Telemetry Data Destination Options
   1. **Azure Log Analytics**
   If you are using Azure Log Analytics as the telemetry destination, the following parameters are required:
   - `laws_workspace_id`: Log Analytics Workspace ID
   - `laws_shared_key`: Log Analytics Shared Key
   - `telemetry_table_name`: Name of the table in Log Analytics

   ```bash
   --extra-vars "laws_workspace_id=12345678-1234-1234-1234-123456789abc,laws_shared_key=**********,telemetry_table_name=SAPTelemetry"
   ```

   2. **Azure Data Explorer**
   If you are using Azure Data Explorer (ADX) as the telemetry destination, the following parameters are required:
   - `adx_cluster_fqdn`: Azure Data Explorer Cluster FQDN
   - `adx_database_name`: Azure Data Explorer Database Name  
   - `adx_client_id`: Azure Data Explorer Client ID
   - `telemetry_table_name`: Name of the table in ADX database

   ```bash
   --extra-vars "adx_cluster_fqdn=myadxcluster.kusto.windows.net,adx_database_name=SAPTelemetryDB,adx_client_id=12345678-1234-1234-1234-123456789abc,telemetry_table_name=SAPTelemetry"
   ```

  



