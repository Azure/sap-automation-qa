# Filesystem Freeze Test Case

## Supported Topologies

This test supports both **Scale-Up** (two-node) and **Scale-Out HSR** (multi-node with sites) topologies.

## Prerequisites

- Functioning HANA cluster
- System replication configured
- NFS provider configured with Azure NetApp Files (ANF)
- STONITH configuration (stonith-enabled=true)
- **Scale-Up**: Two active nodes (primary and secondary)
- **Scale-Out HSR**: Multiple worker nodes across two sites, plus a majority maker node

## Validation

- Check filesystem status
- Verify cluster stability
- Validate node roles
- **Scale-Out HSR**: Verify new primary belongs to the former secondary site

## Pseudocode (Scale-Up)

```pseudocode
FUNCTION FilesystemFreezeTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" OR NFS_provider != "ANF" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == primary_node THEN
            record_start_time()
            
            // Freeze Filesystem
            execute_filesystem_freeze()
            
            // Monitor Cluster Status
            validate_cluster_status()
            
            // Final Validation
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
FUNCTION FilesystemFreezeTest_ScaleOut():
    // ... same setup and filesystem freeze ...

    // Monitoring from secondary (auto-register=true):
    WHILE timeout_not_reached AND retries_remaining DO
        check_cluster_status()
        // New primary must be from old secondary site
        IF new_primary IN old_secondary_site_nodes AND
           new_primary != old_primary_node AND
           new_secondary != "" THEN
            BREAK
        WAIT 10_seconds
    END WHILE

    // Final Validation (from primary after reboot):
    // new_primary IN old_secondary_site_nodes AND new_primary != old_primary_node
END FUNCTION
```

| Check Point | Scale-Up | Scale-Out HSR |
|------------|----------|---------------|
| Auto-register (from secondary) | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary` and `new_secondary != ""` |
| Final validation | `new_primary == old_secondary` and `new_secondary == old_primary` | `new_primary IN old_secondary_site_nodes` and `new_primary != old_primary_node` |