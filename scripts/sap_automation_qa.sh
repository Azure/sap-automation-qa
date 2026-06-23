#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -eo pipefail

# Get script directory in a more portable way
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"

# Source shared utilities (logging, etc.)
source "$script_dir/utils.sh"
source "$script_dir/usage.sh"

# Route API subcommands early — they only need curl, not the venv or Ansible.
case "${1:-}" in
    health|workspace|workspaces|job|jobs|schedule|schedules)
        source "$script_dir/api_utils.sh"
        case "$1" in
            health)              shift; api_health "$@" ;;
            workspace|workspaces) shift; api_workspace "$@" ;;
            job|jobs)            shift; api_job "$@" ;;
            schedule|schedules)  shift; api_schedule "$@" ;;
        esac
        exit $?
        ;;
    -h|--help)
        source "$script_dir/api_utils.sh"
        show_sap_automation_qa_usage "$0"
        exit 0
        ;;
esac

# Activate the virtual environment (required for Ansible playbook execution)
if [[ -f "$project_root/.venv/bin/activate" ]]; then
    source "$project_root/.venv/bin/activate"
else
    echo "ERROR: Virtual environment not found at $project_root/.venv"
    echo "Please run setup.sh first to create the virtual environment."
    exit 1
fi

# Source the version check script
source "$script_dir/version_check.sh"

# Use more portable command directory detection
if command -v readlink >/dev/null 2>&1; then
    cmd_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
else
    # Fallback for systems without readlink -f (like some macOS versions)
    cmd_dir="$script_dir"
fi

# Set the environment variables
export ANSIBLE_COLLECTIONS_PATH="${cmd_dir}/../.ansible/collections:/opt/ansible/collections:${ANSIBLE_COLLECTIONS_PATH:+${ANSIBLE_COLLECTIONS_PATH}}"
export ANSIBLE_CONFIG="${cmd_dir}/../src/ansible.cfg"
export ANSIBLE_MODULE_UTILS="${cmd_dir}/../src/module_utils:${ANSIBLE_MODULE_UTILS:+${ANSIBLE_MODULE_UTILS}}"
export ANSIBLE_HOST_KEY_CHECKING=False
log "INFO" "ANSIBLE_HOST_KEY_CHECKING: $ANSIBLE_HOST_KEY_CHECKING"
set_output_context

# Global variable to store the path of the temporary file.
temp_file=""

