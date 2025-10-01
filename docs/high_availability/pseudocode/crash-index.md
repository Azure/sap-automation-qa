# Primary / Secondary Crash Index Test Case

## Prerequisites

- Functioning HANA cluster
- Two active nodes (primary and secondary)
- System replication configured
- Index server configured on both nodes

## Validation

- Verify node roles
- Check service status

## Pseudocode

```pseudocode
FUNCTION PrimaryIndexServerCrashTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            
            // Get Index Server Process
            index_server_pid = get_index_server_pid()
            
            // Crash Index Server
            kill_process(index_server_pid)
            
            // Monitor Failover
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

        IF current_node == secondary_node THEN
            cleanup_failed_resources()
            validate_cluster_status()
            verify_service_startup()
        END IF

        EXECUTE PostValidations()

    CATCH any_error:
        EXECUTE RescueOperations()
        RETURN "Test Failed"

    RETURN "Test Passed"
END FUNCTION
```

## Note
When executing the Index Server Crash test, the behavior depends on the target node:

**Primary Index Server Crash:**
The test terminates the HANA index server process (hdbindexserver) on primary node, triggering cluster failover. The pseudocode validates complete role change where secondary becomes primary and requires cluster-wide recovery.

**Secondary Index Server Crash:**
When executed on secondary node, the test kills the index server process but maintains cluster roles. The pseudocode validates that:

1. Primary continues normal operation
2. Secondary temporarily disappears from cluster (secondary_node="")
3. Secondary automatically recovers and rejoins replication
4. Final state matches initial state (same primary/secondary roles)

## Implementation Flow

```pseudocode
FUNCTION IndexServerCrashTest():
    // Secondary specific validation
    IF current_node == secondary_node THEN
        kill_index_server_process()
        // Primary remains unchanged
        // Secondary temporarily disappears
        validate_cluster_status(
            expect_primary = initial_primary,
            expect_secondary = ""
        )
        // Wait for recovery
        validate_final_status(
            expect_primary = initial_primary,
            expect_secondary = initial_secondary
        )
    END IF
END FUNCTION