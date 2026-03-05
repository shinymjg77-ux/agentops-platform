# PRD: Creator DM Autopost

## 1. Problem Statement
팀이 다수의 크리에이터 페르소나를 기획하고, 각 페르소나별 콘텐츠를 제작해, 대상 사용자에게 DM으로 전달하는 과정이 수작업 중심이다.
이로 인해 제작 속도 저하, 품질 편차, 발송 누락/중복, 운영 로그 부재 문제가 발생한다.

본 프로젝트의 목적은 `크리에이터 생성 -> 포스트 생성 -> 승인 -> DM 자동 발송 -> 결과 추적` 흐름을 하나의 파이프라인으로 자동화하는 것이다.

## 2. Goals
- 크리에이터 페르소나를 입력 조건(타깃/톤/주제) 기반으로 자동 생성한다.
- 페르소나별 포스트 초안을 자동 생성한다.
- 승인된 포스트를 DM으로 자동 발송한다.
- 발송 결과(성공/실패/재시도)를 추적 가능한 로그로 남긴다.
- 운영자가 캠페인 단위로 상태를 확인하고 제어할 수 있게 한다.

## 3. Non-Goals
- 모든 SNS 채널 동시 지원(1차는 1개 DM 채널만 지원)
- 자율 무제한 발송(수신 동의 및 정책 준수 범위 내 발송만 허용)
- 고급 추천/개인화 모델 고도화(1차는 템플릿+기본 변수 치환 중심)
- 멀티테넌시 SaaS 완성형 아키텍처

## 4. v1 Channel Scope (Locked)
- v1 DM 채널은 `Discord DM (Bot)`으로 고정한다.
- 다른 채널(X/Instagram 등)은 v1 범위에서 제외한다.
- v2 확장을 위해 채널 어댑터 인터페이스(`DMProvider`)를 분리한다.

## 5. Primary Users
- 캠페인 운영자: 크리에이터/콘텐츠 생성 및 발송 승인 담당
- 마케팅 매니저: 캠페인 목표 관리, 성과 확인
- 관리자: 정책/권한/감사 로그 확인

## 6. User Journey (MVP)
1. 운영자가 캠페인 목표와 타깃 조건을 입력한다.
2. 시스템이 크리에이터 페르소나 N개를 생성한다.
3. 운영자가 페르소나를 선택/수정한다.
4. 시스템이 선택된 페르소나 기반 포스트 초안을 생성한다.
5. 운영자가 포스트를 승인(또는 수정)한다.
6. 스케줄러가 승인된 포스트를 대상자에게 DM 발송한다.
7. 대시보드에서 발송 결과와 실패 사유를 확인한다.

## 7. Functional Requirements
### FR-1. Creator Generator
- 입력: 캠페인 목표, 타깃 세그먼트, 금지 키워드, 채널 제약
- 출력: 이름, 톤, 핵심 주제, 샘플 문체를 포함한 페르소나
- 생성 수량과 다양성 옵션(예: 3/5/10개) 제공

### FR-2. Post Generator
- 페르소나별 포스트 초안 생성
- 템플릿 변수(상품명, 혜택, CTA, 링크) 자동 치환
- 금지어/길이/톤 규칙 검증

### FR-3. Approval Workflow
- DM 외부 발송 전 `approved` 상태가 필수
- 승인 이력(승인자, 시간, 버전) 저장
- 승인 거절 시 수정 후 재승인 가능

### FR-4. DM Delivery Pipeline
- 대상자 목록 업로드/선택
- 예약 발송(즉시/시간 지정)
- 속도 제한(rate limit) 적용
- 실패 재시도(지수 백오프, 최대 3회)

### FR-5. Monitoring & Audit
- 발송 상태: queued/sending/sent/failed/retrying/cancelled
- 실패 사유 코드 및 원문 로그
- 감사 로그: 누가 어떤 메시지를 언제 승인/발송했는지 추적

### FR-6. Access Control
- 역할: admin, operator, viewer
- operator는 생성/승인 가능, viewer는 조회만 가능

### FR-7. Consent Management
- `active opt-in`이 없는 수신자는 발송 대상에서 자동 제외
- 동의 획득 시점, 획득 경로, 증빙 참조(proof_ref) 저장
- 수신 거부(opt-out) 즉시 이후 예약/재시도 발송 중단

### FR-8. Delivery State Machine
- `post.status` 전이 규칙:
  - draft -> pending_approval -> approved -> scheduled -> sending -> sent | failed | cancelled
- `delivery.status` 전이 규칙:
  - queued -> sending -> sent | failed | retrying
  - retrying -> queued | failed
- 비정상 전이는 `invalid_state_transition`으로 거부한다.
- `idempotency_key` 중복 요청은 1회만 실제 발송 처리한다.

## 8. Acceptance Criteria (Testable)
### AC-1 Persona Generation
- Given 캠페인 입력값이 존재할 때
- When 운영자가 페르소나 5개 생성을 요청하면
- Then 5개의 유효한 페르소나가 60초 이내 생성되고 필수 필드(name/tone/topic)가 모두 채워진다.

### AC-2 Post Draft Validation
- Given 페르소나와 템플릿이 존재할 때
- When 포스트 초안을 생성하면
- Then 금지 키워드가 포함되지 않고 채널 길이 제한을 초과하지 않는다.