# Parse command line arguments and extract verbose flags
# Sets global ANSIBLE_VERBOSE variable
parse_arguments() {
    ANSIBLE_VERBOSE=""
    OFFLINE_MODE=""
    TEST_GROUPS=""
    TEST_CASES=""
    EXTRA_VARS=""

    CLI_TEST_TYPE=""
    CLI_SYSTEM_CONFIG_NAME=""
    CLI_SAP_FUNCTIONAL_TEST_TYPE=""
    CLI_AUTHENTICATION_TYPE=""
    CLI_WORKSPACES_DIR=""

    CLI_ANSIBLE_OVERRIDES=()

    local expect_extra_vars=false
    for arg in "$@"; do
        if [[ "$expect_extra_vars" == "true" ]]; then
            expect_extra_vars=false
            if [[ "$arg" != -* ]]; then
                EXTRA_VARS="$arg"
                continue
            fi
            log "ERROR" "Option '--extra-vars' requires a value."
            show_sap_automation_qa_usage "$0"
            exit 1
        fi
        case "$arg" in
            -v|-vv|-vvv|-vvvv|-vvvvv|-vvvvvv)
                ANSIBLE_VERBOSE="$arg"
                ;;
            --test-groups=*)
                TEST_GROUPS="${arg#*=}"
                ;;
            --test-cases=*)
                TEST_CASES="${arg#*=}"
                TEST_CASES="${TEST_CASES#[}"
                TEST_CASES="${TEST_CASES%]}"
                ;;
            --extra-vars=*)
                EXTRA_VARS="${arg#*=}"
                if [[ -z "$EXTRA_VARS" ]]; then
                    log "ERROR" "Option '--extra-vars' requires a value."
                    show_sap_automation_qa_usage "$0"
                    exit 1
                fi
                ;;
            --extra-vars)
                expect_extra_vars=true
                ;;
            --offline)
                OFFLINE_MODE="true"
                ;;
            --test-type=*)
                CLI_TEST_TYPE="${arg#*=}"
                ;;
            --system-config=*)
                CLI_SYSTEM_CONFIG_NAME="${arg#*=}"
                ;;
            --functional-test-type=*)
                CLI_SAP_FUNCTIONAL_TEST_TYPE="${arg#*=}"
                ;;
            --auth-type=*)
                CLI_AUTHENTICATION_TYPE="${arg#*=}"
                ;;
            --workspaces-dir=*)
                CLI_WORKSPACES_DIR="${arg#*=}"
                ;;
            --telemetry-destination=*)
                CLI_ANSIBLE_OVERRIDES+=("telemetry_data_destination=${arg#*=}")
                ;;
            --telemetry-table=*)
                CLI_ANSIBLE_OVERRIDES+=("telemetry_table_name=${arg#*=}")
                ;;
            --laws-shared-key=*)
                CLI_ANSIBLE_OVERRIDES+=("laws_shared_key=${arg#*=}")
                ;;
            --laws-workspace-id=*)
                CLI_ANSIBLE_OVERRIDES+=("laws_workspace_id=${arg#*=}")
                ;;
            --laws-subscription-id=*)
                CLI_ANSIBLE_OVERRIDES+=("laws_subscription_id=${arg#*=}")
                ;;
            --laws-resource-group=*)
                CLI_ANSIBLE_OVERRIDES+=("laws_resource_group=${arg#*=}")
                ;;
            --laws-workspace-name=*)
                CLI_ANSIBLE_OVERRIDES+=("laws_workspace_name=${arg#*=}")
                ;;
            --adx-database=*)
                CLI_ANSIBLE_OVERRIDES+=("adx_database_name=${arg#*=}")
                ;;
            --adx-cluster=*)
                CLI_ANSIBLE_OVERRIDES+=("adx_cluster_fqdn=${arg#*=}")
                ;;
            --adx-client-id=*)
                CLI_ANSIBLE_OVERRIDES+=("adx_client_id=${arg#*=}")
                ;;
            --identity-client-id=*)
                CLI_ANSIBLE_OVERRIDES+=("user_assigned_identity_client_id=${arg#*=}")
                ;;
            -h|--help)
                show_sap_automation_qa_usage "$0"
                exit 0
                ;;
            *)
                log "ERROR" "Unknown argument: '$arg'"
                show_sap_automation_qa_usage "$0"
                exit 1
                ;;
        esac
    done

    if [[ "$expect_extra_vars" == "true" ]]; then
        log "ERROR" "Option '--extra-vars' requires a value."
        show_sap_automation_qa_usage "$0"
        exit 1
    fi
}

log "INFO" "ANSIBLE_COLLECTIONS_PATH: $ANSIBLE_COLLECTIONS_PATH"
log "INFO" "ANSIBLE_CONFIG: $ANSIBLE_CONFIG"
log "INFO" "ANSIBLE_MODULE_UTILS: $ANSIBLE_MODULE_UTILS"

# Define the path to the vars.yaml file
VARS_FILE="${cmd_dir}/../vars.yaml"

# Read a single parameter value from vars.yaml.
# :param param_name: The YAML key to read.
# :return: The value, or empty string if not found.
_get_yaml_value() {
    local param_name=$1
    if [[ -f "$VARS_FILE" ]] && grep -q "^${param_name}:" "$VARS_FILE"; then
        grep "^${param_name}:" "$VARS_FILE" | awk '{split($0,a,": "); print a[2]}' | xargs
    fi
}

