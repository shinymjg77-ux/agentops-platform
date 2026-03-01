# Phase 3 API 스펙

## 1) 스케줄
- `GET /v1/schedules`
- `POST /v1/schedules`
- `GET /v1/schedules/{schedule_id}`
- `PATCH /v1/schedules/{schedule_id}`
- `POST /v1/schedules/{schedule_id}/pause`
- `POST /v1/schedules/{schedule_id}/resume`
- `POST /v1/schedules/{schedule_id}/run-now`
- `GET /v1/schedules/{schedule_id}/runs`

## 2) 정책
- `GET /v1/policies`
- `POST /v1/policies`
- `PATCH /v1/policies/{policy_id}`
- `POST /v1/policies/{policy_id}/enable`
- `POST /v1/policies/{policy_id}/disable`
- `GET /v1/policies/{policy_id}/actions`

## 3) 에이전트/노드
- `POST /v1/agents/heartbeat`
- `GET /v1/agents`
- `GET /v1/agents/{agent_id}`

## 4) 운영
- `GET /v1/operations/queue-health`
- `GET /v1/operations/scheduler-health`

## 5) 에러코드
- `400` 잘못된 스케줄/정책 입력
- `404` 대상 리소스 없음
- `409` 스케줄명/정책명 충돌
- `422` payload/rrule 검증 실패
