# Architecture and Components

## Key Components

### Core Framework

- **Ansible Playbooks**: Automated test execution and system validation
- **Test Scripts**: Helper utilities for test case management
- **WORKSPACES**: System-specific configuration and credentials management
- **Reporting Engine**: Generates detailed HTML test reports



## Architecture

### High-Level Framework Structure

```mermaid
graph TB
    subgraph "Framework Structure"
        A[Test Framework Entry] --> B[Test Group Selection]
        B --> C[Test Case Execution]
        C --> D[Result Collection]
        D --> E[Report Generation]
    end

    subgraph "Test Components"
        F[Pre-Validation] --> G[Test Execution]
        G --> H[Post-Validation]
        H --> I[Telemetry]
    end

    subgraph "Result Processing"
        J[Log Collection] --> K[HTML Report]
        J --> L[Azure Log Analytics]
        J --> M[Azure Data Explorer]
    end

    C --> F
    I --> J
```

### Detailed Component Architecture

```mermaid
graph TB
    subgraph "Test Framework Core"
        A[Ansible Playbook] -->|Uses| B[Custom Modules]
        A -->|Includes| C[Common Tasks]
        A -->|References| D[Variables]
    end

    subgraph "Custom Modules"
        B -->|Cluster Status| E[get_cluster_status]
        B -->|Log Processing| F[log_parser]
        B -->|Package Info| G[get_package_list]
        B -->|Load Balancer| H[get_azure_lb]
        B -->|Constraints| I[location_constraints]
    end

    subgraph "Common Tasks"
        C -->|Setup| J[test-case-setup.yml]
        C -->|Pre-check| K[pre-validations.yml]
        C -->|Post-check| L[post-validations.yml]
        C -->|Reporting| M[post-telemetry-data.yml]
    end

    subgraph "Variables"
        D -->|Test Cases| N[input-api.yaml]
        D -->|Constants| O[cluster_constants.py]
        D -->|System| P[host vars]
    end

    subgraph "Output Processing"
        Q[Test Results] -->|Format| R[HTML Report]
        Q -->|Send| S[Azure Log Analytics]
        Q -->|Store| T[Azure Data Explorer]
    end

    A -->|Generates| Q
```

## Directory Structure
```
src/
├── module_utils/          # Shared utilities and constants
├── modules/              # Custom Ansible modules
├── roles/               # Test implementation roles
│   ├── ha_db_hana/     # HANA HA test cases
│   ├── ha_scs/         # SCS HA test cases
│   └── misc/           # Common tasks
├── templates/          # Report and configuration templates
└── vars/              # Framework configuration
```

## Test Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Framework
    participant PreValidation
    participant TestExecution
    participant PostValidation
    participant Reporting

    User->>Framework: Execute Test Suite
    Framework->>PreValidation: Run Pre-Validation Checks
    PreValidation-->>Framework: Validation Results
    
    alt Pre-Validation Successful
        Framework->>TestExecution: Execute Test Case
        TestExecution-->>Framework: Test Results
        Framework->>PostValidation: Run Post-Validation
        PostValidation-->>Framework: Validation Results
        Framework->>Reporting: Generate Reports
        Reporting-->>User: Test Reports
    else Pre-Validation Failed
        Framework->>Reporting: Generate Failure Report
        Reporting-->>User: Failure Report
    end
```