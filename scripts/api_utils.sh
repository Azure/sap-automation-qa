#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# CLI wrapper for the SAP QA Service REST API.
# Sourced by sap_automation_qa.sh — not executed directly.

_API_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_API_BASE_URL="${SAP_QA_API_URL:-http://localhost:8000}"
_API_V1="${_API_BASE_URL}/api/v1"

# Make an API request and handle errors.
# :param method: HTTP method (GET, POST, PATCH, DELETE).
# :param path: API path (e.g., /api/v1/jobs).
# :param data: Optional JSON body.
# :return: Response body on success; exits on failure.
_api_request() {
    local method="$1"
    local path="$2"
    local data="${3:-}"

    local curl_args=(-s -w "\n%{http_code}" -X "$method")
    curl_args+=(-H "Content-Type: application/json")

    if [[ -n "$data" ]]; then
        curl_args+=(-d "$data")
    fi

    local response
    response=$(curl "${curl_args[@]}" "${_API_BASE_URL}${path}" 2>&1)
    local curl_exit=$?

    if [[ $curl_exit -ne 0 ]]; then
        log "ERROR" "Failed to connect to SAP QA Service at ${_API_BASE_URL}" >&2
        log "ERROR" "Is the container running? Try: ./scripts/setup.sh container start" >&2
        exit 1
    fi

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | sed '$d')

    if [[ "$http_code" -ge 400 ]]; then
        local detail
        detail=$(echo "$body" | python3 -c \
            "import sys,json; print(json.load(sys.stdin).get('detail','Unknown error'))" \
            2>/dev/null || echo "$body")
        log "ERROR" "API error ($http_code): $detail" >&2
        exit 1
    fi

    echo "$body"
}

# Format JSON output as readable key-value pairs.
# Objects: "  Key : Value" per line, nulls/empty skipped.
# Arrays inside objects: joined with ", ".
# Top-level arrays: each item separated by a blank line.
# Wrapper keys like "jobs", "schedules", "workspaces" are unwrapped.
_format_json() {
    if ! command -v jq &>/dev/null; then
        python3 -m json.tool 2>/dev/null || cat
        return
    fi
    jq -r '
def fmt_obj:
  to_entries
  | map(select(.value != null and .value != "" and .value != []))
  | (map(.key | length) | max // 0) as $w
  | map(
      "  \(.key | . + " " * ($w - length)) : "
      + (if (.value | type) == "array" then
           (.value | map(tostring) | join(", "))
         elif (.value | type) == "object" then
           (.value | tojson)
         else
           (.value | tostring)
         end)
    )
  | join("\n");

def unwrap:
  if type == "object" then
    if has("jobs")      then .jobs
    elif has("schedules")  then .schedules
    elif has("workspaces") then .workspaces
    else .
    end
  else .
  end;

unwrap
| if type == "array" then
    map(fmt_obj) | join("\n\n")
  else
    fmt_obj
  end
'
}

api_health() {
    log "INFO" "Checking service health..."
    _api_request GET /healthz | _format_json
}

# List or get workspaces.
# :param workspace_id: Optional workspace ID for details.
api_workspace() {
    local workspace_id=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)       workspace_id="$2"; shift 2 ;;
            -h|--help)  _workspace_help; return 0 ;;
            *)          log "ERROR" "Unknown option: $1"; _workspace_help; exit 1 ;;
        esac
    done

    if [[ -n "$workspace_id" ]]; then
        log "INFO" "Getting workspace: $workspace_id"
        _api_request GET "/api/v1/workspaces/$workspace_id" | _format_json
    else
        log "INFO" "Listing workspaces..."
        _api_request GET /api/v1/workspaces | _format_json
    fi
}

_workspace_help() {
    cat << 'EOF'
Usage: sap_automation_qa.sh workspace [OPTIONS]

Options:
  --id <ID>       Get details for a specific workspace
  -h, --help      Show this help message

Examples:
  sap_automation_qa.sh workspace                            # List all
  sap_automation_qa.sh workspace --id DEV-WEEU-SAP01-X00    # Get details
EOF
}

# Manage jobs: create, list, get, log, cancel.
# :param subcommand: One of create, list, get, log, events, cancel.
api_job() {
    local action="${1:-list}"
    shift 2>/dev/null || true

    case "$action" in
        create)  _job_create "$@" ;;
        list)    _job_list "$@" ;;
        get)     _job_get "$@" ;;
        log)     _job_log "$@" ;;
        events)  _job_events "$@" ;;
        cancel)  _job_cancel "$@" ;;
        -h|--help) _job_help; return 0 ;;
        *)       log "ERROR" "Unknown job action: $action"; _job_help; exit 1 ;;
    esac
}

