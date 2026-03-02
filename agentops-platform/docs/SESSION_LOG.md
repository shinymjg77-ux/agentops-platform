# 세션 로그 (Session Log)

작성 기준:
- 이 파일은 현재 프로젝트 세션의 진행 내역을 누적 기록한다.
- 이후 작업 기록은 새 파일을 만들지 않고, 이 파일 하단에 계속 이어서 추가한다.
- 항목은 `완료/오류/다음`을 포함한다.

---

## 2026-03-01 18:08 KST - 세션 누적 요약 (현재 시점)

### 1) 문서/기획
- 한국어 PRD 작성 완료:
  - `docs/PRD_AgentOps_v2_ko.md`
- 1단계 계획서 작성 완료:
  - `docs/Phase1_Plan_ko.md`
- Task Contract 문서 반영 완료:
  - `docs/task-contract-v1.md`
- 작업 회고 로그 체계 도입 완료:
  - `docs/WORK_LOG.md`

### 2) 프로젝트/인프라 초기화
- 프로젝트 루트 구성 완료:
  - `apps/api`, `apps/dashboard`, `workers/celery_worker`, `infra/*`
- Docker Compose 스택 구성 완료:
  - `postgres`, `redis`, `api`, `worker`, `dashboard`, `prometheus`, `grafana`, `loki`
- Docker Desktop 컨텍스트 기준으로 실행 검증 완료.

### 3) 백엔드/API
- 작업 API 구현 완료:
  - `POST /v1/tasks`
  - `GET /v1/tasks`
  - `GET /v1/tasks/{task_id}`
  - `POST /v1/tasks/{task_id}/retry`
  - `GET /v1/tasks/{task_id}/logs`
  - `GET /v1/templates`
- 상태/이력 저장 완료:
  - `tasks`, `task_runs`, `task_logs` 테이블 자동 생성
- 최신 run 기준 목록 조회로 중복 노출 개선 완료.

### 4) 워커
- 샘플 태스크 2종 구현 완료:
  - `sample_echo_task`
  - `sample_http_check_task`
- Celery signal 기반 자동 로그/상태 반영 완료:
  - `task_prerun`, `task_postrun`, `task_retry`, `task_failure`
- 선택형 웹훅 알림 연동 완료:
  - `ALERT_WEBHOOK_URL` 설정 시 실패/재시도 이벤트 전송

### 5) 대시보드
- 작업 목록 화면 구현 완료:
  - 템플릿/상태/시간/Celery Task ID 표시
- 작업 상세 화면 구현 완료:
  - 실행 메타데이터 + 로그 테이블 표시
- 상세 화면 재시도 버튼 구현 완료:
  - `/tasks/[taskId]/retry` route handler 연결

### 6) 계약 강제화(Task Contract Enforcement)
- 템플릿별 payload 검증 강제 완료(Pydantic):
  - `sample_echo_task`: `message`, `force_fail`
  - `sample_http_check_task`: `url`, `timeout_sec(1~60)`
- 유효하지 않은 payload는 `422` 반환하도록 적용 완료.
- `GET /v1/templates`에서 `payload_schema` 노출 완료.

### 7) 운영/실행 상태
- 현재 Compose 서비스 상태: 전체 Up (API/Worker/Dashboard/DB/Redis/Monitoring)
- 기본 기능 E2E 검증:
  - 작업 생성 → 실행 → 상태 반영
  - 실패/재시도 로그 반영
  - 상세 페이지 로그 확인

---

## 2026-03-01 18:08 KST - 본 요청 처리 결과
- 완료:
  - 이 세션의 주요 작성/구현 내용을 본 파일에 기록 완료.
  - 이후부터는 이 파일(`docs/SESSION_LOG.md`)에 이어서 기록하도록 기준 설정 완료.
- 오류:
  - 없음.
- 다음:
  - 이후 작업 시 본 파일 하단에 타임스탬프 단위로 누적 기록.

