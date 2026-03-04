# Primary Node Crash Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- SAP HANA DB user access (sidadm)
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior
- **Scale-Out HSR**: Verify new primary belongs to the former secondary site

## Pseudocode (Scale-Up)

```pseudocode
FUNCTION PrimaryNodeCrashTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            
            // Stop HANA Database
            stop_hana_database()
            
            // Monitor Initial Failover
            WHILE timeout_not_reached DO
                check_cluster_status()
                IF new_primary == old_secondary AND 
                   new_secondary == "" THEN
                    BREAK
                WAIT 10_seconds
            END WHILE

            // Handle Manual Registration
            IF automated_register == false THEN
                register_failed_resource()
            END IF

            cleanup_failed_resources()
            
            // Final Validation
            WHILE timeout_not_reached DO
                check_cluster_status()
                IF new_primary == old_secondary AND 
                   new_secondary == old_primary THEN
                    BREAK
                WAIT 10_seconds
            END WHILE

            record_end_time()
            generate_test_report()
        END IF

        EXECUTE PostValidations()

    CATCH any_error:
        EXECUTE RescueOperations()
        RETURN "Test Failed"

    RETURN "Test Passed"
END FUNCTION
```

## Scale-Out HSR Differences

In a scale-out HSR topology, the validation logic changes from exact node identity checks to **site membership** checks.

### Validation Changes (Scale-Out HSR)

```pseudocode
FUNCTION PrimaryNodeCrashTest_ScaleOut():
    // ... same setup and HANA stop ...

    // Monitor Initial Failover (scale-out)
    WHILE timeout_not_reached DO
        check_cluster_status()
        // New primary must be from the old secondary site
        IF new_primary IN old_secondary_site_nodes AND
           new_secondary == "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // ... registration and cleanup ...

    // Final Validation (scale-out)
    WHILE timeout_not_reached DO
        check_cluster_status()
        IF new_primary IN old_secondary_site_nodes AND
           new_primary != old_primary_node THEN
            BREAK
        WAIT 10_seconds
    END WHILE
END FUNCTION
```

| Check Point | Scale-Up | Scale-Out HSR |
|------------|----------|---------------|
| Mid-failover | `new_primary == old_secondary` and `new_secondary == ""` | `new_primary IN old_secondary_site_nodes` and `new_secondary == ""` |
| Final validation | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary_node` |

## ASCS Node Crash Test Case

This test case is a specific instance of node crash, focusing on simulating an ASCS node crash and validating failover behavior.

### Pre-requisites

- Functioning ASCS/ERS cluster
- Two active nodes (ASCS and ERS)
- Cluster services running
- STONITH configuration (stonith-enabled=true)

### Additional Steps for ASCS Node Crash

- Validate ASCS-specific failover behavior.
- Ensure proper role changes for ASCS and ERS nodes.

### Pseudocode Extension

```pseudocode
FUNCTION ASCSNodeCrashTest():
    // Reuse PrimaryNodeCrashTest pseudocode
    CALL PrimaryNodeCrashTest()

    // Additional ASCS-specific validations
    validate_ascs_failover_behavior()
    ensure_ascs_role_changes()
END FUNCTION
```