import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
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


@app.on_event("startup")
def startup_event() -> None:
    initialize_schema()


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
