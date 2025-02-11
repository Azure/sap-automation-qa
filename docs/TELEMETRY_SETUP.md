# Telemetry Setup Guide

## Overview

This guide outlines the steps to create an Azure Data Explorer (Kusto) cluster and an Azure Log Analytics Workspace. It also covers the Azure roles required to ingest data into these resources.

## Azure Data Explorer (Kusto) Cluster Setup

1. **Log in to the Azure Portal:**  
   Navigate to https://portal.azure.com and sign in with your Azure credentials.

2. **Create a Resource Group:**  
   - Click on "Resource groups" in the left navigation pane.  
   - Click "Add" and provide a name and region for your resource group.

3. **Create an Azure Data Explorer Cluster:**
   - In the Azure Portal, click "Create a resource" and search for "Azure Data Explorer Clusters."  
   - Click "Create."  
   - Fill in the required details:
     - **Subscription and Resource Group:** Select the subscription and resource group created earlier.
     - **Cluster Details:** Provide a unique cluster name and select a region.
     - **Pricing Tier:** Choose the pricing tier that meets your needs.
   - Click "Review + Create" and then "Create" to deploy the cluster.

4. **Create a Database in the Cluster:**
   - Once the cluster deployment is complete, navigate to the cluster resource.
   - Under the "Settings" section, select "Databases."
   - Click "Add database" and provide the database name and retention policies. Have this name handy as it will be one of the parameters for the telemetry setup.
   - Click "Apply" to create the database.

5. **Create a Table in the Database:**
   - In the Azure Data Explorer cluster resource, go to the database you created.
   - Click on Query and run the Kusto Query mentioned [here](../src/templates/telemetry_schema.kql) to create a table schema.

6. **Assign Azure Roles for Data Ingestion:**
   To assign a role:
   - Go to the Azure Data Explorer cluster resource.
   - Click on Permissions under Security and networking.
   - Click "Add" select the AllDatabasesAdmin, then add managed identity that you used to configure the deployer virtual machine.
   - Click "Save."

7. **Parameters**
    - **adx_cluster_fqdn:** Azure Data Explorer Cluster FQDN [Data Ingestion URI].
    - **adx_database_name:** Azure Data Explorer Database Name [Database Name]
    - **adx_client_id:** Azure Data Explorer Client ID [MSI Client ID]
    - **telemetry_table_name:** Name of the table in the ADX database [SAP_AUTOMATION_QA]

## Azure Log Analytics Workspace Setup

1. **Log in to the Azure Portal:**  
   Use https://portal.azure.com with your credentials.

2. **Create a Resource Group (if needed):**  
   If you haven't already created a resource group for Log Analytics, follow the same step as above.

3. **Create a Log Analytics Workspace:**  
   - Click on "Create a resource" and search for "Log Analytics Workspace."  
   - Click "Create."  
   - Fill out the required details:
     - **Subscription and Resource Group:** Select the desired subscription and resource group.
     - **Name:** Provide a unique workspace name.
     - **Region:** Choose the region where the workspace will reside.
   - Click "Review + Create" and then "Create" to deploy the workspace.

4. **Assign Azure Roles for Data Ingestion:**  
   To ingest or work with data in a Log Analytics Workspace, assign the following roles:
   - **Log Analytics Contributor:** Grants permissions to submit and manage data in the workspace.
   
   To assign a role:
   - Navigate to the Log Analytics Workspace resource.
   - Click on "Access control (IAM)."  
   - Click "Add role assignment," choose the role (e.g., Log Analytics Contributor), then add managed identity, group, or service principal.
   - Click "Save."

5. **Parameters**
    - **laws_workspace_id:** Log Analytics Workspace ID [Workspace ID]
    - **laws_shared_key:** Log Analytics Shared Key [Primary Key]
    - **telemetry_table_name:** Name of the table in Log Analytics [SAP_AUTOMATION_QA]