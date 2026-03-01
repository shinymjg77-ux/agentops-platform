# 1단계 계획(Phase 1): Core + Task Contract + MVP 대시보드

## 1. 단계 목표
- Task Contract 기반 실행 파이프라인과 실시간 모니터링 UI를 갖춘 MVP를 완성한다.
- 범위: 단일 머신, 단일 운영자, Docker Compose 기반 운영.

## 2. 완료 기준(Definition of Done)
- `docker compose up`으로 핵심 서비스가 정상 기동된다.
- API로 작업 생성 시 큐에 등록되고 워커가 실행한다.
- 상태 전이와 로그가 저장되고 대시보드에 실시간 반영된다.
- 실패 시 재시도 정책이 적용되고 알림 채널 1개 이상으로 전송된다.

## 3. 산출물
- 모노레포 기본 구조
  - `apps/dashboard` (Next.js)
  - `apps/api` (FastAPI)
  - `workers/celery_worker`
  - `infra/docker-compose.yml`
  - `infra/prometheus`, `infra/grafana`, `infra/loki`
- `Task Contract v1` 명세서 (`docs/task-contract-v1.md`)
- 초기 DB 스키마 및 마이그레이션
- 샘플 작업 템플릿 2개
  - `sample_echo_task`
  - `sample_http_check_task`
- 운영 문서 (`docs/runbook.md`)

## 4. 작업 백로그
1. 레포 구조/기본 설정 파일 초기화
2. Compose에 Postgres/Redis/API/Worker/Dashboard 추가
3. FastAPI 헬스체크 및 작업 생성/조회 API 구현
4. 템플릿/작업/실행/이벤트/로그 DB 모델 구현
5. Celery 워커 및 큐 연동
6. API 입력단 Task Contract 검증기 구현
7. 상태 이벤트 저장/발행 파이프라인 구현
8. 샘플 작업 템플릿 1(에코) 구현
9. 샘플 작업 템플릿 2(HTTP 체크) 구현
10. 재시도 정책(횟수/백오프) 적용
11. WebSocket 또는 SSE 실시간 업데이트 구현
12. 대시보드 요약 카드/작업 목록 화면 구현
13. 실행 상세(로그 스트림) 화면 구현
14. Telegram 또는 Slack 알림 연동
15. API/워커 Prometheus 메트릭 노출
16. Grafana 기본 KPI 대시보드 구성
17. Loki 로그 수집 파이프라인 구성
18. E2E 스모크 테스트(정상 경로) 작성
19. 실패 경로 테스트(재시도/알림) 작성
20. README/Runbook 정리 및 MVP 인수 점검

## 5. 권장 일정(7영업일)
- Day 1: 레포 구조 + Compose + 기본 기동
- Day 2: API + DB 스키마/마이그레이션
- Day 3: 워커 + Task Contract + 샘플 작업
- Day 4: 재시도 + 이벤트 + 실시간 스트림
- Day 5: 대시보드 핵심 화면 구현
- Day 6: 알림 + 관측성(Prometheus/Grafana/Loki)
- Day 7: 테스트/문서/안정화/인수

## 6. 리스크 및 대응
- 실시간 UI 구현 지연
  - 대응: 초기에는 SSE로 단순화 후 WebSocket 확장
- 관측성 스택 설정 복잡도
  - 대응: Phase 1은 최소 패널과 핵심 메트릭만 적용
- 계약 스키마 이탈
  - 대응: API 입력 검증 강제 + 테스트 케이스 고정

## 7. 인수 체크리스트
- [x] 단일 명령으로 전체 서비스 기동
- [x] 작업 생성부터 완료까지 E2E 동작
- [x] 상태/로그 실시간 표시
- [x] 실패 재시도 자동 동작
- [x] 실패 알림 발송 확인
- [x] Grafana 기본 지표 확인
- [x] 재기동/복구 절차 문서화 완료
