# Phase 1 UI 상세 스펙

## 1. 홈(`/`)
- 최근 작업 목록 테이블
- 컬럼: 템플릿, 상태, 생성시각, Task ID/Celery ID
- 동작: 상세 페이지 이동
- 실시간: SSE 이벤트 수신 시 자동 refresh

## 2. 작업 상세(`/tasks/{taskId}`)
- 작업 메타 카드
- 재시도 버튼
- 실행 이력 리스트
- 실패 실행만 보기 토글(`failed_only=1`)
- 실행 비교(`compare_run_id`) 패널
- 실행 로그 테이블(run_id 필터)
- 실시간: SSE 이벤트 수신 시 자동 refresh

## 3. 상태 색상 규칙
- success: green
- failure: red
- started/running: blue
- queued/retry: neutral

## 4. UX 기준
- 상세 진입 시 최신 run 자동 선택
- URL query 기반 상태 유지(run_id/compare_run_id/failed_only)
- 빈 상태/오류 상태 메시지 명시