# Validate and merge input parameters from vars.yaml and CLI flags.
# Precedence: CLI flags > vars.yaml > defaults.
# vars.yaml is optional when all required params are provided via CLI.
# :return: None. Exits with a non-zero status if validation fails.
validate_params() {
    local vars_file_exists="false"
    if [[ -f "$VARS_FILE" ]]; then
        vars_file_exists="true"
        log "INFO" "Reading parameters from $VARS_FILE"
    else
        log "INFO" "vars.yaml not found at $VARS_FILE; using CLI parameters only"
    fi

    TEST_TYPE="${CLI_TEST_TYPE:-$(_get_yaml_value "TEST_TYPE")}"
    SYSTEM_CONFIG_NAME="${CLI_SYSTEM_CONFIG_NAME:-$(_get_yaml_value "SYSTEM_CONFIG_NAME")}"
    SAP_FUNCTIONAL_TEST_TYPE="${CLI_SAP_FUNCTIONAL_TEST_TYPE:-$(_get_yaml_value "SAP_FUNCTIONAL_TEST_TYPE")}"
    AUTHENTICATION_TYPE="${CLI_AUTHENTICATION_TYPE:-$(_get_yaml_value "AUTHENTICATION_TYPE")}"
    WORKSPACES_DIR="${CLI_WORKSPACES_DIR:-$(_get_yaml_value "WORKSPACES_DIR")}"

    if [[ -n "$TEST_GROUPS" && -z "$TEST_TYPE" ]]; then
        TEST_TYPE="SAPFunctionalTests"
        log "INFO" "TEST_TYPE set to 'SAPFunctionalTests' (implied by --test-groups)"
    fi

    local missing_params=()
    if [[ -z "$TEST_TYPE" ]]; then
        missing_params+=("TEST_TYPE (use --test-type=)")
    fi
    if [[ -z "$SYSTEM_CONFIG_NAME" ]]; then
        missing_params+=("SYSTEM_CONFIG_NAME (use --system-config=)")
    fi
    if [[ -z "$AUTHENTICATION_TYPE" ]]; then
        missing_params+=("AUTHENTICATION_TYPE (use --auth-type=)")
    fi

    if [[ ${#missing_params[@]} -ne 0 ]]; then
        log "ERROR" "Error: The following parameters are required: ${missing_params[*]}"
        log "ERROR" "Provide them via CLI flags or in $VARS_FILE"
        exit 1
    fi

    if [[ "$TEST_TYPE" == "SAPFunctionalTests" && -z "$SAP_FUNCTIONAL_TEST_TYPE" ]]; then
        log "ERROR" "Error: SAP_FUNCTIONAL_TEST_TYPE is required when TEST_TYPE is 'SAPFunctionalTests'"
        log "ERROR" "Use --functional-test-type= or set it in $VARS_FILE"
        exit 1
    fi

    # Default WORKSPACES_DIR
    if [[ -z "$WORKSPACES_DIR" ]]; then
        WORKSPACES_DIR="WORKSPACES"
        log "INFO" "WORKSPACES_DIR not set, using default: $WORKSPACES_DIR"
    fi
    export WORKSPACES_DIR

    log "INFO" "TEST_TYPE: $TEST_TYPE"
    log "INFO" "SYSTEM_CONFIG_NAME: $SYSTEM_CONFIG_NAME"
    log "INFO" "AUTHENTICATION_TYPE: $AUTHENTICATION_TYPE"
    log "INFO" "WORKSPACES_DIR: $WORKSPACES_DIR"
    if [[ -n "$SAP_FUNCTIONAL_TEST_TYPE" ]]; then
        log "INFO" "SAP_FUNCTIONAL_TEST_TYPE: $SAP_FUNCTIONAL_TEST_TYPE"
    fi
}

# Build a temporary YAML file with CLI parameter overrides for Ansible.
# Writes core and telemetry overrides, redacts secrets from log output.
# :return: Path to the temp file (empty if no overrides).
build_cli_overrides_file() {
    local has_overrides="false"
    local overrides_content=""

    # Core params that Ansible also needs
    if [[ -n "$CLI_TEST_TYPE" ]]; then
        overrides_content+="TEST_TYPE: ${CLI_TEST_TYPE}\n"
        has_overrides="true"
    fi
    if [[ -n "$CLI_SAP_FUNCTIONAL_TEST_TYPE" ]]; then
        overrides_content+="SAP_FUNCTIONAL_TEST_TYPE: ${CLI_SAP_FUNCTIONAL_TEST_TYPE}\n"
        has_overrides="true"
    fi
    if [[ -n "$CLI_AUTHENTICATION_TYPE" ]]; then
        overrides_content+="AUTHENTICATION_TYPE: ${CLI_AUTHENTICATION_TYPE}\n"
        has_overrides="true"
    fi
    if [[ -n "$CLI_WORKSPACES_DIR" ]]; then
        overrides_content+="WORKSPACES_DIR: ${CLI_WORKSPACES_DIR}\n"
        has_overrides="true"
    fi

    # Telemetry/Ansible pass-through overrides
    for override in "${CLI_ANSIBLE_OVERRIDES[@]}"; do
        local key="${override%%=*}"
        local val="${override#*=}"
        overrides_content+="${key}: ${val}\n"
        has_overrides="true"
    done

    if [[ "$has_overrides" == "true" ]]; then
        local cli_overrides_file
        cli_overrides_file=$(mktemp)
        printf '%b' "$overrides_content" > "$cli_overrides_file"
        chmod 600 "$cli_overrides_file"
        log "INFO" "CLI overrides written to temporary file" >&2
        echo "$cli_overrides_file"
    fi
}

# Extract the error message from a command's output.
# :param error_output: The output containing the error message.
# :return: The extracted error message or a default message if none is found.
extract_error_message() {
    local error_output=$1
    local extracted_message

    extracted_message=$(echo "$error_output" | grep -oP '(?<=Message: ).*' | head -n 1)
    if [[ -z "$extracted_message" ]]; then
        extracted_message="An unknown error occurred. See full error details above."
    fi
    echo "$extracted_message"
}

# Determine the playbook name based on TEST_TYPE and SAP_FUNCTIONAL_TEST_TYPE.
# :param test_type: The overall test type (e.g., "SAPFunctionalTests", "ConfigurationChecks").
# :param sap_functional_test_type: The specific SAP functional test type (e.g., "DatabaseHighAvailability", "CentralServicesHighAvailability").
# :param offline_mode: Whether to use offline mode (optional).
# :return: The name of the playbook.
get_playbook_name() {
    local test_type=$1
    local sap_functional_test_type=$2
    local offline_mode=${3:-""}

    if [[ "$test_type" == "ConfigurationChecks" ]]; then
        echo "playbook_00_configuration_checks"
        return
    fi

    if [[ "$test_type" == "SAPFunctionalTests" ]]; then
        case "$sap_functional_test_type" in
            "DatabaseHighAvailability")
                if [[ "$offline_mode" == "true" ]]; then
                    echo "playbook_01_ha_offline_tests"
                else
                    echo "playbook_00_ha_db_functional_tests"
                fi
                ;;
            "CentralServicesHighAvailability")
                if [[ "$offline_mode" == "true" ]]; then
                    echo "playbook_01_ha_offline_tests"
                else
                    echo "playbook_00_ha_scs_functional_tests"
                fi
                ;;
            "AzureBackupDatabase")
                echo "playbook_00_backup_db_functional_tests"
                ;;
            "ConfigurationChecks")
                echo "playbook_00_configuration_checks"
                ;;
            *)
                log "ERROR" "Unknown SAP_FUNCTIONAL_TEST_TYPE: $sap_functional_test_type"
                exit 1
                ;;
        esac
        return
    fi
    log "ERROR" "Unknown TEST_TYPE: $test_type. Expected 'SAPFunctionalTests' or 'ConfigurationCheck'"
    exit 1
}

