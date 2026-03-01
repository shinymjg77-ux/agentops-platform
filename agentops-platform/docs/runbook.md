# 운영 런북 (Runbook)

## 1) 목적
- 단일 머신(Docker Desktop) 환경에서 AgentOps 플랫폼을 안정적으로 기동/복구/점검하기 위한 운영 절차를 제공한다.

## 2) 사전 조건
- Docker Desktop 실행 중
- 작업 경로: `/Users/junlab/workspace/projects/agentops-platform`
- 기본 포트:
  - Dashboard: `3000`
  - API: `8000`
  - Prometheus: `9090`
  - Grafana: `3001`
  - Loki: `3100`
  - Alert Sink: `18080`

## 3) 기본 운영 명령
- 전체 기동:
  - `make up`
- 상태 확인:
  - `make ps`
- 로그 확인:
  - `make logs`
- 전체 중지:
  - `make down`
- E2E 점검:
  - `make test-e2e`
  - `make test-e2e-phase2`
  - `make test-e2e-phase3`
- 멀티워커(선택) 기동:
  - `docker compose -f infra/compose/docker-compose.yml --profile multiworker up -d --build worker-2`

## 4) 정상 상태 점검 절차
1. 컨테이너 상태 확인
   - `docker compose -f infra/compose/docker-compose.yml ps`
2. 헬스체크 확인
   - `curl -fsS http://localhost:8000/healthz`
   - `curl -fsS http://localhost:8000/readyz`
3. 모니터링 스택 확인
   - `curl -fsS http://localhost:9090/-/healthy`
   - `curl -fsS http://localhost:3001/api/health`
   - `curl -fsS http://localhost:18080/healthz`
4. 기능 E2E 확인
   - `make test-e2e`
   - `make test-e2e-phase2`
   - `make test-e2e-phase3`

## 5) 장애 대응
### A. API/대시보드 응답 없음
1. 상태 확인:
   - `docker compose -f infra/compose/docker-compose.yml ps`
2. 해당 서비스 로그 확인:
   - `docker logs --tail 200 agentops-api`
   - `docker logs --tail 200 agentops-dashboard`
3. 단일 서비스 재기동:
   - `docker compose -f infra/compose/docker-compose.yml up -d --build api dashboard`
4. 헬스체크 재확인:
   - `curl -fsS http://localhost:8000/healthz`

### B. 작업 생성은 되지만 실행 정체
1. 워커 상태/로그 확인:
   - `docker logs --tail 200 agentops-worker`
2. Redis/Postgres 상태 확인:
   - `docker logs --tail 100 agentops-redis`
   - `docker logs --tail 100 agentops-postgres`
3. 워커만 재기동:
   - `docker compose -f infra/compose/docker-compose.yml up -d --build worker`

### C. 실시간 반영(SSE) 미동작
1. API SSE 확인:
   - `curl -sN http://localhost:8000/v1/stream/tasks`
2. Dashboard 프록시 SSE 확인:
   - `curl -sN http://localhost:3000/api/stream/tasks`
3. 대시보드 재기동:
   - `docker compose -f infra/compose/docker-compose.yml up -d --build dashboard`

## 6) 운영 정책/주의사항
- Docker context는 `docker-desktop`으로 고정한다.
- 알림 웹훅은 선택 기능이다. 사용 시 `.env`에 `ALERT_WEBHOOK_URL`을 설정하고 `worker`를 재기동한다.
- 기본 테스트 경로는 `alert-sink` 서비스(`http://alert-sink:8080/events`)를 사용한다.
- 민감정보(토큰/비밀번호/개인키)는 로그/문서에 기록하지 않는다.

## 7) 복구 기준
- 최소 복구 완료 기준:
  - API `healthz/readyz` 정상
  - Dashboard 접속 가능
  - `make test-e2e` 통과
  - (Phase3 환경) `make test-e2e-phase2`, `make test-e2e-phase3` 통과