_job_create() {
    local workspace_id="" test_group="" test_ids=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --workspace)    workspace_id="$2"; shift 2 ;;
            --test-group)   test_group="$2"; shift 2 ;;
            --test-id|--test-ids) test_ids="$2"; shift 2 ;;
            *)              log "ERROR" "Unknown option: $1"; _job_help; exit 1 ;;
        esac
    done

    if [[ -z "$workspace_id" || -z "$test_group" ]]; then
        log "ERROR" "--workspace and --test-group are required"
        _job_help
        exit 1
    fi

    local payload="{\"workspace_id\":\"$workspace_id\",\"test_group\":\"$test_group\""
    if [[ -n "$test_ids" ]]; then
        # Convert comma-separated to JSON array
        local ids_json
        ids_json=$(echo "$test_ids" | python3 -c \
            "import sys,json; print(json.dumps(sys.stdin.read().strip().split(',')))")
        payload+=",\"test_ids\":$ids_json"
    fi
    payload+="}"

    log "INFO" "Creating job: workspace=$workspace_id test_group=$test_group"
    _api_request POST /api/v1/jobs "$payload" | _format_json
}

_job_list() {
    local workspace_id="" status="" active_only=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --workspace)    workspace_id="$2"; shift 2 ;;
            --status)       status="$2"; shift 2 ;;
            --active)       active_only="true"; shift ;;
            *)              log "ERROR" "Unknown option: $1"; _job_help; exit 1 ;;
        esac
    done

    local query=""
    [[ -n "$workspace_id" ]] && query+="workspace_id=$workspace_id&"
    [[ -n "$status" ]] && query+="status=$status&"
    [[ -n "$active_only" ]] && query+="active_only=true&"
    query="${query%&}"

    local path="/api/v1/jobs"
    [[ -n "$query" ]] && path+="?$query"

    log "INFO" "Listing jobs..."
    _api_request GET "$path" | _format_json
}

_job_get() {
    local job_id=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)   job_id="$2"; shift 2 ;;
            *)      job_id="$1"; shift ;;
        esac
    done

    if [[ -z "$job_id" ]]; then
        log "ERROR" "Job ID is required"
        exit 1
    fi

    _api_request GET "/api/v1/jobs/$job_id" | _format_json
}

_job_log() {
    local job_id="" tail=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)     job_id="$2"; shift 2 ;;
            --tail)   tail="$2"; shift 2 ;;
            *)        job_id="$1"; shift ;;
        esac
    done

    if [[ -z "$job_id" ]]; then
        log "ERROR" "Job ID is required"
        exit 1
    fi

    local path="/api/v1/jobs/$job_id/log"
    [[ -n "$tail" ]] && path+="?tail=$tail"

    _api_request GET "$path"
}

_job_events() {
    local job_id=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)   job_id="$2"; shift 2 ;;
            *)      job_id="$1"; shift ;;
        esac
    done

    if [[ -z "$job_id" ]]; then
        log "ERROR" "Job ID is required"
        exit 1
    fi

    _api_request GET "/api/v1/jobs/$job_id/events" | _format_json
}

_job_cancel() {
    local job_id="" reason="cancelled via CLI"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)       job_id="$2"; shift 2 ;;
            --reason)   reason="$2"; shift 2 ;;
            *)          job_id="$1"; shift ;;
        esac
    done

    if [[ -z "$job_id" ]]; then
        log "ERROR" "Job ID is required"
        exit 1
    fi

    log "INFO" "Cancelling job: $job_id"
    _api_request POST "/api/v1/jobs/$job_id/cancel" \
        "{\"reason\":\"$reason\"}" | _format_json
}

_job_help() {
    cat << 'EOF'
Usage: sap_automation_qa.sh job <action> [OPTIONS]

Actions:
  create    Create and run a new job
  list      List jobs (default)
  get       Get job details
  log       Get Ansible output for a job
  events    Get lifecycle events for a job
  cancel    Cancel a running job

Create options:
  --workspace <ID>         Workspace ID (required)
  --test-group <GROUP>     Test group (required): DatabaseHighAvailability, CentralServicesHighAvailability, ConfigurationChecks
  --test-ids <IDS>         Comma-separated test case IDs (optional)

List options:
  --workspace <ID>         Filter by workspace
  --status <STATUS>        Filter by status: pending, running, completed, failed, cancelled
  --active                 Show only active jobs

Get / Log / Events / Cancel:
  --id <JOB_ID>            Job ID (or pass as positional argument)

Log options:
  --tail <N>               Show only last N lines

Cancel options:
  --reason <TEXT>           Cancellation reason

Examples:
  sap_automation_qa.sh job create --workspace DEV-WEEU-SAP01-X00 --test-group DatabaseHighAvailability
  sap_automation_qa.sh job list --status running
  sap_automation_qa.sh job log --id <job-id> --tail 50
  sap_automation_qa.sh job cancel --id <job-id> --reason "maintenance"
EOF
}

