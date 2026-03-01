# Phase 2 데이터 모델 설계

## 1. 목표
- 템플릿 레지스트리와 버전 메타를 영속화하여, 실행 이력의 버전 추적과 비교를 가능하게 한다.

## 2. 신규 테이블
## `task_templates`
- `id UUID PK`
- `name TEXT UNIQUE NOT NULL`
- `display_name TEXT NOT NULL`
- `description TEXT`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

인덱스:
- `idx_task_templates_active (is_active)`

## `task_template_versions`
- `id UUID PK`
- `template_id UUID NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE`
- `version TEXT NOT NULL` (예: `1.0.0`)
- `adapter_name TEXT NOT NULL` (예: `tasks.sample_echo_task`)
- `adapter_version TEXT` (예: git sha or semver)
- `input_schema_json JSONB NOT NULL`
- `retry_policy_json JSONB`
- `timeout_sec INT`
- `is_default BOOLEAN NOT NULL DEFAULT FALSE`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at TIMESTAMPTZ NOT NULL`

유니크 제약:
- `(template_id, version)`
- `is_default=TRUE`는 템플릿당 1개만 허용(Partial Unique Index)

인덱스:
- `idx_template_versions_template_id (template_id)`
- `idx_template_versions_default (template_id, is_default)`

## 3. 기존 테이블 확장
## `tasks`
- 유지: `template_name` (하위호환)
- 추가:
  - `template_id UUID NULL REFERENCES task_templates(id)`
  - `template_version TEXT NULL`

## `task_runs`
- 추가:
  - `template_id UUID NULL REFERENCES task_templates(id)`
  - `template_version TEXT NULL`
  - `adapter_version TEXT NULL`
  - `error_code TEXT NULL`
  - `error_message TEXT NULL`

인덱스:
- `idx_task_runs_template_version (template_id, template_version, started_at DESC)`
- `idx_task_runs_status_started_at (status, started_at DESC)`

## 4. 마이그레이션 전략
1. 신규 테이블 생성
2. 샘플 템플릿 2종을 `task_templates` + `task_template_versions`로 시드
3. 기존 `tasks.template_name` 값을 기준으로 `template_id/template_version` 백필
4. 신규 코드 배포 후 신규 실행건부터 version 메타 강제
5. 안정화 후 `template_name` 축소 여부 검토

## 5. 하위호환 정책
- Phase 2 동안 `template_name` 필드는 유지한다.
- 레지스트리에 없는 템플릿 호출 시 `400` 반환(옵션: fallback 허용 플래그).