### AC-3 Approval Gate
- Given 포스트 상태가 `draft`일 때
- When 발송 API 호출이 시도되면
- Then 시스템은 발송을 거부하고 `approval_required` 오류를 반환한다.

### AC-4 Scheduled DM Send
- Given 승인된 포스트와 예약 시간이 있을 때
- When 예약 시간이 도래하면
- Then 대상자에게 DM이 발송되고 상태가 `sent` 또는 `failed`로 갱신된다.

### AC-5 Retry Policy
- Given 일시적 실패(429/5xx)가 발생했을 때
- When 재시도 정책이 실행되면
- Then 최대 3회 재시도 후 최종 상태가 기록된다.

### AC-6 Auditability
- Given 운영자가 승인/발송 작업을 수행했을 때
- When 감사 로그를 조회하면
- Then actor, action, target, timestamp가 모두 확인 가능하다.

### AC-7 Consent Enforcement
- Given 수신자의 active opt-in이 없거나 opt-out 처리된 상태일 때
- When 발송/예약 API가 호출되면
- Then 해당 수신자는 발송 대상에서 제외되고 `consent_missing` 또는 `consent_revoked` 사유가 기록된다.

### AC-8 Idempotent Delivery
- Given 동일한 `idempotency_key`로 발송 요청이 중복 수신될 때
- When 시스템이 요청을 처리하면
- Then `deliveries` 레코드는 1건만 생성되고 실제 DM 발송도 1회만 수행된다.

## 9. Technical Constraints
- DM 발송은 Discord 공식 API/약관을 준수해야 한다.
- 수신 동의(opt-in) 없는 대상을 기본 발송 목록에 포함할 수 없다.
- 발송 속도 및 일일 한도는 설정 가능해야 한다.
- 민감 정보(API 키/토큰)는 시크릿 매니저 또는 환경 변수로만 관리한다.
- 모든 발송 이벤트는 멱등 키(idempotency key)로 중복 발송을 방지한다.
- 예약 스케줄 기준 시간대는 캠페인 단위(`campaign.timezone`)로 고정한다.

## 10. Data Model (MVP)
- `campaigns`: id, name, goal, status, channel(discord), timezone, created_at
- `creators`: id, campaign_id, name, tone, topic, style_sample
- `posts`: id, creator_id, content, version, status, approved_by, approved_at
- `recipients`: id, campaign_id, channel_user_id, latest_opt_in_status
- `recipient_consents`: id, recipient_id, status(opt_in/opt_out), consent_source, proof_ref, consented_at, revoked_at
- `deliveries`: id, post_id, recipient_id, status, error_code, attempts, idempotency_key, scheduled_at, sent_at
- `audit_logs`: id, actor_id, action, target_type, target_id, metadata, timestamp

## 11. Metrics (SLO)
- 페르소나 생성 시간: 5개 생성 기준 p95 <= 60초
- 포스트 생성 시간: 페르소나 1개 기준 p95 <= 30초
- DM 발송 성공률: 유효 opt-in 대상 기준 >= 95%
- 중복 발송률: 0%
- 승인/발송 감사 로그 적재율: 100%

## 12. Risks & Mitigations
- 정책 위반/스팸 리스크: opt-in 강제, 발송 상한, 금칙어 필터
- API 한도 초과: 큐+레이트 리미터+백오프
- 품질 편차: 승인 워크플로우와 템플릿 가드레일
- 중복 발송: 멱등 키 및 상태 머신 검증

## 13. Implementation Phases
### Phase 1: Foundation
- 프로젝트 구조, 환경 변수, 기본 DB 스키마, 인증/권한 기초
- Discord DM provider 인터페이스 및 기본 클라이언트 구성

### Phase 2: Creator + Post Generation
- 페르소나 생성기, 포스트 생성기, 규칙 검증

### Phase 3: Approval + DM Delivery
- 승인 플로우, 예약/발송 큐, 재시도 정책
- 상태머신 및 멱등키 처리 구현

### Phase 4: Observability + Hardening
- 대시보드, 감사 로그, 알림, 운영 안정화
- SLO 측정 리포트 및 운영 Runbook 작성

## 14. Definition of Done
- AC-1 ~ AC-8 전부 통과
- 승인 없는 발송이 시스템적으로 차단됨
- 발송/실패/재시도 로그가 조회 가능함
- 운영자 관점의 최소 대시보드가 제공됨
- Stage 환경 7일 관찰에서 SLO 미달 항목이 없음

## 15. Open Questions
- 승인 단계에 다중 승인(2인 승인)이 필요한가?
- v2 채널 확장 우선순위는 X vs Instagram 중 무엇인가?

## 16. Locked Defaults (2026-03-05)
- 기본 운영 범위: 단일 운영 서버(길드) 기준 Discord Bot 배포
- 기본 권한 원칙: 최소 권한(관리자 권한 금지), `bot` 스코프 + 발송 필수 권한만 허용
- 기본 인텐트: Privileged intent 미사용(필요 시 변경 승인 절차 후 확장)
- 수신자 입력 포맷(v1): `CSV only`
- CSV 필수 컬럼(v1): `channel_user_id,opt_in_status,consent_source,proof_ref`
