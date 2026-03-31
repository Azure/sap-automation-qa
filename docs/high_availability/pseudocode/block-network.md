# Block Network Communication Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

For scale-out HSR, the framework supports two origin variants:

- **Primary master block-network**: Network isolation is injected from the current primary master node.
- **Secondary master block-network**: Network isolation is injected from the current secondary master node.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- Cluster services running
- iptables service accessible
- STONITH configuration (stonith-enabled=true)
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

For **Scale-Up**, the network-partition scenario requires `PRIORITY_FENCING_DELAY` to avoid symmetric fencing races.
For **Scale-Out HSR**, this requirement is not enforced by the framework.

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior
- **Scale-Out HSR**: Verify surviving site nodes retain or assume correct roles via site membership checks

## Pseudocode (Scale-Up)

```pseudocode
FUNCTION BlockNetworkTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            get_secondary_node_ip()

             // Block Network Communication
            success = create_iptables_rules(secondary_node_ip)
            IF NOT success THEN
                THROW "Failed to create firewall rules"
            
            // Monitor Node Status
            start_monitoring_time = current_time()
            WHILE (current_time() - start_monitoring_time) < TIMEOUT DO
                primary_reachable = check_node_connectivity(primary_node_ip)
                secondary_reachable = check_node_connectivity(secondary_node_ip)
                
                IF NOT secondary_reachable AND primary_reachable THEN
                    // Verify Cluster Status
                    cluster_status = validate_cluster_status()
                    IF cluster_status.primary_active AND NOT cluster_status.secondary_active THEN
                        BREAK
                
                WAIT CHECK_INTERVAL
            END WHILE
            
            // Restore Network
            remove_iptables_rules(secondary_node_ip)
            
            // Wait for Cluster Recovery
            success = wait_for_cluster_stability(MAX_RETRIES, CHECK_INTERVAL)
            IF NOT success THEN
                THROW "Cluster failed to stabilize"
            
            // Final Validation
            final_status = validate_final_cluster_status()
            IF NOT final_status.is_stable THEN
                THROW "Final cluster status validation failed"
            
            record_end_time()
            generate_test_report()
        END IF

        EXECUTE PostValidations()

    CATCH any_error:
        LOG "Error occurred: " + any_error
        EXECUTE RescueOperations()
        EXECUTE CleanupOperations()
        RETURN "TEST_FAILED"
    FINALLY:
        EXECUTE EnsureClusterHealth()
        
    RETURN "TEST_PASSED"
END FUNCTION
```

## Scale-Out HSR Differences

In a scale-out HSR topology, the block-network scenarios use site membership checks instead of exact node identity. The behavior depends on which master node initiates the partition.

### Primary Master Block-Network (Scale-Out HSR)

```pseudocode
FUNCTION PrimaryMasterBlockNetworkTest_ScaleOut():
    // ... same setup and iptables blocking ...

    // Outcome A: Primary site node survives
    // Mid-test check: primary is from pre.primary_site_nodes, secondary is empty
    IF new_primary IN old_primary_site_nodes AND new_secondary == "" THEN
        // After recovery: original roles restored
        // Final: primary IN old_primary_site_nodes AND secondary IN old_secondary_site_nodes
    END IF

    // Outcome B: Secondary site node survives (failover occurred)
    // Mid-test check: primary is from pre.secondary_site_nodes, secondary is empty
    IF new_primary IN old_secondary_site_nodes AND new_secondary == "" THEN
        // After recovery: roles swapped at site level
        // Final: primary IN old_secondary_site_nodes AND primary != old_primary_node
    END IF
END FUNCTION
```

### Secondary Master Block-Network (Scale-Out HSR)

```pseudocode
FUNCTION SecondaryMasterBlockNetworkTest_ScaleOut():
    // Inject the partition from the secondary master node
    create_iptables_rules(primary_master_ip)

    // Primary site should retain the primary role
    WHILE timeout_not_reached DO
        check_cluster_status()
        IF new_primary IN old_primary_site_nodes AND
           (new_secondary == "" OR new_secondary IN old_secondary_site_nodes) THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    remove_iptables_rules(primary_master_ip)
    validate_final_status(
        expect_primary IN old_primary_site_nodes,
        expect_secondary IN old_secondary_site_nodes
    )
END FUNCTION
```

| Check Point | Scale-Up | Scale-Out HSR |
|------------|----------|---------------|
| Primary-master partition: primary site survives | `primary == pre.primary` and `secondary == pre.secondary` | `primary IN pre.primary_site_nodes` and `secondary IN pre.secondary_site_nodes` |
| Primary-master partition: failover outcome | `primary == pre.secondary` and `secondary == pre.primary` | `primary IN pre.secondary_site_nodes` and `primary != pre.primary_node` |
| Secondary-master partition: mid-test | Not applicable | `primary IN pre.primary_site_nodes` and `(secondary == "" OR secondary IN pre.secondary_site_nodes)` |
| Secondary-master partition: final | Not applicable | `primary IN pre.primary_site_nodes` and `secondary IN pre.secondary_site_nodes` |

## ASCS Block Network Test Case

This test case is a specific instance of blocking network communication, focusing on ASCS-specific scenarios.

### Pre-requisites

- Functioning ASCS/ERS cluster
- Two active nodes (ASCS and ERS)
- Cluster services running
- iptables service accessible
- STONITH configuration (stonith-enabled=true)

### Additional Steps for ASCS Block Network

- Validate ASCS-specific failover behavior.
- Ensure proper role changes for ASCS and ERS nodes.

### Pseudocode Extension

```pseudocode
FUNCTION ASCSBlockNetworkTest():
    // Reuse BlockNetworkTest pseudocode
    CALL BlockNetworkTest()

    // Additional ASCS-specific validations
    validate_ascs_failover_behavior()
    ensure_ascs_role_changes()
END FUNCTION
```