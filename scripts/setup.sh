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
    cd "$PROJECT_ROOT"

    packages=("python3-pip" "sshpass" "python3-venv")
    install_packages "${packages[@]}"

    if ! command_exists az; then
        log "INFO" "Azure CLI not found. Installing Azure CLI..."
        curl -L https://aka.ms/InstallAzureCli | bash
        if command_exists az; then
            log "INFO" "Azure CLI installed successfully."
        else
            log "ERROR" \
                "Failed to install Azure CLI. Install it manually."
            exit 1
        fi
    fi

    if ! command_exists python3; then
        log "ERROR" \
            "Python3 is not available. Install Python3 manually."
        exit 1
    fi

    if [[ ! -d ".venv" ]]; then
        log "INFO" "Creating Python virtual environment..."
        if python3 -m venv .venv; then
            log "INFO" "Python virtual environment created."
        else
            log "ERROR" "Failed to create Python virtual environment."
            exit 1
        fi
    fi

    log "INFO" "Activating Python virtual environment..."
    if source .venv/bin/activate; then
        log "INFO" "Python virtual environment activated."
    else
        log "ERROR" "Failed to activate Python virtual environment."
        exit 1
    fi

    log "INFO" "Installing Python packages..."
    pip install --upgrade pip || log "ERROR" "Failed to upgrade pip."
    if pip install -r requirements.in; then
        log "INFO" "Python packages installed successfully."
    else
        log "ERROR" "Failed to install Python packages."
    fi

    log "INFO" "Which Python: $(which python)"

    export ANSIBLE_HOST_KEY_CHECKING=False
    export ANSIBLE_PYTHON_INTERPRETER=$(which python3)

    log "INFO" "Setup completed successfully!"
    log "INFO" "Virtual environment: $(pwd)/.venv"
    log "INFO" \
        "To activate manually: source .venv/bin/activate"
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  (none)                Install prerequisites and set up the"
    echo "                        local environment for running tests"
    echo "  container start       Build and start the SAP AUTOMATION QA service"
    echo "  container update      Rebuild and restart the SAP AUTOMATION QA service"
    echo "  container stop        Stop the SAP AUTOMATION QA service"
    echo "  container remove      Remove the container, network, and volumes"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Container options:"
    echo "  --image, -i <URL>     Pull ACR image instead of building"
    echo "  --username, -u <USER> ACR username"
    echo "  --password, -p <PASS> ACR password"
    echo ""
    echo "Examples:"
    echo "  $0                            # Local Environment setup"
    echo "  $0 container start            # Start service"
    echo "  $0 container start -i myacr.azurecr.io/sap-qa:latest"
    echo "  $0 container update           # Update service"
    echo "  $0 container stop"
    echo "  $0 container remove"
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
        "")
            setup_environment
            ;;
        *)
            log "ERROR" "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
