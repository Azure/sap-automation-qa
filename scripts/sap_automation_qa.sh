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

# Function to print logs with color based on severity
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

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to validate input parameters from vars.yaml
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

# Function to check if a file exists
check_file_exists() {
    local file_path=$1
    local error_message=$2

    if [[ ! -f "$file_path" ]]; then
        log "ERROR" "Error: $error_message"
        exit 1
    fi
}

# Function to determine the playbook name based on the sap_functional_test_type
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

# Function to get MSI object ID using Azure Instance Metadata Service (IMDS)
get_msi_object_id() {
    # Use IMDS to get the system-assigned MSI object ID
    msi_object_id=$(curl -s -H "Metadata:true" "http://169.254.169.254/metadata/identity/info?api-version=2019-08-01" | jq -r '.compute.identity.systemAssignedIdentity')
    if [[ -z "$msi_object_id" || "$msi_object_id" == "null" ]]; then
        log "ERROR" "Failed to retrieve system-assigned MSI object ID using IMDS."
        exit 1
    fi

    echo "$msi_object_id"
}

# Updated check_msi_permissions function to use MSI token
check_msi_permissions() {
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

    log "INFO" "Checking MSI permissions on Key Vault: $key_vault_name..."

    # Get MSI object ID using IMDS
    msi_object_id=$(get_msi_object_id "$resource_group_name" "$VM_NAME")
    log "INFO" "MSI OBJECT ID: $msi_object_id..."
    log "INFO" "resource group NAME: $resource_group_name..."
    if [[ -z "$msi_object_id" ]]; then
        log "ERROR" "Failed to retrieve MSI object ID."
        exit 1
    fi
    
    # Log in using MSI object ID
    log "INFO" "Logging in using MSI object ID: $msi_object_id"
    az login --identity
    az account set --subscription "$subscription_id"
    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to log in using MSI object ID: $msi_object_id"
        exit 1
    fi

    # Check Key Vault permissions
    permissions=$(az keyvault show --name "$key_vault_name" --query "properties.accessPolicies[?objectId=='$msi_object_id'].permissions.secrets" -o tsv)
    if [[ ! "$permissions" =~ (^|[[:space:]])"$required_permission"($|[[:space:]]) ]]; then
        log "ERROR" "MSI does not have the required '$required_permission' permission on Key Vault $key_vault_name."
        exit 1
    fi

    log "INFO" "MSI has the required permissions on Key Vault $key_vault_name."
}

# Function to run the ansible playbook
run_ansible_playbook() {
    local playbook_name=$1
    local system_hosts=$2
    local system_params=$3
    local auth_type=$4
    local system_config_folder=$5
    local secret_name=$6
    local temp_file

    if [[ "$auth_type" == "SSHKEY" ]]; then
        log "INFO" "Authentication type is SSHKEY."

        # Extract key_vault_id from sap-parameters.yaml
        key_vault_id=$(grep "^key_vault_id:" "$system_params" | awk '{split($0,a,": "); print a[2]}' | xargs)
        if [[ -z "$key_vault_id" ]]; then
            log "ERROR" "Error: key_vault_id is not defined in $system_params."
            exit 1
        fi
        log "INFO" "Extracted key_vault_id: $key_vault_id"

        # Extract Key Vault details and check MSI permissions
        check_msi_permissions "$key_vault_id"
        if [[ -n "$key_vault_name" && -n "$secret_name" ]]; then
            log "INFO" "Using Key Vault for SSH key retrieval."
            secret_value=$(az keyvault secret show --vault-name "$key_vault_name" --name "$secret_name" --query "value" -o tsv)
            if [[ -z "$secret_value" ]]; then
                log "ERROR" "Failed to retrieve secret '$secret_name' from Key Vault '$key_vault_name'."
                exit 1
            fi
            temp_file=$(mktemp --suffix=.ppk)
            echo "$secret_value" > "$temp_file"
            log "INFO" "Temporary SSH key file created: $temp_file"
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $temp_file \
            -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder'"
        else
            local ssh_key="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk"
            log "INFO" "Using local SSH key: $ssh_key."
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts --private-key $ssh_key \
            -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder'"
        fi
    elif [[ "$auth_type" == "VMPASSWORD" ]]; then
        if [[ -n "$key_vault_name" && -n "$secret_name" ]]; then
            log "INFO" "Using Key Vault for password retrieval."
            secret_value=$(az keyvault secret show --vault-name "$key_vault_name" --name "$secret_name" --query "value" -o tsv)
            if [[ -z "$secret_value" ]]; then
                log "ERROR" "Failed to retrieve secret '$secret_name' from Key Vault '$key_vault_name'."
                exit 1
            fi
            temp_file=$(mktemp --suffix=.password)
            echo "$secret_value" > "$temp_file"
            log "INFO" "Temporary password file created: $temp_file"
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
            --extra-vars \"ansible_ssh_pass=$(cat $temp_file)\" --extra-vars @$VARS_FILE -e @$system_params \
            -e '_workspace_directory=$system_config_folder'"
        else
            local password_file="${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password"
            log "INFO" "Using local password file: $password_file."
            command="ansible-playbook ${cmd_dir}/../src/$playbook_name.yml -i $system_hosts \
            --extra-vars \"ansible_ssh_pass=$(cat $password_file)\" --extra-vars @$VARS_FILE -e @$system_params \
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

# Main script execution
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

    # log "INFO" "Checking if the SSH key or password file exists..."
    # if [[ "$AUTHENTICATION_TYPE" == "SSHKEY" ]]; then
    #     check_file_exists "${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk" \
    #         "ssh_key.ppk not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    # elif [[ "$AUTHENTICATION_TYPE" == "VMPASSWORD" ]]; then
    #     check_file_exists "${cmd_dir}/../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password" \
    #         "password file not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    # elif [[ "$AUTHENTICATION_TYPE" == "KEYVAULT" ]]; then
    #     log "INFO" "Key Vault authentication selected. Ensure Key Vault parameters are set."
    # fi

    # Extract secret_name from sap-parameters.yaml
    secret_name=$(grep "^secret_name:" "$SYSTEM_PARAMS" | awk '{split($0,a,": "); print a[2]}' | xargs)

    if [[ -z "$secret_name" ]]; then
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