# Secrets and Rotation Guide

## Scope
- `DISCORD_BOT_TOKEN`
- DB 계정 비밀번호
- 기타 외부 API 키

## Rules
- `.env`는 로컬 개발 전용으로 사용한다.
- 운영 환경은 시크릿 매니저를 사용한다.
- 토큰/비밀번호는 저장소에 커밋하지 않는다.

## Rotation Steps (Discord Bot Token)
1. Discord Developer Portal에서 토큰 재발급
2. 시크릿 매니저 값 업데이트
3. API/Worker 롤링 재시작
4. `/health` 및 발송 샌드박스 테스트로 정상 동작 확인
5. 이전 토큰 폐기 확인

## Rotation Cadence
- 정기 회전: 90일
- 비정기 회전: 유출 의심 즉시

## Verification Checklist
- [ ] 서비스 시작 정상
- [ ] DM 발송 샌드박스 테스트 통과
- [ ] 감사 로그에 토큰 값 미노출 확인