# Generate filtered test configuration as JSON for Ansible extra vars
# :return: JSON string with filtered test configuration
get_filtered_test_config() {
    local input_api_file="${cmd_dir}/../src/vars/input-api.yaml"
    local test_filter_script="${cmd_dir}/../src/module_utils/filter_tests.py"

    if [[ ! -f "$test_filter_script" ]]; then
        log "ERROR" "Test filter script not found: $test_filter_script" >&2
        exit 1
    fi

    local group_arg="null"
    local cases_arg="null"

    if [[ -n "$TEST_GROUPS" ]]; then
        group_arg="$TEST_GROUPS"
    fi

    if [[ -n "$TEST_CASES" ]]; then
        cases_arg="$TEST_CASES"
    fi

    local filtered_config
    filtered_config=$(python3 "$test_filter_script" "$input_api_file" "$group_arg" "$cases_arg" 2>&1)
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Failed to filter test configuration: $filtered_config" >&2
        exit 1
    fi

    echo "$filtered_config"
}

# Retrieve a secret from Azure Key Vault.
# :param key_vault_id: The ID of the Key Vault.
# :param secret_id: The ID of the secret in the Key Vault.
# :param auth_type: The authentication type (e.g., "SSHKEY", "VMPASSWORD").
# :return: None. Exits with a non-zero status if retrieval fails.
retrieve_secret_from_key_vault() {
    local key_vault_id=$1
    local secret_id=$2
    local auth_type=$3  # Add auth_type as a parameter

    subscription_id=$(echo "$key_vault_id" | awk -F'/' '{for(i=1;i<=NF;i++){if($i=="subscriptions"){print $(i+1)}}}')

    if [[ -z "$key_vault_id" || -z "$secret_id" ]]; then
        log "ERROR" "Key Vault ID or secret ID is missing."
        exit 1
    fi

    log "INFO" "Using Key Vault ID: $key_vault_id"
    log "INFO" "Using secret ID: $secret_id"

    # Authenticate using MSI
    log "INFO" "Authenticating using MSI..."
    az login --identity
    az account set --subscription "$subscription_id"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to authenticate using MSI."
        exit 1
    fi

    # Attempt to retrieve the secret value and handle errors
    log "INFO" "Retrieving secret from Key Vault using resource ID..."
    set +e  # Temporarily disable exit on error
    secret_value=$(az keyvault secret show --id "$secret_id" --query "value" -o tsv 2>&1)
    az_exit_code=$?  # Capture the exit code of the az command
    set -e  # Re-enable exit on error

    if [[ $az_exit_code -ne 0 || -z "$secret_value" ]]; then
        extracted_message=$(extract_error_message "$secret_value")
        log "ERROR" "Failed to retrieve secret from Key Vault: $extracted_message"
        exit 1
    fi

    log "INFO" "Successfully retrieved secret from Key Vault."

    # Define a unique temporary file path based on auth_type
    if [[ "$auth_type" == "SSHKEY" ]]; then
        temp_file=$(mktemp --dry-run --suffix=.ppk)
    elif [[ "$auth_type" == "VMPASSWORD" ]]; then
        temp_file=$(mktemp --dry-run)
    else
        log "ERROR" "Unknown authentication type: $auth_type"
        exit 1
    fi

    if [[ -f "$temp_file" ]]; then
        log "ERROR" "Temporary file already exists: $temp_file"
        exit 1
    fi

    # Create the temporary file and write the secret value to it
    echo "$secret_value" > "$temp_file"
    chmod 600 "$temp_file"  # Set the correct permissions for the file
    if [[ ! -s "$temp_file" ]]; then
        log "ERROR" "Failed to store the retrieved secret in the temporary file."
        exit 1
    fi
    log "INFO" "Temporary file created with secure permissions: $temp_file"
}

