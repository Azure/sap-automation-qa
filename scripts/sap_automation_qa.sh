#!/bin/bash

# Define the path to the vars.yaml file
VARS_FILE="../vars.yaml"

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}
export ANSIBLE_HOST_KEY_CHECKING=False

RED='\033[0;31m'
GREEN='\033[0;32m'

# Function to validate input parameters from vars.yaml
validate_params() {
    local missing_params=()
    local params=("TEST_TYPE" "SYSTEM_CONFIG_NAME" "sap_functional_test_type" "AUTHENTICATION_TYPE")

    # Check if vars.yaml exists
    if [ ! -f "$VARS_FILE" ]; then
        echo "Error: $VARS_FILE not found."
        exit 1
    fi

    for param in "${params[@]}"; do
        # Use grep to find the line and awk to split the line and get the value
        value=$(grep "^$param:" "$VARS_FILE" | awk '{split($0,a,": "); print a[2]}' | xargs)

        if [[ -z "$value" ]]; then
            missing_params+=("$param")
        else
            echo "$param: $value"
            declare -g "$param=$value"
        fi
    done

    if [ ${#missing_params[@]} -ne 0 ]; then
        echo "Error: The following parameters cannot be empty: ${missing_params[*]}"
        exit 1
    fi
}

# Check if ansible is installed, if not, install it
install_package() {
    local package_name=$1
    if ! command_exists "$package_name"; then
        echo "$package_name is not installed. Installing now..."
        # Assuming the use of a Debian-based system
        apt install "$package_name" -y
    else
        echo "$package_name is already installed."
    fi
}

echo "Starting SAP Automation QA script..."

# Main script execution
echo "Validating input parameters..."
validate_params
echo "Input parameters validated."


packages=("python3-pip" "ansible" "sshpass" "python3-venv")

for package in "${packages[@]}"; do
    echo "Checking $package installation and updating packages..."
    install_package "$package"
done

sudo apt update -y

echo "Enable python virtual environment..."
python3 -m venv ../.venv
source ../.venv/bin/activate
echo "Python virtual environment enabled."

# Check if the SYSTEM_HOSTS and SYSTEM_PARAMS directory exists inside the WORKSPACES/SYSTEM folder
SYSTEM_CONFIG_FOLDER="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME"
SYSTEM_HOSTS="$SYSTEM_CONFIG_FOLDER/hosts.yaml"
SYSTEM_PARAMS="$SYSTEM_CONFIG_FOLDER/sap-parameters.yaml"
TEST_TIER=$(echo "$TEST_TIER" | tr '[:upper:]' '[:lower:]')


echo -e "${GREEN}Using inventory: $SYSTEM_HOSTS."
echo -e "${GREEN}Using SAP parameters: $SYSTEM_PARAMS."
echo -e "${GREEN}Using AUthentication Type: $AUTHENTICATION_TYPE."

if [[ ! -f "$SYSTEM_HOSTS" ]]; then
    echo -e "${RED}Error: hosts.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
fi

if [[ ! -f "$SYSTEM_PARAMS" ]]; then
    echo -e "${RED}Error: sap-parameters.yaml not found in WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
fi

if [[ "$AUTHENTICATION_TYPE" == "SSHKEY" ]]; then
    ssh_key="../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/ssh_key.ppk"
    echo -e "${GREEN}Using SSH key: $ssh_key."
    command="ansible-playbook ../ansible/playbook_00_ha_functional_tests.yml -i $SYSTEM_HOSTS --private-key $ssh_key -e @$VARS_FILE -e @$SYSTEM_PARAMS -e '_workspace_directory=$SYSTEM_CONFIG_FOLDER'"
else
    echo -e "${GREEN}Using password authentication."
    command="ansible-playbook ../ansible/playbook_00_ha_functional_tests.yml -i $SYSTEM_HOSTS --extra-vars "ansible_ssh_pass=$(cat ../WORKSPACES/SYSTEM/$SYSTEM_CONFIG_NAME/password)" --extra-vars @$VARS_FILE -e @$SYSTEM_PARAMS -e '_workspace_directory=$SYSTEM_CONFIG_FOLDER'"
fi

echo -e "${GREEN}Running ansible playbook..."
echo -e "${GREEN}Executing: $command"
eval $command
return_code=$?
echo "Ansible playbook execution completed."

exit 0
