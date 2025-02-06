# Primary / Secondary Echo B Test Case

## Prerequisites

- Functioning HANA cluster
- Two active nodes (primary and secondary)
- System replication configured
- sysrq-trigger access enabled
- STONITH configuration (stonith-enabled=true)

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior

## Pseudocode

```pseudocode
FUNCTION PrimaryEchoBTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            
            // Trigger System Crash
            execute_echo_b_command()
            
        ELIF current_node == secondary_node THEN
            // Monitor Failover
            IF automated_register == true THEN
                WHILE timeout_not_reached DO
                    check_cluster_status()
                    IF new_primary == old_secondary AND 
                       new_secondary == old_primary THEN
                        BREAK
                    WAIT 10_seconds
                END WHILE
            ELSE
                wait_for_primary_down()
                register_failed_resource()
                cleanup_failed_resources()
            END IF

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

When executing the Echo B test, the behavior depends on the target node:

**Primary Echo B:**
The test triggers immediate system crash using `echo b > /proc/sysrq-trigger` on primary node, forcing an abrupt reboot. This initiates cluster failover where:

1. Primary node goes down immediately
2. Secondary promotes to primary
3. Original primary rejoins as secondary after reboot
4. Requires automated/manual registration based on configuration

**Secondary Echo B:**
When executed on secondary node, the test triggers immediate crash but maintains cluster roles:

1. Primary continues normal operation
2. Secondary temporarily disappears (secondary_node="")
3. Secondary node reboots and auto-recovers
4. Cluster returns to original state with same roles

## Implementation Flow

```pseudocode
FUNCTION EchoBTest():
    // Secondary specific validation
    IF current_node == secondary_node THEN
        execute_echo_b_command()
        // Primary remains unchanged
        validate_cluster_status(
            expect_primary = initial_primary,
            expect_secondary = ""
        )
        // Wait for recovery and rejoin
        validate_final_status(
            expect_primary = initial_primary,
            expect_secondary = initial_secondary
        )
    END IF
END FUNCTION
```