# Run the ansible playbook.
# :param playbook_name: The name of the playbook to run.
# :param system_hosts: The path to the inventory file.
# :param system_params: The path to the SAP parameters file.
# :param auth_type: The authentication type (e.g., "SSHKEY", "VMPASSWORD").
# :param system_config_folder: The path to the system configuration folder.
# :return: None. Exits with the return code of the ansible-playbook command.
run_ansible_playbook() {
    local playbook_name=$1
    local system_hosts=$2
    local system_params=$3
    local auth_type=$4
    local system_config_folder=$5

    local vars_file_args=""
    if [[ -f "$VARS_FILE" ]]; then
        vars_file_args="-e @$VARS_FILE"
    fi

    local cli_overrides_file=""
    cli_overrides_file=$(build_cli_overrides_file)
    local cli_overrides_args=""
    if [[ -n "$cli_overrides_file" ]]; then
        cli_overrides_args="-e @$cli_overrides_file"
    fi

    local extra_vars=""
    if [[ -n "$TEST_GROUPS" || -n "$TEST_CASES" ]]; then
        local filtered_config
        filtered_config=$(get_filtered_test_config)
        if [[ -n "$filtered_config" ]]; then
            local temp_config_file=$(mktemp)
            echo "$filtered_config" > "$temp_config_file"
            extra_vars="--extra-vars @$temp_config_file"
        fi
    fi

    if [[ -n "$EXTRA_VARS" ]]; then
        log "INFO" "Using additional extra vars: $EXTRA_VARS"
        escaped_extra_vars="${EXTRA_VARS//\'/\'\"\'\"\'}"
        extra_vars+=" --extra-vars '$escaped_extra_vars'"
    fi

    local common_extra_vars="$vars_file_args -e @$system_params -e '_workspace_directory=$system_config_folder' $extra_vars $cli_overrides_args"

    # Skip authentication setup if in offline mode
    if [[ "$OFFLINE_MODE" == "true" ]]; then
        log "INFO" "Offline mode: Skipping SSH authentication setup"
        command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
            $common_extra_vars --connection=local"
    else
        # Set local secret_id and key_vault_id if defined
        local secret_id=$(grep "^secret_id:" "$system_params" | awk '{split($0,a,": "); print a[2]}' | xargs || true)
        local key_vault_id=$(grep "^key_vault_id:" "$system_params" | awk '{split($0,a,": "); print a[2]}' | xargs || true)

        if [[ -n "$secret_id" ]]; then
            log "INFO" "Extracted secret_id: $secret_id"
        fi

        if [[ -n "$key_vault_id" ]]; then
            log "INFO" "Extracted key_vault_id: $key_vault_id"
        fi

        if [[ "$auth_type" == "SSHKEY" ]]; then
            log "INFO" "Authentication type is SSHKEY."

            if [[ -n "$key_vault_id" && -n "$secret_id" ]]; then
                log "INFO" "Key Vault ID and Secret ID are set. Retrieving SSH key from Key Vault."
                retrieve_secret_from_key_vault "$key_vault_id" "$secret_id" "SSHKEY"

                check_file_exists "$temp_file" \
                    "Temporary SSH key file not found. Please check the Key Vault secret ID."
                command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $temp_file \
                    $common_extra_vars"
            else
                local ssh_key_dir="${cmd_dir}/../$WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME"
                local ssh_key=""
                local extensions=("ppk" "pem" "key" "private" "rsa" "ed25519" "ecdsa" "dsa" "")

                for ext in "${extensions[@]}"; do
                    if [[ -n "$ext" ]]; then
                        local key_file="${ssh_key_dir}/ssh_key.${ext}"
                    else
                        local key_file="${ssh_key_dir}/ssh_key"
                    fi

                    if [[ -f "$key_file" ]]; then
                        ssh_key="$key_file"
                        log "INFO" "Found SSH key file: $ssh_key"
                        break
                    fi
                done

                if [[ -z "$ssh_key" ]]; then
                    ssh_key=$(find "$ssh_key_dir" -name "*ssh_key*" -type f | head -n 1)
                    if [[ -n "$ssh_key" ]]; then
                        log "INFO" "Found SSH key file with pattern: $ssh_key"
                    fi
                fi

                check_file_exists "$ssh_key" \
                    "SSH key file not found in $WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME directory. Looked for files with patterns: ssh_key.*, *ssh_key*"

                chmod 600 "$ssh_key"
                command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $ssh_key \
                    $common_extra_vars"
            fi

        elif [[ "$auth_type" == "VMPASSWORD" ]]; then
            log "INFO" "Authentication type is VMPASSWORD."

            if [[ -n "$key_vault_id" && -n "$secret_id" ]]; then
                log "INFO" "Key Vault ID and Secret ID are set. Retrieving VM password from Key Vault."
                retrieve_secret_from_key_vault "$key_vault_id" "$secret_id" "VMPASSWORD"

                check_file_exists "$temp_file" \
                    "Temporary password file not found. Please check the Key Vault secret ID."
                command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
                    --extra-vars 'ansible_password=$(cat $temp_file)' $common_extra_vars"
            else
                local password_file="${cmd_dir}/../$WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME/password"
                check_file_exists "$password_file" \
                    "password file not found in $WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME directory."
                command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
                    --extra-vars 'ansible_password=$(cat $password_file)' $common_extra_vars"
            fi

        else
            log "ERROR" "Unknown authentication type: $auth_type"
            exit 1
        fi
    fi

    # Add verbosity if specified
    if [[ -n "$ANSIBLE_VERBOSE" ]]; then
        command+=" $ANSIBLE_VERBOSE"
    fi

    if [[ "${ANSIBLE_SYNTAX_CHECK:-}" == "true" ]]; then
        command+=" --syntax-check"
        log "INFO" "Syntax-check mode enabled (ANSIBLE_SYNTAX_CHECK=true)"
    fi

    # Set ANSIBLE_LOG_PATH so execution output is captured for HTML reports
    local log_dir="${system_config_folder}/logs"
    mkdir -p "$log_dir"
    export ANSIBLE_LOG_PATH="${log_dir}/execution_$(date +%Y%m%d_%H%M%S).log"
    log "INFO" "Ansible execution log: $ANSIBLE_LOG_PATH"

    log "INFO" "Running ansible playbook... Command: $command"
    eval $command
    return_code=$?
    log "INFO" "Ansible playbook execution completed with return code: $return_code"

    # Clean up temporary files if they exist
    if [[ -n "$temp_file" && -f "$temp_file" ]]; then
        rm -f "$temp_file"
        log "INFO" "Temporary file deleted: $temp_file"
    fi
    
    if [[ -n "$temp_config_file" && -f "$temp_config_file" ]]; then
        rm -f "$temp_config_file"
        log "INFO" "Temporary config file deleted: $temp_config_file"
    fi

    if [[ -n "$cli_overrides_file" && -f "$cli_overrides_file" ]]; then
        rm -f "$cli_overrides_file"
        log "INFO" "CLI overrides file deleted"
    fi

    exit $return_code
}

