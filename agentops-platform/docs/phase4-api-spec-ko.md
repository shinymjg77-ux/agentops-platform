# Phase 4 API 스펙 (초안 v0)

## 1. 인증

### `POST /v1/auth/login`
- 요청:
```json
{
  "email": "admin@agentops.local",
  "password": "change-me-now"
}
```
- 응답:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_at": "2026-03-02T12:00:00+00:00",
  "user": {
    "id": "<uuid>",
    "email": "admin@agentops.local",
    "role": "admin"
  }
}
```

### `POST /v1/auth/logout`
- 인증 필요(`Authorization: Bearer <token>`)
- 응답:
```json
{
  "status": "ok"
}
```

### `GET /v1/auth/me`
- 인증 필요
- 응답: 현재 사용자 + 멤버십 프로젝트 목록

## 2. 사용자/권한

### `GET /v1/users`
- `admin` 전용
- 사용자 목록 조회

### `POST /v1/users`
- `admin` 전용
- 사용자 생성
- 요청:
```json
{
  "email": "viewer@agentops.local",
  "password": "viewer-pass",
  "role": "viewer",
  "is_active": true
}
```

### `PATCH /v1/users/{user_id}`
- `admin` 전용
- 역할/활성화 상태 변경

## 3. 프로젝트

### `GET /v1/projects`
- 인증 필요
- `admin`: 전체 프로젝트 반환
- 그 외: 본인 멤버십 프로젝트만 반환

### `POST /v1/projects`
- `admin` 전용
- 프로젝트 생성 + 생성자를 프로젝트 admin 멤버로 자동 등록

## 4. 감사 로그

### `GET /v1/audit/logs`
- 인증 필요
- 쿼리:
  - `project_id` (선택)
  - `limit` (기본 100, 최대 500)
- 기본 이벤트:
  - `auth.login`
  - `auth.logout`
  - `user.create`
  - `user.update`
  - `project.create`

## 5. 백업 이력

### `GET /v1/backups/runs`
- 인증 필요(`admin/member/viewer` 가능)
- 백업 실행 이력 조회

## 6. 인증 모드

- `AUTH_MODE=disabled`: 인증 비활성
- `AUTH_MODE=optional`: 토큰 있으면 검증, 없어도 기존 API 흐름 허용(기본값)
- `AUTH_MODE=required`: 로그인 제외 `/v1/*` 인증 강제

## 7. 역할 정책

- `admin`: 전체 API
- `member`: 조회 + 일반 작업 API (현재 `required` 모드에서 토큰 기반 접근)
- `viewer`: 읽기 전용(비-GET 요청 차단)
