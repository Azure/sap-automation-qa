#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Activate the virtual environment
source "$(realpath $(dirname $(realpath $0))/..)/.venv/bin/activate"

cmd_dir="$(dirname "$(readlink -e "${BASH_SOURCE[0]}")")"

# Set the environment variables
export ANSIBLE_COLLECTIONS_PATH=/opt/ansible/collections:${ANSIBLE_COLLECTIONS_PATH:+${ANSIBLE_COLLECTIONS_PATH}}
export ANSIBLE_CONFIG="${cmd_dir}/ansible.cfg"
export ANSIBLE_MODULE_UTILS="${cmd_dir}/src/module_utils:${ANSIBLE_MODULE_UTILS:+${ANSIBLE_MODULE_UTILS}}
export ANSIBLE_HOST_KEY_CHECKING=False

# Define the path to the vars.yaml file
VARS_FILE="../vars.yaml"

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

# Function to run the ansible playbook
run_ansible_playbook() {
    local playbook_name=$1
    local system_hosts=$2
    local system_params=$3
    local auth_type=$4
    local system_config_folder=$5

    if [[ "$auth_type" == "SSHKEY" ]]; then
        local ssh_key="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk"
        log "INFO" "Using SSH key: $ssh_key."
        command="ansible-playbook ../src/$playbook_name.yml -i $system_hosts --private-key $ssh_key \
        -e @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder'"
    else
        log "INFO" "Using password authentication."
        command="ansible-playbook ../src/$playbook_name.yml -i $system_hosts \
        --extra-vars \"ansible_ssh_pass=$(cat ../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password)\" \
        --extra-vars @$VARS_FILE -e @$system_params -e '_workspace_directory=$system_config_folder'"
    fi

    log "INFO" "Running ansible playbook..."
    log "INFO" "Executing: $command"
    eval $command
    return_code=$?
    log "INFO" "Ansible playbook execution completed with return code: $return_code"

    exit $return_code
}

# Main script execution
main() {
    log "INFO" "Activate the virtual environment..."
    set -e

    # Validate parameters
    validate_params

    # Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside WORKSPACES/SYSTEM folder
    SYSTEM_CONFIG_FOLDER="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME"
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

    log "INFO" "Checking if the SSH key or password file exists..."
    if [[ "$AUTHENTICATION_TYPE" == "SSHKEY" ]]; then
        check_file_exists "../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk" \
            "ssh_key.ppk not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    else
        check_file_exists "../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password" \
            "password file not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    fi

    playbook_name=$(get_playbook_name "$sap_functional_test_type")
    log "INFO" "Using playbook: $playbook_name."

    run_ansible_playbook "$playbook_name" \
        "$SYSTEM_HOSTS" "$SYSTEM_PARAMS" "$AUTHENTICATION_TYPE" "$SYSTEM_CONFIG_FOLDER"
}

# Execute the main function
main