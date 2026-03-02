# Phase 4 테스트 계획 (초안 v1)

## 1) 목적
- 인증/권한/RBAC/감사로그/백업이력 API의 최소 운영 신뢰성을 검증한다.
- Phase1~3 회귀 영향이 없는지 함께 확인한다.

## 2) 실행 대상
- 스크립트: `scripts/e2e_phase4.sh`
- 타겟: `make test-e2e-phase4`
- 회귀 세트:
  - `make test-e2e`
  - `make test-e2e-phase2`
  - `make test-e2e-phase3`

## 3) 사전 조건
- `make up` 완료
- API `healthz/readyz` 정상
- 기본 관리자 시드 계정 사용 가능

## 4) 핵심 시나리오
1. 비인증 접근 거부
   - `GET /v1/auth/me` -> `401`
2. 관리자 로그인
   - `POST /v1/auth/login` -> `200`, `access_token` 반환
3. viewer 권한 제한
   - viewer 로그인 후 `POST /v1/projects` -> `403`
4. 프로젝트 생성/조회
   - admin으로 프로젝트 생성 후 목록 조회에서 확인
5. 감사 로그 생성/조회
   - `auth.login`, `project.create` 이벤트 확인
6. 백업 이력 조회
   - `GET /v1/backups/runs` 응답 구조 확인

## 5) 합격 기준
- `make test-e2e-phase4` PASS
- 회귀 세트(phase1~3) PASS
- API 로그에 인증 오류 폭증/예외 스택 없음

## 6) 실패 시 점검 순서
1. 컨테이너 상태:
   - `make ps`
2. API 로그:
   - `docker logs --tail 300 agentops-api`
3. 환경값 점검:
   - `AUTH_MODE`, `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD`
4. 재기동:
   - `docker compose -f infra/compose/docker-compose.yml up -d --build api dashboard worker`

## 7) 후속 보강 항목
- `AUTH_MODE=required` 별도 강제 모드 테스트 분리
- 토큰 만료/변조 케이스 추가
- 감사 로그 권한 경계 테스트 강화
