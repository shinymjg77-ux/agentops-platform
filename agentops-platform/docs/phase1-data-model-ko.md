# Phase 1 데이터 모델 상세

## 1. 범위
- Core 실행 파이프라인과 모니터링 MVP에 필요한 최소 영속 모델 정의.

## 2. 테이블
## `tasks`
- `id UUID PK`
- `template_name TEXT NOT NULL`
- `payload_json JSONB NOT NULL`
- `status TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`

## `task_runs`
- `id UUID PK`
- `task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE`
- `celery_task_id TEXT UNIQUE`
- `status TEXT NOT NULL`
- `started_at TIMESTAMPTZ NOT NULL`
- `finished_at TIMESTAMPTZ NULL`
- `result_json JSONB NULL`

## `task_logs`
- `id BIGSERIAL PK`
- `task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE`
- `run_id UUID NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE`
- `ts TIMESTAMPTZ NOT NULL`
- `level TEXT NOT NULL`
- `message TEXT NOT NULL`
- `metadata_json JSONB NULL`

## 3. 인덱스
- `idx_task_runs_task_id`
- `idx_task_runs_celery_task_id` (UNIQUE)
- `idx_task_logs_task_id_ts`
- `idx_task_logs_run_id_ts`

## 4. 상태 흐름
- `queued -> started -> success`
- `queued -> started -> retry -> started -> ... -> failure`

## 5. 데이터 무결성 규칙
- `task_logs.run_id`는 반드시 존재하는 `task_runs.id`를 참조
- `task_runs.task_id`와 `task_logs.task_id`는 동일 task를 가리켜야 함(애플리케이션 레벨 보장)
- 최신 상태는 `tasks.status`, 상세 실행 상태는 `task_runs.status` 기준
