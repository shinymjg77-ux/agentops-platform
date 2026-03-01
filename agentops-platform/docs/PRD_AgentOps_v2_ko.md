# PRD v2: 재사용 가능한 24/7 에이전트 작업 모니터링 플랫폼

## 1. 제품 개요
- 제품명(가칭): `AgentOps Platform`
- 목표: 항상 켜져 있는 단일 머신에서 멀티에이전트 작업을 실행/모니터링하고, 앞으로 추가될 작업도 동일한 방식으로 계속 수용한다.
- 핵심 가치:
  - 현재/미래 작업을 단일 대시보드에서 운영
  - 실패 감지 및 복구 자동화
  - 템플릿 기반 재사용 구조로 신규 작업 온보딩 비용 최소화

## 2. 문제 정의
- 자동화 작업이 늘어날수록 실행 방식, 로그 형식, 오류 처리 방식이 분산된다.
- 표준 인터페이스가 없으면 모니터링 정확도가 떨어지고 운영 부담이 커진다.
- 신규 작업이 들어와도 코어를 수정하지 않고 붙일 수 있는 구조가 필요하다.

## 3. 목표 / 비목표
### 목표
- 현재 작업뿐 아니라 미래 작업까지 동일 프레임워크로 수용
- 공통 상태 모델 강제: `queued`, `running`, `success`, `failed`, `retrying`, `canceled`
- 상태/로그/알림/이력을 중앙화
- 24시간 운영 기준의 안정성(재시도, 헬스체크, 자동 복구) 확보

### 비목표(MVP)
- 멀티테넌시/세분화 RBAC
- 멀티 노드 오토스케일링
- 결제/정산 기능

## 4. 사용자 및 시나리오
- 사용자: 단일 운영자(개발자 본인)
- 시나리오:
  - 템플릿/어댑터 방식으로 신규 작업 등록
  - 대시보드에서 수동 실행/스케줄 실행
  - 실시간 상태/로그 확인
  - 실패 작업 재시도 및 알림 수신

## 5. 기능 요구사항
### A. 미래 작업 수용
- `Task Contract v1` 정의:
  - 입력 스키마(JSON)
  - 상태 이벤트 스키마
  - 로그 포맷
  - 결과 아티팩트 메타데이터
- 신규 작업은 어댑터 추가로 통합 가능해야 하며 코어 수정은 최소화한다.
- 템플릿 레지스트리(버전 관리 포함) 제공

### B. 실행/오케스트레이션
- Celery + Redis 기반 비동기 실행
- 작업별 재시도 정책(최대 횟수, 백오프, 타임아웃)
- 수동 제어(취소/재실행/재시도)
- 우선순위/동시성 제어(선택)

### C. 대시보드 모니터링
- 전체 현황 카드(실행중/대기/실패/완료)
- 에이전트 상태 및 heartbeat
- 작업별 실시간 로그 스트리밍
- 실패 원인/재시도율/성공률 지표

### D. 이력/분석
- 기간/상태/템플릿/태그 기준 검색
- SLA 지표: 성공률, 평균 실행시간, MTTD, MTTR
- 템플릿/어댑터 버전별 실행 비교

### E. 알림
- 실패/지연/복구 이벤트 알림
- Telegram 또는 Slack Webhook(초기 1개 이상)
- 템플릿 그룹별 라우팅(기본 규칙)

## 6. 비기능 요구사항
- 가용성: 재부팅 후 자동 기동
- 신뢰성: at-least-once + 멱등성 가이드
- 성능: 상태 반영 1~3초(로컬 기준)
- 보안: SSH 키 기반 운영, `.env` 비밀값 분리
- 유지보수성: 코어/어댑터 경계 명확화 및 버전 추적

## 7. 기술 스택
- Frontend: Next.js + Tailwind + shadcn/ui
- Backend API: FastAPI
- Worker: Celery
- Queue/Broker: Redis
- Database: PostgreSQL
- Realtime: WebSocket(SSE 보조)
- Observability: Prometheus + Grafana + Loki
- Infra: Docker Compose
- Reverse Proxy: Caddy 또는 Nginx
- Alerting: Telegram/Slack Webhook

## 8. 아키텍처 원칙
1. Core/Adapter 분리
   - Core: 큐, 상태관리, 로그, 알림, 분석
   - Adapter: 작업별 비즈니스 로직
2. 이벤트 중심 파이프라인
   - 상태 변화는 이벤트로 저장하고 UI/알림/지표가 공통 소비
3. 버전 가시성
   - 각 실행 이력에 템플릿/어댑터 버전 기록

## 9. 데이터 모델(초안)
- `task_templates`: id, name, version, input_schema, retry_policy, timeout_sec
- `tasks`: id, template_id, params_json, status, priority, schedule_type
- `task_runs`: id, task_id, attempt, started_at, finished_at, status, error_code, error_message
- `task_events`: id, run_id, ts, event_type, payload_json
- `task_logs`: id, run_id, ts, level, message, source
- `agents`: id, name, status, last_heartbeat, capacity
- `alerts`: id, run_id, channel, event_type, sent_at, status

## 10. MVP 범위
- Task Contract v1
- 샘플 템플릿 2종 이상
- 실행/재시도/취소
- 실시간 상태 및 로그
- 알림 채널 1개 연동
- 기본 KPI 패널(성공률/실패율/평균시간)

## 11. 성공 지표
- 신규 작업 온보딩 시간: 1일 이내
- 공통 대시보드 커버리지: 90% 이상
- MTTD: 1분 이내
- MTTR: 10분 이내
- 월간 수동 개입 횟수: 50% 이상 감소

## 12. 리스크 및 대응
- 장시간 실행 중 메모리 누수
  - 헬스체크 + 자동 재시작 + 워커 재생성 정책
- 큐 적체
  - 동시성 제한 + 타임아웃 + 우선순위 큐
- 로그 폭증
  - 보관 기간/용량 정책(TTL) 적용
- 외부 노출 보안
  - Tailscale 또는 IP 제한 + 프록시 보안 설정

## 13. 로드맵
1. Phase 1: Core + Task Contract + MVP 대시보드
2. Phase 2: 템플릿 레지스트리/버전 비교/고급 검색
3. Phase 3: 정책형 스케줄러/멀티머신 확장(필요 시)

## 15. 실행 원칙(업데이트)
- 기능 우선 원칙:
  - Phase 3 기간에는 디자인 리뉴얼보다 운영 기능 완성도를 우선한다.
  - UI는 기존 패턴을 유지하되 정보 밀도/가독성 개선 수준으로 제한한다.
- 문서 우선 원칙:
  - 각 Phase 착수 전 `계획/데이터모델/API/UI/테스트` 문서 세트를 먼저 확정한다.
  - 구현 중 변경사항은 세션 로그와 작업 회고 로그에 즉시 반영한다.

## 14. 수용 기준
1. 신규 어댑터 추가 시 코어 수정 없이 통합 가능
2. 모든 실행이 공통 상태 모델로 UI에 표시
3. 실패 시 재시도 정책 및 알림이 동작
4. 이력에서 버전/실패 원인을 역추적 가능
