# Changelog

All notable changes to this project will be documented in this file.

## 1.1.0
Release Date: 05-11-2026
1. Add support for scale-out HANA System Replication (HSR) topology in HA functional tests
   - Support for SAPHanaSR-ScaleOut provider alongside SAPHanaSR and SAPHanaSR-angi.
   - Updated all HA DB test scenarios (resource migration, node crash/kill, echo-b, crash-index, block-network, fs-freeze, sbd-fencing) with scale-out HSR support.
   - New `display_test_summary` module and role task for consolidated test result reporting.
   - Updated HTML report template and telemetry injection for scale-out topologies.
2. Scheduling functional tests and configuration checks via REST API and CLI
   - Scheduling support for both HA functional tests and configuration checks through REST API and CLI.
   - API endpoints for triggering tests and checks, retrieving results, and managing test runs.
   - Docker deployment with multi-stage build, non-root user, and healthcheck.
   - CLI wrapper scripts (`api_utils.sh`, `container_setup.sh`) for API and Docker management.
3. Azure Backup Configuration Validation and Functional Testing
   - New `azure_backup_hana` Ansible module for backup discovery, restore-to-database, restore-to-filesystem, restore job monitoring, and cross-VM (ALR) restores.
   - Five test cases: backup setup verification, original location restore (OLR), restore to filesystem, native HANA recovery via database commands, and alternate location restore (ALR, disabled by default).
   - Support for both HA (two-node HSR cluster) and non-HA (single-node) HANA deployments.
   - HANA data-at-rest encryption support with automatic root key transfer (SAP Note 3619961) during cross-VM and cross-site restores.

## 1.0.2
Release Date: 09-01-2026
1. Enhance telemetry injection for configuration checks and scale out
2. Improvements to telemetry data handling and reporting
3. Introduce a version check mechanism
4. Package updates and dependency management

## 1.0.1
Release Date: 12-09-2025
1. CI/CD Workflow Upgrades:
2. HA constants, validation logic updates and validation enhancements
3. SAP Automation Script Improvements

## 1.0.0
Release Date: 11-04-2025

1. High Availability Functional Tests:
   - Added comprehensive functional tests for High Availability (HA) configurations for SAP HANA Database with scale-up architecture.
   - Added functional tests for HA configurations for SAP Central Services (ASCS) with Primary and Secondary nodes for ENSA1 and ENSA2 system types.
   - Support for running HA functional tests for systems with new HANA topology - SAP HANA SR-angi.
   - Offline Validation for HA configurations for SAP HANA Database and Central Services.
2. Configuration Checks (preview release):
   - Initial implementation of configuration checks for SAP systems.
   - Support for validating SAP systems with HANA and IBM Db2 databases.
