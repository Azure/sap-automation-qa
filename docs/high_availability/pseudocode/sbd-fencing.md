# SBD Fencing Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- STONITH configuration (stonith-enabled=true)
- iSCSI-based SBD configuration
- sbd: inquisitor process enabled
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Verify node roles switched correctly
- Check cluster stability
- Validate failover behavior
- **Scale-Out HSR**: Verify new primary belongs to the former secondary site

## Pseudocode (Scale-Up)

```pseudocode
FUNCTION SBDFencingTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" OR database_cluster_type != "ISCSI" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            
            // Find and Kill Inquisitor
            inquisitor_pid = find_sbd_inquisitor_process()
            kill_process(inquisitor_pid)
            
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

## Scale-Out HSR Differences

In a scale-out HSR topology, validation uses site membership checks instead of exact node matching.

### Validation Changes (Scale-Out HSR)

```pseudocode
FUNCTION SBDFencingTest_ScaleOut():
    // ... same SBD inquisitor kill on primary ...

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

    // Final Validation:
    // new_primary IN old_secondary_site_nodes AND new_primary != old_primary_node
END FUNCTION
```

| Check Point | Scale-Up | Scale-Out HSR |
|------------|----------|---------------|
| Auto-register (from secondary) | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary` and `new_secondary != ""` |
| Final validation | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary_node` |