# Primary / Secondary Crash Index Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- Index server configured on both nodes
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Verify node roles
- Check service status
- **Scale-Out HSR**: Verify site membership for role validation

## Pseudocode (Scale-Up)

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

**Scale-Out Worker Index Server Crash:**
When executed on a non-master worker node, the test kills `hdbindexserver` on that worker but does not target a site master. The expected behavior is site-level role stability: the primary site remains primary, the secondary site remains secondary, and the cluster returns to a healthy replicated state after worker recovery.

## Scale-Out HSR Differences

In a scale-out HSR topology, validation uses site membership checks instead of exact node matching.

### Primary Index Server Crash (Scale-Out HSR)

```pseudocode
FUNCTION PrimaryIndexServerCrashTest_ScaleOut():
    // ... same setup and index server kill ...

    // Monitor Failover (auto-register=true)
    WHILE timeout_not_reached AND retries_remaining DO
        check_cluster_status()
        // New primary must be from old secondary site
        IF new_primary IN old_secondary_site_nodes AND
           new_primary != old_primary_node AND
           new_secondary != "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // Monitor Failover (auto-register=false)
    WHILE timeout_not_reached AND retries_remaining DO
        check_cluster_status()
        IF new_primary IN old_secondary_site_nodes AND
           new_secondary == "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // Final Validation
    // new_primary IN old_secondary_site_nodes AND new_primary != old_primary_node
END FUNCTION
```

### Secondary Index Server Crash (Scale-Out HSR)

```pseudocode
FUNCTION SecondaryIndexServerCrashTest_ScaleOut():
    // ... same index server kill on secondary ...

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

### Worker Index Server Crash (Scale-Out HSR)

```pseudocode
FUNCTION WorkerIndexServerCrashTest_ScaleOut(target_site):
    // target_site is either primary or secondary
    // ... kill hdbindexserver on a non-master worker node ...

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
| Primary crash (auto-register) | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary` and `new_secondary != ""` |
| Primary crash (manual) | `new_primary == old_secondary` and `new_secondary == ""` | `new_primary IN old_secondary_site_nodes` and `new_secondary == ""` |
| Secondary crash (mid) | `primary == old_primary` and `secondary == ""` | `primary IN old_primary_site_nodes` and `secondary == ""` |
| Secondary crash (final) | `primary == old_primary` and `secondary == old_secondary` | `primary IN old_primary_site_nodes` and `secondary IN old_secondary_site_nodes` |
| Worker crash (primary or secondary site) | Not applicable | `primary IN old_primary_site_nodes` and `secondary IN old_secondary_site_nodes` |

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