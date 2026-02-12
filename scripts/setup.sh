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

# Usage / help
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --upgrade, -u              Remove the existing virtual environment and
                             recreate it from scratch (full upgrade).
  --python,  -p <executable> Use a specific Python interpreter for the
                             virtual environment (e.g. python3.11,
                             /usr/bin/python3.12). Defaults to python3.
  --help,    -h              Show this help message and exit.

Examples:
  $(basename "$0")                          # incremental setup
  $(basename "$0") --upgrade                # destroy & recreate venv
  $(basename "$0") -p python3.11            # use Python 3.11
  $(basename "$0") -u -p /usr/bin/python3.12 # upgrade with Python 3.12
EOF
    exit 0
}

# Parse arguments
UPGRADE=false
PYTHON_BIN="python3"   # default interpreter

while [[ $# -gt 0 ]]; do
    case "$1" in
        --upgrade|-u)
            UPGRADE=true
            shift
            ;;
        --python|-p)
            if [[ -z "${2:-}" ]]; then
                log "ERROR" "--python requires a value (e.g. python3.11 or /usr/bin/python3.12)."
                exit 1
            fi
            PYTHON_BIN="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            log "ERROR" "Unknown option: $1"
            usage
            ;;
    esac
done

packages=("python3-pip" "sshpass" "python3-venv")
install_packages "${packages[@]}"

# Install az cli if not present
if ! command_exists az; then
		log "INFO" "Azure CLI not found. Installing Azure CLI..."
		curl -L https://aka.ms/InstallAzureCli | bash
		if command_exists az; then
				log "INFO" "Azure CLI installed successfully."
		else
				log "ERROR" "Failed to install Azure CLI. Please install it manually."
				exit 1
		fi
fi

# Resolve & validate the requested Python interpreter
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    log "ERROR" "Python interpreter '$PYTHON_BIN' not found. Please install it or provide a valid path."
    exit 1
fi

PYTHON_BIN="$(command -v "$PYTHON_BIN")"   # resolve to absolute path
PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "INFO" "Using Python interpreter: $PYTHON_BIN (Python $PYTHON_VERSION)"

# Enforce minimum Python 3.10
MINOR=${PYTHON_VERSION#3.}
if [[ "${PYTHON_VERSION%%.*}" -lt 3 ]] || [[ "$MINOR" -lt 10 ]]; then
    log "ERROR" "Python >= 3.10 is required. Detected $PYTHON_VERSION at $PYTHON_BIN."
    exit 1
fi


# Upgrade: tear down existing venv so it is rebuilt from scratch
if [[ "$UPGRADE" == true ]]; then
    if [[ -d ".venv" ]]; then
        log "INFO" "Upgrade requested — removing existing virtual environment..."
        # Deactivate if we are inside the venv (ignore errors when not active)
        deactivate 2>/dev/null || true
        rm -rf .venv
        log "INFO" "Existing virtual environment removed."
    else
        log "INFO" "Upgrade requested but no existing virtual environment found. Creating fresh."
    fi
fi

# Create virtual environment if it doesn't exist
if [[ ! -d ".venv" ]]; then
    log "INFO" "Creating Python virtual environment with $PYTHON_BIN ..."
    if "$PYTHON_BIN" -m venv .venv; then
        log "INFO" "Python virtual environment created (Python $PYTHON_VERSION)."
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
if pip install -r requirements.in; then
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
