# Primary / Secondary Node Kill Test Case

## Prerequisites

- Functioning HANA cluster
- Two active nodes (primary and secondary)
- System replication configured
- STONITH configuration (stonith-enabled=true)
- SAP HANA DB user access (sidadm)

## Validation

- Verify node roles switched correctly ( Primary node kill only)
- Check cluster stability

## Pseudocode

```pseudocode
FUNCTION PrimaryNodeKillTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            
            // Kill HANA Processes
            execute_hdb_kill9()
            
            IF automated_register == true THEN
                // Monitor Failover
                WHILE timeout_not_reached DO
                    check_cluster_status()
                    IF new_primary == old_secondary AND 
                       new_secondary == old_primary THEN
                        BREAK
                    WAIT 10_seconds
                END WHILE
            ELSE
                // Manual Registration Flow
                WHILE timeout_not_reached DO
                    check_cluster_status()
                    IF new_primary == old_secondary AND 
                       new_secondary == "" THEN
                        BREAK
                    WAIT 10_seconds
                END WHILE
                register_failed_resource()
            END IF

            cleanup_failed_resources()
            validate_final_cluster_status()
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

## Note
When executing the Node Kill test, the behavior depends on the target node:

**Primary Node:**
The test executes kill-9 on HANA processes, triggering cluster failover. The pseudocode validates role changes where secondary becomes primary. If automated registration is disabled, manual registration of the failed node is required after recovery.

**Secondary Node:**
When executed on secondary, the test terminates HANA processes but maintains cluster roles. The pseudocode only validates that primary continues operation while secondary recovers. No registration is needed as secondary automatically rejoins replication.

## Implementation Flow

```pseudocode
...existing pseudocode...
// Primary Node Specific
IF current_node == primary_node THEN
    // Checks for role swap
    validate_cluster_status(expect_role_change=true)
    handle_registration_if_needed()
END IF

// Secondary Node Specific 
IF current_node == secondary_node THEN
    // Only checks replication recovery
    validate_cluster_status(expect_role_change=false)
    wait_for_replication_resume()
END IF
...existing pseudocode...