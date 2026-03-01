# Phase 2 UI 스펙

## 1. 정보 구조
- 상단 네비게이션 메뉴 추가:
  - `대시보드`
  - `템플릿 레지스트리`
  - `실행 검색`
  - `버전 비교`

## 2. 템플릿 레지스트리 화면
## 경로
- `/templates`

## 주요 컴포넌트
- 검색바(name/display_name)
- 템플릿 목록 테이블
  - 이름, 표시명, 기본버전, 활성여부, 최근 수정시각
- 템플릿 생성 버튼
- 템플릿 상세 패널(우측 또는 별도 페이지)
  - 버전 목록
  - 기본버전 변경
  - 버전 활성/비활성

## 3. 실행 검색 화면
## 경로
- `/runs/search`

## 필터
- 기간(from/to)
- 상태(status)
- 템플릿명
- 템플릿 버전
- 오류 키워드

## 결과 테이블
- run_id, task_id, template_name, template_version, status, started_at, finished_at, duration
- 클릭 시 기존 상세(`/tasks/{task_id}?run_id=...`)로 이동

## 4. 버전 비교 화면
## 경로
- `/templates/compare`

## 입력
- 템플릿 선택
- 버전 다중 선택(최소 2)
- 기간 선택

## 출력
- 요약 카드:
  - total_runs
  - success_rate
  - failure_rate
  - avg_duration_ms
  - p95_duration_ms
- 비교 테이블(버전별 행)
- 보조 차트(선택)

## 5. 공통 UX 원칙
- 상태 색상 규칙 고정(success: green, failure: red, running: blue)
- 필터 상태를 URL query로 유지(새로고침/공유 가능)
- 기본 정렬: `started_at DESC`
- 빈 상태/오류 상태 메시지 명확화
