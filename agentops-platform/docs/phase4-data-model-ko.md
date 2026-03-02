# Phase 4 데이터 모델 (초안 v1)

## 1) 개요
- Phase4 1차 구현 범위는 인증/권한/RBAC/감사로그/백업이력의 기반 스키마다.
- 기존 Phase1~3 스키마와 공존하며 무중단 확장(`IF NOT EXISTS`)을 원칙으로 한다.

## 2) 신규 테이블

## `users`
- `id UUID PK`
- `email TEXT UNIQUE NOT NULL`
- `password_hash TEXT NOT NULL`
- `role TEXT NOT NULL DEFAULT 'member'`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`

인덱스:
- `idx_users_role_active (role, is_active)`

## `projects`
- `id UUID PK`
- `name TEXT UNIQUE NOT NULL`
- `description TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`

## `project_memberships`
- `id UUID PK`
- `project_id UUID NOT NULL FK -> projects(id)`
- `user_id UUID NOT NULL FK -> users(id)`
- `role TEXT NOT NULL DEFAULT 'member'`
- `created_at TIMESTAMPTZ NOT NULL`
- `UNIQUE(project_id, user_id)`

인덱스:
- `idx_project_memberships_user (user_id)`

## `audit_logs`
- `id UUID PK`
- `actor_user_id UUID NULL FK -> users(id)`
- `project_id UUID NULL FK -> projects(id)`
- `event_type TEXT NOT NULL`
- `payload_json JSONB NULL`
- `created_at TIMESTAMPTZ NOT NULL`

인덱스:
- `idx_audit_logs_created_at (created_at DESC)`
- `idx_audit_logs_project_created_at (project_id, created_at DESC)`

## `backup_runs`
- `id UUID PK`
- `started_at TIMESTAMPTZ NOT NULL`
- `finished_at TIMESTAMPTZ NULL`
- `status TEXT NOT NULL`
- `artifact_path TEXT NULL`
- `message TEXT NULL`

인덱스:
- `idx_backup_runs_started_at (started_at DESC)`

## 3) 시드 정책
- 기본 프로젝트 1개 생성:
  - `DEFAULT_PROJECT_NAME` (기본 `default`)
- 기본 관리자 1명 생성:
  - `DEFAULT_ADMIN_EMAIL`
  - `DEFAULT_ADMIN_PASSWORD`
- 기본 관리자와 기본 프로젝트 멤버십(admin) 자동 연결

## 4) 무결성/운영 규칙
- `users.email`은 대소문자 무시 비교를 애플리케이션에서 보장한다.
- `viewer` 역할은 읽기 전용(미들웨어 수준에서 non-GET 차단).
- 감사 로그는 보안/운영 중요 이벤트만 적재한다.

## 5) 향후 확장(Phase4 후속)
- `sessions`(토큰 블랙리스트/강제 로그아웃) 테이블
- `alert_channels`, `policy_channel_bindings` 테이블
- 백업 아티팩트 체크섬/보관주기 필드
