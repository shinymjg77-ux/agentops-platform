# AgentOps Platform

24시간 운영을 전제로 한 멀티에이전트 작업 모니터링 플랫폼 프로젝트입니다.

## 디렉터리 구조

```text
.
├── apps
│   ├── api
│   ├── alert_sink
│   └── dashboard
├── workers
│   └── celery_worker
├── infra
│   ├── compose
│   ├── prometheus
│   ├── grafana
│   └── loki
└── docs
```

## 실행 방법(초기)

```bash
make up
```

또는:

```bash
docker compose -f infra/compose/docker-compose.yml up -d --build
```

E2E 테스트 실행:

```bash
make test-e2e
make test-e2e-phase2
make test-e2e-phase3
```

멀티워커(선택) 실행:

```bash
docker compose -f infra/compose/docker-compose.yml --profile multiworker up -d --build worker-2
```

## 접속 주소

- Dashboard: `http://localhost:3000`
- API Health: `http://localhost:8000/healthz`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (admin/admin)
- Loki: `http://localhost:3100`
- Alert Sink(테스트용 웹훅 수신기): `http://localhost:18080`

## API 빠른 테스트

작업 생성:

```bash
curl -sS -X POST http://localhost:8000/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "template_name": "sample_echo_task",
    "payload": {"message": "hello"}
  }'
```

작업 목록 조회:

```bash
curl -sS http://localhost:8000/v1/tasks
```

작업 로그 조회:

```bash
curl -sS http://localhost:8000/v1/tasks/<TASK_ID>/logs
```

run 단위 로그 조회:

```bash
curl -sS "http://localhost:8000/v1/tasks/<TASK_ID>/logs?run_id=<RUN_ID>"
```

실행 이력 조회:

```bash
curl -sS http://localhost:8000/v1/tasks/<TASK_ID>/runs
```

실시간 이벤트 스트림(SSE):

```bash
curl -sN http://localhost:8000/v1/stream/tasks
```

작업 재시도:

```bash
curl -sS -X POST http://localhost:8000/v1/tasks/<TASK_ID>/retry
```

웹훅 알림(선택):
- `.env`에 `ALERT_WEBHOOK_URL` 설정 시 워커가 실패/재시도 이벤트를 POST 전송
- 기본값은 테스트용 `alert-sink`(`http://alert-sink:8080/events`)로 설정됨

## 작업 회고 로그

- 경로: `docs/WORK_LOG.md`
- 목적: 작업 중 문제/미흡점/개선안을 누적 기록
- 새 항목 추가:

```bash
scripts/add_work_log.sh "제목"
```

## 세션 기록 파일

- 경로: `docs/SESSION_LOG.md`
- 규칙: 세션 진행 기록은 이 파일 하단에 계속 누적(새 세션 파일 추가 생성 지양)

## 운영 문서

- Runbook: `docs/runbook.md`

## Phase 2 문서 세트

- 계획: `docs/Phase2_Plan_ko.md`
- 데이터 모델: `docs/phase2-data-model-ko.md`
- API 스펙: `docs/phase2-api-spec-ko.md`
- UI 스펙: `docs/phase2-ui-spec-ko.md`
- 테스트 계획: `docs/phase2-test-plan-ko.md`

## Phase 3 문서 세트

- 계획: `docs/Phase3_Plan_ko.md`
- 데이터 모델: `docs/phase3-data-model-ko.md`
- API 스펙: `docs/phase3-api-spec-ko.md`
- UI 스펙: `docs/phase3-ui-spec-ko.md`
- 테스트 계획: `docs/phase3-test-plan-ko.md`

## Phase 4 문서 세트

- PRD: `docs/PRD_AgentOps_v3_ko.md`
- 계획: `docs/Phase4_Plan_ko.md`

## Phase 1 문서 세트(상세)

- 데이터 모델: `docs/phase1-data-model-ko.md`
- API 스펙: `docs/phase1-api-spec-ko.md`
- UI 스펙: `docs/phase1-ui-spec-ko.md`
- 테스트 계획: `docs/phase1-test-plan-ko.md`

## 현재 상태

- 1단계: 프로젝트 골격 생성 완료
- 2단계: 인프라 기본 기동 구성 완료(초안)
- 3단계: 작업 생성/조회 API + DB 스키마 + 큐 연동 초안 완료
- 4단계: 실행 로그 자동 적재(task_logs) + 상세 로그 화면 완료
- 5단계: 상세 화면 재시도 버튼 + 실패/재시도 웹훅 알림 완료
- 6단계: run 이력 조회 + run 단위 로그 필터링 완료
- 7단계: 실패 run 필터 + run 결과 비교 패널 완료
- 8단계: SSE 실시간 갱신(홈/상세 자동 refresh) 완료
- 9단계: Phase1 E2E 스모크/실패 경로 테스트 스크립트 완료
- 10단계: webhook 수신 검증(alert-sink)까지 포함한 Phase1 체크리스트 완료
- 11단계: Phase2(템플릿 레지스트리/버전 비교/고급 검색) 구현 및 E2E 완료
- 12단계: Phase3(스케줄/정책/에이전트/멀티워커) 구현 및 E2E 완료
