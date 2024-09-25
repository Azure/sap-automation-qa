#!/bin/bash

set -e

# Define the path to the vars.yaml file
VARS_FILE="../vars.yaml"

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}
export ANSIBLE_HOST_KEY_CHECKING=False

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

# Validate parameters
validate_params

# Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside the WORKSPACES/SYSTEM folder
SYSTEM_CONFIG_FOLDER="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME"
SYSTEM_HOSTS="$SYSTEM_CONFIG_FOLDER/hosts.yaml"
SYSTEM_PARAMS="$SYSTEM_CONFIG_FOLDER/sap-parameters.yaml"
TEST_TIER=$(echo "$TEST_TIER" | tr '[:upper:]' '[:lower:]')

log "INFO" "Using inventory: $SYSTEM_HOSTS."
log "INFO" "Using SAP parameters: $SYSTEM_PARAMS."
log "INFO" "Using Authentication Type: $AUTHENTICATION_TYPE."

check_file_exists "$SYSTEM_HOSTS" "hosts.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
check_file_exists "$SYSTEM_PARAMS" "sap-parameters.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."

log "INFO" "Checking if the SSH key or password file exists..."
if [[ "$AUTHENTICATION_TYPE" == "SSHKEY" ]]; then
    check_file_exists "../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk" "ssh_key.ppk not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
else
    check_file_exists "../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password" "password file not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
fi

if [ "$sap_functional_test_type" = "DatabaseHighAvailability" ]; then
    playbook_name="playbook_00_ha_db_functional_tests"
elif [ "$sap_functional_test_type" = "CentralServicesHighAvailability" ]; then
    playbook_name="playbook_00_ha_scs_functional_tests"
else
    echo "Unknown sap_functional_test_type: $sap_functional_test_type"
    exit 1
fi

log "INFO" "Using playbook: $playbook_name."

log "INFO" "Activate the virtual environment..."
source ../.venv/bin/activate

if [[ "$AUTHENTICATION_TYPE" == "SSHKEY" ]]; then
    ssh_key="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk"
    log "INFO" "Using SSH key: $ssh_key."
    command="ansible-playbook ../ansible/$playbook_name.yml -i $SYSTEM_HOSTS --private-key $ssh_key -e @$VARS_FILE -e @$SYSTEM_PARAMS -e '_workspace_directory=$SYSTEM_CONFIG_FOLDER'"
else
    log "INFO" "Using password authentication."
    command="ansible-playbook ../ansible/$playbook_name.yml -i $SYSTEM_HOSTS --extra-vars \"ansible_ssh_pass=$(cat ../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password)\" --extra-vars @$VARS_FILE -e @$SYSTEM_PARAMS -e '_workspace_directory=$SYSTEM_CONFIG_FOLDER'"
fi

log "INFO" "Running ansible playbook..."
log "INFO" "Executing: $command"
eval $command
return_code=$?
log "INFO" "Ansible playbook execution completed with return code: $return_code"

exit $return_code
