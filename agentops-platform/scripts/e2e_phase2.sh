#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

log() {
  printf '[e2e-phase2] %s\n' "$1"
}

json_get() {
  local key="$1"
  python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get(sys.argv[1], ""))' "$key"
}

wait_for_health() {
  local url="$1"
  local name="$2"
  local timeout_sec="${3:-30}"
  local started
  started="$(date +%s)"
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - started > timeout_sec )); then
      log "timeout: ${name} is not ready (${url})"
      return 1
    fi
    sleep 1
  done
}

wait_for_task_status() {
  local task_id="$1"
  local expected="$2"
  local timeout_sec="${3:-60}"
  local started
  started="$(date +%s)"
  while true; do
    local body
    body="$(curl -fsS "${API_BASE_URL}/v1/tasks/${task_id}")"
    local status
    status="$(printf '%s' "$body" | json_get status)"
    if [[ "$status" == "$expected" ]]; then
      return 0
    fi
    if (( $(date +%s) - started > timeout_sec )); then
      log "timeout: task ${task_id} did not reach status=${expected} (now=${status})"
      return 1
    fi
    sleep 1
  done
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local msg="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    log "assert failed: ${msg} (missing: ${needle})"
    return 1
  fi
}

log "1) health check"
wait_for_health "${API_BASE_URL}/healthz" "api"
wait_for_health "${API_BASE_URL}/readyz" "api-ready"

TS="$(date +%s)"
TEMPLATE_NAME="phase2_echo_${TS}"

log "2) create template"
CREATE_TEMPLATE="$(curl -fsS -X POST "${API_BASE_URL}/v1/template-registry" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"${TEMPLATE_NAME}\",\"display_name\":\"Phase2 Echo ${TS}\",\"description\":\"phase2 e2e\"}")"
TEMPLATE_ID="$(printf '%s' "$CREATE_TEMPLATE" | json_get id)"
if [[ -z "$TEMPLATE_ID" ]]; then
  log "failed to parse template id"
  exit 1
fi

log "3) add versions"
curl -fsS -X POST "${API_BASE_URL}/v1/template-registry/${TEMPLATE_ID}/versions" \
  -H 'Content-Type: application/json' \
  -d '{"version":"1.0.0","adapter_name":"tasks.sample_echo_task","adapter_version":"v1","input_schema":{"type":"object"},"set_default":true}' >/dev/null

curl -fsS -X POST "${API_BASE_URL}/v1/template-registry/${TEMPLATE_ID}/versions" \
  -H 'Content-Type: application/json' \
  -d '{"version":"1.1.0","adapter_name":"tasks.sample_echo_task","adapter_version":"v2","input_schema":{"type":"object"},"set_default":false}' >/dev/null

curl -fsS -X POST "${API_BASE_URL}/v1/template-registry/${TEMPLATE_ID}/versions/1.1.0/set-default" >/dev/null

DETAIL="$(curl -fsS "${API_BASE_URL}/v1/template-registry/${TEMPLATE_ID}")"
assert_contains "$DETAIL" '"version":"1.1.0"' "detail should include version 1.1.0"
assert_contains "$DETAIL" '"is_default":true' "detail should include default version"

log "4) create tasks with default/explicit version"
TASK_DEFAULT="$(curl -fsS -X POST "${API_BASE_URL}/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d "{\"template_name\":\"${TEMPLATE_NAME}\",\"payload\":{\"message\":\"phase2-default\"}}")"
TASK_DEFAULT_ID="$(printf '%s' "$TASK_DEFAULT" | json_get task_id)"

TASK_V1="$(curl -fsS -X POST "${API_BASE_URL}/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d "{\"template_name\":\"${TEMPLATE_NAME}\",\"template_version\":\"1.0.0\",\"payload\":{\"message\":\"phase2-v1\"}}")"
TASK_V1_ID="$(printf '%s' "$TASK_V1" | json_get task_id)"

wait_for_task_status "$TASK_DEFAULT_ID" "success" 120
wait_for_task_status "$TASK_V1_ID" "success" 120

log "5) search runs"
SEARCH="$(curl -fsS "${API_BASE_URL}/v1/search/runs?template_name=${TEMPLATE_NAME}&limit=20")"
assert_contains "$SEARCH" '"total":' "search should return total"
assert_contains "$SEARCH" '"template_name":"'"${TEMPLATE_NAME}"'"' "search should include template"
assert_contains "$SEARCH" '"template_version":"1.1.0"' "search should include default version run"
assert_contains "$SEARCH" '"template_version":"1.0.0"' "search should include explicit version run"

log "6) analytics"
ANALYTICS="$(curl -fsS "${API_BASE_URL}/v1/analytics/template-versions?template_name=${TEMPLATE_NAME}")"
assert_contains "$ANALYTICS" '"template_version":"1.0.0"' "analytics should include version 1.0.0"
assert_contains "$ANALYTICS" '"template_version":"1.1.0"' "analytics should include version 1.1.0"

log "PASS: phase2 e2e checks passed"
