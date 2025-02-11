# Telemetry Setup Guide


## Overview

## Azure Kusto (Azure Data Explorer) Data Ingestion

To ingest data into an Azure Kusto (Azure Data Explorer) cluster, you need specific roles or permissions. The primary roles involved in data ingestion are:

Database Admin: This role provides full access to the database, including the ability to ingest data.
Database Ingestor: This role specifically allows for data ingestion into the database.
AllDatabasesAdmin: This role grants full permissions across all databases in the cluster, including data ingestion12.
You can assign these roles through the Azure portal by navigating to your Azure Data Explorer cluster, selecting "Permissions" under the "Security + networking" section, and then adding the appropriate role to the desired principal (user, group, or app)2.