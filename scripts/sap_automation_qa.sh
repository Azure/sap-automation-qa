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
install_package() {
    local package_name=$1
    if ! command_exists "$package_name"; then
        echo "$package_name is not installed. Installing now..."
        # Assuming the use of a Debian-based system
        sudo apt update && sudo apt install "$package_name" -y
    else
        echo "$package_name is already installed."
    fi
}

# Check if ansible is installed, if not, install it
install_az_cli() {
    $package_name="az"
    if ! command_exists "$package_name"; then
        echo "$package_name is not installed. Installing now..."
        # Assuming the use of a Debian-based system
        sudo apt update && sudo apt install "azure-cli" -y
    else
        echo "$package_name is already installed."
    fi
}

# Main script execution
echo "Validating input parameters..."
validate_params
echo "Input parameters validated."

echo "Checking Ansible installation..."
install_package "ansible"
echo "Ansible installation checked."

echo "Checking Az CLI installation..."
install_az_cli
echo "Az CLI installation checked."

# Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside the WORKSPACES/SYSTEM folder
SYSTEM_CONFIG_FOLDER="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME"
SYSTEM_HOSTS="$SYSTEM_CONFIG_FOLDER/hosts.yaml"
SYSTEM_PARAMS="$SYSTEM_CONFIG_FOLDER/sap-parameters.yaml"
TEST_TIER=$(echo "$TEST_TIER" | tr '[:upper:]' '[:lower:]')

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

# Check if the ssh_key is to be fethed from the Azure Key Vault
SSH_KEY_KV=$(grep -Po 'ssh_key_from_keyvault: \K.*' $SYSTEM_PARAMS)

if [[ "$SSH_KEY_KV" == "true" ]]; then
    # Read the MSI_CLIENT_ID from the SYSTEM_PARAMS file form the parameter name managed_identity_resource_id
    SUBSCRIPTION_ID=$(grep -Po 'subscription_id: \K.*' $SYSTEM_PARAMS)
    SSH_KEY_SECRET_NAME=$(grep -Po 'ssh_key_secret_name: \K.*' $SYSTEM_PARAMS)
    KEY_VAULT_NAME=$(grep -Po 'keyvault_resource_id: \K.*' $SYSTEM_PARAMS)
    echo "UBSCRIPTION_ID: $SUBSCRIPTION_ID KEY_VAULT_NAME: $KEY_VAULT_NAME SSH_KEY_SECRET_NAME: $SSH_KEY_SECRET_NAME"

    az login --identity --allow-no-subscriptions --output none
    ssh_key=$(az keyvault secret show --name "$SSH_KEY_SECRET_NAME" --vault-name "$KEY_VAULT_NAME" --query value -o tsv)
    echo "SSH key retrieved."
else
    # Set the ssk key path to the default filename in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory
    ssh_key="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk"
    echo "Using SSH key: $ssh_key."
fi

echo "Running ansible playbook..."
# Proceed with running ansible playbook using the inventory from the verified directory
command="ansible-playbook ../ansible/playbook_00_ha_functional_tests.yml -i $SYSTEM_HOSTS --private-key $ssh_key -e @$VARS_FILE -e @$SYSTEM_PARAMS -e '_workspace_directory=$SYSTEM_CONFIG_FOLDER'"
echo "Executing: $command"
eval $command
return_code=$?
echo "Ansible playbook execution completed."

exit 0
