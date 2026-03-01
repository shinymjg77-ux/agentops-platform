# Phase 1 API 상세 스펙

## 1. 헬스
- `GET /healthz`
- `GET /readyz`

## 2. 템플릿
- `GET /v1/templates`
  - 템플릿 목록 + `payload_schema` 반환

## 3. 작업
- `POST /v1/tasks`
  - body: `template_name`, `payload`
  - 성공: `201` + `task_id/run_id/celery_task_id/status`
  - 실패: `422`(payload 검증 실패)

- `GET /v1/tasks?limit=20`
  - task별 최신 run 기준 목록 반환

- `GET /v1/tasks/{task_id}`
  - task 메타 + 최신 run 상세 반환

- `POST /v1/tasks/{task_id}/retry`
  - 기존 task payload로 신규 run 생성

## 4. 실행 이력/로그
- `GET /v1/tasks/{task_id}/runs?limit=50`
  - run 이력 반환

- `GET /v1/tasks/{task_id}/logs?limit=200&run_id=<uuid>`
  - run_id 선택 시 해당 실행 로그만 반환

## 5. 실시간
- `GET /v1/stream/tasks`
  - SSE(`ready`, `task_update`, heartbeat)

## 6. 메트릭
- `GET /metrics`
  - Prometheus scrape endpoint