## 2026-03-01 18:30 KST - run 이력 분리 조회 확장

### 작업 내용
- API 확장:
  - `GET /v1/tasks/{task_id}/runs` 추가 (run 이력 목록)
  - `GET /v1/tasks/{task_id}/logs`에 `run_id` 필터 추가
  - 내부 상태 동기화 로직을 `sync_and_persist_run()`으로 공통화
- 대시보드 확장:
  - 상세 페이지에 `실행 이력` 리스트 추가
  - run 선택 링크(`?run_id=...`)로 로그를 run 단위 조회 가능하게 변경
  - 선택된 run ID를 화면에 명시

### 검증
- 작업 생성 후 `runs` 엔드포인트에서 run 목록 조회 성공
- `logs?run_id=<RUN_ID>` 필터 조회 성공
- 상세 페이지에서 실행 이력 링크/선택 실행 ID/로그 렌더링 확인

### 완료/오류
- 완료:
  - run 단위 이력/로그 조회 기능 구현 및 동작 검증 완료
- 오류:
  - 없음

### 다음
- run 결과 비교(이전 실행 vs 최신 실행) UI 추가
- 실패 run만 빠르게 보는 필터 추가

## 2026-03-01 18:32 KST - run 비교/필터 UI + API 안정성 보완

### 작업 내용
- 대시보드 상세 페이지 확장:
  - `failed_only=1` 쿼리 기반 `실패 실행만 보기` 토글 추가
  - 선택 실행과 다른 실행을 `compare_run_id`로 비교하는 `실행 결과 비교` 패널 추가
  - 실행 이력 목록에서 `이 실행과 비교` 링크 제공
- API 안정성 보완:
  - `POST /v1/tasks` 간헐 500 원인(`redis transport import deadlock`) 확인
  - API 시작 시 `redis.auth.token` 선로딩으로 초기 import deadlock 완화 적용

### 검증
- API 재빌드 후 헬스체크 정상 확인
- 작업 생성 → 재시도 → 실행 이력 조회 성공
- 상세 페이지에서 다음 UI 렌더링 확인:
  - `실패 실행만 보기`
  - `이 실행과 비교`
  - `실행 결과 비교`

### 완료/오류
- 완료:
  - 실패 run 필터, run 결과 비교 UI 구현 완료
  - 작업 생성 간헐 500 이슈 대응 적용 및 재검증 완료
- 오류:
  - 없음

### 다음
- 비교 패널에 payload/result 차이(diff) 요약 표시 추가
- 실패 run 전용 빠른 액션(재시도, 로그 고정 링크) 추가

## 2026-03-01 18:45 KST - SSE 실시간 반영(홈/상세) 구현

### 작업 내용
- API:
  - `GET /v1/stream/tasks` SSE 엔드포인트 추가
  - `task_logs`의 최신 ID 변화를 감지해 `task_update` 이벤트 전송
  - heartbeat 주기 전송으로 연결 유지
- Dashboard:
  - `GET /api/stream/tasks` 프록시 route 추가 (브라우저 동일 출처 구독용)
  - `LiveTaskStream` 클라이언트 컴포넌트 추가
  - 홈(`/`)과 상세(`/tasks/[taskId]`)에서 SSE `task_update` 수신 시 `router.refresh()` 자동 반영

### 검증
- `curl -sN http://localhost:8000/v1/stream/tasks`에서 `ready/task_update` 이벤트 확인
- `curl -sN http://localhost:3000/api/stream/tasks` 프록시 이벤트 확인
- 작업 생성 시 스트림에 `task_update` 이벤트 발생 확인
- API/대시보드 컨테이너 재빌드/재기동 후 정상 동작 확인

### 완료/오류
- 완료:
  - 실시간 반영 1차(SSE 기반 자동 refresh) 구현 완료
- 오류:
  - 없음

