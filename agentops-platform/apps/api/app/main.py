import os
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import psycopg

try:
    # Prevent intermittent import deadlock in redis transport on first send_task call.
    import redis.auth.token  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    pass

from celery import Celery
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, ValidationError

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agentops:agentops@postgres:5432/agentops")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = FastAPI(title="AgentOps API", version="0.3.0")
REQUEST_COUNTER = Counter("agentops_api_requests_total", "Total API requests")
TASK_CREATED_COUNTER = Counter("agentops_tasks_created_total", "Total tasks created")
celery_app = Celery("agentops_api", broker=REDIS_URL, backend=REDIS_URL)
_SCHEDULER_THREAD_STARTED = False


class TaskCreateRequest(BaseModel):
    template_name: str = "sample_echo_task"
    template_version: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TaskCreateResponse(BaseModel):
    task_id: UUID
    run_id: UUID
    celery_task_id: str
    status: str


class EchoPayload(BaseModel):
    message: str | None = None
    force_fail: bool = False


class HttpCheckPayload(BaseModel):
    url: str = "http://api:8000/healthz"
    timeout_sec: int = Field(default=5, ge=1, le=60)


class TemplateCreateRequest(BaseModel):
    name: str
    display_name: str
    description: str | None = None


class TemplateUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class TemplateVersionCreateRequest(BaseModel):
    version: str
    adapter_name: str
    adapter_version: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any] | None = None
    timeout_sec: int | None = Field(default=None, ge=1, le=3600)
    set_default: bool = False


class ScheduleCreateRequest(BaseModel):
    name: str
    template_name: str
    template_version: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    # Phase3 MVP: "every:<seconds>" format only (e.g. every:60)
    rrule_text: str = "every:60"
    timezone: str = "Asia/Seoul"
    is_active: bool = True


class ScheduleUpdateRequest(BaseModel):
    payload: dict[str, Any] | None = None
    rrule_text: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class PolicyCreateRequest(BaseModel):
    name: str
    scope_type: str = "template"
    scope_ref: str | None = None
    metric_key: str = "failure_rate"
    operator: str = "gte"
    threshold_value: float
    window_minutes: int = Field(default=15, ge=1, le=1440)
    cooldown_minutes: int = Field(default=30, ge=1, le=1440)
    action_type: str = "pause_schedule"
    action_payload: dict[str, Any] | None = None


class PolicyUpdateRequest(BaseModel):
    threshold_value: float | None = None
    window_minutes: int | None = Field(default=None, ge=1, le=1440)
    cooldown_minutes: int | None = Field(default=None, ge=1, le=1440)
    is_active: bool | None = None


PAYLOAD_MODEL_BY_ADAPTER: dict[str, type[BaseModel]] = {
    "tasks.sample_echo_task": EchoPayload,
    "tasks.sample_http_check_task": HttpCheckPayload,
}

PAYLOAD_MODEL_BY_TEMPLATE_NAME: dict[str, type[BaseModel]] = {
    "sample_echo_task": EchoPayload,
    "sample_http_check_task": HttpCheckPayload,
}


@contextmanager
def db_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


def now_utc() -> datetime:
    return datetime.now(UTC)


def _template_seed_id(name: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"agentops-template:{name}")


def _template_version_seed_id(name: str, version: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"agentops-template:{name}:{version}")


def _seed_registry(conn: psycopg.Connection) -> None:
    samples = [
        {
            "name": "sample_echo_task",
            "display_name": "샘플 에코",
            "description": "입력 payload를 그대로 반환",
            "version": "1.0.0",
            "adapter_name": "tasks.sample_echo_task",
            "adapter_version": "builtin",
            "input_schema": EchoPayload.model_json_schema(),
            "retry_policy": {"max_retries": 3, "backoff": True},
            "timeout_sec": 60,
        },
        {
            "name": "sample_http_check_task",
            "display_name": "샘플 HTTP 체크",
            "description": "URL 상태코드 확인",
            "version": "1.0.0",
            "adapter_name": "tasks.sample_http_check_task",
            "adapter_version": "builtin",
            "input_schema": HttpCheckPayload.model_json_schema(),
            "retry_policy": {"max_retries": 3, "backoff": True},
            "timeout_sec": 60,
        },
    ]

    for item in samples:
        template_id = _template_seed_id(item["name"])
        conn.execute(
            """
            INSERT INTO task_templates (id, name, display_name, description, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, TRUE, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                updated_at = EXCLUDED.updated_at
            """,
            (
                template_id,
                item["name"],
                item["display_name"],
                item["description"],
                now_utc(),
                now_utc(),
            ),
        )

        version_id = _template_version_seed_id(item["name"], item["version"])
        conn.execute(
            """
            INSERT INTO task_template_versions (
                id, template_id, version, adapter_name, adapter_version,
                input_schema_json, retry_policy_json, timeout_sec,
                is_default, is_active, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, TRUE, %s)
            ON CONFLICT (template_id, version) DO UPDATE
            SET adapter_name = EXCLUDED.adapter_name,
                adapter_version = EXCLUDED.adapter_version,
                input_schema_json = EXCLUDED.input_schema_json,
                retry_policy_json = EXCLUDED.retry_policy_json,
                timeout_sec = EXCLUDED.timeout_sec,
                is_active = TRUE
            """,
            (
                version_id,
                template_id,
                item["version"],
                item["adapter_name"],
                item["adapter_version"],
                Jsonb(item["input_schema"]),
                Jsonb(item["retry_policy"]),
                item["timeout_sec"],
                now_utc(),
            ),
        )

        conn.execute(
            """
            UPDATE task_template_versions
            SET is_default = CASE WHEN version = %s THEN TRUE ELSE FALSE END
            WHERE template_id = %s
            """,
            (item["version"], template_id),
        )


