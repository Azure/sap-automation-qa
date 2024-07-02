#!/bin/bash

# Check if vars.yaml exists in the current directory
if [ ! -f ../vars.yaml ]; then
    echo "Error: vars.yaml not found in the parent directory."
    exit 1
fi

# Load variables from vars.yaml file
eval "$(yq eval '(. | to_entries[] | .key + "=" + (.value | tojson))' ../vars.yaml)"

# Parse variables
SYSTEM_CONFIG_NAME=$(echo $SYSTEM_CONFIG_NAME | tr -d '"')
TEST_TYPE=$(echo $TEST_TYPE | tr -d '"')
TEST_TIER=$(echo $TEST_TIER | tr -d '"')
SAP_CONNECTION_TYPE=$(echo $SAP_CONNECTION_TYPE | tr -d '"')
SAP_CONNECTION_USER=$(echo $SAP_CONNECTION_USER | tr -d '"')
SSH_KEY_PATH=$(echo $SSH_KEY_PATH | tr -d '"')
SSH_PASSWORD=$(echo $SSH_PASSWORD | tr -d '"')
EXTRA_PARAMS=$(echo $EXTRA_PARAMS | tr -d '"')
EXTRA_PARAM_FILE=$(echo $EXTRA_PARAM_FILE | tr -d '"')

ANSIBLE_FILE_PATH="ansible/playbook_00_ha_funtional_tests.yml"
PARAMETERS_FOLDER="SYSTEM/$SYSTEM_CONFIG_NAME"
SAP_PARAMS="SYSTEM/$SYSTEM_CONFIG_NAME/sap-parameters.yaml"
INVENTORY="SYSTEM/$SYSTEM_CONFIG_NAME/hosts.yaml"

# Check if ansible is installed and if not install it
if ! command -v ansible-playbook &> /dev/null; then
    echo "Ansible is not installed. Installing Ansible..."
    sudo apt install ansible -y
fi

# Check if parameters are empty
if [ -z "$SYSTEM_CONFIG_NAME" ] || [ -z "$TEST_TYPE" ] || [ -z "$TEST_TIER" ] || [ -z "$SAP_CONNECTION_TYPE" ] || [ -z "$SAP_CONNECTION_USER" ] || [ -z "$SSH_KEY_PATH" ] && [ -z "$SSH_PASSWORD" ]; then
    echo "Error: One or more parameters are empty."
    exit 1
else
    echo -e "\033[1;32mInput Parameters validated.\033[0m"
fi

# Check if SYSTEM/$SYSTEM_CONFIG_NAME directory exists
if [ ! -f $SAP_PARAMS ]; then
    echo "Error: System configuration not found in SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
else
    echo -e "\033[1;32mSystem Configuration validated.\033[0m"
fi
# Check if hosts.yaml file exists in SYSTEM/$SYSTEM_CONFIG_NAME directory
if [ ! -f $INVENTORY ]; then
    echo "Error: hosts.yaml not found in SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
else
    echo -e "\033[1;32mUsing inventory: $SYSETM_CONFIG_NAME.\033[0m"
fi

command = "ansible-playbook -i $INVENTORY --private-key $SSH_KEY_PATH    \
    -e @$SAP_PARAMS -e 'download_directory=$(Agent.TempDirectory)' -e '_workspace_directory=$PARAMETERS_FOLDER' \
    -e ansible_ssh_pass='${SSH_PASSWORD}' "$EXTRA_PARAMS" $EXTRA_PARAM_FILE                                   \
    $ANSIBLE_FILE_PATH"

echo "##[section]Executing [$command]..."
    echo "##[group]- output"
    eval $command
    return_code=$?
    echo "##[section]Ansible playbook execution completed with exit code [$return_code]"
    echo "##[endgroup]"
