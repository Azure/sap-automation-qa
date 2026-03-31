# Primary / Secondary Echo B Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- sysrq-trigger access enabled
- STONITH configuration (stonith-enabled=true)
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior
- **Scale-Out HSR**: Verify site membership for role validation

## Pseudocode (Scale-Up)

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

**Scale-Out Worker Echo B:**
When executed on a non-master worker node, the test triggers an immediate crash on that worker only. The expected behavior is site-level stability: the primary master remains on the primary site, the secondary master remains on the secondary site, and the cluster returns to a healthy replicated state after the worker reboots.

## Scale-Out HSR Differences

In a scale-out HSR topology, validation uses site membership checks instead of exact node matching.

### Primary Echo B (Scale-Out HSR)

```pseudocode
FUNCTION PrimaryEchoBTest_ScaleOut():
    // ... same echo b on primary ...

    // Monitoring from secondary (auto-register=true):
    WHILE timeout_not_reached DO
        check_cluster_status()
        // New primary must be from old secondary site
        IF new_primary IN old_secondary_site_nodes AND
           new_primary != old_primary_node AND
           new_secondary != "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // Monitoring from secondary (auto-register=false):
    WHILE timeout_not_reached DO
        check_cluster_status()
        IF new_primary IN old_secondary_site_nodes AND
           new_secondary == "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // Final: new_primary IN old_secondary_site_nodes AND new_primary != old_primary_node
END FUNCTION
```

### Secondary Echo B (Scale-Out HSR)

```pseudocode
FUNCTION SecondaryEchoBTest_ScaleOut():
    // ... same echo b on secondary ...

    // Mid-crash: primary stays in primary site, secondary is empty
    validate_cluster_status(
        expect_primary IN old_primary_site_nodes,
        expect_secondary = ""
    )

    // Final: both sites restored
    validate_final_status(
        expect_primary IN old_primary_site_nodes,
        expect_secondary IN old_secondary_site_nodes
    )
END FUNCTION
```

### Worker Echo B (Scale-Out HSR)

```pseudocode
FUNCTION WorkerEchoBTest_ScaleOut(target_site):
    // target_site is either primary or secondary
    // ... same echo b on a non-master worker ...

    validate_cluster_status(
        expect_primary IN old_primary_site_nodes,
        expect_secondary IN old_secondary_site_nodes
    )

    wait_for_cluster_stability()
    validate_final_status(
        expect_primary IN old_primary_site_nodes,
        expect_secondary IN old_secondary_site_nodes
    )
END FUNCTION
```

| Check Point | Scale-Up | Scale-Out HSR |
|------------|----------|---------------|
| Primary echo-b (auto-register) | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary` and `new_secondary != ""` |
| Primary echo-b (manual) | `new_primary == old_secondary` and `new_secondary == ""` | `new_primary IN old_secondary_site_nodes` and `new_secondary == ""` |
| Secondary echo-b (mid) | `primary == old_primary` and `secondary == ""` | `primary IN old_primary_site_nodes` and `secondary == ""` |
| Secondary echo-b (final) | `primary == old_primary` and `secondary == old_secondary` | `primary IN old_primary_site_nodes` and `secondary IN old_secondary_site_nodes` |
| Worker echo-b (primary or secondary site) | Not applicable | `primary IN old_primary_site_nodes` and `secondary IN old_secondary_site_nodes` |

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