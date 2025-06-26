#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -euo pipefail
# Activate the virtual environment
source "$(realpath $(dirname $(realpath $0))/..)/.venv/bin/activate"

cmd_dir="$(dirname "$(readlink -e "${BASH_SOURCE[0]}")")"

# Set the environment variables
export ANSIBLE_COLLECTIONS_PATH=/opt/ansible/collections:${ANSIBLE_COLLECTIONS_PATH:+${ANSIBLE_COLLECTIONS_PATH}}
export ANSIBLE_CONFIG="${cmd_dir}/../src/ansible.cfg"
export ANSIBLE_MODULE_UTILS="${cmd_dir}/../src/module_utils:${ANSIBLE_MODULE_UTILS:+${ANSIBLE_MODULE_UTILS}}"
export ANSIBLE_HOST_KEY_CHECKING=False
# Colors for error messages
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Global variable to store the path of the temporary file.
temp_file=""

# Parse command line arguments and extract verbose flags
# Sets global ANSIBLE_VERBOSE variable
parse_arguments() {
    ANSIBLE_VERBOSE=""

    for arg in "$@"; do
        case "$arg" in
            -v|-vv|-vvv|-vvvv|-vvvvv|-vvvvvv)
                ANSIBLE_VERBOSE="$arg"
                ;;
            --test_groups=*)
                TEST_GROUPS="${arg#*=}"
                ;;
            --test_cases=*)
                TEST_CASES="${arg#*=}"
                # Remove brackets and convert to array
                TEST_CASES="${TEST_CASES#[}"
                TEST_CASES="${TEST_CASES%]}"
                ;;
						--extra-vars=*)
								EXTRA_VARS="${arg#*=}"
								;;
            -h|--help)
                show_usage
                exit 0
                ;;
        esac
    done
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  -v, -vv, -vvv, etc.       Set Ansible verbosity level
  --test_groups=GROUP       Specify test group to run (e.g., HA_DB_HANA, HA_SCS)
  --test_cases=[case1,case2] Specify specific test cases to run (comma-separated, in brackets)
	--extra-vars=VAR          Specify additional Ansible extra variables (e.g., --extra-vars='{"key":"value"}')
  -h, --help                Show this help message

Examples:
  $0 --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash]
  $0 --test_groups=HA_SCS
	$0 --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash] -vv
	$0 --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash] --extra-vars='{"key":"value"}'

Configuration is read from vars.yaml file.
EOF
}

# Print logs with color based on severity.
# :param severity: The severity level of the log (e.g., "INFO", "ERROR").
# :param message: The message to log.
log() {
    local severity=$1
    local message=$2

    if [[ "$severity" == "ERROR" ]]; then
        echo -e "${RED}[ERROR] $message${NC}"
    else
        echo -e "${GREEN}[INFO] $message${NC}"
    fi
}

log "INFO" "ANSIBLE_COLLECTIONS_PATH: $ANSIBLE_COLLECTIONS_PATH"
log "INFO" "ANSIBLE_CONFIG: $ANSIBLE_CONFIG"
log "INFO" "ANSIBLE_MODULE_UTILS: $ANSIBLE_MODULE_UTILS"

# Define the path to the vars.yaml file
VARS_FILE="${cmd_dir}/../vars.yaml"

# Check if a command exists.
# :param command: The command to check.
# :return: None. Exits with a non-zero status if the command does not exist.
command_exists() {
    command -v "$1" &> /dev/null
}

