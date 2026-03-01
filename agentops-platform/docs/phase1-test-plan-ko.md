# Phase 1 테스트 계획

## 1. 목표
- Core 실행/재시도/로그/알림/실시간의 기본 동작을 자동 검증한다.

## 2. 자동화 스크립트
- `scripts/e2e_phase1.sh`
- 실행: `make test-e2e`

## 3. 시나리오
1. API health/ready 정상
2. 성공 경로: 작업 생성 -> success -> completion log
3. 수동 재시도: retry -> runs 반영
4. 실패 경로: force_fail -> retry log -> failure log
5. 알림 경로: `task_retry`, `task_failure` webhook 수신
6. 계약 검증: 잘못된 payload에 `422` 반환

## 4. 합격 기준
- 전 시나리오 PASS
- 실패 시 에러 원인 로그 즉시 확인 가능

## 5. 수동 점검 항목
- Dashboard 홈/상세에서 실시간 갱신 체감 확인
- Grafana/Prometheus/Loki 접속 상태 확인
