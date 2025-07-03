#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -euo pipefail

# Source the utils script for logging and utility functions
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/utils.sh"
set_output_context

# Ensure we're in the project root directory
cd "$(dirname "$script_dir")"

packages=("python3-pip" "ansible" "sshpass" "python3-venv")
install_packages "${packages[@]}"

# Verify Python3 is available
if ! command_exists python3; then
    log "ERROR" "Python3 is not available after installation. Please install Python3 manually."
    exit 1
fi


# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    log "INFO" "Creating Python virtual environment..."
    if python3 -m venv .venv; then
        log "INFO" "Python virtual environment created."
    else
        log "ERROR" "Failed to create Python virtual environment."
        exit 1
    fi
fi

# Ensure virtual environment is activated
log "INFO" "Activating Python virtual environment..."
if source .venv/bin/activate; then
    log "INFO" "Python virtual environment activated."
else
    log "ERROR" "Failed to activate Python virtual environment."
    exit 1
fi

log "INFO" "Installing Python packages..."
if ! pip install --upgrade pip; then
		log "ERROR" "Failed to upgrade pip."
fi
if pip install pyyaml requests azure-identity azure-kusto-data azure-kusto-ingest azure-mgmt-network azure-storage-blob azure-storage-queue; then
    log "INFO" "Python packages installed successfully."
else
    log "ERROR" "Failed to install Python packages."
fi

log "INFO" "Which Python: $(which python)"

export ANSIBLE_HOST_KEY_CHECKING=False
export ANSIBLE_PYTHON_INTERPRETER=$(which python3)

log "INFO" "Setup completed successfully!"
log "INFO" "Virtual environment is located at: $(pwd)/.venv"
log "INFO" "To activate the virtual environment manually, run: source .venv/bin/activate"