# Validate input parameters from vars.yaml.
# :return: None. Exits with a non-zero status if validation fails.
validate_params() {
    local missing_params=()
    local params=("TEST_TYPE" "SYSTEM_CONFIG_NAME" "sap_functional_test_type" "AUTHENTICATION_TYPE")

    # Check if vars.yaml exists
    if [ ! -f "$VARS_FILE" ]; then
        log "ERROR" "Error: $VARS_FILE not found."
        exit 1
    fi

    for param in "${params[@]}"; do
        # Use grep to find the line and awk to split the line and get the value
        value=$(grep "^$param:" "$VARS_FILE" | awk '{split($0,a,": "); print a[2]}' | xargs)

        if [[ -z "$value" ]]; then
            missing_params+=("$param")
        else
            log "INFO" "$param: $value"
            declare -g "$param=$value"
        fi
    done

    if [ ${#missing_params[@]} -ne 0 ]; then
        log "ERROR" "Error: The following parameters cannot be empty: ${missing_params[*]}"
        exit 1
    fi
}

# Check if a file exists.
# :param file_path: The path to the file to check.
# :param error_message: The error message to display if the file does not exist.
# :return: None. Exits with a non-zero status if the file does not exist.
check_file_exists() {
    local file_path=$1
    local error_message=$2
    log "INFO" "Checking if file exists: $file_path"
    if [[ ! -f "$file_path" ]]; then
        log "ERROR" "Error: $error_message"
        exit 1
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

# Determine the playbook name based on the sap_functional_test_type.
# :param test_type: The type of SAP functional test.
# :return: The name of the playbook.
get_playbook_name() {
    local test_type=$1

    case "$test_type" in
        "DatabaseHighAvailability")
            echo "playbook_00_ha_db_functional_tests"
            ;;
        "CentralServicesHighAvailability")
            echo "playbook_00_ha_scs_functional_tests"
            ;;
        *)
            log "ERROR" "Unknown sap_functional_test_type: $test_type"
            exit 1
            ;;
    esac
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


    local extra_vars=""
    if [[ -n "$TEST_GROUPS" || -n "$TEST_CASES" ]]; then
        local filtered_config
        filtered_config=$(get_filtered_test_config)
        if [[ -n "$filtered_config" ]]; then
            extra_vars="--extra-vars '$filtered_config'"
        fi
    fi

		if [[ -n "$EXTRA_VARS" ]]; then
				log a "INFO" "Using additional extra vars: $EXTRA_VARS"
				escaped_extra_vars="${EXTRA_VARS//\'/\'\"\'\"\'}"
				extra_vars+=" --extra-vars '$escaped_extra_vars'"
		fi

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
                -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder' $extra_vars"
        else
            local ssh_key_dir="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME"
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
                "SSH key file not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory. Looked for files with patterns: ssh_key.*, *ssh_key*"

            chmod 600 "$ssh_key"
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $ssh_key \
                -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder' $extra_vars"
        fi

    elif [[ "$auth_type" == "VMPASSWORD" ]]; then
        log "INFO" "Authentication type is VMPASSWORD."

        if [[ -n "$key_vault_id" && -n "$secret_id" ]]; then
            log "INFO" "Key Vault ID and Secret ID are set. Retrieving VM password from Key Vault."
            retrieve_secret_from_key_vault "$key_vault_id" "$secret_id" "VMPASSWORD"

            check_file_exists "$temp_file" \
                "Temporary SSH key file not found. Please check the Key Vault secret ID."
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
                --extra-vars \"ansible_ssh_pass=$(cat $temp_file)\" --extra-vars @$VARS_FILE -e @$system_params \
                -e '_workspace_directory=$system_config_folder'"
        else
            local password_file="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password"
            check_file_exists "$password_file" \
                "password file not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
                --extra-vars \"ansible_ssh_pass=$(cat $password_file)\" --extra-vars @$VARS_FILE -e @$system_params \
                -e '_workspace_directory=$system_config_folder'"
        fi

    else
        log "ERROR" "Unknown authentication type: $auth_type"
        exit 1
    fi

		# Add verbosity if specified
		if [[ -n "$ANSIBLE_VERBOSE" ]]; then
				command+=" $ANSIBLE_VERBOSE"
		fi

    log "INFO" "Running ansible playbook... Command: $command"
    eval $command
    return_code=$?
    log "INFO" "Ansible playbook execution completed with return code: $return_code"

    # Clean up temporary file if it exists
    if [[ -n "$temp_file" && -f "$temp_file" ]]; then
        rm -f "$temp_file"
        log "INFO" "Temporary file deleted: $temp_file"
    fi

    exit $return_code
}

# Main script execution.
# :return: None. Exits with a non-zero status if any step fails.
main() {
    log "INFO" "Activate the virtual environment..."
    set -e

		# Parse command line arguments
		parse_arguments "$@"

		if [[ -n "$TEST_GROUPS" ]]; then
        log "INFO" "Test group specified: $TEST_GROUPS"
    fi
    if [[ -n "$TEST_CASES" ]]; then
        log "INFO" "Test cases specified: $TEST_CASES"
    fi

    # Validate parameters
    validate_params

    # Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside WORKSPACES/SYSTEM folder
    SYSTEM_CONFIG_FOLDER="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME"
    SYSTEM_HOSTS="$SYSTEM_CONFIG_FOLDER/hosts.yaml"
    SYSTEM_PARAMS="$SYSTEM_CONFIG_FOLDER/sap-parameters.yaml"
    TEST_TIER=$(echo "$TEST_TIER" | tr '[:upper:]' '[:lower:]')

    log "INFO" "Using inventory: $SYSTEM_HOSTS."
    log "INFO" "Using SAP parameters: $SYSTEM_PARAMS."
    log "INFO" "Using Authentication Type: $AUTHENTICATION_TYPE."

    check_file_exists "$SYSTEM_HOSTS" \
        "hosts.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    check_file_exists "$SYSTEM_PARAMS" \
        "sap-parameters.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."

    playbook_name=$(get_playbook_name "$sap_functional_test_type")
    log "INFO" "Using playbook: $playbook_name."

    run_ansible_playbook "$playbook_name" "$SYSTEM_HOSTS" "$SYSTEM_PARAMS" "$AUTHENTICATION_TYPE" "$SYSTEM_CONFIG_FOLDER"

}

# Execute the main function
main "$@"
