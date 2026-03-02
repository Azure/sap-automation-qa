# Resource Migration Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- Cluster services running
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior
- **Scale-Out HSR**: Verify new primary belongs to the former secondary site (site membership check)

## Pseudocode (Scale-Up)

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

## Scale-Out HSR Differences

In a scale-out HSR topology, the validation logic changes from exact node identity checks to **site membership** checks. The cluster contains multiple worker nodes per site, so any node from the promoted site can become the new master nameserver.

### Pre-Validation (Scale-Out HSR)

```pseudocode
// Scale-out pre-validation requires:
//   - primary_site_nodes list is non-empty
//   - secondary_site_nodes list is non-empty
//   - majority_maker_node is non-empty
//   - master_nameserver_node belongs to primary_site_nodes
```

### Validation Changes (Scale-Out HSR)

```pseudocode
FUNCTION ResourceMigrationTest_ScaleOut():
    // ... same setup and migration execution ...

    // Initial Migration Check (scale-out)
    WHILE timeout_not_reached AND retries_remaining DO
        check_cluster_status()
        // New primary must be from the old secondary site
        IF new_primary IN old_secondary_site_nodes AND new_secondary == "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // ... registration and constraint removal ...

    // Final Validation (scale-out)
    WHILE timeout_not_reached AND retries_remaining DO
        check_cluster_status()
        // New primary is from old secondary site and is not the old primary
        IF new_primary IN old_secondary_site_nodes AND
           new_primary != old_primary_node THEN
            BREAK
        WAIT 10_seconds
    END WHILE
END FUNCTION
```

| Check Point | Scale-Up | Scale-Out HSR |
|------------|----------|---------------|
| Mid-migration | `new_primary == old_secondary` | `new_primary IN old_secondary_site_nodes` |
| Final validation | `new_primary == old_secondary AND new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes AND new_primary != old_primary_node` |

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