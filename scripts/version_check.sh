#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Version checking utility for SAP Automation QA Framework
# This script checks for newer versions available on GitHub

VERSION_CHECK_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_CHECK_PROJECT_ROOT="$(cd "$VERSION_CHECK_SCRIPT_DIR/.." && pwd)"
LOCAL_VERSION_FILE="${VERSION_CHECK_PROJECT_ROOT}/VERSION"
REMOTE_VERSION_URL="https://raw.githubusercontent.com/Azure/sap-automation-qa/refs/heads/main/VERSION"

# Compare two semantic versions (X.Y.Z format)
# :param version1: First version string (e.g., "1.2.3")
# :param version2: Second version string (e.g., "1.2.4")
# :return: 0 if equal, 1 if first > second, 2 if first < second
compare_versions() {
    local version1=$1
    local version2=$2

    version1=$(echo "$version1" | tr -d '[:space:]')
    version2=$(echo "$version2" | tr -d '[:space:]')

    if [[ "$version1" == "$version2" ]]; then
        return 0
    fi

    local IFS='.'
    read -ra v1_parts <<< "$version1"
    read -ra v2_parts <<< "$version2"

    for i in 0 1 2; do
        local v1_num=${v1_parts[$i]:-0}
        local v2_num=${v2_parts[$i]:-0}

        if (( v1_num > v2_num )); then
            return 1
        elif (( v1_num < v2_num )); then
            return 2
        fi
    done

    return 0
}

# Check for newer version available on GitHub
# Shows a red warning if a newer version is available and waits 20 seconds
# :return: None. Continues after countdown if update is available.
check_version_update() {
    local local_version
    local remote_version
    if [[ -f "$LOCAL_VERSION_FILE" ]]; then
        local_version=$(cat "$LOCAL_VERSION_FILE" | tr -d '[:space:]')
    else
        log "WARN" "Local VERSION file not found at $LOCAL_VERSION_FILE"
        return
    fi
    remote_version=$(curl -s --connect-timeout 5 --max-time 10 "$REMOTE_VERSION_URL" 2>/dev/null | tr -d '[:space:]')
    if [[ -z "$remote_version" ]]; then
        log "WARN" "Could not fetch remote version from GitHub"
        return
    fi

    log "INFO" "Local version: $local_version"
    log "INFO" "Remote version: $remote_version"

    local result
    compare_versions "$local_version" "$remote_version" && result=0 || result=$?

    if [[ $result -eq 2 ]]; then
        echo ""
        echo -e "\033[1;31m╔════════════════════════════════════════════════════════════════════════════╗\033[0m"
        echo -e "\033[1;31m║                            UPDATE AVAILABLE                                ║\033[0m"
        echo -e "\033[1;31m╠════════════════════════════════════════════════════════════════════════════╣\033[0m"
        echo -e "\033[1;31m║  A newer version of SAP Automation QA Framework is available!              ║\033[0m"
        echo -e "\033[1;31m║                                                                            ║\033[0m"
        echo -e "\033[1;31m║  Current version:  $local_version                                                   ║\033[0m"
        echo -e "\033[1;31m║  Latest version:   $remote_version                                                   ║\033[0m"
        echo -e "\033[1;31m║                                                                            ║\033[0m"
        echo -e "\033[1;31m║  Press Ctrl+C within 20 seconds to exit and update.                        ║\033[0m"
        echo -e "\033[1;31m║  Otherwise, the process will continue with the current version.            ║\033[0m"
        echo -e "\033[1;31m╚════════════════════════════════════════════════════════════════════════════╝\033[0m"
        echo ""
        
        for i in {20..1}; do
            echo -ne "\033[1;33mContinuing in $i seconds... (Press Ctrl+C to exit and update)\033[0m\r"
            sleep 1
        done
        echo -e "\033[1;32mProceeding with current version ($local_version)...                              \033[0m"
        echo ""
    elif [[ $result -eq 0 ]]; then
        log "INFO" "You are running the latest version ($local_version)"
    else
        log "INFO" "You are running a newer version ($local_version) than the released version ($remote_version)"
    fi
}