# Manage schedules: create, list, get, update, delete, trigger, jobs.
# :param subcommand: One of create, list, get, update, delete, trigger, jobs.
api_schedule() {
    local action="${1:-list}"
    shift 2>/dev/null || true

    case "$action" in
        create)  _schedule_create "$@" ;;
        list)    _schedule_list "$@" ;;
        get)     _schedule_get "$@" ;;
        update)  _schedule_update "$@" ;;
        delete)  _schedule_delete "$@" ;;
        trigger) _schedule_trigger "$@" ;;
        jobs)    _schedule_jobs "$@" ;;
        -h|--help) _schedule_help; return 0 ;;
        *)       log "ERROR" "Unknown schedule action: $action"; _schedule_help; exit 1 ;;
    esac
}

_schedule_create() {
    local name="" cron="" timezone="UTC" workspace_ids="" test_group=""
    local enabled="true" description="" test_ids=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --name)         name="$2"; shift 2 ;;
            --cron)         cron="$2"; shift 2 ;;
            --timezone)     timezone="$2"; shift 2 ;;
            --workspaces)   workspace_ids="$2"; shift 2 ;;
            --test-group)   test_group="$2"; shift 2 ;;
            --test-id|--test-ids) test_ids="$2"; shift 2 ;;
            --description)  description="$2"; shift 2 ;;
            --disabled)     enabled="false"; shift ;;
            *)              log "ERROR" "Unknown option: $1"; _schedule_help; exit 1 ;;
        esac
    done

    if [[ -z "$name" || -z "$cron" || -z "$workspace_ids" ]]; then
        log "ERROR" "--name, --cron, and --workspaces are required"
        _schedule_help
        exit 1
    fi

    # Convert comma-separated workspace IDs to JSON array
    local ws_json
    ws_json=$(echo "$workspace_ids" | python3 -c \
        "import sys,json; print(json.dumps(sys.stdin.read().strip().split(',')))")

    local payload="{\"name\":\"$name\",\"cron_expression\":\"$cron\""
    payload+=",\"timezone\":\"$timezone\",\"workspace_ids\":$ws_json"
    payload+=",\"enabled\":$enabled"
    [[ -n "$test_group" ]] && payload+=",\"test_group\":\"$test_group\""
    [[ -n "$description" ]] && payload+=",\"description\":\"$description\""
    if [[ -n "$test_ids" ]]; then
        local ids_json
        ids_json=$(echo "$test_ids" | python3 -c \
            "import sys,json; print(json.dumps(sys.stdin.read().strip().split(',')))")
        payload+=",\"test_ids\":$ids_json"
    fi
    payload+="}"

    log "INFO" "Creating schedule: $name"
    _api_request POST /api/v1/schedules "$payload" | _format_json
}

_schedule_list() {
    local enabled_only=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --enabled)  enabled_only="true"; shift ;;
            *)          log "ERROR" "Unknown option: $1"; _schedule_help; exit 1 ;;
        esac
    done

    local path="/api/v1/schedules"
    [[ -n "$enabled_only" ]] && path+="?enabled_only=true"

    log "INFO" "Listing schedules..."
    _api_request GET "$path" | _format_json
}

_schedule_get() {
    local schedule_id=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)   schedule_id="$2"; shift 2 ;;
            *)      schedule_id="$1"; shift ;;
        esac
    done

    if [[ -z "$schedule_id" ]]; then
        log "ERROR" "Schedule ID is required"
        exit 1
    fi

    _api_request GET "/api/v1/schedules/$schedule_id" | _format_json
}

