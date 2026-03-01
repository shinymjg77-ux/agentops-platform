#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

log() {
  printf '[e2e-phase3] %s\n' "$1"
}

json_get() {
  local key="$1"
  python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get(sys.argv[1], ""))' "$key"
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

wait_for_schedule_runs() {
  local schedule_id="$1"
  local min_count="$2"
  local timeout_sec="${3:-40}"
  local started
  started="$(date +%s)"
  while true; do
    local body
    body="$(curl -fsS "${API_BASE_URL}/v1/schedules/${schedule_id}/runs?limit=20")"
    local count
    count="$(python3 -c 'import json,sys; print(len(json.loads(sys.stdin.read())))' <<<"$body")"
    if (( count >= min_count )); then
      return 0
    fi
    if (( $(date +%s) - started > timeout_sec )); then
      log "timeout: schedule ${schedule_id} runs < ${min_count} (now=${count})"
      return 1
    fi
    sleep 1
  done
}

wait_for_policy_actions() {
  local policy_id="$1"
  local min_count="$2"
  local timeout_sec="${3:-40}"
  local started
  started="$(date +%s)"
  while true; do
    local body
    body="$(curl -fsS "${API_BASE_URL}/v1/policies/${policy_id}/actions?limit=20")"
    local count
    count="$(python3 -c 'import json,sys; print(len(json.loads(sys.stdin.read())))' <<<"$body")"
    if (( count >= min_count )); then
      return 0
    fi
    if (( $(date +%s) - started > timeout_sec )); then
      log "timeout: policy ${policy_id} actions < ${min_count} (now=${count})"
      return 1
    fi
    sleep 1
  done
}

log "1) health check"
wait_for_health "${API_BASE_URL}/healthz" "api"
wait_for_health "${API_BASE_URL}/readyz" "api-ready"

TS="$(date +%s)"
SCHEDULE_NAME="phase3_schedule_${TS}"
POLICY_NAME="phase3_policy_${TS}"

log "2) create schedule"
CREATE_SCHEDULE="$(curl -fsS -X POST "${API_BASE_URL}/v1/schedules" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"${SCHEDULE_NAME}\",\"template_name\":\"sample_echo_task\",\"payload\":{\"message\":\"phase3-${TS}\"},\"rrule_text\":\"every:20\",\"timezone\":\"Asia/Seoul\",\"is_active\":true}")"
SCHEDULE_ID="$(printf '%s' "$CREATE_SCHEDULE" | json_get id)"
if [[ -z "$SCHEDULE_ID" ]]; then
  log "failed to parse schedule id"
  exit 1
fi

log "3) schedule run-now and runs list"
curl -fsS -X POST "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}/run-now" >/dev/null
wait_for_schedule_runs "$SCHEDULE_ID" 1 40
RUNS_BODY="$(curl -fsS "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}/runs?limit=10")"
assert_contains "$RUNS_BODY" '"status":"queued"' "schedule run should be queued"

log "4) pause/resume schedule"
curl -fsS -X POST "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}/pause" >/dev/null
SCHEDULE_DETAIL="$(curl -fsS "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}")"
assert_contains "$SCHEDULE_DETAIL" '"is_active":false' "schedule should be paused"

curl -fsS -X POST "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}/resume" >/dev/null
SCHEDULE_DETAIL="$(curl -fsS "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}")"
assert_contains "$SCHEDULE_DETAIL" '"is_active":true' "schedule should be resumed"

log "5) create policy and wait action"
CREATE_POLICY="$(curl -fsS -X POST "${API_BASE_URL}/v1/policies" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"${POLICY_NAME}\",\"scope_type\":\"schedule\",\"scope_ref\":\"${SCHEDULE_NAME}\",\"metric_key\":\"failure_rate\",\"operator\":\"gte\",\"threshold_value\":0,\"window_minutes\":1,\"cooldown_minutes\":1,\"action_type\":\"pause_schedule\"}")"
POLICY_ID="$(printf '%s' "$CREATE_POLICY" | json_get id)"
if [[ -z "$POLICY_ID" ]]; then
  log "failed to parse policy id"
  exit 1
fi

wait_for_policy_actions "$POLICY_ID" 1 50
POLICY_ACTIONS="$(curl -fsS "${API_BASE_URL}/v1/policies/${POLICY_ID}/actions?limit=10")"
assert_contains "$POLICY_ACTIONS" '"status":"success"' "policy action should be success"

SCHEDULE_DETAIL="$(curl -fsS "${API_BASE_URL}/v1/schedules/${SCHEDULE_ID}")"
assert_contains "$SCHEDULE_DETAIL" '"is_active":false' "policy should pause schedule"

log "6) agents list"
AGENTS="$(curl -fsS "${API_BASE_URL}/v1/agents")"
assert_contains "$AGENTS" '"name":"agentops-worker-1"' "agents should include worker heartbeat"

log "PASS: phase3 e2e checks passed"
