# creator-dm-autopost

Creator generation -> post draft -> approval -> Discord DM automated delivery pipeline.

## Stack (v1)
- Backend: FastAPI
- Database: PostgreSQL
- Queue/Retry: Redis
- Channel: Discord DM (Bot)

## Structure
- `api/`: FastAPI service
- `worker/`: delivery worker skeleton
- `domain/`: shared domain statuses
- `infra/`: local docker compose for postgres/redis
- `docs/`: PRD, backlog, checklists

## Quick start
1. Copy `.env.example` to `.env`
2. Start infra:
   ```bash
   docker compose -f infra/docker-compose.yml up -d
   ```
3. Install API deps and run:
   ```bash
   pip install -r api/requirements.txt
   cd api && alembic upgrade head && cd ..
   uvicorn app.main:app --app-dir api --host 0.0.0.0 --port 8000 --reload
   ```
4. Run worker:
   ```bash
   pip install -r worker/requirements.txt
   python worker/app/worker.py
   ```

## RBAC quick check
- Header: `X-Role: admin|operator|viewer`
- `GET /rbac/me` -> any valid role
- `POST /rbac/operator` -> `operator` or `admin`
- `DELETE /rbac/admin` -> `admin` only

## Discord Provider (Phase 1 skeleton)
- Interface: `api/app/dm/provider.py` (`DMProvider`)
- Implementation: `api/app/dm/discord.py` (`DiscordDMProvider`)
- Default behavior: `DISCORD_DM_DRY_RUN=true` (실제 발송 없이 성공 응답 시뮬레이션)

## Creator Generation API (Phase 2)
- Endpoint: `POST /creators/generate`
- Authz: `X-Role: operator|admin`
- Required body fields: `campaign_goal`, `target_segment`
- Optional body fields: `count(1~10, default 5)`, `banned_keywords`, `channel_constraints`, `diversity_mode`

## Post Draft API (Phase 2)
- Endpoint: `POST /posts/draft`
- Authz: `X-Role: operator|admin`
- Required body fields: `persona_name`, `persona_tone`, `persona_topic`, `template`
- Behavior: template 변수 치환 -> 금지어 필터 -> 길이 제한 적용 -> 검증 결과(`violations`) 반환

## Post Version APIs (Phase 2)
- `POST /posts/versioned`: 초안 버전 1 생성
- `POST /posts/{post_id}/revisions`: 수정 버전 추가
- `GET /posts/{post_id}/revisions`: 버전 히스토리 조회 (`viewer` 이상)

## Generation Metrics (Phase 2)
- Endpoint: `GET /metrics/generation`
- Fields: `creator_count`, `creator_p95_ms`, `post_count`, `post_p95_ms`

## Approval Workflow API (Phase 3)
- `POST /approval/posts/{post_id}/submit` -> `draft -> pending_approval`
- `POST /approval/posts/{post_id}/approve` -> `pending_approval -> approved`
- `POST /approval/posts/{post_id}/transition` -> 상태머신 검증 적용 (`invalid_state_transition` 반환)
- `GET /approval/posts/{post_id}` -> 현재 승인 상태 조회

## Consent API (Phase 3)
- `POST /consents/{recipient_id}` -> opt-in/opt-out 상태 기록
- `GET /consents/{recipient_id}` -> 현재 동의 상태 조회

## Delivery API (Phase 3)
- `POST /deliveries/schedule` -> 승인+동의+멱등키 검증 후 예약 생성
- `POST /deliveries/process-due` -> due/retrying 건 처리(재시도 포함)
- `GET /deliveries/{delivery_id}` -> 발송 상태 조회
- `GET /deliveries/idempotency/{idempotency_key}` -> 멱등키 기반 조회

## Audit Logs (Phase 4)
- `GET /audit/logs?limit=100` -> actor/action/target/timestamp 기반 감사 로그 조회

## Dashboard (Phase 4)
- `GET /dashboard/delivery-summary` -> status별 건수 + 최근 실패 목록 조회

## Alerts (Phase 4)
- `GET /alerts/failures` -> 실패 코드 분류(`rate_limit`, `provider_transient`, `provider_fatal`) 조회

## Weekly SLO Report (Phase 4)
- Script: `scripts/generate_slo_report.py`
- Manual run: `python scripts/generate_slo_report.py`
- Scheduled workflow: `.github/workflows/weekly-slo-report.yml`
