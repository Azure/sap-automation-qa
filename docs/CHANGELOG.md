# Changelog

All notable changes to this project will be documented in this file.

## 1.1.2
Release Date: 06-30-2026

1. Configuration checks parity with legacy QualityCheck
   - Added Oracle OEL database checks (DB-ORA-0001 through DB-ORA-0007).
   - Added HANA filesystem/storage checks (DB-HANA-0058 through DB-HANA-0065) with disk consistency and storage-type validators.
   - Added RHEL Mellanox kernel guards (DB-HANA-0066 through DB-HANA-0072).
2. Windows SAP system support for configuration checks
   - WinRM/CredSSP connectivity, OS-dispatched commands via `windows_command` field in check definitions.
   - WSFC cluster parameter validation (SAP-0019 through SAP-0031) and Windows OS checks (IC-0042 through IC-0048).
   - Renamed MSSQL to SQLSERVER across check definitions and VM support matrix.
3. ANGI and simple mount support for RHEL HANA clusters
   - SAPHanaSR-angi resource agent support for RHEL with correct resource ID discovery.
   - Simple mount architecture support for SCS/ERS on RHEL.
4. AI assistant skills and plugins for Copilot CLI, Claude Code, and Gemini CLI
5. Ansible collections management via `collections/requirements.yml` with pinned versions
6. Documentation overhaul: README restructured, Windows hosts.yaml examples in SETUP.MD
7. Bug fixes: `default('', true)` for managed identity auth, role extraction case sensitivity, storage_type normalization

## 1.1.1
Release Date: 05-30-2026

1. Copilot CLI Skills
   - Added Copilot CLI skills for helping users with test execution, configuration checks, and troubleshooting.
   - Skills include natural language queries for test status, configuration validation, and error resolution.
2. Standardize Ansible task labels with phase-based prefixes and dynamic `{{ item.name }}` references for traceability
   - CI-enforced label validation tests and defensive `| default('')` filter for runtime resilience.
   - Fixed loop variable shadowing in `secondary-block-network.yml`.
3. Add CLI flags to `sap_automation_qa.sh` for runtime parameter overrides without modifying `vars.yaml`
   - Fixed bug where `SAP_FUNCTIONAL_TEST_TYPE` was incorrectly required for configuration checks.
4. Publish Docker image to GitHub Container Registry (GHCR) on PR merge to main
   - Docker build validation on every PR raise and push event.

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
