#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

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

"""
Global variable to store the path of the temporary file.
"""
temp_file=""

"""
Print logs with color based on severity.

:param severity: The severity level of the log (e.g., "INFO", "ERROR").
:param message: The message to log.
"""
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

"""
Check if a command exists.

:param command: The command to check.
:return: None. Exits with a non-zero status if the command does not exist.
"""
command_exists() {
    command -v "$1" &> /dev/null
}

"""
Validate input parameters from vars.yaml.

:return: None. Exits with a non-zero status if validation fails.
"""
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

"""
Check if a file exists.

:param file_path: The path to the file to check.
:param error_message: The error message to display if the file does not exist.
:return: None. Exits with a non-zero status if the file does not exist.
"""
check_file_exists() {
    local file_path=$1
    local error_message=$2

    if [[ ! -f "$file_path" ]]; then
        log "ERROR" "Error: $error_message"
        exit 1
    fi
}

"""
Extract the error message from a command's output.

:param error_output: The output containing the error message.
:return: The extracted error message or a default message if none is found.
"""
extract_error_message() {
    local error_output=$1
    local extracted_message

    extracted_message=$(echo "$error_output" | grep -oP '(?<=Message: ).*' | head -n 1)
    if [[ -z "$extracted_message" ]]; then
        extracted_message="An unknown error occurred. See full error details above."
    fi
    echo "$extracted_message"
}

"""
Determine the playbook name based on the sap_functional_test_type.

:param test_type: The type of SAP functional test.
:return: The name of the playbook.
"""
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

"""
Retrieve a secret from Azure Key Vault.

:param key_vault_id: The ID of the Key Vault.
:return: None. Exits with a non-zero status if retrieval fails.
"""
retrieve_secret_from_key_vault() {
    local key_vault_id=$1
    local required_permission="Get"

    # Extract resource group name and key vault name from key_vault_id
    resource_group_name=$(echo "$key_vault_id" | awk -F'/' '{for(i=1;i<=NF;i++){if($i=="resourceGroups"){print $(i+1)}}}')
    key_vault_name=$(echo "$key_vault_id" | awk -F'/' '{for(i=1;i<=NF;i++){if($i=="vaults"){print $(i+1)}}}')
    subscription_id=$(echo "$key_vault_id" | awk -F'/' '{for(i=1;i<=NF;i++){if($i=="subscriptions"){print $(i+1)}}}')

    if [[ -z "$resource_group_name" || -z "$key_vault_name" ]]; then
        log "ERROR" "Failed to extract resource group name or key vault name from key_vault_id: $key_vault_id"
        exit 1
    fi

    log "INFO" "Extracted resource group name: $resource_group_name"
    log "INFO" "Extracted key vault name: $key_vault_name"

    # Authenticate using MSI
    log "INFO" "Authenticating using MSI..."
    az login --identity
    az account set --subscription "$subscription_id"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to authenticate using MSI."
        exit 1
    fi

    # Attempt to access Key Vault to verify permissions
    log "INFO" "Verifying permissions on Key Vault: $key_vault_name..."
    set +e  # Temporarily disable exit on error
    error_message=$(az keyvault secret list --vault-name "$key_vault_name" 2>&1)
    az_exit_code=$?  # Capture the exit code of the az command
    set -e  # Re-enable exit on error

    if [[ $az_exit_code -ne 0 ]]; then
        extracted_message=$(extract_error_message "$error_message")
        log "ERROR" "Azure CLI error: $extracted_message"
        exit 1
    fi
    
    # Attempt to retrieve the secret value and handle errors
    log "INFO" "Retrieving secret '$secret_name' from Key Vault '$key_vault_name'..."
    set +e  # Temporarily disable exit on error
    secret_value=$(az keyvault secret show --vault-name "$key_vault_name" --name "$secret_name" --query "value" -o tsv 2>&1)
    az_exit_code=$?  # Capture the exit code of the az command
    set -e  # Re-enable exit on error

    if [[ $az_exit_code -ne 0 ]]; then
        extracted_message=$(extract_error_message "$secret_value")
        log "ERROR" "Failed to retrieve secret '$secret_name' from Key Vault '$key_vault_name': $extracted_message"
        exit 1
    fi

    log "INFO" "Successfully retrieved secret from Key Vault."
    temp_file=$(mktemp --suffix=.ppk)

    # Check if the temporary file already exists
    check_file_exists "$temp_file" "Temporary file already exists: $temp_file"

    echo "$secret_value" > "$temp_file"
    log "INFO" "Temporary SSH key file created: $temp_file"
}

