#!/bin/bash

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

# Check if ansible is installed, if not, install it
install_packages() {
    local packages=("$@")
    local to_install=()
    for package in "${packages[@]}"; do
        if ! command_exists "$package"; then
            log "INFO" "$package is not installed. Adding to install list..."
            to_install+=("$package")
        else
            log "INFO" "$package is already installed."
        fi
    done

    if [ ${#to_install[@]} -ne 0 ]; then
        log "INFO" "Updating package list and installing missing packages..."
        if sudo apt update -y && sudo apt install -y "${to_install[@]}"; then
            log "INFO" "Packages installed successfully."
        else
            log "ERROR" "Failed to install packages."
        fi
    fi
}

packages=("python3-pip" "ansible" "sshpass" "python3-venv")

install_packages "${packages[@]}"

log "INFO" "Installing Python packages..."
if pip install azure-kusto-data azure-kusto-ingest; then
    log "INFO" "Python packages installed successfully."
else
    log "ERROR" "Failed to install Python packages."
fi

if [ ! -d "../.venv" ]; then
    log "INFO" "Creating and enabling Python virtual environment..."
    if python3 -m venv ../.venv && source ../.venv/bin/activate; then
        log "INFO" "Python virtual environment enabled."
    else
        log "ERROR" "Failed to create or enable Python virtual environment."
    fi
else
    log "INFO" "Python virtual environment already exists. Enabling..."
    if source ../.venv/bin/activate; then
        log "INFO" "Python virtual environment enabled."
    else
        log "ERROR" "Failed to enable Python virtual environment."
    fi
fi

log "INFO" "Which Python: $(which python)"

export ANSIBLE_PYTHON_INTERPRETER=$(which python3)