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
    log "INFO" "=== SAP QA Service Deployment ==="
    
    if [[ ! -d "$DEPLOY_DIR" ]]; then
        log "ERROR" "Deploy directory not found: $DEPLOY_DIR"
        exit 1
    fi
    
    check_file_exists "$DEPLOY_DIR/docker-compose.yml" "docker-compose.yml not found in $DEPLOY_DIR"
    check_file_exists "$DEPLOY_DIR/Dockerfile" "Dockerfile not found in $DEPLOY_DIR"

    log "INFO" "Creating data directories..."
    mkdir -p "$PROJECT_ROOT/data/jobs/history"

    log "INFO" "Stopping existing container (if any)..."
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" down 2>/dev/null || true
    
    log "INFO" "Building Docker image..."
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" build
    
    log "INFO" "Starting SAP QA service..."
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d
    
    log "INFO" "Waiting for service to be healthy..."
    sleep 5
    
    if docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps | grep -q "Up"; then
        log "INFO" "=== Deployment Successful ==="
        echo ""
        echo "SAP QA Service is running at: http://localhost:8000"
        echo "Health check: http://localhost:8000/health"
        echo ""
        echo "The service will auto-restart on system reboot."
        echo ""
        echo "Commands:"
        echo "  View logs:    docker compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
        echo "  Stop:         docker compose -f $DEPLOY_DIR/docker-compose.yml down"
        echo "  Restart:      docker compose -f $DEPLOY_DIR/docker-compose.yml restart"
        echo ""
        
        if command_exists curl; then
            curl -s http://localhost:8000/health && echo ""
        fi
    else
        log "ERROR" "=== Deployment Failed ==="
        log "ERROR" "Check logs: docker compose -f $DEPLOY_DIR/docker-compose.yml logs"
        exit 1
    fi
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
    local command="${1:-deploy}"
    
    case "$command" in
        deploy|start)
            ensure_docker
            deploy_container
            ;;
        stop)
            stop_container
            ;;
        restart)
            stop_container
            deploy_container
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
            echo "Usage: $0 {deploy|start|stop|restart|status|logs|install-docker}"
            echo ""
            echo "Commands:"
            echo "  deploy        Install Docker (if needed) and start the service"
            echo "  start         Same as deploy"
            echo "  stop          Stop the service"
            echo "  restart       Restart the service"
            echo "  status        Show service status"
            echo "  logs          Show service logs (follow mode)"
            echo "  install-docker  Install Docker only"
            exit 1
            ;;
    esac
}

main "$@"
