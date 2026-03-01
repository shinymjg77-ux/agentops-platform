# Phase 3 테스트 계획

## 1) 자동화
- 스크립트: `scripts/e2e_phase3.sh`
- 타겟: `make test-e2e-phase3`

## 2) 시나리오
1. 스케줄 생성 후 자동 실행 발생
2. 스케줄 pause 시 실행 중단 확인
3. run-now 호출 시 즉시 실행
4. 실패율 정책 위반 시 액션 발동
5. 워커 heartbeat 중단 시 `offline` 전환
6. 멀티워커에서 실행 분산 확인

## 3) 회귀 범위
- `make test-e2e` (Phase1)
- `make test-e2e-phase2` (Phase2)
- `make test-e2e-phase3` (Phase3)

## 4) 합격 기준
- 필수 시나리오 전부 PASS
- 정책 액션/스케줄 실행/노드 상태가 DB와 UI에서 일치
