# AgentOps Platform PRD v3 (Phase 4)

## 1. 문서 목적
- Phase 1~3 완료 기준선 위에서 Phase 4(운영 고도화/외부 공개 준비) 제품 요구사항을 정의한다.
- 구현 우선순위, 수용 기준, 운영 리스크 대응을 명확히 한다.

## 2. 배경
- 현재 플랫폼은 단일 머신 기준에서 작업 실행/모니터링/정책 자동 제어까지 확보했다.
- 다음 단계는 실제 운영 환경에서 안전하게 서비스하기 위한 보안/배포/알림/가용성 강화다.

## 3. 문제 정의
- 인증/권한 부재로 다중 사용자 운영이 불가하다.
- 외부 접속(도메인/HTTPS) 기준이 없어 내부 개발 수준에 머물러 있다.
- 장애/이상 상황 알림이 테스트 채널 중심이라 실운영 대응력이 약하다.
- 데이터 백업/복구 표준이 없어 장애 시 복원 리스크가 높다.

## 4. 목표
- 외부 접근 가능한 운영 환경을 안전하게 제공한다.
- 프로젝트 단위 권한과 감사 추적을 확보한다.
- 정책 이벤트를 실사용 알림 채널로 연결한다.
- 장애 복구 기준(RPO/RTO)과 운영 절차를 문서화한다.

## 5. 비목표 (Phase 4 제외)
- 결제/과금 기능
- 모바일 네이티브 앱
- 고급 ML 기반 이상탐지(룰 기반을 우선)

## 6. 주요 사용자
- 운영자(Admin): 전체 시스템/권한/배포 설정 관리
- 개발자(Member): 프로젝트 작업 실행/관찰
- 뷰어(Viewer): 읽기 전용 모니터링

## 7. 범위 (Phase 4)

### 7.1 인증/권한
- 이메일+비밀번호 기반 로그인(초기), 이후 SSO 확장 가능한 구조
- 세션/JWT 기반 인증
- RBAC: `admin`, `member`, `viewer`
- 프로젝트 리소스 접근 제어(작업/스케줄/정책/로그)

### 7.2 외부 배포 기준
- Reverse proxy(Nginx/Caddy) 도입
- 도메인 연결 + HTTPS(자동 인증서 갱신)
- 환경 분리(`dev/staging/prod`) 구성 원칙

### 7.3 알림 고도화
- Slack Webhook, Telegram Bot 채널 지원
- 정책별 채널 라우팅(예: 실패율 > 임계값 시 운영 채널)
- 알림 소음 제어: 집계/쿨다운/중복 억제

### 7.4 백업/복구
- PostgreSQL 정기 백업(일 단위 + 보관정책)
- Redis는 캐시/큐 특성 기준 복구 정책 분리
- 복구 리허설 절차(월 1회 권장) 문서화

### 7.5 운영 감사/추적
- 주요 변경 이벤트 감사 로그:
  - 권한 변경
  - 정책 변경
  - 스케줄 생성/중지
- 운영자 검색 가능한 감사 로그 화면

## 8. 기능 요구사항

### FR-01 인증
- 로그인/로그아웃 API 제공
- 인증 없는 요청은 보호 엔드포인트 접근 불가(401)

### FR-02 권한
- 사용자 역할별 API 접근 제한(403)
- 대시보드 메뉴/액션도 역할 기반 제어

### FR-03 프로젝트 스코프
- 작업/스케줄/정책/로그는 프로젝트 식별자를 포함
- 사용자-프로젝트 멤버십으로 접근 제한

### FR-04 알림 채널
- 채널 생성/활성/비활성 API 제공
- 정책과 채널 매핑 가능

### FR-05 감사 로그
- 보안/운영 핵심 이벤트 자동 적재
- 시간/사용자/프로젝트 기준 조회 제공

### FR-06 백업 실행 가시성
- 최근 백업 시각/상태 표시
- 실패 시 알림 이벤트 생성

## 9. 비기능 요구사항
- 보안: 기본 비밀번호 정책, TLS 강제, 보안 헤더 적용
- 가용성: 단일 장애 시 복구 절차 30분 내 수행 가능(RTO 30m 목표)
- 데이터: 백업 기준 RPO 24시간 이내
- 관측성: auth/permission 실패율, 알림 실패율 지표 노출

## 10. 데이터 모델(초안)
- `users`:
  - id, email(unique), password_hash, role, is_active, created_at, updated_at
- `projects`:
  - id, name(unique), description, created_at
- `project_memberships`:
  - id, project_id, user_id, role, created_at
- `alert_channels`:
  - id, project_id, type(slack/telegram), config_json, is_active, created_at
- `policy_channel_bindings`:
  - id, policy_id, channel_id, created_at
- `audit_logs`:
  - id, actor_user_id, project_id, event_type, payload_json, created_at
- `backup_runs`:
  - id, started_at, finished_at, status, artifact_path, message

## 11. API 요구사항(초안)
- Auth:
  - `POST /v1/auth/login`
  - `POST /v1/auth/logout`
  - `GET /v1/auth/me`
- Users/Projects:
  - `GET /v1/users`
  - `GET /v1/projects`
  - `POST /v1/projects`
- Channels:
  - `GET /v1/alerts/channels`
  - `POST /v1/alerts/channels`
  - `PATCH /v1/alerts/channels/{id}`
- Audit/Backup:
  - `GET /v1/audit/logs`
  - `GET /v1/backups/runs`
  - `POST /v1/backups/run-now`

## 12. UI 요구사항(초안)
- 로그인 페이지
- 프로젝트 선택/전환 UI
- 권한에 따른 메뉴 노출 제어
- 알림 채널 관리 화면
- 감사 로그 화면
- 백업 상태/실행 이력 화면

## 13. 수용 기준(Definition of Done)
- 인증 없는 보호 API 접근이 차단된다.
- 최소 2개 역할(admin/viewer) 권한 테스트가 통과한다.
- HTTPS 환경에서 대시보드/API 외부 접속이 가능하다.
- Slack 또는 Telegram 중 1개 이상 실채널 알림 검증 완료.
- 백업 실행/복구 절차가 문서대로 재현 가능하다.
- 감사 로그에서 정책/권한 변경 이벤트가 조회된다.

## 14. 리스크 및 대응
- 인증 도입 시 기존 API 호환성 저하:
  - 단계적 보호 적용, 내부 헬스체크 제외
- 알림 과다 발생:
  - 정책별 쿨다운/중복억제 기본값 적용
- 외부 노출 보안 리스크:
  - TLS 강제, 최소 포트 오픈, 관리자 계정 보호 절차

## 15. 마이그레이션 원칙
- 기존 Phase 1~3 API를 즉시 중단하지 않는다.
- 신규 인증은 점진적 옵트인으로 적용 후 전환한다.
- DB 스키마 변경은 `IF NOT EXISTS`/백필 전략으로 무중단 지향.

## 16. 성공 지표
- 장애 인지 시간(MTTD) 감소
- 알림 누락률 < 1%
- 권한 오용(무권한 접근) 0건
- 월간 백업 복구 리허설 성공률 100%