"""
Run the ansible playbook.

:param playbook_name: The name of the playbook to run.
:param system_hosts: The path to the inventory file.
:param system_params: The path to the SAP parameters file.
:param auth_type: The authentication type (e.g., "SSHKEY", "VMPASSWORD").
:param system_config_folder: The path to the system configuration folder.
:param secret_name: The name of the secret in the Key Vault.
:return: None. Exits with the return code of the ansible-playbook command.
"""
run_ansible_playbook() {
    local playbook_name=$1
    local system_hosts=$2
    local system_params=$3
    local auth_type=$4
    local system_config_folder=$5
    local secret_name=$6

    if [[ "$auth_type" == "SSHKEY" ]]; then
        log "INFO" "Authentication type is SSHKEY."

        # Extract key_vault_id from sap-parameters.yaml
        key_vault_id=$(grep "^key_vault_id:" "$system_params" | awk '{split($0,a,": "); print a[2]}' | xargs)

        local ssh_key="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk"
        if [[ -f "$ssh_key" ]]; then
            log "INFO" "Local SSH key is present: $ssh_key. Skipping secret_name requirement."
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $ssh_key \
            -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder'"
        elif [[ -n "$key_vault_id" ]]; then
            log "INFO" "Extracted key_vault_id: $key_vault_id"

            # Extract Key Vault details and retrieve secret
            retrieve_secret_from_key_vault "$key_vault_id"
            if [[ -z "$secret_value" ]]; then
                log "ERROR" "Error: Secret value is not retrieved, and no local SSH key is present."
                exit 1
            else
                log "INFO" "Using Key Vault for SSH key retrieval."
                log "INFO" "Temporary SSH key file: $temp_file"
                command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $temp_file \
                -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder'"
            fi
        else
            log "ERROR" "Error: key_vault_id is not defined in $system_params, and no local SSH key is present."
            exit 1
        fi
    elif [[ "$auth_type" == "VMPASSWORD" ]]; then
        local password_file="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password"
        if [[ -f "$password_file" ]]; then
            log "INFO" "Local password file is present: $password_file."
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
            --extra-vars \"ansible_ssh_pass=$(cat $password_file)\" --extra-vars @$VARS_FILE -e @$system_params \
            -e '_workspace_directory=$system_config_folder'"
        else
            log "INFO" "Local password file not found. Retrieving password from Key Vault."
            temp_file=$(mktemp --suffix=.password)
            retrieve_secret_from_key_vault "$key_vault_id"
            echo "$secret_value" > "$temp_file"
            log "INFO" "Temporary password file created: $temp_file"
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
            --extra-vars \"ansible_ssh_pass=$(cat $temp_file)\" --extra-vars @$VARS_FILE -e @$system_params \
            -e '_workspace_directory=$system_config_folder'"
        fi
    else
        log "ERROR" "Unknown authentication type: $auth_type"
        exit 1
    fi

    log "INFO" "Running ansible playbook..."
    log "INFO" "Executing: $command"
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

"""
Main script execution.

:return: None. Exits with a non-zero status if any step fails.
"""
main() {
    log "INFO" "Activate the virtual environment..."
    set -e

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

    # Extract secret_name from sap-parameters.yaml
    secret_name=$(grep "^secret_name:" "$SYSTEM_PARAMS" | awk '{split($0,a,": "); print a[2]}' | xargs)

    if [[ -z "$secret_name" && "$AUTHENTICATION_TYPE" != "SSHKEY" ]]; then
        log "ERROR" "Error: secret_name is not defined in $SYSTEM_PARAMS."
        exit 1
    fi
    log "INFO" "Extracted secret_name: $secret_name"

    playbook_name=$(get_playbook_name "$sap_functional_test_type")
    log "INFO" "Using playbook: $playbook_name."

    run_ansible_playbook "$playbook_name" "$SYSTEM_HOSTS" "$SYSTEM_PARAMS" "$AUTHENTICATION_TYPE" "$SYSTEM_CONFIG_FOLDER" "$secret_name"

    # Clean up any remaining temporary files
    if [[ -n "$temp_file" && -f "$temp_file" ]]; then
        rm -f "$temp_file"
        log "INFO" "Temporary file deleted: $temp_file"
    fi
}

# Execute the main function
main