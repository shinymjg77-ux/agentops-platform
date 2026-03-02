#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ADMIN_EMAIL="${DEFAULT_ADMIN_EMAIL:-admin@agentops.local}"
ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-change-me-now}"

log() {
  printf '[e2e-phase4] %s\n' "$1"
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

assert_http_code() {
  local expected="$1"
  shift
  local code
  code="$(curl -sS -o /tmp/agentops_phase4_http_body.json -w '%{http_code}' "$@")"
  if [[ "$code" != "$expected" ]]; then
    log "expected http ${expected}, got ${code}"
    cat /tmp/agentops_phase4_http_body.json
    return 1
  fi
}

TS="$(date +%s)"
VIEWER_EMAIL="viewer_${TS}@agentops.local"
VIEWER_PASSWORD="viewer-pass-${TS}"
PROJECT_NAME="phase4_project_${TS}"

log "1) health check"
wait_for_health "${API_BASE_URL}/healthz" "api"
wait_for_health "${API_BASE_URL}/readyz" "api-ready"

log "2) auth/me must require token"
assert_http_code "401" "${API_BASE_URL}/v1/auth/me"

log "3) admin login"
LOGIN_BODY="$(curl -fsS -X POST "${API_BASE_URL}/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")"
ADMIN_TOKEN="$(printf '%s' "$LOGIN_BODY" | json_get access_token)"
if [[ -z "$ADMIN_TOKEN" ]]; then
  log "failed to get admin token"
  exit 1
fi

ME_BODY="$(curl -fsS "${API_BASE_URL}/v1/auth/me" -H "Authorization: Bearer ${ADMIN_TOKEN}")"
assert_contains "$ME_BODY" "\"email\":\"${ADMIN_EMAIL}\"" "me should include admin email"
assert_contains "$ME_BODY" '"role":"admin"' "me should include admin role"

log "4) create viewer user and verify readonly restriction"
curl -fsS -X POST "${API_BASE_URL}/v1/users" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d "{\"email\":\"${VIEWER_EMAIL}\",\"password\":\"${VIEWER_PASSWORD}\",\"role\":\"viewer\",\"is_active\":true}" >/dev/null

VIEWER_LOGIN="$(curl -fsS -X POST "${API_BASE_URL}/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${VIEWER_EMAIL}\",\"password\":\"${VIEWER_PASSWORD}\"}")"
VIEWER_TOKEN="$(printf '%s' "$VIEWER_LOGIN" | json_get access_token)"
if [[ -z "$VIEWER_TOKEN" ]]; then
  log "failed to get viewer token"
  exit 1
fi

assert_http_code "403" -X POST "${API_BASE_URL}/v1/projects" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${VIEWER_TOKEN}" \
  -d "{\"name\":\"viewer_denied_${TS}\"}"

log "5) admin project create and audit logs"
PROJECT_BODY="$(curl -fsS -X POST "${API_BASE_URL}/v1/projects" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d "{\"name\":\"${PROJECT_NAME}\",\"description\":\"phase4 e2e project\"}")"
assert_contains "$PROJECT_BODY" "\"name\":\"${PROJECT_NAME}\"" "project create response should include project name"

PROJECTS_BODY="$(curl -fsS "${API_BASE_URL}/v1/projects" -H "Authorization: Bearer ${ADMIN_TOKEN}")"
assert_contains "$PROJECTS_BODY" "\"name\":\"${PROJECT_NAME}\"" "project list should include created project"

AUDIT_BODY="$(curl -fsS "${API_BASE_URL}/v1/audit/logs?limit=30" -H "Authorization: Bearer ${ADMIN_TOKEN}")"
assert_contains "$AUDIT_BODY" '"event_type":"project.create"' "audit should include project.create"
assert_contains "$AUDIT_BODY" '"event_type":"auth.login"' "audit should include auth.login"

log "6) backups list"
BACKUPS_BODY="$(curl -fsS "${API_BASE_URL}/v1/backups/runs?limit=5" -H "Authorization: Bearer ${ADMIN_TOKEN}")"
assert_contains "$BACKUPS_BODY" '[' "backups endpoint should return array json"

log "PASS: phase4 e2e checks passed"
