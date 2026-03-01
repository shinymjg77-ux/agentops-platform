# Phase 2 API 스펙

## 1. 템플릿 레지스트리
## `GET /v1/template-registry`
- 설명: 템플릿 목록 조회
- 쿼리:
  - `active_only` (default: true)
  - `q` (name/display_name 검색)

## `POST /v1/template-registry`
- 설명: 템플릿 생성
- body:
  - `name`, `display_name`, `description?`

## `GET /v1/template-registry/{template_id}`
- 설명: 템플릿 상세 + 버전 목록

## `PATCH /v1/template-registry/{template_id}`
- 설명: 템플릿 메타 수정/활성화 제어

## 2. 템플릿 버전
## `POST /v1/template-registry/{template_id}/versions`
- 설명: 버전 추가
- body:
  - `version`
  - `adapter_name`
  - `adapter_version?`
  - `input_schema`
  - `retry_policy?`
  - `timeout_sec?`
  - `set_default?` (bool)

## `POST /v1/template-registry/{template_id}/versions/{version}/activate`
- 설명: 버전 활성화

## `POST /v1/template-registry/{template_id}/versions/{version}/set-default`
- 설명: 기본 버전 지정

## 3. 작업 생성(확장)
## `POST /v1/tasks`
- 기존 body 확장:
  - `template_name` (필수)
  - `template_version` (선택; 미지정 시 default 버전 resolve)
  - `payload`
- 동작:
  - 레지스트리에서 버전 resolve
  - resolved `template_version/adapter_version`를 run 메타에 저장

## 4. 고급 검색
## `GET /v1/search/runs`
- 쿼리:
  - `from`, `to` (ISO datetime)
  - `status` (`queued|started|retry|success|failure`)
  - `template_name`
  - `template_version`
  - `error_keyword`
  - `limit` (1~200), `offset`
- 반환:
  - run 목록 + total

## 5. 버전 비교
## `GET /v1/analytics/template-versions`
- 쿼리:
  - `template_name` (필수)
  - `from`, `to`
  - `versions` (comma-separated; 미지정 시 최근 N개)
- 반환:
  - 버전별 `total_runs`, `success_rate`, `failure_rate`, `avg_duration_ms`, `p95_duration_ms`

## 6. 오류 코드
- `400` 잘못된 템플릿/버전
- `404` 리소스 없음
- `409` 버전 중복/기본버전 제약 위반
- `422` payload 검증 실패
