#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/utils.sh"
set_output_context

PROJECT_ROOT="$(dirname "$script_dir")"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

# Check and install Docker if needed
ensure_docker() {
    if ! command_exists docker; then
        log "INFO" "Docker not found. Installing..."
        install_docker
    else
        log "INFO" "Docker is already installed."
    fi

    if ! docker compose version &> /dev/null; then
        log "ERROR" "Docker Compose plugin not available."
        log "INFO" "Attempting to install Docker Compose plugin..."
        install_docker
    fi

    if ! docker info &> /dev/null 2>&1; then
        log "INFO" "Starting Docker daemon..."
        if command_exists systemctl && systemctl is-system-running &>/dev/null; then
            sudo systemctl start docker
        else
            sudo service docker start
        fi
    fi

    if command_exists systemctl && systemctl is-system-running &>/dev/null; then
        log "INFO" "Enabling Docker to start on system boot..."
        sudo systemctl enable docker 2>/dev/null || true
    fi
}

# Build and start the container
deploy_container() {
    local acr_image="${1:-}"
    
    log "INFO" "=== SAP QA Service Deployment ==="
    
    if [[ ! -d "$DEPLOY_DIR" ]]; then
        log "ERROR" "Deploy directory not found: $DEPLOY_DIR"
        exit 1
    fi
    
    check_file_exists "$DEPLOY_DIR/docker-compose.yml" "docker-compose.yml not found in $DEPLOY_DIR"

    log "INFO" "Creating data directories..."
    mkdir -p "$PROJECT_ROOT/data/jobs/history"

    log "INFO" "Stopping existing container (if any)..."
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" down 2>/dev/null || true
    
    if [[ -n "$acr_image" ]]; then
        log "INFO" "Pulling image from ACR: $acr_image"
        pull_from_acr "$acr_image"
    else
        check_file_exists "$DEPLOY_DIR/Dockerfile" "Dockerfile not found in $DEPLOY_DIR"
        log "INFO" "Building Docker image locally..."
        docker compose -f "$DEPLOY_DIR/docker-compose.yml" build
    fi
    
    log "INFO" "Starting SAP QA service..."
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d
    
    log "INFO" "Waiting for service to be healthy..."
    sleep 5
    
    if docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps | grep -q "Up"; then
        log "INFO" "=== Deployment Successful ==="
        echo ""
        echo "SAP QA Service is running at: http://localhost:8000"
        echo "Health check: http://localhost:8000/healthz"
        echo ""
        echo "The service will auto-restart on system reboot."
        echo ""
        echo "Commands:"
        echo "  View logs:    docker compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
        echo "  Stop:         docker compose -f $DEPLOY_DIR/docker-compose.yml down"
        echo "  Restart:      docker compose -f $DEPLOY_DIR/docker-compose.yml restart"
        echo ""
        
        if command_exists curl; then
            curl -s http://localhost:8000/healthz && echo ""
        fi
    else
        log "ERROR" "=== Deployment Failed ==="
        log "ERROR" "Check logs: docker compose -f $DEPLOY_DIR/docker-compose.yml logs"
        exit 1
    fi
}

# Pull image from ACR and update docker-compose to use it
pull_from_acr() {
    local acr_image="$1"
    local acr_name
    
    # Extract ACR name from image (e.g., myacr.azurecr.io/image:tag -> myacr)
    acr_name=$(echo "$acr_image" | cut -d'.' -f1)
    
    log "INFO" "Logging into ACR: $acr_name"
    if ! az acr login --name "$acr_name" 2>/dev/null; then
        log "WARN" "az acr login failed, trying docker login..."
        if [[ -z "${ACR_USERNAME:-}" ]] || [[ -z "${ACR_PASSWORD:-}" ]]; then
            log "ERROR" "ACR login failed. Either run 'az login' first or set ACR_USERNAME and ACR_PASSWORD"
            exit 1
        fi
        echo "$ACR_PASSWORD" | docker login "${acr_name}.azurecr.io" -u "$ACR_USERNAME" --password-stdin
    fi
    
    log "INFO" "Pulling image: $acr_image"
    docker pull "$acr_image"
    
    # Tag the pulled image for docker-compose
    docker tag "$acr_image" "sap-automation-qa:latest"
    log "INFO" "Image tagged as sap-automation-qa:latest"
}

# Stop the container
stop_container() {
    log "INFO" "Stopping SAP QA service..."
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" down
    log "INFO" "Service stopped."
}

# Show container status
status_container() {
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps
}

# Show container logs
logs_container() {
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" logs -f
}

# Main entry point
main() {
    local command=""
    local acr_image=""
    local acr_username=""
    local acr_password=""
    
    # Check for --help anywhere in arguments first
    for arg in "$@"; do
        if [[ "$arg" == "--help" ]] || [[ "$arg" == "-h" ]]; then
            show_help
            exit 0
        fi
    done
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --image|-i)
                acr_image="$2"
                shift 2
                ;;
            --username|-u)
                acr_username="$2"
                shift 2
                ;;
            --password|-p)
                acr_password="$2"
                shift 2
                ;;
            deploy|start|stop|restart|status|logs|install-docker)
                command="$1"
                shift
                ;;
            *)
                # Legacy positional argument support
                if [[ -z "$command" ]]; then
                    command="$1"
                elif [[ -z "$acr_image" ]]; then
                    acr_image="$1"
                fi
                shift
                ;;
        esac
    done
    
    command="${command:-deploy}"
    
    # Export credentials if provided
    [[ -n "$acr_username" ]] && export ACR_USERNAME="$acr_username"
    [[ -n "$acr_password" ]] && export ACR_PASSWORD="$acr_password"
    
    case "$command" in
        deploy|start)
            ensure_docker
            deploy_container "$acr_image"
            ;;
        stop)
            stop_container
            ;;
        restart)
            stop_container
            deploy_container "$acr_image"
            ;;
        status)
            status_container
            ;;
        logs)
            logs_container
            ;;
        install-docker)
            install_docker
            ;;
        *)
            show_help
            exit 1
            ;;
    esac
}

show_help() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  deploy        Install Docker (if needed) and start the service"
    echo "  start         Same as deploy"
    echo "  stop          Stop the service"
    echo "  restart       Restart the service"
    echo "  status        Show service status"
    echo "  logs          Show service logs (follow mode)"
    echo "  install-docker  Install Docker only"
    echo ""
    echo "Options:"
    echo "  -i, --image <IMAGE>      ACR image (e.g., myacr.azurecr.io/sap-automation-qa:latest)"
    echo "  -u, --username <USER>    ACR username"
    echo "  -p, --password <PASS>    ACR password"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy                                              # Build locally"
    echo "  $0 deploy -i myacr.azurecr.io/sap-automation-qa:latest # Pull from ACR (uses az login)"
    echo "  $0 deploy -i myacr.azurecr.io/sap-automation-qa:latest -u myuser -p mypass"
    echo ""
    echo "Environment variables (alternative to options):"
    echo "  ACR_USERNAME    ACR username"
    echo "  ACR_PASSWORD    ACR password"
}

main "$@"
