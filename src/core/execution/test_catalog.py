# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


"""Static mapping from STAF test groups to authoritative playbooks."""

TEST_GROUP_PLAYBOOKS: dict[str, str] = {
    "ConfigurationChecks": "playbook_00_configuration_checks.yml",
    "DatabaseHighAvailability": "playbook_00_ha_db_functional_tests.yml",
    "CentralServicesHighAvailability": "playbook_00_ha_scs_functional_tests.yml",
    "AzureBackupDatabase": "playbook_00_backup_db_functional_tests.yml",
}

OFFLINE_PLAYBOOK = "playbook_01_ha_offline_tests.yml"
