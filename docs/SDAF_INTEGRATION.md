# SAP High Availability Testing with SAP Deployment Automation Framework ([SDAF](https://github.com/Azure/sap-automation))

## Overview

The SAP Testing Automation Framework started as an addition to the SAP Deployment Automation Framework (SDAF) to provide a comprehensive testing solution for SAP systems on Azure. The framework is designed to validate the configuration and performance of SAP systems under a wide array of scenarios, bringing confidence and assurance by simulating real-world conditions.

This guide will help you set up your existing SAP Deployment Automation Framework environment to include the SAP Testing Automation Framework. The integration will allow you to run automated tests on your SAP systems, ensuring that they meet strict reliability and availability requirements.

## Steps (Internal Bug Bash, to be updated later for public release)

1. **Get the SDAF feature branch:**  
   - Add a remote fork to the existing SDAF repository on your local machine. Pull the feature branch into your forked repository and push it to your forked repository.
   - Execute the following commands:

   ```bash
   git remote add devanshjainms https://github.com/devanshjainms/sap-automation/tree/devanshjain/ha-pr
   git pull devanshjainms devanshjain/ha-pr
   git push origin devanshjain/ha-pr
   ```

2. **Create Pipeline in Azure DevOps:** 
    - Create a new pipeline in Azure DevOps named SAP Automation QA in your Azure DevOps project
    - Steps:
        i. Create a new file (13-sap-quality-assurance.yml) in the pipelines directory in the root of the ADO project. Add the content from the file in the [template](../src/templates/azure-pipeline.yml) of this repository as the pipeline configuration.

        ii. Navigate to the Pipelines page in Azure DevOps and click on New Pipeline. Answer the questions to create a new pipeline as follows:

        - **Where is your code?**: Azure DevOps
        - **Repository**: Your ADO project name
        - **Classify the pipeline** Non-production
        - Click on Configure Pipeline
        - **Configure your pipeline**: Existing Azure Pipelines YAML file
        - **Path**: /pipelines/13-sap-quality-assurance.yml
        - **Run**: Save (not save and run)

3. **Run the pipeline**:
    - Navigate to the Pipelines page in Azure DevOps and click on the **All** tab.
    - Select the pipeline you just created and click on **Run Pipeline**.

4. **Input Parameters**: The pipeline requires the following parameters:

    - **SAP System configuration name**, use the following syntax: ENV-LOCA-VNET-SID based on the existing SAP system configuration in the SDAF workspace.
    - **Workload Environment** (DEV, QUA, PRD, ...)
    - **SAP Functional Tests Type** Options: DatabaseHighAvailability, CentralServicesHighAvailability
    - **Telemetry Data Destination** Options: AzureLogAnalytics, AzureDataExplorer
    - **Extra Parameters**
      - Refer to the [telemetry setup guide](../docs/TELEMETRY_SETUP.md) to setup the telemetry data ingestion in Azure Log Analytics or Azure Data Explorer.
      - Required for internal Testing:
        - github_pat: Personal Access Token to pull the private repository devanshjainms/sap-automation-qa
      - Required if you want to test the telemetry data ingestion (AzureLogAnalytics):
        - laws_workspace_id: Log Analytics Workspace ID
        - laws_shared_key: Log Analytics Shared Key
        - telemetry_table_name: Name of the table in Log Analytics
      - Required if you want to test the telemetry data ingestion (AzureDataExplorer):
        - adx_cluster_fqdn: Azure Data Explorer Cluster FQDN
        - adx_database_name: Azure Data Explorer Database Name
        - adx_client_id: Azure Data Explorer Client ID
        - telemetry_table_name: Name of the table in ADX database