### 다음
- SSE 이벤트 payload를 활용한 부분 업데이트(전체 refresh 최소화)
- 상세 페이지 로그 영역만 부분 갱신하도록 클라이언트 분리

## 2026-03-01 18:58 KST - Phase1 E2E 테스트 자동화

### 작업 내용
- 테스트 스크립트 추가:
  - `scripts/e2e_phase1.sh`
  - 검증 범위:
    - API health/ready
    - 성공 경로(create -> success -> completion log)
    - 수동 재시도 경로(retry -> runs 반영)
    - 실패 경로(force_fail -> retry log -> failure log)
    - Task Contract 검증 실패(422)
- 실행 진입점 추가:
  - `Makefile`에 `test-e2e` 타겟 추가

### 검증
- `make test-e2e` 실행 결과 `PASS: phase1 e2e checks passed` 확인

### 완료/오류
- 완료:
  - 정상/실패 핵심 경로 E2E 자동 검증 가능 상태로 전환
- 오류:
  - 없음

### 다음
- `docs/runbook.md` 작성 및 재기동/복구 절차 정리
- Phase1 인수 체크리스트 문서상 완료 표시 반영

## 2026-03-01 19:06 KST - 운영 런북 작성 및 인수 체크리스트 갱신

### 작업 내용
- 운영 문서 추가:
  - `docs/runbook.md` 신규 작성
  - 포함 범위: 기본 운영 명령, 정상 점검, 장애 대응(API/워커/SSE), 복구 기준
- Phase1 체크리스트 갱신:
  - `docs/Phase1_Plan_ko.md` 인수 체크리스트 상태 업데이트
  - 현재 미완료 항목은 `실패 알림 발송 확인` 1건만 유지
- README 업데이트:
  - runbook 경로 및 최신 진행 상태 반영

### 검증
- Prometheus/Grafana health API 확인
- 기존 `make test-e2e` 재사용 가능 상태 확인

### 완료/오류
- 완료:
  - 운영 런북 문서화 완료
  - Phase1 잔여 항목이 문서상 명확해짐(알림 발송 확인만 남음)
- 오류:
  - 없음

### 다음
- 테스트용 webhook receiver를 붙여 `task_retry/task_failure` 실제 수신 검증 후 체크리스트 마지막 항목 완료 처리

## 2026-03-01 19:18 KST - webhook 수신 검증 완료(Phase1 최종)

### 작업 내용
- 테스트용 웹훅 수신기 추가:
  - `apps/alert_sink` (FastAPI)
  - 엔드포인트: `POST /events`, `GET /events`, `DELETE /events`, `GET /healthz`
- Compose 확장:
  - `alert-sink` 서비스 추가(`18080:8080`)
  - worker 기본 `ALERT_WEBHOOK_URL`을 `http://alert-sink:8080/events`로 연결
- E2E 확장:
  - `scripts/e2e_phase1.sh`에 webhook 수신 검증 단계(`task_retry`, `task_failure`) 추가
  - `make test-e2e`에서 알림 수신까지 통합 검증
- 문서 갱신:
  - `README.md`, `runbook.md`, `Phase1_Plan_ko.md` 반영

### 검증
- `docker compose ... up -d --build worker alert-sink` 후 `make test-e2e` 통과
- alert-sink 이벤트 목록에서 `task_retry`, `task_failure` 확인

### 완료/오류
- 완료:
  - Phase1 체크리스트 전 항목 완료 처리
- 오류:
  - 없음

### 다음
- Phase2(템플릿 레지스트리/버전 비교/고급 검색) 진입 준비

## 2026-03-01 19:48 KST - Phase2 문서 세트 작성 완료

### 작업 내용
- Phase2 문서 세트 신규 작성:
  - `docs/Phase2_Plan_ko.md`
  - `docs/phase2-data-model-ko.md`
  - `docs/phase2-api-spec-ko.md`
  - `docs/phase2-ui-spec-ko.md`
  - `docs/phase2-test-plan-ko.md`
