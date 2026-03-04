#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -euo pipefail

# Source the utils script for logging and utility functions
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/utils.sh"
source "${script_dir}/container_setup.sh"
set_output_context

PROJECT_ROOT="$(dirname "$script_dir")"

setup_environment() {
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
            *)
                log "ERROR" "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    cd "$PROJECT_ROOT"

    packages=("python3-pip" "sshpass" "python3-venv")
    install_packages "${packages[@]}"

    if ! command_exists az; then
		log "INFO" "Azure CLI not found. Installing Azure CLI..."
		if [[ "${DISTRO_FAMILY:-}" == "debian" ]]; then
			curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
		else
			curl -sL https://aka.ms/InstallAzureCli | bash
		fi
		if command_exists az; then
			log "INFO" "Azure CLI installed successfully."
		else
			log "ERROR" "Failed to install Azure CLI. Please install it manually."
			log "ERROR" "See https://learn.microsoft.com/cli/azure/install-azure-cli"
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

    if [[ "${DISTRO_FAMILY:-}" == "debian" ]]; then
        local venv_pkg="python${PYTHON_VERSION}-venv"
        if ! is_package_installed "$venv_pkg"; then
            log "INFO" "Installing version-specific venv package: $venv_pkg"
            if sudo ${PKG_INSTALL} "$venv_pkg"; then
                log "INFO" "$venv_pkg installed successfully."
            else
                log "WARN" "Could not install $venv_pkg. Virtual environment creation may fail."
            fi
        fi
    fi

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
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [command] [OPTIONS]

Commands:
  (none)                Install prerequisites and set up the
                        local environment for running tests
  container start       Build and start the SAP AUTOMATION QA service
  container update      Rebuild and restart the SAP AUTOMATION QA service
  container stop        Stop the SAP AUTOMATION QA service
  container remove      Remove the container, network, and volumes
  -h, --help            Show this help message

Setup options:
  --upgrade, -u              Remove the existing virtual environment and
                             recreate it from scratch (full upgrade).
  --python,  -p <executable> Use a specific Python interpreter for the
                             virtual environment (e.g. python3.11,
                             /usr/bin/python3.12). Defaults to python3.

Container options:
  --image, -i <URL>     Pull ACR image instead of building
  --username, -u <USER> ACR username
  --password, -p <PASS> ACR password

Telemetry / LAWS:
  Update vars.yaml before running setup.
  See docs/TELEMETRY_SETUP.md for details.

Examples:
  $(basename "$0")                          # Local Environment setup
  $(basename "$0") --upgrade                # destroy & recreate venv
  $(basename "$0") -p python3.11            # use Python 3.11
  $(basename "$0") -u -p /usr/bin/python3.12 # upgrade with Python 3.12
  $(basename "$0") container start          # Start service
  $(basename "$0") container start -i myacr.azurecr.io/sap-qa:latest
  $(basename "$0") container update         # Update service
  $(basename "$0") container stop
  $(basename "$0") container remove
EOF
}

run_container() {
    local command=""
    local acr_image=""
    local acr_username=""
    local acr_password=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --image|-i)   acr_image="$2";   shift 2 ;;
            --username|-u) acr_username="$2"; shift 2 ;;
            --password|-p) acr_password="$2"; shift 2 ;;
            -h|--help)    show_help; exit 0 ;;
            start|update|stop|remove)
                command="$1"; shift ;;
            *)
                log "ERROR" "Unknown container command: $1"
                show_help; exit 1 ;;
        esac
    done

    if [[ -z "$command" ]]; then
        log "ERROR" "Missing container command (start|update|stop|remove)."
        show_help
        exit 1
    fi

    [[ -n "$acr_username" ]] && export ACR_USERNAME="$acr_username"
    [[ -n "$acr_password" ]] && export ACR_PASSWORD="$acr_password"

    case "$command" in
        start)  container_start "$acr_image" ;;
        update) container_update "$acr_image" ;;
        stop)   container_stop ;;
        remove) container_remove ;;
    esac
}

main() {
    case "${1:-}" in
        container)
            shift
            run_container "$@"
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        --upgrade|-u|--python|-p|"")
            setup_environment "$@"
            ;;
        *)
            log "ERROR" "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
