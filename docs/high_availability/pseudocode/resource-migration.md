# Resource Migration Test Case

## Prerequisites

- Functioning HANA cluster
- Two active nodes (primary and secondary)
- System replication configured
- Cluster services running

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior

## Pseudocode

```pseudocode
FUNCTION ResourceMigrationTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        // Only run on primary HANA node
        IF current_node == cluster_status_pre.primary_node THEN
            // Start Test
            record_start_time()

            // Migrate HANA Resources
            execute_resource_migration_command()
            
            // Validate Initial Migration
            WHILE timeout_not_reached AND retries_remaining DO
                check_cluster_status()
                IF new_primary == old_secondary AND new_secondary == "" THEN
                    BREAK
                WAIT 10_seconds
            END WHILE

            // Handle Manual Registration if needed
            IF automated_register == false THEN
                register_failed_resource()
                cleanup_failed_resources()
            END IF

            // Remove Location Constraints
            remove_location_constraints()
            wait_for_cluster_stability(100_seconds)

            // Final Validation
            WHILE timeout_not_reached AND retries_remaining DO
                check_cluster_status()
                IF new_primary == old_secondary AND 
                   new_secondary == old_primary THEN
                    BREAK
                WAIT 10_seconds
            END WHILE

            record_end_time()
            generate_test_report()
        END IF

        // Post Validation
        EXECUTE PostValidations()

    CATCH any_error:
        EXECUTE RescueOperations()
        RETURN "Test Failed"

    RETURN "Test Passed"
END FUNCTION
```

## ASCS Migration Test Case

This test case is a specific instance of resource migration, focusing on migrating the ASCS resource to the ERS node.

### Pre-requisites

- Functioning ASCS/ERS cluster
- Two active nodes (ASCS and ERS)
- Cluster services running
- STONITH configuration (stonith-enabled=true)

### Additional Steps for ASCS Migration

- Validate ASCS-specific constraints and cleanup.
- Ensure proper role changes for ASCS and ERS nodes.

### Pseudocode Extension

```pseudocode
FUNCTION ManualASCSMigrationTest():
    // Reuse ResourceMigrationTest pseudocode
    CALL ResourceMigrationTest()

    // Additional ASCS-specific validations
    validate_ascs_constraints()
    ensure_ascs_role_changes()
END FUNCTION
```