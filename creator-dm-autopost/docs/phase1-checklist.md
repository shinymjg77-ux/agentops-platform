# Phase 1 Checklist

## 목적
Foundation 단계 완료 여부를 객관적으로 판정한다.

## 완료 조건
- [ ] 서비스가 로컬에서 실행된다 (`api`, `worker`)
- [ ] DB/Redis 컨테이너가 정상 기동된다
- [ ] 초기 마이그레이션이 성공한다
- [ ] RBAC(`admin`, `operator`, `viewer`) 권한 테스트가 통과한다
- [ ] `DMProvider` + `DiscordDMProvider` 기본 연결 테스트가 통과한다
- [ ] 감사 로그 미들웨어가 승인/발송 이벤트를 기록한다
- [ ] `idempotency_key` 유니크 제약 테스트가 통과한다
- [ ] CI에서 lint/unit/migration 테스트가 통과한다

## 증빙 링크
- [ ] 실행 로그 파일:
- [ ] 테스트 리포트:
- [ ] 마이그레이션 결과:
- [ ] CI 실행 URL:

## 판정
- [ ] Phase 1 Pass
- [ ] Phase 1 Rework Required

## 작성자
- 이름:
- 날짜:
