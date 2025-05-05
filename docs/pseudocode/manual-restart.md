<!-- filepath: /home/devanshjain/SDAF/sap-automation-qa/docs/pseudocode/manual-restart.md -->
# Manual Restart of ASCS Instance Test Case

## Prerequisites

- Functioning ASCS/ERS cluster
- Two active nodes (ASCS and ERS)
- Cluster services running
- Proper resource configuration

## Validation

- Verify ASCS instance restarts successfully
- Check cluster stability
- Validate proper role changes

## Pseudocode

```pseudocode
FUNCTION ManualRestartASCSInstanceTest():
    // Setup Phase
    EXECUTE TestSetup()
    EXECUTE PreValidations()

    IF pre_validations_status != "PASSED" THEN
        RETURN "Test Prerequisites Failed"

    // Main Test Execution
    TRY:
        IF current_node == ascs_node THEN
            record_start_time()

            // Restart ASCS Instance
            success = restart_ascs_instance()
            IF NOT success THEN
                THROW "Failed to restart ASCS instance"

            // Validate ASCS Instance Status
            cluster_status = validate_cluster_status()
            IF cluster_status.ascs_node != ascs_node THEN
                THROW "ASCS instance did not restart as expected"

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
