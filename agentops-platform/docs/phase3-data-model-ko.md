# Phase 3 데이터 모델 설계

## 1) 신규 테이블
## `task_schedules`
- `id UUID PK`
- `name TEXT UNIQUE NOT NULL`
- `template_id UUID NOT NULL REFERENCES task_templates(id)`
- `template_version TEXT NULL`
- `payload_json JSONB NOT NULL`
- `rrule_text TEXT NOT NULL`
- `timezone TEXT NOT NULL DEFAULT 'Asia/Seoul'`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `next_run_at TIMESTAMPTZ NULL`
- `last_run_at TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

## `schedule_runs`
- `id UUID PK`
- `schedule_id UUID NOT NULL REFERENCES task_schedules(id) ON DELETE CASCADE`
- `task_id UUID NULL REFERENCES tasks(id)`
- `planned_at TIMESTAMPTZ NOT NULL`
- `started_at TIMESTAMPTZ NOT NULL`
- `finished_at TIMESTAMPTZ NULL`
- `status TEXT NOT NULL`
- `error_message TEXT NULL`

## `agents`
- `id UUID PK`
- `name TEXT UNIQUE NOT NULL`
- `hostname TEXT`
- `status TEXT NOT NULL` (`online|degraded|offline`)
- `last_heartbeat_at TIMESTAMPTZ NOT NULL`
- `capacity INT NOT NULL DEFAULT 1`
- `queue_names TEXT[] NOT NULL DEFAULT '{}'`

## `policy_rules`
- `id UUID PK`
- `name TEXT UNIQUE NOT NULL`
- `scope_type TEXT NOT NULL` (`global|template|schedule`)
- `scope_ref TEXT NULL`
- `metric_key TEXT NOT NULL` (`failure_rate|queue_lag_ms|retry_rate`)
- `operator TEXT NOT NULL` (`gt|gte|lt|lte|eq`)
- `threshold_value DOUBLE PRECISION NOT NULL`
- `window_minutes INT NOT NULL DEFAULT 15`
- `cooldown_minutes INT NOT NULL DEFAULT 30`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at TIMESTAMPTZ NOT NULL`

## `policy_actions`
- `id UUID PK`
- `rule_id UUID NOT NULL REFERENCES policy_rules(id) ON DELETE CASCADE`
- `action_type TEXT NOT NULL` (`pause_schedule|raise_alert|limit_retry`)
- `action_payload_json JSONB NULL`
- `executed_at TIMESTAMPTZ NOT NULL`
- `status TEXT NOT NULL` (`success|failed|skipped`)
- `message TEXT NULL`

## 2) 인덱스
- `idx_task_schedules_active_next (is_active, next_run_at)`
- `idx_schedule_runs_schedule_started (schedule_id, started_at DESC)`
- `idx_agents_last_heartbeat (last_heartbeat_at DESC)`
- `idx_policy_rules_active (is_active)`
- `idx_policy_actions_rule_executed (rule_id, executed_at DESC)`
