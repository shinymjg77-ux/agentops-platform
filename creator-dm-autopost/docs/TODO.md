# TODO (PRD Execution Backlog)

## 0. 선행 의사결정 (Blockers)
- [x] B-1. 백엔드 기술 스택 확정 (`Python/FastAPI` 선택)
- [x] B-2. DB/큐 확정 (`PostgreSQL` + `Redis` 확정)
- [x] B-3. Discord Bot 운영 서버/권한 범위 확정 (단일 운영 서버, 최소 권한, privileged intent 미사용)
- [x] B-4. 수신자 업로드 포맷 확정 (v1: CSV only, 필수 컬럼 `channel_user_id,opt_in_status,consent_source,proof_ref`)

## 1. Phase 1: Foundation
- [x] P1-1. 서비스 골격 생성 (`api`, `worker`, `domain`, `infra`)
- [x] P1-2. 로컬 인프라 구성 (`docker-compose`: db, redis)
- [x] P1-3. DB 마이그레이션 초기화 (`campaigns`, `creators`, `posts`, `recipients`, `recipient_consents`, `deliveries`, `audit_logs`)
- [x] P1-4. RBAC 구현 (`admin`, `operator`, `viewer`) [AC-6 기반]
- [x] P1-5. `DMProvider` 인터페이스와 `DiscordDMProvider` 기본 구현
- [x] P1-6. 시크릿/환경변수 정책 정리 (`.env.example`, key rotation 가이드)
- [x] P1-7. 감사 로그 미들웨어(승인/발송 액션 추적) [AC-6]
- [x] P1-8. 발송 멱등키 유니크 제약/인덱스 설계 [AC-8 기반]
- [x] P1-9. CI 기본 파이프라인 (lint, unit test, migration test)
- [x] P1-10. Phase 1 종료 점검 문서 작성 (`docs/phase1-checklist.md`)

## 2. Phase 2: Creator + Post Generation
- [x] P2-1. 크리에이터 페르소나 생성 API 구현 [AC-1]
- [x] P2-2. 포스트 초안 생성 API 구현 [AC-2]
- [x] P2-3. 금지어/길이/톤 검증 모듈 구현 [AC-2]
- [x] P2-4. 포스트 버전 관리 (`posts.version`) 및 수정 이력 저장
- [x] P2-5. 생성 성능 측정(p95) 메트릭 수집 [SLO]

## 3. Phase 3: Approval + DM Delivery
- [x] P3-1. 승인 워크플로우 API (`draft -> pending_approval -> approved`) [AC-3]
- [x] P3-2. 상태머신 검증기 구현 (`invalid_state_transition` 차단) [AC-3, AC-8]
- [x] P3-3. 예약 발송 스케줄러 구현 (`campaign.timezone` 기준) [AC-4]
- [x] P3-4. Discord DM 발송 워커 구현 [AC-4]
- [x] P3-5. 재시도 정책 구현 (429/5xx, 최대 3회, 백오프) [AC-5]
- [x] P3-6. 동의 상태 필터링 (`consent_missing`, `consent_revoked`) [AC-7]
- [x] P3-7. 멱등 발송 처리 및 중복 요청 보호 [AC-8]

## 4. Phase 4: Observability + Hardening
- [x] P4-1. 발송 상태 대시보드(queued/sending/sent/failed/retrying/cancelled)
- [x] P4-2. 감사 로그 조회 UI/엔드포인트 [AC-6]
- [x] P4-3. 실패 코드 분류/알림 연동 (운영자 알림)
- [x] P4-4. SLO 리포트 자동 생성 (주간)
- [ ] P4-5. Stage 7일 관찰 및 DoD 체크리스트 완료

## 5. 테스트 체크리스트 (AC Traceability)
- [x] T-1. AC-1: 5개 페르소나 60초 내 생성 테스트
- [x] T-2. AC-2: 금지어/길이 제한 검증 테스트
- [x] T-3. AC-3: 승인 없는 발송 차단 테스트
- [x] T-4. AC-4: 예약 시각 도래 발송 테스트
- [x] T-5. AC-5: 재시도 3회 후 상태 기록 테스트
- [x] T-6. AC-6: 감사 로그 필수 필드 검증 테스트
- [x] T-7. AC-7: opt-in/opt-out 발송 필터링 테스트
- [x] T-8. AC-8: 동일 멱등키 중복 발송 방지 테스트