- README 반영:
  - `Phase 2 문서 세트` 섹션 추가로 문서 진입 경로 정리

### 검증
- 문서 파일 생성/경로 확인 완료
- 기존 PRD/Phase1 계획과 충돌 없는지 구조 점검 완료

### 완료/오류
- 완료:
  - Phase2 개발 착수 전 필요한 기획/명세 문서 세트 준비 완료
- 오류:
  - 없음

### 다음
- Phase2 구현 1순위: DB 스키마 확장 + 템플릿 레지스트리 API 초안

## 2026-03-01 19:52 KST - Phase1 문서 세트 상세화

### 작업 내용
- Phase1 상세 문서 추가:
  - `docs/phase1-data-model-ko.md`
  - `docs/phase1-api-spec-ko.md`
  - `docs/phase1-ui-spec-ko.md`
  - `docs/phase1-test-plan-ko.md`
- README 업데이트:
  - `Phase 1 문서 세트(상세)` 섹션 추가

### 검증
- 문서 파일 생성 확인
- README 링크/경로 확인

### 완료/오류
- 완료:
  - Phase1/Phase2 모두 동일 밀도의 문서 체계로 정렬 완료
- 오류:
  - 없음

### 다음
- Phase2 구현 착수(DB 스키마 확장부터)

## 2026-03-01 20:05 KST - Phase2 구현 완료(DB/API/UI/E2E)

### 작업 내용
- API/DB:
  - `task_templates`, `task_template_versions` 테이블 및 인덱스/시드 추가
  - `tasks`, `task_runs`에 `template_id/template_version/adapter_version/error_*` 컬럼 확장
  - 신규 API 구현:
    - `GET/POST/PATCH /v1/template-registry...`
    - `POST /v1/template-registry/{template_id}/versions`
    - `POST /v1/template-registry/{template_id}/versions/{version}/set-default`
    - `POST /v1/template-registry/{template_id}/versions/{version}/activate`
    - `GET /v1/search/runs`
    - `GET /v1/analytics/template-versions`
  - 기존 API 확장:
    - `POST /v1/tasks`에 `template_version` 지원
    - `GET /v1/tasks`, `GET /v1/tasks/{id}`, `GET /v1/tasks/{id}/runs`에 버전 메타 노출
- Worker:
  - 실패 시 `task_runs.error_code/error_message` 기록 확장
- Dashboard:
  - 공통 네비게이션 추가(대시보드/레지스트리/검색/비교)
  - 템플릿 레지스트리 페이지(`/templates`) + 생성 폼
  - 템플릿 상세/버전관리 페이지(`/templates/[templateId]`)
  - 실행 검색 페이지(`/runs/search`)
  - 버전 비교 페이지(`/templates/compare`)
- 테스트:
  - `scripts/e2e_phase2.sh` 추가
  - `Makefile`에 `test-e2e-phase2` 타겟 추가

### 검증
- `make test-e2e` 통과(Phase1 회귀)
- `make test-e2e-phase2` 통과(레지스트리/검색/분석 경로)
- 대시보드 신규 경로 응답 확인(`/templates`, `/runs/search`)

### 완료/오류
- 완료:
  - Phase2 계획서 체크리스트 전 항목 완료
- 오류:
  - 구현 중 DB backfill 쿼리 참조 오류 1건 발생 후 수정/재검증 완료

### 다음
- Phase3 후보 기능(정책형 스케줄러, 멀티머신 확장) 우선순위 합의 후 착수

## 2026-03-01 19:27 KST - Phase3 문서 세트 및 PRD 원칙 업데이트

### 작업 내용
- Phase3 문서 세트 작성:
  - `docs/Phase3_Plan_ko.md`
  - `docs/phase3-data-model-ko.md`
  - `docs/phase3-api-spec-ko.md`
  - `docs/phase3-ui-spec-ko.md`
  - `docs/phase3-test-plan-ko.md`
