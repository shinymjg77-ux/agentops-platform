#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ALERT_SINK_URL="${ALERT_SINK_URL:-http://localhost:18080}"

log() {
  printf '[e2e] %s\n' "$1"
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
wait_for_health "${ALERT_SINK_URL}/healthz" "alert-sink"
curl -fsS -X DELETE "${ALERT_SINK_URL}/events" >/dev/null

log "2) success path (create -> success -> logs)"
create_success="$(curl -fsS -X POST "${API_BASE_URL}/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"template_name":"sample_echo_task","payload":{"message":"e2e-success","force_fail":false}}')"
success_task_id="$(printf '%s' "$create_success" | json_get task_id)"
if [[ -z "${success_task_id}" ]]; then
  log "failed to parse success task_id"
  exit 1
fi
wait_for_task_status "$success_task_id" "success" 90
success_logs="$(curl -fsS "${API_BASE_URL}/v1/tasks/${success_task_id}/logs?limit=50")"
assert_contains "$success_logs" "task completed" "success logs should include completion message"

log "3) retry path (manual retry -> runs increase)"
retry_resp="$(curl -fsS -X POST "${API_BASE_URL}/v1/tasks/${success_task_id}/retry")"
retry_run_id="$(printf '%s' "$retry_resp" | json_get run_id)"
if [[ -z "${retry_run_id}" ]]; then
  log "failed to parse retry run_id"
  exit 1
fi
wait_for_task_status "$success_task_id" "success" 90
runs_after_retry="$(curl -fsS "${API_BASE_URL}/v1/tasks/${success_task_id}/runs?limit=10")"
assert_contains "$runs_after_retry" "$retry_run_id" "runs should include retry run"

log "4) failure path (force_fail -> retry logs -> failure)"
create_failure="$(curl -fsS -X POST "${API_BASE_URL}/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"template_name":"sample_echo_task","payload":{"message":"e2e-fail","force_fail":true}}')"
failure_task_id="$(printf '%s' "$create_failure" | json_get task_id)"
if [[ -z "${failure_task_id}" ]]; then
  log "failed to parse failure task_id"
  exit 1
fi
wait_for_task_status "$failure_task_id" "failure" 150
failure_logs="$(curl -fsS "${API_BASE_URL}/v1/tasks/${failure_task_id}/logs?limit=300")"
assert_contains "$failure_logs" "task retry scheduled" "failure logs should include retry scheduling"
assert_contains "$failure_logs" "task failed" "failure logs should include failed message"

log "4-1) webhook path (retry/failure alert delivery)"
alerts_json="$(curl -fsS "${ALERT_SINK_URL}/events?limit=100")"
assert_contains "$alerts_json" "task_retry" "alert sink should receive task_retry event"
assert_contains "$alerts_json" "task_failure" "alert sink should receive task_failure event"

log "5) contract validation path (invalid payload -> 422)"
http_code="$(curl -sS -o /tmp/agentops_invalid_payload.json -w '%{http_code}' -X POST "${API_BASE_URL}/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"template_name":"sample_http_check_task","payload":{"url":"http://api:8000/healthz","timeout_sec":999}}')"
if [[ "$http_code" != "422" ]]; then
  log "expected 422 but got ${http_code}"
  cat /tmp/agentops_invalid_payload.json
  exit 1
fi

log "PASS: phase1 e2e checks passed"
