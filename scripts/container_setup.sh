#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

_CONTAINER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CONTAINER_PROJECT_ROOT="$(dirname "$_CONTAINER_SCRIPT_DIR")"
_CONTAINER_DEPLOY_DIR="$_CONTAINER_PROJECT_ROOT/deploy"
_CONTAINER_ENV_FILE="$_CONTAINER_DEPLOY_DIR/.env"
_CONTAINER_PORT=8000
_CONTAINER_HEALTH_RETRIES=15
_CONTAINER_HEALTH_INTERVAL=2

# Ensure Docker and Docker Compose are available and running.
_ensure_docker() {
    if ! command_exists docker; then
        log "INFO" "Docker not found. Installing..."
        install_docker
    else
        log "INFO" "Docker is already installed."
    fi

    if ! docker compose version &>/dev/null; then
        log "ERROR" "Docker Compose plugin not available."
        log "INFO" "Attempting to install Docker Compose plugin..."
        install_docker
    fi

    if ! docker info &>/dev/null 2>&1; then
        log "INFO" "Starting Docker daemon..."
        if command_exists systemctl \
            && systemctl is-system-running &>/dev/null; then
            sudo systemctl start docker
            sudo systemctl enable docker 2>/dev/null || true
        else
            sudo service docker start
        fi
    fi
}

# Wait for the health endpoint to return 200.
_wait_for_healthy() {
    log "INFO" "Waiting for service to be healthy..."
    local attempt=0

    while [[ $attempt -lt $_CONTAINER_HEALTH_RETRIES ]]; do
        attempt=$((attempt + 1))
        if command_exists curl; then
            local code
            code=$(curl -s -o /dev/null -w "%{http_code}" \
                "http://localhost:${_CONTAINER_PORT}/healthz" \
                2>/dev/null || echo "000")
            if [[ "$code" == "200" ]]; then
                log "INFO" "=== Service is healthy ==="
                echo ""
                echo "SAP QA: http://localhost:${_CONTAINER_PORT}"
                echo "API docs:         http://localhost:${_CONTAINER_PORT}/docs"
                echo ""
                return 0
            fi
        fi
        log "INFO" \
            "Health check attempt $attempt/$_CONTAINER_HEALTH_RETRIES..."
        sleep "$_CONTAINER_HEALTH_INTERVAL"
    done

    log "ERROR" "Service did not become healthy in" \
        "$((_CONTAINER_HEALTH_RETRIES * _CONTAINER_HEALTH_INTERVAL))s."
    log "ERROR" "Check logs: docker compose" \
        "-f $_CONTAINER_DEPLOY_DIR/docker-compose.yml logs --tail=50"
    return 1
}

# Pull an image from ACR and tag it for docker-compose.
_pull_from_acr() {
    local acr_image="$1"
    local acr_name
    acr_name=$(echo "$acr_image" | cut -d'.' -f1)

    log "INFO" "Logging into ACR: $acr_name"
    if ! az acr login --name "$acr_name" 2>/dev/null; then
        log "WARN" "az acr login failed, trying docker login..."
        if [[ -z "${ACR_USERNAME:-}" ]] \
            || [[ -z "${ACR_PASSWORD:-}" ]]; then
            log "ERROR" "ACR login failed. Run 'az login' first" \
                "or set ACR_USERNAME and ACR_PASSWORD."
            exit 1
        fi
        echo "$ACR_PASSWORD" | docker login \
            "${acr_name}.azurecr.io" -u "$ACR_USERNAME" \
            --password-stdin
    fi

    log "INFO" "Pulling image: $acr_image"
    docker pull "$acr_image"
    docker tag "$acr_image" "sap-automation-qa:latest"
    log "INFO" "Image tagged as sap-automation-qa:latest"
}

# Build (or pull) and start the container.
# :param acr_image: Optional ACR image reference.  If empty, builds locally.
container_start() {
    local acr_image="${1:-}"

    log "INFO" "=== Starting SAP QA ==="

    _ensure_docker

    if [[ ! -d "$_CONTAINER_DEPLOY_DIR" ]]; then
        log "ERROR" "Deploy directory not found: $_CONTAINER_DEPLOY_DIR"
        exit 1
    fi
    check_file_exists "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" \
        "docker-compose.yml not found in $_CONTAINER_DEPLOY_DIR"

    mkdir -p "$_CONTAINER_PROJECT_ROOT/data/jobs/history"
    mkdir -p "$_CONTAINER_PROJECT_ROOT/data/logs"

    # Load .env if present
    if [[ -f "$_CONTAINER_ENV_FILE" ]]; then
        log "INFO" "Loading environment from $_CONTAINER_ENV_FILE"
        set -a
        source "$_CONTAINER_ENV_FILE"
        set +a
    fi

    if [[ -n "$acr_image" ]]; then
        _pull_from_acr "$acr_image"
    fi

    log "INFO" "Starting container..."
    docker compose -f "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" \
        up -d --build

    _wait_for_healthy
}

# Rebuild the image and restart the container (zero-downtime update).
# :param acr_image: Optional ACR image reference.  If empty, rebuilds locally.
container_update() {
    local acr_image="${1:-}"

    log "INFO" "=== Updating SAP QA ==="

    _ensure_docker

    check_file_exists "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" \
        "docker-compose.yml not found in $_CONTAINER_DEPLOY_DIR"

    # Load .env if present
    if [[ -f "$_CONTAINER_ENV_FILE" ]]; then
        log "INFO" "Loading environment from $_CONTAINER_ENV_FILE"
        set -a
        source "$_CONTAINER_ENV_FILE"
        set +a
    fi

    if [[ -n "$acr_image" ]]; then
        _pull_from_acr "$acr_image"
    else
        check_file_exists "$_CONTAINER_DEPLOY_DIR/Dockerfile" \
            "Dockerfile not found in $_CONTAINER_DEPLOY_DIR"
        log "INFO" "Rebuilding Docker image..."
        docker compose -f "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" \
            build --pull
    fi

    log "INFO" "Restarting container with updated image..."
    docker compose -f "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" up -d

    _wait_for_healthy
}

# Stop the container without removing it.
container_stop() {
    log "INFO" "=== Stopping SAP QA ==="
    docker compose -f "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" stop
    log "INFO" "Service stopped."
}

# Remove the container, network, and volumes.
container_remove() {
    log "INFO" "=== Removing SAP QA ==="
    docker compose -f "$_CONTAINER_DEPLOY_DIR/docker-compose.yml" down -v
    log "INFO" "Service removed."
}
