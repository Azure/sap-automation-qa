#!/bin/bash

# Define the path to the vars.yaml file
VARS_FILE="../vars.yaml"

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to validate input parameters from vars.yaml
validate_params() {
    # Read each line from vars.yaml
    while IFS=": " read -r key value; do
        case "$key" in
            "TEST_TYPE")
                if [[ -z "$value" ]]; then
                    echo "TEST_TYPE cannot be empty"
                    exit 1
                else
                    TEST_TYPE="$value"
                    echo "TEST_TYPE: $value"
                fi
                ;;
            "TEST_TIER")
                if [[ -z "$value" ]]; then
                    echo "TEST_TIER cannot be empty"
                    exit 1
                else
                    TEST_TIER="$value"
                    echo "TEST_TIER: $value"
                fi
                ;;
            "SYSTEM_CONFIG_NAME")
                if [[ -z "$value" ]]; then
                    echo "SYSTEM_CONFIG_NAME cannot be empty"
                    exit 1
                else
                    echo "SYSTEM_CONFIG_NAME: $value"
                    SYSTEM_CONFIG_NAME="$value"
                fi
                ;;
            "TELEMETRY_DATA_DESTINATION")
                if [[ -z "$value" ]]; then
                    echo "TELEMETRY_DATA_DESTINATION cannot be empty"
                    exit 1
                else
                    echo "TELEMETRY_DATA_DESTINATION: $value"
                fi
                ;;
            # Add more parameter validations as needed
            *)
                ;;
        esac
    done < "$VARS_FILE" || { echo "Error: $VARS_FILE not found."; exit 1; }
}

# Check if ansible is installed, if not, install it
install_ansible() {
    if ! command_exists ansible; then
        echo "Ansible is not installed. Installing now..."
        # Assuming the use of a Debian-based system
        sudo apt update && sudo apt install ansible -y
    else
        echo "Ansible is already installed."
    fi
}

# Main script execution
echo "Validating input parameters..."
validate_params
echo "Input parameters validated."

echo "Checking Ansible installation..."
install_ansible
echo "Ansible installation checked."

# Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside the WORKSPACES/SYSTEM folder
SYSTEM_HOSTS="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/hosts.yaml"
SYSTEM_PARAMS="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/sap-parameters.yaml"

echo "Using inventory: $SYSTEM_HOSTS."
echo "Using SAP parameters: $SYSTEM_PARAMS."

if [[ ! -f "$SYSTEM_HOSTS" ]]; then
    echo "Error: hosts.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
fi

if [[ ! -f "$SYSTEM_PARAMS" ]]; then
    echo "Error: sap-parameters.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
fi

echo "Running ansible playbook..."
# Proceed with running ansible playbook using the inventory from the verified directory
ansible-playbook ../ansible/playbook_00_ha_functional_tests.yml -i "$SYSTEM_PARAMS" -e @"$VARS_FILE" -e "$EXTRA_PARAMS" = "$EXTRA_PARAM_FILE" 
echo "Ansible playbook execution completed."

exit 0