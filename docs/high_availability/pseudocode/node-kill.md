# Primary / Secondary Node Kill Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- STONITH configuration (stonith-enabled=true)
- SAP HANA DB user access (sidadm)
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Verify node roles switched correctly (Primary node kill only)
- Check cluster stability
- **Scale-Out HSR**: Verify site membership for role validation

## Pseudocode (Scale-Up)

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

**Scale-Out Worker Node:**
When executed on a non-master worker node, the test terminates HANA processes on that worker but does not target a site master. The expected behavior is site-level role stability: the primary site remains primary, the secondary site remains secondary, and the cluster returns to a healthy replicated state after worker recovery.

## Scale-Out HSR Differences

In a scale-out HSR topology, validation uses site membership checks instead of exact node matching.

### Primary Node Kill (Scale-Out HSR)

```pseudocode
FUNCTION PrimaryNodeKillTest_ScaleOut():
    // ... same setup and HDB kill-9 ...

    IF automated_register == true THEN
        // New primary from old secondary site, with non-empty secondary
        WHILE timeout_not_reached DO
            check_cluster_status()
            IF new_primary IN old_secondary_site_nodes AND
               new_primary != old_primary_node AND
               new_secondary != "" THEN
                BREAK
            WAIT 10_seconds
        END WHILE
    ELSE
        // New primary from old secondary site, secondary still empty
        WHILE timeout_not_reached DO
            check_cluster_status()
            IF new_primary IN old_secondary_site_nodes AND
               new_secondary == "" THEN
                BREAK
            WAIT 10_seconds
        END WHILE
        register_failed_resource()
    END IF

    // Final: new_primary IN old_secondary_site_nodes AND new_primary != old_primary_node
END FUNCTION
```

### Secondary Node Kill (Scale-Out HSR)

```pseudocode
FUNCTION SecondaryNodeKillTest_ScaleOut():
    // ... same HDB kill-9 on secondary ...

    // Mid-kill: primary stays in primary site, secondary is empty
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

### Worker Node Kill (Scale-Out HSR)

```pseudocode
FUNCTION WorkerNodeKillTest_ScaleOut(target_site):
    // target_site is either primary or secondary
    // Kill HANA processes on a non-master worker node in that site
    execute_hdb_kill9_on_worker()

    // Site-level master roles should remain stable
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
| Primary kill (auto-register) | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary` and `new_secondary != ""` |
| Primary kill (manual) | `new_primary == old_secondary` and `new_secondary == ""` | `new_primary IN old_secondary_site_nodes` and `new_secondary == ""` |
| Secondary kill (mid) | `primary == old_primary` and `secondary == ""` | `primary IN old_primary_site_nodes` and `secondary == ""` |
| Secondary kill (final) | `primary == old_primary` and `secondary == old_secondary` | `primary IN old_primary_site_nodes` and `secondary IN old_secondary_site_nodes` |
| Worker kill (primary or secondary site) | Not applicable | `primary IN old_primary_site_nodes` and `secondary IN old_secondary_site_nodes` |

## Implementation Flow

```pseudocode
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
```