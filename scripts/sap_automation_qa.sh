#!/bin/bash

# Check if vars.yaml exists in the current directory
if [ ! -f vars.yaml ]; then
    echo "Error: vars.yaml not found in the current directory."
    exit 1
fi

# Read parameters from the vars.yaml file
SYSTEM_CONFIG_NAME=$(yq r vars.yaml SYSTEM_CONFIG_NAME)
TEST_TYPE=$(yq r vars.yaml TEST_TYPE)
TEST_TIER=$(yq r vars.yaml TEST_TIER)
SAP_CONNECTION_TYPE=$(yq r vars.yaml SAP_CONNECTION)
SAP_CONNECTION_USER=$(yq r vars.yaml SAP_CONNECTION_USER)
SSH_KEY_PATH=$(yq r vars.yaml SSH_KEY_PATH)
SSH_PASSWORD=$(yq r vars.yaml SSH_PASSWORD)
EXTRA_PARAMS=$(yq r vars.yaml EXTRA_PARAMS)
EXTRA_PARAM_FILE=$(yq r vars.yaml EXTRA_PARAM_FILE)

ANSIBLE_FILE_PATH="ansible/playbook_00_ha_funtional_tests.yml"
PARAMETERS_FOLDER="SYSTEM/$SYSTEM_CONFIG_NAME"
SAP_PARAMS="SYSTEM/$SYSTEM_CONFIG_NAME/sap-parameters.yaml"
INVENTORY="SYSTEM/$SYSTEM_CONFIG_NAME/hosts.yaml"

# Check if parameters are empty
if [ -z "$SYSTEM_CONFIG_NAME" ] || [ -z "$TEST_TYPE" ] || [ -z "$TEST_TIER" ] || [ -z "$SAP_CONNECTION_TYPE" ] || [ -z "$SAP_CONNECTION_USER" ] || [ -z "$SSH_KEY_PATH" ] && [ -z "$SSH_PASSWORD" ]; then
    echo "Error: One or more parameters are empty."
    exit 1
fi

# Check if SYSTEM/$SYSTEM_CONFIG_NAME directory exists
if [ ! -f $SAP_PARAMS ]; then
    echo "Error: System configuration not found in SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
fi
# Check if hosts.yaml file exists in SYSTEM/$SYSTEM_CONFIG_NAME directory
if [ ! -f $INVENTORY ]; then
    echo "Error: hosts.yaml not found in SYSTEM/$SYSTEM_CONFIG_NAME directory."
    exit 1
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