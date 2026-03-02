# Phase 4 UI 스펙 (초안 v1)

## 1) 목표
- 인증/권한 기반 운영 화면 진입을 가능하게 한다.
- 최소 운영 화면(프로젝트/사용자/감사로그)을 제공한다.

## 2) 화면 목록

## `/login`
- 입력:
  - email
  - password
- 동작:
  - `POST /v1/auth/login` 성공 시 토큰 저장
  - 실패 시 오류 메시지 노출

## `/me` (또는 헤더 사용자 패널)
- 데이터:
  - `GET /v1/auth/me`
- 노출:
  - 사용자 이메일/역할
  - 멤버십 프로젝트 목록

## `/projects`
- 데이터:
  - `GET /v1/projects`
- 동작:
  - `admin`만 생성 버튼 노출
  - 생성 시 `POST /v1/projects`

## `/users` (admin 전용)
- 데이터:
  - `GET /v1/users`
- 동작:
  - 사용자 생성 `POST /v1/users`
  - 역할/활성 변경 `PATCH /v1/users/{id}`

## `/audit/logs`
- 데이터:
  - `GET /v1/audit/logs?limit=...`
- 기능:
  - event_type, actor, created_at 컬럼 표시
  - 프로젝트 필터(옵션)

## `/backups`
- 데이터:
  - `GET /v1/backups/runs`
- 기능:
  - 백업 실행 이력 목록 표시

## 3) 권한 정책(UI)
- `admin`:
  - 모든 메뉴 표시
- `member`:
  - 프로젝트/감사로그/백업 조회 메뉴
  - 사용자 관리 메뉴 숨김
- `viewer`:
  - 읽기 메뉴만 표시
  - 작성/수정 버튼 숨김

## 4) 공통 UX
- 인증 실패(401): 로그인 화면으로 이동
- 권한 실패(403): 권한 부족 안내 배너 + 이전 화면 복귀 링크
- 로딩/에러/빈 상태를 공통 컴포넌트로 통일

## 5) 후속 확장
- 프로젝트 전환 드롭다운
- 역할별 홈 대시보드 카드
- 감사 로그 상세 드로어(JSON pretty print)
