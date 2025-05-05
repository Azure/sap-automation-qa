# Primary Node Crash Test Case

## Prerequisites

- Functioning HANA cluster
- Two active nodes (primary and secondary)
- System replication configured
- SAP HANA DB user access (sidadm)

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior

## Pseudocode

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