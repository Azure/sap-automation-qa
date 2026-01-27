#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Set color codes for output
set_output_context() {
		RED='\033[0;31m'
		GREEN='\033[0;32m'
		NC='\033[0m'
}

# Print logs with color based on severity.
# :param severity: The severity level of the log (e.g., "INFO", "WARN", "ERROR").
# :param message: The message to log.
log() {
    local severity=$1
    local message=$2
    local YELLOW='\033[0;33m'

    case "$severity" in
        ERROR)
            echo -e "${RED}[ERROR] $message${NC}"
            ;;
        WARN)
            echo -e "${YELLOW}[WARN] $message${NC}"
            ;;
        *)
            echo -e "${GREEN}[INFO] $message${NC}"
            ;;
    esac
}

# Check if a command exists.
# :param command: The command to check.
# :return: None. Exits with a non-zero status if the command does not exist.
command_exists() {
    command -v "$1" &> /dev/null
}


# Check if a file exists.
# :param file_path: The path to the file to check.
# :param error_message: The error message to display if the file does not exist.
# :return: None. Exits with a non-zero status if the file does not exist.
check_file_exists() {
    local file_path=$1
    local error_message=$2
    log "INFO" "Checking if file exists: $file_path"
    if [[ ! -f "$file_path" ]]; then
        log "ERROR" "Error: $error_message"
        exit 1
    fi
}

# Detect the Linux distribution
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_FAMILY=$ID_LIKE
    elif command_exists lsb_release; then
        DISTRO=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
    elif [[ -f /etc/redhat-release ]]; then
        DISTRO="rhel"
    elif [[ -f /etc/debian_version ]]; then
        DISTRO="debian"
    elif [[ -f /etc/SuSE-release ]]; then
        DISTRO="suse"
    else
        log "ERROR" "Cannot detect Linux distribution"
        exit 1
    fi
    case "$DISTRO" in
        ubuntu|debian)
            DISTRO_FAMILY="debian"
            ;;
        rhel|centos|fedora|rocky|almalinux)
            DISTRO_FAMILY="rhel"
            ;;
        opensuse*|sles|suse)
            DISTRO_FAMILY="suse"
            ;;
        *)
            if [[ -n "$DISTRO_FAMILY" ]]; then
                case "$DISTRO_FAMILY" in
                    *debian*)
                        DISTRO_FAMILY="debian"
                        ;;
                    *rhel*|*fedora*)
                        DISTRO_FAMILY="rhel"
                        ;;
                    *suse*)
                        DISTRO_FAMILY="suse"
                        ;;
                esac
            else
                log "ERROR" "Unsupported Linux distribution: $DISTRO"
                exit 1
            fi
            ;;
    esac

    log "INFO" "Detected distribution: $DISTRO (family: $DISTRO_FAMILY)"
}

# Get package manager commands based on distribution
get_package_manager_commands() {
    detect_distro

    case "$DISTRO_FAMILY" in
        debian)
            PKG_UPDATE="apt update -y"
            PKG_INSTALL="apt install -y"
            PKG_CHECK="dpkg -l"
            ;;
        rhel)
            if command_exists dnf; then
                PKG_UPDATE="dnf makecache"
                PKG_INSTALL="dnf install -y"
                PKG_CHECK="rpm -q"
            elif command_exists yum; then
                PKG_UPDATE="yum makecache"
                PKG_INSTALL="yum install -y"
                PKG_CHECK="rpm -q"
            else
                log "ERROR" "Neither dnf nor yum package manager found"
                exit 1
            fi
            ;;
        suse)
            PKG_UPDATE="zypper refresh"
            PKG_INSTALL="zypper install -y"
            PKG_CHECK="rpm -q"
            ;;
        *)
            log "ERROR" "Unsupported distribution family: $DISTRO_FAMILY"
            exit 1
            ;;
    esac
}

# Map generic package names to distribution-specific names
map_package_names() {
    local generic_packages=("$@")
    local mapped_packages=()
    for package in "${generic_packages[@]}"; do
        case "$package" in
            python3-pip)
                case "$DISTRO_FAMILY" in
                    debian) mapped_packages+=("python3-pip") ;;
                    rhel) mapped_packages+=("python3-pip") ;;
                    suse) mapped_packages+=("python3-pip") ;;
                esac
                ;;
            ansible)
                case "$DISTRO_FAMILY" in
                    debian) mapped_packages+=("ansible") ;;
                    rhel) mapped_packages+=("ansible-core") ;;
                    suse) mapped_packages+=("ansible") ;;
                esac
                ;;
            sshpass)
                case "$DISTRO_FAMILY" in
                    debian) mapped_packages+=("sshpass") ;;
                    rhel) mapped_packages+=("sshpass") ;;
                    suse)
												>&2 log "INFO" "Skipping sshpass installation on SUSE systems (not available in standard repositories)"
                        ;;
                esac
                ;;
            python3-venv)
                case "$DISTRO_FAMILY" in
                    debian) mapped_packages+=("python3-venv") ;;
                    rhel)
                        >&2 log "INFO" "Skipping python3-venv installation on Red Hat systems"
                        ;;
                    suse)
                        >&2 log "INFO" "Skipping python3-venv installation on SUSE systems"
                        ;;
                esac
                ;;
            *)
                mapped_packages+=("$package")
                ;;
        esac
    done

    echo "${mapped_packages[@]}"
}

# Check if a package is installed
is_package_installed() {
    local package=$1
    case "$DISTRO_FAMILY" in
        debian)
            dpkg -l "$package" &> /dev/null
            ;;
        rhel|suse)
            rpm -q "$package" &> /dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

# Install packages with distribution-specific package manager
# :param packages: Array of package names to install.
# :return: None. Exits with a non-zero status if installation fails.
install_packages() {
    local packages=("$@")
    local to_install=()
    get_package_manager_commands
    local mapped_packages
    read -ra mapped_packages <<< "$(map_package_names "${packages[@]}")"
    for package in "${mapped_packages[@]}"; do
        if ! command_exists "${package}" && ! is_package_installed "${package}"; then
            log "INFO" "$package is not installed. Adding to install list..."
            to_install+=("$package")
        else
            log "INFO" "$package is already installed or available."
        fi
    done
    if [ ${#to_install[@]} -ne 0 ]; then
        log "INFO" "Updating package cache and installing missing packages: ${to_install[*]}"
        log "INFO" "Updating package cache..."
        if ! sudo $PKG_UPDATE; then
            log "ERROR" "Failed to update package cache"
            exit 1
        fi
        log "INFO" "Installing packages: ${to_install[*]}"
        if sudo $PKG_INSTALL "${to_install[@]}"; then
            log "INFO" "Packages installed successfully."
        else
            log "ERROR" "Failed to install packages: ${to_install[*]}"
            exit 1
        fi
    else
        log "INFO" "All required packages are already installed."
    fi
}