_schedule_update() {
    local schedule_id="" payload="{"
    local has_fields=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)           schedule_id="$2"; shift 2 ;;
            --name)         $has_fields && payload+=","; payload+="\"name\":\"$2\""; has_fields=true; shift 2 ;;
            --cron)         $has_fields && payload+=","; payload+="\"cron_expression\":\"$2\""; has_fields=true; shift 2 ;;
            --timezone)     $has_fields && payload+=","; payload+="\"timezone\":\"$2\""; has_fields=true; shift 2 ;;
            --test-group)   $has_fields && payload+=","; payload+="\"test_group\":\"$2\""; has_fields=true; shift 2 ;;
            --test-id|--test-ids)
                $has_fields && payload+=","
                local ids_json
                ids_json=$(echo "$2" | python3 -c \
                    "import sys,json; print(json.dumps(sys.stdin.read().strip().split(',')))")
                payload+="\"test_ids\":$ids_json"
                has_fields=true; shift 2 ;;
            --description)  $has_fields && payload+=","; payload+="\"description\":\"$2\""; has_fields=true; shift 2 ;;
            --enable)       $has_fields && payload+=","; payload+="\"enabled\":true"; has_fields=true; shift ;;
            --disable)      $has_fields && payload+=","; payload+="\"enabled\":false"; has_fields=true; shift ;;
            --workspaces)
                $has_fields && payload+=","
                local ws_json
                ws_json=$(echo "$2" | python3 -c \
                    "import sys,json; print(json.dumps(sys.stdin.read().strip().split(',')))")
                payload+="\"workspace_ids\":$ws_json"
                has_fields=true; shift 2 ;;
            *)              log "ERROR" "Unknown option: $1"; _schedule_help; exit 1 ;;
        esac
    done
    payload+="}"

    if [[ -z "$schedule_id" ]]; then
        log "ERROR" "--id is required"
        exit 1
    fi

    if ! $has_fields; then
        log "ERROR" "At least one field to update is required"
        exit 1
    fi

    log "INFO" "Updating schedule: $schedule_id"
    _api_request PATCH "/api/v1/schedules/$schedule_id" "$payload" | _format_json
}

_schedule_delete() {
    local schedule_id=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)   schedule_id="$2"; shift 2 ;;
            *)      schedule_id="$1"; shift ;;
        esac
    done

    if [[ -z "$schedule_id" ]]; then
        log "ERROR" "Schedule ID is required"
        exit 1
    fi

    log "INFO" "Deleting schedule: $schedule_id"
    _api_request DELETE "/api/v1/schedules/$schedule_id" | _format_json
}

_schedule_trigger() {
    local schedule_id=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)   schedule_id="$2"; shift 2 ;;
            *)      schedule_id="$1"; shift ;;
        esac
    done

    if [[ -z "$schedule_id" ]]; then
        log "ERROR" "Schedule ID is required"
        exit 1
    fi

    log "INFO" "Triggering schedule: $schedule_id"
    _api_request POST "/api/v1/schedules/$schedule_id/trigger" | _format_json
}

_schedule_jobs() {
    local schedule_id="" limit="50"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --id)       schedule_id="$2"; shift 2 ;;
            --limit)    limit="$2"; shift 2 ;;
            *)          schedule_id="$1"; shift ;;
        esac
    done

    if [[ -z "$schedule_id" ]]; then
        log "ERROR" "Schedule ID is required"
        exit 1
    fi

    _api_request GET "/api/v1/schedules/$schedule_id/jobs?limit=$limit" | _format_json
}

_schedule_help() {
    cat << 'EOF'
Usage: sap_automation_qa.sh schedule <action> [OPTIONS]

Actions:
  create    Create a new schedule
  list      List schedules (default)
  get       Get schedule details
  update    Update a schedule
  delete    Delete a schedule
  trigger   Trigger a schedule immediately
  jobs      Get jobs for a schedule

Create options:
  --name <NAME>            Schedule name (required)
  --cron <EXPRESSION>      Cron expression, e.g. "0 2 * * *" (required)
  --workspaces <IDS>       Comma-separated workspace IDs (required)
  --test-group <GROUP>     Test group: DatabaseHighAvailability, CentralServicesHighAvailability, ConfigurationChecks
  --test-ids <IDS>         Comma-separated test IDs, e.g. resource-migration,kill-indexserver
  --timezone <TZ>          IANA timezone (default: UTC)
  --description <TEXT>     Description
  --disabled               Create in disabled state

Update options:
  --id <ID>                Schedule ID (required)
  --name <NAME>            New name
  --cron <EXPRESSION>      New cron expression
  --workspaces <IDS>       New workspace IDs (comma-separated)
  --test-group <GROUP>     New test group
  --test-ids <IDS>         New test IDs (comma-separated)
  --timezone <TZ>          New timezone
  --description <TEXT>     New description
  --enable                 Enable the schedule
  --disable                Disable the schedule

Get / Delete / Trigger:
  --id <ID>                Schedule ID (or pass as positional argument)

Jobs options:
  --id <ID>                Schedule ID (required)
  --limit <N>              Max results (default: 50)

Examples:
  sap_automation_qa.sh schedule create --name "Nightly HA" --cron "0 2 * * *" \
      --workspaces DEV-WEEU-SAP01-X00 --test-group DatabaseHighAvailability \
      --test-ids resource-migration,kill-indexserver

  sap_automation_qa.sh schedule list --enabled
  sap_automation_qa.sh schedule update --id <id> --cron "0 3 * * *" --disable
  sap_automation_qa.sh schedule trigger --id <id>
  sap_automation_qa.sh schedule delete --id <id>
  sap_automation_qa.sh schedule jobs --id <id> --limit 10
EOF
}