- PRD 업데이트:
  - `docs/PRD_AgentOps_v2_ko.md`에 실행 원칙(기능 우선, 문서 우선) 섹션 추가
- README 업데이트:
  - Phase3 문서 세트 인덱스 추가

### 검증
- 문서 파일 생성/경로 확인 완료
- PRD/README에 Phase3 문서 링크 반영 확인

### 완료/오류
- 완료:
  - Phase3 구현 착수 전 문서 기준선 확정 완료
- 오류:
  - 없음

### 다음
- Phase3 구현 1순위: 스케줄러 DB/API 코어부터 착수

## 2026-03-01 19:42 KST - Phase3 구현/검증 완료

### 작업 내용
- API/DB:
  - 스케줄/정책/에이전트 테이블 및 인덱스 반영(`task_schedules`, `schedule_runs`, `policy_rules`, `policy_actions`, `agents`)
  - 스케줄 CRUD + run-now + 실행이력 API 구현
  - 정책 룰/액션 API 및 백그라운드 스케줄러 루프 구현
  - 에이전트 heartbeat 수집/조회 API 구현
  - 정책 `scope_type=schedule` 필터 SQL 버그 수정(`EXISTS ... task_logs` 기반)
- Worker:
  - heartbeat 전송 루프 추가(API `/v1/agents/heartbeat`)
  - `tasks.py` 들여쓰기 오류 수정 후 재배포
- Dashboard:
  - `/schedules`, `/policies`, `/agents` 페이지 및 액션 route 추가
- Infra:
  - `worker-2` 서비스(`multiworker` profile) 추가
- 테스트:
  - `scripts/e2e_phase3.sh` 추가
  - `Makefile`에 `test-e2e-phase3` 타겟 추가

### 검증
- `make test-e2e` 통과
- `make test-e2e-phase2` 통과
- `make test-e2e-phase3` 통과
- `GET /v1/agents`에서 `agentops-worker-1`, `agentops-worker-2` heartbeat 확인
- 멀티워커 분산 실행 확인(양쪽 worker 로그에서 task 수신 확인)

### 완료/오류
- 완료:
  - Phase3 인수 체크리스트 항목 전부 완료 처리
- 오류:
  - 1) worker `IndentationError` 1건 발생 -> 즉시 수정
  - 2) 정책 schedule scope SQL 버그 1건 발생 -> 조건식 수정 후 E2E 재통과

### 다음
- 원격 저장소 커밋/푸시 단위 정리

## 2026-03-02 10:20 KST - Phase4 코드/문서 정리 및 검증

### 작업 내용
- 점검:
  - 실행 컨테이너가 구버전 API를 바라봐 `/v1/auth/*`가 404였던 상태를 확인
  - `make up` 재빌드 후 Phase4 인증 엔드포인트 반영 확인
- 코드 정리:
  - `.gitignore`에 `.omx/` 추가(로컬 CLI 상태 파일 제외)
- 문서 정리:
  - `README.md` Phase4 문서/상태 최신화
  - `docs/runbook.md`에 Phase4 E2E 및 인증 모드 정책 반영
  - `docs/Phase4_Plan_ko.md` 체크리스트 진행 상태 반영
  - Phase4 누락 문서 3종 추가:
    - `docs/phase4-data-model-ko.md`
    - `docs/phase4-ui-spec-ko.md`
    - `docs/phase4-test-plan-ko.md`

### 검증
- `make test-e2e` 통과
- `make test-e2e-phase2` 통과
- `make test-e2e-phase3` 통과
- `make test-e2e-phase4` 통과

### 완료/오류
- 완료:
  - Phase4 1차 구현 기준으로 코드/문서/테스트 정리 완료
- 오류:
  - 없음(재빌드 전 404 이슈는 해소)

### 다음
- 정리된 변경분 커밋/푸시