# Main script execution.
# :return: None. Exits with a non-zero status if any step fails.
main() {
    log "INFO" "Activate the virtual environment..."
    set -e

    parse_arguments "$@"

    check_version_update
    if [[ -n "$TEST_GROUPS" ]]; then
        log "INFO" "Test group specified: $TEST_GROUPS"
    fi
    if [[ -n "$TEST_CASES" ]]; then
        log "INFO" "Test cases specified: $TEST_CASES"
    fi
    if [[ "$OFFLINE_MODE" == "true" ]]; then
        log "INFO" "Offline mode enabled - using previously collected CIB data"
    fi

    # Validate parameters
    validate_params

    # Validate worksapce status for any running  jobs
    check_workspace_busy $SYSTEM_CONFIG_NAME

    # Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside WORKSPACES/SYSTEM folder
    SYSTEM_CONFIG_FOLDER="${cmd_dir}/../$WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME"
    SID=$(echo "$SYSTEM_CONFIG_NAME" | awk -F'-' '{print $NF}')
    
    if [[ -f "$SYSTEM_CONFIG_FOLDER/hosts.yaml" ]]; then
        SYSTEM_HOSTS="$SYSTEM_CONFIG_FOLDER/hosts.yaml"
        log "INFO" "Using standard inventory: hosts.yaml"
    elif [[ -f "$SYSTEM_CONFIG_FOLDER/${SID}_hosts.yaml" ]]; then
        SYSTEM_HOSTS="$SYSTEM_CONFIG_FOLDER/${SID}_hosts.yaml"
        log "INFO" "Using SID-specific inventory: ${SID}_hosts.yaml"
    else
        log "ERROR" "No inventory file found. Looked for hosts.yaml in $WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME directory."
        exit 1
    fi

    SYSTEM_PARAMS="$SYSTEM_CONFIG_FOLDER/sap-parameters.yaml"
    TEST_TIER=$(echo "$TEST_TIER" | tr '[:upper:]' '[:lower:]')

    log "INFO" "Using inventory: $SYSTEM_HOSTS."
    log "INFO" "Using SAP parameters: $SYSTEM_PARAMS."
    log "INFO" "Using Authentication Type: $AUTHENTICATION_TYPE."

    check_file_exists "$SYSTEM_PARAMS" \
        "sap-parameters.yaml not found in $WORKSPACES_DIR/SYSTEM/$SYSTEM_CONFIG_NAME directory."

		if [[ "$OFFLINE_MODE" == "true" ]]; then
        local crm_report_dir="$SYSTEM_CONFIG_FOLDER/offline_validation"
        if [[ ! -d "$crm_report_dir" ]]; then
            log "ERROR" "Offline mode requires CIB data in $crm_report_dir directory. Please run online tests first to collect CIB data."
            exit 1
        fi

        local cib_files=$(find "$crm_report_dir" -name "cib" -type f 2>/dev/null | wc -l)
        if [[ "$cib_files" -eq 0 ]]; then
            log "ERROR" "No CIB files found in $crm_report_dir. Please run online tests first to collect CIB data."
            exit 1
        fi

        log "INFO" "Found $cib_files CIB file(s) for offline analysis"
    fi

    # Override SAP_FUNCTIONAL_TEST_TYPE based on --test-groups if specified
    if [[ -n "$TEST_GROUPS" ]]; then
        if [[ "$TEST_TYPE" != "SAPFunctionalTests" ]]; then
            log "INFO" "Overriding TEST_TYPE: '$TEST_TYPE' -> 'SAPFunctionalTests' (--test-groups implies functional tests)"
            TEST_TYPE="SAPFunctionalTests"
        fi
        local test_filter_script="${cmd_dir}/../src/module_utils/filter_tests.py"
        local input_api_file="${cmd_dir}/../src/vars/input-api.yaml"
        local resolved_type
        resolved_type=$(python3 "$test_filter_script" "$input_api_file" "$TEST_GROUPS" "null" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('SAP_FUNCTIONAL_TEST_TYPE',''))" 2>/dev/null || true)
        if [[ -n "$resolved_type" && "$resolved_type" != "$SAP_FUNCTIONAL_TEST_TYPE" ]]; then
            log "INFO" "Overriding SAP_FUNCTIONAL_TEST_TYPE: '$SAP_FUNCTIONAL_TEST_TYPE' -> '$resolved_type' (from --test-groups=$TEST_GROUPS)"
            SAP_FUNCTIONAL_TEST_TYPE="$resolved_type"
        fi
    fi

    playbook_name=$(get_playbook_name "$TEST_TYPE" "$SAP_FUNCTIONAL_TEST_TYPE" "$OFFLINE_MODE")
    log "INFO" "Using playbook: $playbook_name."

    run_ansible_playbook "$playbook_name" "$SYSTEM_HOSTS" "$SYSTEM_PARAMS" "$AUTHENTICATION_TYPE" "$SYSTEM_CONFIG_FOLDER"

}

# Execute the main function
main "$@"