def initialize_schema() -> None:
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id UUID PRIMARY KEY,
                template_name TEXT NOT NULL,
                payload_json JSONB NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_runs (
                id UUID PRIMARY KEY,
                task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                celery_task_id TEXT,
                status TEXT NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ,
                result_json JSONB
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_templates (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_template_versions (
                id UUID PRIMARY KEY,
                template_id UUID NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
                version TEXT NOT NULL,
                adapter_name TEXT NOT NULL,
                adapter_version TEXT,
                input_schema_json JSONB NOT NULL,
                retry_policy_json JSONB,
                timeout_sec INT,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL,
                UNIQUE(template_id, version)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_logs (
                id BIGSERIAL PRIMARY KEY,
                task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                run_id UUID NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
                ts TIMESTAMPTZ NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json JSONB
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_schedules (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                template_id UUID NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
                template_name TEXT NOT NULL,
                template_version TEXT,
                payload_json JSONB NOT NULL,
                rrule_text TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                next_run_at TIMESTAMPTZ,
                last_run_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id UUID PRIMARY KEY,
                schedule_id UUID NOT NULL REFERENCES task_schedules(id) ON DELETE CASCADE,
                task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
                planned_at TIMESTAMPTZ NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ,
                status TEXT NOT NULL,
                error_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                hostname TEXT,
                status TEXT NOT NULL,
                last_heartbeat_at TIMESTAMPTZ NOT NULL,
                capacity INT NOT NULL DEFAULT 1,
                queue_names TEXT[] NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_rules (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                scope_type TEXT NOT NULL,
                scope_ref TEXT,
                metric_key TEXT NOT NULL,
                operator TEXT NOT NULL,
                threshold_value DOUBLE PRECISION NOT NULL,
                window_minutes INT NOT NULL DEFAULT 15,
                cooldown_minutes INT NOT NULL DEFAULT 30,
                action_type TEXT NOT NULL,
                action_payload_json JSONB,
                last_triggered_at TIMESTAMPTZ,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_actions (
                id UUID PRIMARY KEY,
                rule_id UUID NOT NULL REFERENCES policy_rules(id) ON DELETE CASCADE,
                action_type TEXT NOT NULL,
                action_payload_json JSONB,
                executed_at TIMESTAMPTZ NOT NULL,
                status TEXT NOT NULL,
                message TEXT
            )
            """
        )

        conn.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS template_id UUID")
        conn.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS template_version TEXT")
        conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name='tasks' AND constraint_name='tasks_template_id_fkey'
                ) THEN
                    ALTER TABLE tasks
                    ADD CONSTRAINT tasks_template_id_fkey
                    FOREIGN KEY (template_id) REFERENCES task_templates(id);
                END IF;
            END $$
            """
        )

        conn.execute("ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS template_id UUID")
        conn.execute("ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS template_version TEXT")
        conn.execute("ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS adapter_version TEXT")
        conn.execute("ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS error_code TEXT")
        conn.execute("ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS error_message TEXT")
        conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name='task_runs' AND constraint_name='task_runs_template_id_fkey'
                ) THEN
                    ALTER TABLE task_runs
                    ADD CONSTRAINT task_runs_template_id_fkey
                    FOREIGN KEY (template_id) REFERENCES task_templates(id);
                END IF;
            END $$
            """
        )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON task_runs(task_id)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_task_runs_celery_task_id ON task_runs(celery_task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_logs_task_id_ts ON task_logs(task_id, ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_logs_run_id_ts ON task_logs(run_id, ts DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_templates_active ON task_templates(is_active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_template_versions_template_id ON task_template_versions(template_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_runs_template_version ON task_runs(template_id, template_version, started_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_runs_status_started_at ON task_runs(status, started_at DESC)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_template_default_unique ON task_template_versions(template_id) WHERE is_default"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_schedules_active_next ON task_schedules(is_active, next_run_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedule_runs_schedule_started ON schedule_runs(schedule_id, started_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agents_last_heartbeat ON agents(last_heartbeat_at DESC)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_rules_active ON policy_rules(is_active)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policy_actions_rule_executed ON policy_actions(rule_id, executed_at DESC)"
        )

        _seed_registry(conn)

        conn.execute(
            """
            UPDATE tasks t
            SET template_id = tt.id,
                template_version = COALESCE(t.template_version, tv.version)
            FROM task_templates tt
            JOIN task_template_versions tv
              ON tv.template_id = tt.id
             AND tv.is_default = TRUE
            WHERE t.template_name = tt.name
              AND t.template_id IS NULL
            """
        )

        conn.execute(
            """
            UPDATE task_runs tr
            SET template_id = t.template_id,
                template_version = COALESCE(tr.template_version, t.template_version),
                adapter_version = COALESCE(tr.adapter_version, tv.adapter_version)
            FROM tasks t
            LEFT JOIN task_template_versions tv
              ON tv.template_id = t.template_id
             AND tv.version = t.template_version
            WHERE tr.task_id = t.id
              AND (tr.template_id IS NULL OR tr.template_version IS NULL OR tr.adapter_version IS NULL)
            """
        )

        conn.commit()


def resolve_template_version(conn: psycopg.Connection, template_name: str, template_version: str | None) -> dict[str, Any]:
    if template_version:
        row = conn.execute(
            """
            SELECT tt.id, tt.name, tt.display_name, ttv.version, ttv.adapter_name,
                   ttv.adapter_version, ttv.input_schema_json, ttv.retry_policy_json, ttv.timeout_sec
            FROM task_templates tt
            JOIN task_template_versions ttv ON ttv.template_id = tt.id
            WHERE tt.name = %s AND ttv.version = %s AND tt.is_active = TRUE AND ttv.is_active = TRUE
            """,
            (template_name, template_version),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT tt.id, tt.name, tt.display_name, ttv.version, ttv.adapter_name,
                   ttv.adapter_version, ttv.input_schema_json, ttv.retry_policy_json, ttv.timeout_sec
            FROM task_templates tt
            JOIN task_template_versions ttv ON ttv.template_id = tt.id
            WHERE tt.name = %s AND ttv.is_default = TRUE AND tt.is_active = TRUE AND ttv.is_active = TRUE
            """,
            (template_name,),
        ).fetchone()

    if not row:
        detail = f"Template/version not found: {template_name}"
        if template_version:
            detail = f"Template/version not found: {template_name}@{template_version}"
        raise HTTPException(status_code=400, detail=detail)

    return {
        "template_id": row[0],
        "name": row[1],
        "display_name": row[2],
        "version": row[3],
        "adapter_name": row[4],
        "adapter_version": row[5],
        "input_schema": row[6],
        "retry_policy": row[7],
        "timeout_sec": row[8],
    }


def dispatch_task(adapter_name: str, payload: dict[str, Any]) -> str:
    normalized = adapter_name
    if not normalized.startswith("tasks."):
        normalized = f"tasks.{normalized}"

    if normalized == "tasks.sample_echo_task":
        msg = celery_app.send_task("tasks.sample_echo_task", kwargs={"payload": payload})
    elif normalized == "tasks.sample_http_check_task":
        msg = celery_app.send_task("tasks.sample_http_check_task", kwargs={"payload": payload})
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported adapter: {adapter_name}")
    return msg.id


def normalize_payload(template_name: str, adapter_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = PAYLOAD_MODEL_BY_ADAPTER.get(adapter_name)
    if model is None:
        model = PAYLOAD_MODEL_BY_TEMPLATE_NAME.get(template_name)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unsupported template/adapter: {template_name}/{adapter_name}")

    try:
        normalized = model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": f"Invalid payload for {template_name}", "errors": exc.errors()},
        ) from exc

    return normalized.model_dump()


def sync_run_status(celery_task_id: str) -> tuple[str, Any]:
    result = AsyncResult(celery_task_id, app=celery_app)
    state = result.state
    data: Any = None
    if result.ready():
        try:
            data = result.get(timeout=0.5)
        except Exception as exc:  # pragma: no cover
            data = {"error": str(exc)}
    return state.lower(), data


def sync_and_persist_run(
    conn: psycopg.Connection,
    *,
    task_id: UUID,
    run_id: UUID,
    celery_task_id: str,
) -> tuple[str, Any, datetime | None]:
    current_state, result_data = sync_run_status(celery_task_id)
    finished_at = now_utc() if current_state in {"success", "failure"} else None
    conn.execute(
        """
        UPDATE task_runs
        SET status = %s,
            finished_at = COALESCE(finished_at, %s),
            result_json = COALESCE(%s, result_json),
            error_message = CASE
                WHEN %s = 'failure' THEN COALESCE(error_message, %s)
                ELSE error_message
            END,
            error_code = CASE
                WHEN %s = 'failure' THEN COALESCE(error_code, 'runtime_error')
                ELSE error_code
            END
        WHERE id = %s
        """,
        (
            current_state,
            finished_at,
            Jsonb(result_data) if result_data is not None else None,
            current_state,
            str(result_data) if result_data is not None else None,
            current_state,
            run_id,
        ),
    )
    conn.execute("UPDATE tasks SET status = %s WHERE id = %s", (current_state, task_id))
    return current_state, result_data, finished_at


def append_task_log(
    conn: psycopg.Connection,
    *,
    task_id: UUID,
    run_id: UUID,
    level: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO task_logs (task_id, run_id, ts, level, message, metadata_json)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            task_id,
            run_id,
            now_utc(),
            level,
            message,
            Jsonb(metadata) if metadata is not None else None,
        ),
    )


def _parse_iso_dt(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _parse_every_seconds(rrule_text: str) -> int:
    if not rrule_text.startswith("every:"):
        raise HTTPException(status_code=422, detail="rrule_text must be 'every:<seconds>'")
    raw = rrule_text.split(":", 1)[1]
    try:
        seconds = int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid every seconds") from exc
    if seconds < 10 or seconds > 86400:
        raise HTTPException(status_code=422, detail="every seconds must be between 10 and 86400")
    return seconds


def _schedule_next_run(base: datetime, rrule_text: str) -> datetime:
    seconds = _parse_every_seconds(rrule_text)
    return base + timedelta(seconds=seconds)


def _execute_schedule_run(conn: psycopg.Connection, schedule_row: tuple[Any, ...]) -> None:
    # row: id, name, template_name, template_version, payload_json, rrule_text, next_run_at
    schedule_id = schedule_row[0]
    template_name = schedule_row[2]
    template_version = schedule_row[3]
    payload_json = schedule_row[4]
    rrule_text = schedule_row[5]
    planned_at = schedule_row[6]

    resolved = resolve_template_version(conn, template_name, template_version)
    normalized_payload = normalize_payload(template_name, resolved["adapter_name"], payload_json)
    created_at = now_utc()
    task_id = uuid4()
    run_id = uuid4()
    celery_task_id = dispatch_task(resolved["adapter_name"], normalized_payload)

    conn.execute(
        """
        INSERT INTO tasks (id, template_name, template_id, template_version, payload_json, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            task_id,
            template_name,
            resolved["template_id"],
            resolved["version"],
            Jsonb(normalized_payload),
            "queued",
            created_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO task_runs (
            id, task_id, celery_task_id, status, started_at,
            template_id, template_version, adapter_version
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            run_id,
            task_id,
            celery_task_id,
            "queued",
            created_at,
            resolved["template_id"],
            resolved["version"],
            resolved["adapter_version"],
        ),
    )
    append_task_log(
        conn,
        task_id=task_id,
        run_id=run_id,
        level="info",
        message="scheduled task queued",
        metadata={
            "schedule_id": str(schedule_id),
            "schedule_name": schedule_row[1],
            "template_name": template_name,
            "template_version": resolved["version"],
            "celery_task_id": celery_task_id,
        },
    )
    conn.execute(
        """
        INSERT INTO schedule_runs (id, schedule_id, task_id, planned_at, started_at, finished_at, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (uuid4(), schedule_id, task_id, planned_at, created_at, now_utc(), "queued"),
    )
    conn.execute(
        """
        UPDATE task_schedules
        SET last_run_at = %s,
            next_run_at = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (created_at, _schedule_next_run(created_at, rrule_text), now_utc(), schedule_id),
    )


def _evaluate_metric(metric_key: str, operator: str, actual: float, threshold: float) -> bool:
    if metric_key not in {"failure_rate", "queue_lag_ms", "retry_rate"}:
        return False
    if operator == "gt":
        return actual > threshold
    if operator == "gte":
        return actual >= threshold
    if operator == "lt":
        return actual < threshold
    if operator == "lte":
        return actual <= threshold
    if operator == "eq":
        return actual == threshold
    return False


def _policy_metric_value(conn: psycopg.Connection, rule_row: tuple[Any, ...]) -> tuple[float, str]:
    # rule: id, scope_type, scope_ref, metric_key, operator, threshold, window, cooldown, action_type, action_payload, last_triggered
    scope_type = rule_row[1]
    scope_ref = rule_row[2]
    metric_key = rule_row[3]
    window_minutes = int(rule_row[6])
    since = now_utc() - timedelta(minutes=window_minutes)

    where = ["tr.started_at >= %s"]
    params: list[Any] = [since]

    if scope_type == "template" and scope_ref:
        where.append("t.template_name = %s")
        params.append(scope_ref)
    elif scope_type == "schedule" and scope_ref:
        where.append(
            "EXISTS (SELECT 1 FROM task_logs tl WHERE tl.task_id = tr.task_id AND tl.metadata_json->>'schedule_name' = %s)"
        )
        params.append(scope_ref)

    where_sql = " AND ".join(where)

    if metric_key == "failure_rate":
        row = conn.execute(
            f"""
            SELECT
              COUNT(*)::float AS total,
              SUM(CASE WHEN tr.status = 'failure' THEN 1 ELSE 0 END)::float AS failures
            FROM task_runs tr
            JOIN tasks t ON t.id = tr.task_id
            WHERE {where_sql}
            """,
            tuple(params),
        ).fetchone()
        total = float(row[0] or 0)
        failures = float(row[1] or 0)
        value = (failures / total) * 100 if total > 0 else 0.0
        return value, f"failure_rate={value:.2f}% (window={window_minutes}m)"

    if metric_key == "retry_rate":
        row = conn.execute(
            f"""
            SELECT
              COUNT(*)::float AS total,
              SUM(CASE WHEN tr.status = 'retry' THEN 1 ELSE 0 END)::float AS retries
            FROM task_runs tr
            JOIN tasks t ON t.id = tr.task_id
            WHERE {where_sql}
            """,
            tuple(params),
        ).fetchone()
        total = float(row[0] or 0)
        retries = float(row[1] or 0)
        value = (retries / total) * 100 if total > 0 else 0.0
        return value, f"retry_rate={value:.2f}% (window={window_minutes}m)"

    # queue_lag_ms approximation with queued logs not started in recent window.
    row = conn.execute(
        f"""
        SELECT COALESCE(MAX(EXTRACT(EPOCH FROM (%s - tr.started_at)) * 1000), 0)
        FROM task_runs tr
        JOIN tasks t ON t.id = tr.task_id
        WHERE {where_sql} AND tr.status = 'queued'
        """,
        tuple([now_utc()] + params),
    ).fetchone()
    value = float(row[0] or 0)
    return value, f"queue_lag_ms={value:.0f} (window={window_minutes}m)"


def _execute_policy_action(conn: psycopg.Connection, rule_row: tuple[Any, ...], summary: str) -> None:
    rule_id = rule_row[0]
    scope_type = rule_row[1]
    scope_ref = rule_row[2]
    action_type = rule_row[8]
    action_payload = rule_row[9]

    status = "success"
    message = summary

    try:
        if action_type == "pause_schedule":
            if scope_type == "schedule" and scope_ref:
                conn.execute(
                    "UPDATE task_schedules SET is_active = FALSE, updated_at = %s WHERE name = %s",
                    (now_utc(), scope_ref),
                )
            elif scope_type == "template" and scope_ref:
                conn.execute(
                    """
                    UPDATE task_schedules
                    SET is_active = FALSE, updated_at = %s
                    WHERE template_name = %s
                    """,
                    (now_utc(), scope_ref),
                )
            message = f"{summary} -> schedules paused"
        elif action_type == "limit_retry":
            message = f"{summary} -> limit_retry noop (phase3 mvp)"
        elif action_type == "raise_alert":
            message = f"{summary} -> raise_alert noop (phase3 mvp)"
        else:
            status = "skipped"
            message = f"unsupported action_type: {action_type}"
    except Exception as exc:  # pragma: no cover
        status = "failed"
        message = f"action failed: {exc}"

    conn.execute(
        """
        INSERT INTO policy_actions (id, rule_id, action_type, action_payload_json, executed_at, status, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            rule_id,
            action_type,
            Jsonb(action_payload) if action_payload is not None else None,
            now_utc(),
            status,
            message,
        ),
    )
    conn.execute("UPDATE policy_rules SET last_triggered_at = %s WHERE id = %s", (now_utc(), rule_id))


def scheduler_tick() -> None:
    with db_conn() as conn:
        due_rows = conn.execute(
            """
            SELECT id, name, template_name, template_version, payload_json, rrule_text, next_run_at
            FROM task_schedules
            WHERE is_active = TRUE
              AND next_run_at IS NOT NULL
              AND next_run_at <= %s
            ORDER BY next_run_at ASC
            LIMIT 20
            """,
            (now_utc(),),
        ).fetchall()

        for row in due_rows:
            try:
                _execute_schedule_run(conn, row)
            except Exception as exc:  # pragma: no cover
                conn.execute(
                    """
                    INSERT INTO schedule_runs (id, schedule_id, task_id, planned_at, started_at, finished_at, status, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (uuid4(), row[0], None, row[6], now_utc(), now_utc(), "failed", str(exc)),
                )
                conn.execute(
                    "UPDATE task_schedules SET next_run_at = %s, updated_at = %s WHERE id = %s",
                    (_schedule_next_run(now_utc(), row[5]), now_utc(), row[0]),
                )

        rules = conn.execute(
            """
            SELECT id, scope_type, scope_ref, metric_key, operator, threshold_value,
                   window_minutes, cooldown_minutes, action_type, action_payload_json, last_triggered_at
            FROM policy_rules
            WHERE is_active = TRUE
            ORDER BY created_at ASC
            """
        ).fetchall()

        for rule in rules:
            cooldown_until = rule[10] + timedelta(minutes=int(rule[7])) if rule[10] else None
            if cooldown_until and cooldown_until > now_utc():
                continue

            actual, summary = _policy_metric_value(conn, rule)
            if _evaluate_metric(rule[3], rule[4], actual, float(rule[5])):
                _execute_policy_action(conn, rule, summary)

        conn.commit()


def _scheduler_loop() -> None:
    while True:
        try:
            scheduler_tick()
        except Exception:
            pass
        time.sleep(5)


def start_scheduler_thread_once() -> None:
    global _SCHEDULER_THREAD_STARTED
    if _SCHEDULER_THREAD_STARTED:
        return
    thread = threading.Thread(target=_scheduler_loop, daemon=True, name="agentops-scheduler-loop")
    thread.start()
    _SCHEDULER_THREAD_STARTED = True


@app.on_event("startup")
def startup_event() -> None:
    initialize_schema()
    start_scheduler_thread_once()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    REQUEST_COUNTER.inc()
    return {"status": "ok", "service": "api"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    REQUEST_COUNTER.inc()
    return {"status": "ready"}


@app.get("/v1/templates")
def templates() -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT tt.name, tt.description, ttv.version, ttv.input_schema_json
            FROM task_templates tt
            JOIN task_template_versions ttv ON ttv.template_id = tt.id
            WHERE tt.is_active = TRUE AND ttv.is_default = TRUE AND ttv.is_active = TRUE
            ORDER BY tt.name
            """
        ).fetchall()

    return [
        {
            "name": row[0],
            "description": row[1],
            "default_version": row[2],
            "payload_schema": row[3],
        }
        for row in rows
    ]


@app.get("/v1/template-registry")
def list_template_registry(active_only: bool = True, q: str | None = None) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        conditions: list[str] = []
        params: list[Any] = []

        if active_only:
            conditions.append("tt.is_active = TRUE")
        if q:
            conditions.append("(tt.name ILIKE %s OR tt.display_name ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"""
            SELECT tt.id, tt.name, tt.display_name, tt.description, tt.is_active,
                   tt.created_at, tt.updated_at,
                   ttv.version AS default_version
            FROM task_templates tt
            LEFT JOIN task_template_versions ttv
              ON ttv.template_id = tt.id
             AND ttv.is_default = TRUE
            {where_clause}
            ORDER BY tt.updated_at DESC, tt.name
            """,
            tuple(params),
        ).fetchall()

    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "display_name": row[2],
            "description": row[3],
            "is_active": row[4],
            "created_at": row[5].isoformat(),
            "updated_at": row[6].isoformat(),
            "default_version": row[7],
        }
        for row in rows
    ]


@app.post("/v1/template-registry", status_code=201)
def create_template_registry(req: TemplateCreateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    now = now_utc()
    template_id = uuid4()

    with db_conn() as conn:
        exists = conn.execute("SELECT 1 FROM task_templates WHERE name = %s", (req.name,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail=f"Template already exists: {req.name}")

        conn.execute(
            """
            INSERT INTO task_templates (id, name, display_name, description, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, TRUE, %s, %s)
            """,
            (template_id, req.name, req.display_name, req.description, now, now),
        )
        conn.commit()

    return {
        "id": str(template_id),
        "name": req.name,
        "display_name": req.display_name,
        "description": req.description,
        "is_active": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@app.get("/v1/template-registry/{template_id}")
def get_template_registry(template_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, display_name, description, is_active, created_at, updated_at
            FROM task_templates
            WHERE id = %s
            """,
            (template_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")

        versions = conn.execute(
            """
            SELECT version, adapter_name, adapter_version, input_schema_json,
                   retry_policy_json, timeout_sec, is_default, is_active, created_at
            FROM task_template_versions
            WHERE template_id = %s
            ORDER BY created_at DESC, version DESC
            """,
            (template_id,),
        ).fetchall()

    return {
        "id": str(row[0]),
        "name": row[1],
        "display_name": row[2],
        "description": row[3],
        "is_active": row[4],
        "created_at": row[5].isoformat(),
        "updated_at": row[6].isoformat(),
        "versions": [
            {
                "version": v[0],
                "adapter_name": v[1],
                "adapter_version": v[2],
                "input_schema": v[3],
                "retry_policy": v[4],
                "timeout_sec": v[5],
                "is_default": v[6],
                "is_active": v[7],
                "created_at": v[8].isoformat(),
            }
            for v in versions
        ],
    }


@app.patch("/v1/template-registry/{template_id}")
def update_template_registry(template_id: UUID, req: TemplateUpdateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        current = conn.execute(
            "SELECT display_name, description, is_active FROM task_templates WHERE id = %s",
            (template_id,),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Template not found")

        display_name = req.display_name if req.display_name is not None else current[0]
        description = req.description if req.description is not None else current[1]
        is_active = req.is_active if req.is_active is not None else current[2]

        conn.execute(
            """
            UPDATE task_templates
            SET display_name = %s,
                description = %s,
                is_active = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (display_name, description, is_active, now_utc(), template_id),
        )
        conn.commit()

    return get_template_registry(template_id)


@app.post("/v1/template-registry/{template_id}/versions", status_code=201)
def create_template_version(template_id: UUID, req: TemplateVersionCreateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        template_row = conn.execute(
            "SELECT name FROM task_templates WHERE id = %s",
            (template_id,),
        ).fetchone()
        if not template_row:
            raise HTTPException(status_code=404, detail="Template not found")

        dup = conn.execute(
            "SELECT 1 FROM task_template_versions WHERE template_id = %s AND version = %s",
            (template_id, req.version),
        ).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail=f"Version already exists: {req.version}")

        version_id = uuid4()
        conn.execute(
            """
            INSERT INTO task_template_versions (
                id, template_id, version, adapter_name, adapter_version,
                input_schema_json, retry_policy_json, timeout_sec,
                is_default, is_active, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            """,
            (
                version_id,
                template_id,
                req.version,
                req.adapter_name,
                req.adapter_version,
                Jsonb(req.input_schema),
                Jsonb(req.retry_policy) if req.retry_policy is not None else None,
                req.timeout_sec,
                req.set_default,
                now_utc(),
            ),
        )

        if req.set_default:
            conn.execute(
                """
                UPDATE task_template_versions
                SET is_default = CASE WHEN id = %s THEN TRUE ELSE FALSE END
                WHERE template_id = %s
                """,
                (version_id, template_id),
            )

        conn.execute("UPDATE task_templates SET updated_at = %s WHERE id = %s", (now_utc(), template_id))
        conn.commit()

    return get_template_registry(template_id)


@app.post("/v1/template-registry/{template_id}/versions/{version}/activate")
def activate_template_version(template_id: UUID, version: str, active: bool = True) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        updated = conn.execute(
            """
            UPDATE task_template_versions
            SET is_active = %s
            WHERE template_id = %s AND version = %s
            RETURNING version
            """,
            (active, template_id, version),
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Template version not found")
        conn.execute("UPDATE task_templates SET updated_at = %s WHERE id = %s", (now_utc(), template_id))
        conn.commit()

    return get_template_registry(template_id)


@app.post("/v1/template-registry/{template_id}/versions/{version}/set-default")
def set_default_template_version(template_id: UUID, version: str) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM task_template_versions WHERE template_id = %s AND version = %s",
            (template_id, version),
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Template version not found")

        conn.execute(
            """
            UPDATE task_template_versions
            SET is_default = CASE WHEN version = %s THEN TRUE ELSE FALSE END
            WHERE template_id = %s
            """,
            (version, template_id),
        )
        conn.execute("UPDATE task_templates SET updated_at = %s WHERE id = %s", (now_utc(), template_id))
        conn.commit()

    return get_template_registry(template_id)


@app.post("/v1/tasks", response_model=TaskCreateResponse, status_code=201)
def create_task(req: TaskCreateRequest) -> TaskCreateResponse:
    REQUEST_COUNTER.inc()
    TASK_CREATED_COUNTER.inc()

    with db_conn() as conn:
        resolved = resolve_template_version(conn, req.template_name, req.template_version)
        normalized_payload = normalize_payload(req.template_name, resolved["adapter_name"], req.payload)

        task_id = uuid4()
        run_id = uuid4()
        created_at = now_utc()
        celery_task_id = dispatch_task(resolved["adapter_name"], normalized_payload)

        conn.execute(
            """
            INSERT INTO tasks (id, template_name, template_id, template_version, payload_json, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                task_id,
                req.template_name,
                resolved["template_id"],
                resolved["version"],
                Jsonb(normalized_payload),
                "queued",
                created_at,
            ),
        )

        conn.execute(
            """
            INSERT INTO task_runs (
                id, task_id, celery_task_id, status, started_at,
                template_id, template_version, adapter_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                task_id,
                celery_task_id,
                "queued",
                created_at,
                resolved["template_id"],
                resolved["version"],
                resolved["adapter_version"],
            ),
        )

        append_task_log(
            conn,
            task_id=task_id,
            run_id=run_id,
            level="info",
            message="task queued",
            metadata={
                "template_name": req.template_name,
                "template_version": resolved["version"],
                "adapter_name": resolved["adapter_name"],
                "celery_task_id": celery_task_id,
            },
        )
        conn.commit()

    return TaskCreateResponse(task_id=task_id, run_id=run_id, celery_task_id=celery_task_id, status="queued")


@app.get("/v1/tasks")
def list_tasks(limit: int = 20) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    safe_limit = min(max(limit, 1), 100)
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT DISTINCT ON (t.id)
                       t.id, t.template_name, t.template_version, t.status, t.created_at,
                       tr.id AS run_id, tr.celery_task_id, tr.status AS run_status,
                       tr.template_version AS run_template_version
                FROM tasks t
                JOIN task_runs tr ON tr.task_id = t.id
                ORDER BY t.id, tr.started_at DESC
            ) latest
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (safe_limit,),
        ).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            current_state, _, _ = sync_and_persist_run(
                conn,
                task_id=row[0],
                run_id=row[5],
                celery_task_id=row[6],
            )
            items.append(
                {
                    "task_id": str(row[0]),
                    "template_name": row[1],
                    "template_version": row[8] or row[2],
                    "status": current_state,
                    "created_at": row[4].isoformat(),
                    "run_id": str(row[5]),
                    "celery_task_id": row[6],
                }
            )
        conn.commit()
        return items


@app.get("/v1/tasks/{task_id}")
def get_task(task_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT t.id, t.template_name, t.template_version, t.payload_json, t.status, t.created_at,
                   tr.id, tr.celery_task_id, tr.status, tr.started_at, tr.finished_at, tr.result_json,
                   tr.template_version, tr.adapter_version, tr.error_code, tr.error_message
            FROM tasks t
            JOIN task_runs tr ON tr.task_id = t.id
            WHERE t.id = %s
            ORDER BY tr.started_at DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        current_state, result_data, finished_at = sync_and_persist_run(
            conn,
            task_id=row[0],
            run_id=row[6],
            celery_task_id=row[7],
        )
        conn.commit()

    return {
        "task_id": str(row[0]),
        "template_name": row[1],
        "template_version": row[12] or row[2],
        "payload": row[3],
        "status": current_state,
        "created_at": row[5].isoformat(),
        "run": {
            "run_id": str(row[6]),
            "celery_task_id": row[7],
            "status": current_state,
            "started_at": row[9].isoformat(),
            "finished_at": finished_at.isoformat() if finished_at else (row[10].isoformat() if row[10] else None),
            "result": result_data if result_data is not None else row[11],
            "template_version": row[12] or row[2],
            "adapter_version": row[13],
            "error_code": row[14],
            "error_message": row[15],
        },
    }


@app.get("/v1/tasks/{task_id}/logs")
def get_task_logs(task_id: UUID, limit: int = 200, run_id: UUID | None = None) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    safe_limit = min(max(limit, 1), 1000)
    with db_conn() as conn:
        exists = conn.execute("SELECT 1 FROM tasks WHERE id = %s", (task_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Task not found")
        if run_id is None:
            rows = conn.execute(
                """
                SELECT run_id, ts, level, message, metadata_json
                FROM task_logs
                WHERE task_id = %s
                ORDER BY ts DESC
                LIMIT %s
                """,
                (task_id, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT run_id, ts, level, message, metadata_json
                FROM task_logs
                WHERE task_id = %s AND run_id = %s
                ORDER BY ts DESC
                LIMIT %s
                """,
                (task_id, run_id, safe_limit),
            ).fetchall()
    return [
        {
            "run_id": str(row[0]),
            "ts": row[1].isoformat(),
            "level": row[2],
            "message": row[3],
            "metadata": row[4],
        }
        for row in rows
    ]


@app.get("/v1/tasks/{task_id}/runs")
def get_task_runs(task_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    safe_limit = min(max(limit, 1), 200)
    with db_conn() as conn:
        exists = conn.execute("SELECT 1 FROM tasks WHERE id = %s", (task_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Task not found")
        rows = conn.execute(
            """
            SELECT id, celery_task_id, status, started_at, finished_at, result_json,
                   template_version, adapter_version, error_code, error_message
            FROM task_runs
            WHERE task_id = %s
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (task_id, safe_limit),
        ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            current_state, result_data, finished_at = sync_and_persist_run(
                conn,
                task_id=task_id,
                run_id=row[0],
                celery_task_id=row[1],
            )
            result.append(
                {
                    "run_id": str(row[0]),
                    "celery_task_id": row[1],
                    "status": current_state,
                    "started_at": row[3].isoformat(),
                    "finished_at": finished_at.isoformat() if finished_at else (row[4].isoformat() if row[4] else None),
                    "result": result_data if result_data is not None else row[5],
                    "template_version": row[6],
                    "adapter_version": row[7],
                    "error_code": row[8],
                    "error_message": row[9],
                }
            )
        conn.commit()
        return result


@app.post("/v1/tasks/{task_id}/retry")
def retry_task(task_id: UUID) -> dict[str, str]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        task_row = conn.execute(
            "SELECT template_name, template_version, payload_json FROM tasks WHERE id = %s",
            (task_id,),
        ).fetchone()
        if not task_row:
            raise HTTPException(status_code=404, detail="Task not found")

        resolved = resolve_template_version(conn, task_row[0], task_row[1])
        normalized_payload = normalize_payload(task_row[0], resolved["adapter_name"], task_row[2])

        run_id = uuid4()
        celery_task_id = dispatch_task(resolved["adapter_name"], normalized_payload)
        created_at = now_utc()
        conn.execute(
            """
            INSERT INTO task_runs (
                id, task_id, celery_task_id, status, started_at,
                template_id, template_version, adapter_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                task_id,
                celery_task_id,
                "queued",
                created_at,
                resolved["template_id"],
                resolved["version"],
                resolved["adapter_version"],
            ),
        )
        conn.execute("UPDATE tasks SET status = %s WHERE id = %s", ("queued", task_id))
        append_task_log(
            conn,
            task_id=task_id,
            run_id=run_id,
            level="info",
            message="task retried",
            metadata={
                "template_version": resolved["version"],
                "adapter_name": resolved["adapter_name"],
                "celery_task_id": celery_task_id,
            },
        )
        conn.commit()

    return {"task_id": str(task_id), "run_id": str(run_id), "celery_task_id": celery_task_id, "status": "queued"}


@app.get("/v1/search/runs")
def search_runs(
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    status: str | None = None,
    template_name: str | None = None,
    template_version: str | None = None,
    error_keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    REQUEST_COUNTER.inc()

    safe_limit = min(max(limit, 1), 200)
    safe_offset = max(offset, 0)

    from_dt = _parse_iso_dt(from_ts)
    to_dt = _parse_iso_dt(to_ts)

    conditions = ["1=1"]
    params: list[Any] = []

    if from_dt:
        conditions.append("tr.started_at >= %s")
        params.append(from_dt)
    if to_dt:
        conditions.append("tr.started_at <= %s")
        params.append(to_dt)
    if status:
        conditions.append("tr.status = %s")
        params.append(status)
    if template_name:
        conditions.append("t.template_name = %s")
        params.append(template_name)
    if template_version:
        conditions.append("COALESCE(tr.template_version, t.template_version) = %s")
        params.append(template_version)
    if error_keyword:
        conditions.append("(COALESCE(tr.error_message, '') ILIKE %s OR COALESCE(tr.result_json::text, '') ILIKE %s)")
        params.append(f"%{error_keyword}%")
        params.append(f"%{error_keyword}%")

    where_sql = " AND ".join(conditions)

    with db_conn() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM task_runs tr
            JOIN tasks t ON t.id = tr.task_id
            WHERE {where_sql}
            """,
            tuple(params),
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT tr.id, tr.task_id, t.template_name, COALESCE(tr.template_version, t.template_version),
                   tr.status, tr.started_at, tr.finished_at, tr.celery_task_id,
                   tr.error_code, tr.error_message
            FROM task_runs tr
            JOIN tasks t ON t.id = tr.task_id
            WHERE {where_sql}
            ORDER BY tr.started_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [safe_limit, safe_offset]),
        ).fetchall()

    items = []
    for row in rows:
        duration_ms = None
        if row[6]:
            duration_ms = int((row[6] - row[5]).total_seconds() * 1000)
        items.append(
            {
                "run_id": str(row[0]),
                "task_id": str(row[1]),
                "template_name": row[2],
                "template_version": row[3],
                "status": row[4],
                "started_at": row[5].isoformat(),
                "finished_at": row[6].isoformat() if row[6] else None,
                "duration_ms": duration_ms,
                "celery_task_id": row[7],
                "error_code": row[8],
                "error_message": row[9],
            }
        )

    return {"total": int(total), "limit": safe_limit, "offset": safe_offset, "items": items}


@app.get("/v1/analytics/template-versions")
def analytics_template_versions(
    template_name: str,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    versions: str | None = None,
) -> dict[str, Any]:
    REQUEST_COUNTER.inc()

    from_dt = _parse_iso_dt(from_ts)
    to_dt = _parse_iso_dt(to_ts)

    conditions = ["t.template_name = %s"]
    params: list[Any] = [template_name]

    if from_dt:
        conditions.append("tr.started_at >= %s")
        params.append(from_dt)
    if to_dt:
        conditions.append("tr.started_at <= %s")
        params.append(to_dt)

    version_list: list[str] = []
    if versions:
        version_list = [v.strip() for v in versions.split(",") if v.strip()]
        if version_list:
            placeholders = ",".join(["%s"] * len(version_list))
            conditions.append(f"COALESCE(tr.template_version, t.template_version) IN ({placeholders})")
            params.extend(version_list)

    where_sql = " AND ".join(conditions)

    with db_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
                COALESCE(tr.template_version, t.template_version, 'unknown') AS version,
                COUNT(*) AS total_runs,
                SUM(CASE WHEN tr.status = 'success' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN tr.status = 'failure' THEN 1 ELSE 0 END) AS failure_count,
                AVG(EXTRACT(EPOCH FROM (COALESCE(tr.finished_at, now()) - tr.started_at)) * 1000) AS avg_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (COALESCE(tr.finished_at, now()) - tr.started_at)) * 1000
                ) AS p95_duration_ms
            FROM task_runs tr
            JOIN tasks t ON t.id = tr.task_id
            WHERE {where_sql}
            GROUP BY COALESCE(tr.template_version, t.template_version, 'unknown')
            ORDER BY version
            """,
            tuple(params),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        total_runs = int(row[1])
        success_count = int(row[2] or 0)
        failure_count = int(row[3] or 0)
        success_rate = round((success_count / total_runs) * 100, 2) if total_runs > 0 else 0.0
        failure_rate = round((failure_count / total_runs) * 100, 2) if total_runs > 0 else 0.0

        items.append(
            {
                "template_version": row[0],
                "total_runs": total_runs,
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "avg_duration_ms": float(row[4]) if row[4] is not None else None,
                "p95_duration_ms": float(row[5]) if row[5] is not None else None,
            }
        )

    return {
        "template_name": template_name,
        "from": from_ts,
        "to": to_ts,
        "versions": version_list if version_list else None,
        "items": items,
    }


@app.get("/v1/schedules")
def list_schedules(active_only: bool = False) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        where = "WHERE is_active = TRUE" if active_only else ""
        rows = conn.execute(
            f"""
            SELECT id, name, template_name, template_version, payload_json, rrule_text, timezone,
                   is_active, next_run_at, last_run_at, created_at, updated_at
            FROM task_schedules
            {where}
            ORDER BY updated_at DESC, name
            """
        ).fetchall()
    return [
        {
            "id": str(r[0]),
            "name": r[1],
            "template_name": r[2],
            "template_version": r[3],
            "payload": r[4],
            "rrule_text": r[5],
            "timezone": r[6],
            "is_active": r[7],
            "next_run_at": r[8].isoformat() if r[8] else None,
            "last_run_at": r[9].isoformat() if r[9] else None,
            "created_at": r[10].isoformat(),
            "updated_at": r[11].isoformat(),
        }
        for r in rows
    ]


@app.post("/v1/schedules", status_code=201)
def create_schedule(req: ScheduleCreateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    schedule_id = uuid4()
    now = now_utc()
    _parse_every_seconds(req.rrule_text)
    with db_conn() as conn:
        dup = conn.execute("SELECT 1 FROM task_schedules WHERE name = %s", (req.name,)).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail=f"Schedule already exists: {req.name}")
        resolved = resolve_template_version(conn, req.template_name, req.template_version)
        normalized_payload = normalize_payload(req.template_name, resolved["adapter_name"], req.payload)
        next_run = _schedule_next_run(now, req.rrule_text)
        conn.execute(
            """
            INSERT INTO task_schedules (
                id, name, template_id, template_name, template_version, payload_json, rrule_text,
                timezone, is_active, next_run_at, last_run_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                schedule_id,
                req.name,
                resolved["template_id"],
                req.template_name,
                resolved["version"],
                Jsonb(normalized_payload),
                req.rrule_text,
                req.timezone,
                req.is_active,
                next_run if req.is_active else None,
                None,
                now,
                now,
            ),
        )
        conn.commit()
    return {"id": str(schedule_id), "name": req.name, "status": "created"}


@app.get("/v1/schedules/{schedule_id}")
def get_schedule(schedule_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, template_name, template_version, payload_json, rrule_text, timezone,
                   is_active, next_run_at, last_run_at, created_at, updated_at
            FROM task_schedules
            WHERE id = %s
            """,
            (schedule_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Schedule not found")
    return {
        "id": str(row[0]),
        "name": row[1],
        "template_name": row[2],
        "template_version": row[3],
        "payload": row[4],
        "rrule_text": row[5],
        "timezone": row[6],
        "is_active": row[7],
        "next_run_at": row[8].isoformat() if row[8] else None,
        "last_run_at": row[9].isoformat() if row[9] else None,
        "created_at": row[10].isoformat(),
        "updated_at": row[11].isoformat(),
    }


@app.patch("/v1/schedules/{schedule_id}")
def update_schedule(schedule_id: UUID, req: ScheduleUpdateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT name, template_name, template_version, payload_json, rrule_text, timezone, is_active
            FROM task_schedules
            WHERE id = %s
            """,
            (schedule_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Schedule not found")

        payload = req.payload if req.payload is not None else row[3]
        rrule_text = req.rrule_text if req.rrule_text is not None else row[4]
        timezone = req.timezone if req.timezone is not None else row[5]
        is_active = req.is_active if req.is_active is not None else row[6]
        _parse_every_seconds(rrule_text)

        resolved = resolve_template_version(conn, row[1], row[2])
        normalized_payload = normalize_payload(row[1], resolved["adapter_name"], payload)

        next_run = _schedule_next_run(now_utc(), rrule_text) if is_active else None
        conn.execute(
            """
            UPDATE task_schedules
            SET payload_json = %s,
                rrule_text = %s,
                timezone = %s,
                is_active = %s,
                next_run_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (Jsonb(normalized_payload), rrule_text, timezone, is_active, next_run, now_utc(), schedule_id),
        )
        conn.commit()
    return get_schedule(schedule_id)


@app.post("/v1/schedules/{schedule_id}/pause")
def pause_schedule(schedule_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        updated = conn.execute(
            "UPDATE task_schedules SET is_active = FALSE, next_run_at = NULL, updated_at = %s WHERE id = %s RETURNING id",
            (now_utc(), schedule_id),
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Schedule not found")
        conn.commit()
    return {"schedule_id": str(schedule_id), "status": "paused"}


@app.post("/v1/schedules/{schedule_id}/resume")
def resume_schedule(schedule_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute("SELECT rrule_text FROM task_schedules WHERE id = %s", (schedule_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Schedule not found")
        next_run = _schedule_next_run(now_utc(), row[0])
        conn.execute(
            "UPDATE task_schedules SET is_active = TRUE, next_run_at = %s, updated_at = %s WHERE id = %s",
            (next_run, now_utc(), schedule_id),
        )
        conn.commit()
    return {"schedule_id": str(schedule_id), "status": "active", "next_run_at": next_run.isoformat()}


@app.post("/v1/schedules/{schedule_id}/run-now")
def run_schedule_now(schedule_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, template_name, template_version, payload_json, rrule_text, %s
            FROM task_schedules
            WHERE id = %s
            """,
            (now_utc(), schedule_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Schedule not found")
        _execute_schedule_run(conn, row)
        conn.commit()
    return {"schedule_id": str(schedule_id), "status": "queued"}


@app.get("/v1/schedules/{schedule_id}/runs")
def list_schedule_runs(schedule_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    safe_limit = min(max(limit, 1), 200)
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, schedule_id, task_id, planned_at, started_at, finished_at, status, error_message
            FROM schedule_runs
            WHERE schedule_id = %s
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (schedule_id, safe_limit),
        ).fetchall()
    return [
        {
            "id": str(r[0]),
            "schedule_id": str(r[1]),
            "task_id": str(r[2]) if r[2] else None,
            "planned_at": r[3].isoformat(),
            "started_at": r[4].isoformat(),
            "finished_at": r[5].isoformat() if r[5] else None,
            "status": r[6],
            "error_message": r[7],
        }
        for r in rows
    ]


@app.get("/v1/policies")
def list_policies(active_only: bool = False) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        where = "WHERE is_active = TRUE" if active_only else ""
        rows = conn.execute(
            f"""
            SELECT id, name, scope_type, scope_ref, metric_key, operator, threshold_value,
                   window_minutes, cooldown_minutes, action_type, action_payload_json,
                   last_triggered_at, is_active, created_at
            FROM policy_rules
            {where}
            ORDER BY created_at DESC, name
            """
        ).fetchall()
    return [
        {
            "id": str(r[0]),
            "name": r[1],
            "scope_type": r[2],
            "scope_ref": r[3],
            "metric_key": r[4],
            "operator": r[5],
            "threshold_value": r[6],
            "window_minutes": r[7],
            "cooldown_minutes": r[8],
            "action_type": r[9],
            "action_payload": r[10],
            "last_triggered_at": r[11].isoformat() if r[11] else None,
            "is_active": r[12],
            "created_at": r[13].isoformat(),
        }
        for r in rows
    ]


@app.post("/v1/policies", status_code=201)
def create_policy(req: PolicyCreateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        dup = conn.execute("SELECT 1 FROM policy_rules WHERE name = %s", (req.name,)).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail=f"Policy already exists: {req.name}")
        policy_id = uuid4()
        conn.execute(
            """
            INSERT INTO policy_rules (
                id, name, scope_type, scope_ref, metric_key, operator, threshold_value,
                window_minutes, cooldown_minutes, action_type, action_payload_json,
                last_triggered_at, is_active, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            """,
            (
                policy_id,
                req.name,
                req.scope_type,
                req.scope_ref,
                req.metric_key,
                req.operator,
                req.threshold_value,
                req.window_minutes,
                req.cooldown_minutes,
                req.action_type,
                Jsonb(req.action_payload) if req.action_payload is not None else None,
                None,
                now_utc(),
            ),
        )
        conn.commit()
    return {"id": str(policy_id), "name": req.name, "status": "created"}


@app.patch("/v1/policies/{policy_id}")
def update_policy(policy_id: UUID, req: PolicyUpdateRequest) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT threshold_value, window_minutes, cooldown_minutes, is_active
            FROM policy_rules
            WHERE id = %s
            """,
            (policy_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found")

        threshold = req.threshold_value if req.threshold_value is not None else row[0]
        window_minutes = req.window_minutes if req.window_minutes is not None else row[1]
        cooldown_minutes = req.cooldown_minutes if req.cooldown_minutes is not None else row[2]
        is_active = req.is_active if req.is_active is not None else row[3]

        conn.execute(
            """
            UPDATE policy_rules
            SET threshold_value = %s,
                window_minutes = %s,
                cooldown_minutes = %s,
                is_active = %s
            WHERE id = %s
            """,
            (threshold, window_minutes, cooldown_minutes, is_active, policy_id),
        )
        conn.commit()
    return {"id": str(policy_id), "status": "updated"}


@app.post("/v1/policies/{policy_id}/enable")
def enable_policy(policy_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        updated = conn.execute(
            "UPDATE policy_rules SET is_active = TRUE WHERE id = %s RETURNING id",
            (policy_id,),
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Policy not found")
        conn.commit()
    return {"id": str(policy_id), "status": "enabled"}


@app.post("/v1/policies/{policy_id}/disable")
def disable_policy(policy_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    with db_conn() as conn:
        updated = conn.execute(
            "UPDATE policy_rules SET is_active = FALSE WHERE id = %s RETURNING id",
            (policy_id,),
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Policy not found")
        conn.commit()
    return {"id": str(policy_id), "status": "disabled"}


@app.get("/v1/policies/{policy_id}/actions")
def get_policy_actions(policy_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    safe_limit = min(max(limit, 1), 200)
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, action_type, action_payload_json, executed_at, status, message
            FROM policy_actions
            WHERE rule_id = %s
            ORDER BY executed_at DESC
            LIMIT %s
            """,
            (policy_id, safe_limit),
        ).fetchall()
    return [
        {
            "id": str(r[0]),
            "action_type": r[1],
            "action_payload": r[2],
            "executed_at": r[3].isoformat(),
            "status": r[4],
            "message": r[5],
        }
        for r in rows
    ]


@app.post("/v1/agents/heartbeat")
def agent_heartbeat(
    name: str,
    hostname: str | None = None,
    capacity: int = 1,
    queue_names: str | None = None,
) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    if capacity < 1:
        capacity = 1
    queue_list = [q.strip() for q in (queue_names or "celery").split(",") if q.strip()]
    agent_id = uuid5(NAMESPACE_DNS, f"agent:{name}")
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO agents (id, name, hostname, status, last_heartbeat_at, capacity, queue_names)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET hostname = EXCLUDED.hostname,
                status = EXCLUDED.status,
                last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                capacity = EXCLUDED.capacity,
                queue_names = EXCLUDED.queue_names
            """,
            (agent_id, name, hostname, "online", now_utc(), capacity, queue_list),
        )
        conn.commit()
    return {"id": str(agent_id), "name": name, "status": "online"}


@app.get("/v1/agents")
def list_agents() -> list[dict[str, Any]]:
    REQUEST_COUNTER.inc()
    now = now_utc()
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, hostname, status, last_heartbeat_at, capacity, queue_names
            FROM agents
            ORDER BY last_heartbeat_at DESC, name
            """
        ).fetchall()
    result: list[dict[str, Any]] = []
    for r in rows:
        diff_sec = (now - r[4]).total_seconds()
        derived = "online"
        if diff_sec > 60:
            derived = "degraded"
        if diff_sec > 180:
            derived = "offline"
        result.append(
            {
                "id": str(r[0]),
                "name": r[1],
                "hostname": r[2],
                "status": derived,
                "last_heartbeat_at": r[4].isoformat(),
                "capacity": r[5],
                "queue_names": r[6],
            }
        )
    return result


@app.get("/v1/agents/{agent_id}")
def get_agent(agent_id: UUID) -> dict[str, Any]:
    REQUEST_COUNTER.inc()
    agents = list_agents()
    for agent in agents:
        if agent["id"] == str(agent_id):
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/stream/tasks")
def stream_tasks() -> StreamingResponse:
    def event_stream() -> Iterator[str]:
        last_log_id = -1
        last_heartbeat = time.monotonic()

        yield 'event: ready\ndata: {"status":"connected"}\n\n'
        while True:
            with db_conn() as conn:
                row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_logs").fetchone()
                current_log_id = int(row[0]) if row and row[0] is not None else 0

            if current_log_id != last_log_id:
                last_log_id = current_log_id
                payload = f'{{"last_log_id": {current_log_id}, "ts": "{now_utc().isoformat()}"}}'
                yield f"event: task_update\\ndata: {payload}\\n\\n"

            now_monotonic = time.monotonic()
            if now_monotonic - last_heartbeat >= 15:
                yield ": heartbeat\\n\\n"
                last_heartbeat = now_monotonic

            time.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
