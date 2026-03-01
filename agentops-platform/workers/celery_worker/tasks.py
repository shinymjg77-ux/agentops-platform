import os
import socket
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import UUID

import psycopg
import requests
from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from psycopg.types.json import Jsonb

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agentops:agentops@postgres:5432/agentops")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000").rstrip("/")
AGENT_NAME = os.getenv("AGENT_NAME", socket.gethostname())

celery_app = Celery("agentops_worker", broker=REDIS_URL, backend=REDIS_URL)


def now_utc() -> datetime:
    return datetime.now(UTC)


@contextmanager
def db_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


def lookup_run(conn: psycopg.Connection, celery_task_id: str) -> tuple[UUID, UUID] | None:
    row = conn.execute(
        """
        SELECT id, task_id
        FROM task_runs
        WHERE celery_task_id = %s
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (celery_task_id,),
    ).fetchone()
    if not row:
        return None
    return row[0], row[1]


def append_log(
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
        (task_id, run_id, now_utc(), level, message, Jsonb(metadata) if metadata is not None else None),
    )


def update_status(
    conn: psycopg.Connection,
    *,
    task_id: UUID,
    run_id: UUID,
    status: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    finish: bool = False,
) -> None:
    finished_at = now_utc() if finish else None
    conn.execute(
        """
        UPDATE task_runs
        SET status = %s,
            finished_at = COALESCE(finished_at, %s),
            result_json = COALESCE(%s, result_json),
            error_code = COALESCE(%s, error_code),
            error_message = COALESCE(%s, error_message)
        WHERE id = %s
        """,
        (
            status,
            finished_at,
            Jsonb(result) if result is not None else None,
            error_code,
            error_message,
            run_id,
        ),
    )
    conn.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))


def send_alert(event_type: str, payload: dict[str, Any]) -> None:
    if not ALERT_WEBHOOK_URL:
        return
    body = {"source": "agentops-worker", "event_type": event_type, "payload": payload}
    try:
        requests.post(ALERT_WEBHOOK_URL, json=body, timeout=3)
    except Exception:
        # 알림 실패는 작업 실행 흐름을 막지 않는다.
        return


def send_heartbeat() -> None:
    try:
        requests.post(
            f"{API_BASE_URL}/v1/agents/heartbeat",
            params={
                "name": AGENT_NAME,
                "hostname": socket.gethostname(),
                "capacity": 1,
                "queue_names": "celery",
            },
            timeout=3,
        )
    except Exception:
        return


def heartbeat_loop() -> None:
    while True:
        send_heartbeat()
        time.sleep(15)


threading.Thread(target=heartbeat_loop, daemon=True, name="worker-heartbeat-loop").start()


@task_prerun.connect
def on_task_prerun(task_id: str | None = None, task=None, **kwargs) -> None:
    if not task_id:
        return
    with db_conn() as conn:
        run_ref = lookup_run(conn, task_id)
        if not run_ref:
            return
        run_id, parent_task_id = run_ref
        update_status(conn, task_id=parent_task_id, run_id=run_id, status="started")
        append_log(
            conn,
            task_id=parent_task_id,
            run_id=run_id,
            level="info",
            message="task started",
            metadata={"celery_task_name": task.name if task else "unknown"},
        )
        conn.commit()


@task_retry.connect
def on_task_retry(request=None, reason=None, **kwargs) -> None:
    if request is None:
        return
    with db_conn() as conn:
        run_ref = lookup_run(conn, request.id)
        if not run_ref:
            return
        run_id, parent_task_id = run_ref
        update_status(conn, task_id=parent_task_id, run_id=run_id, status="retry")
        append_log(
            conn,
            task_id=parent_task_id,
            run_id=run_id,
            level="warning",
            message="task retry scheduled",
            metadata={"reason": str(reason)},
        )
        conn.commit()
    send_alert(
        "task_retry",
        {
            "task_id": str(parent_task_id),
            "run_id": str(run_id),
            "reason": str(reason),
            "celery_task_id": request.id,
        },
    )


@task_failure.connect
def on_task_failure(task_id: str | None = None, exception=None, **kwargs) -> None:
    if not task_id:
        return
    with db_conn() as conn:
        run_ref = lookup_run(conn, task_id)
        if not run_ref:
            return
        run_id, parent_task_id = run_ref
        update_status(
            conn,
            task_id=parent_task_id,
            run_id=run_id,
            status="failure",
            result={"error": str(exception)},
            error_code="runtime_error",
            error_message=str(exception),
            finish=True,
        )
        append_log(
            conn,
            task_id=parent_task_id,
            run_id=run_id,
            level="error",
            message="task failed",
            metadata={"error": str(exception)},
        )
        conn.commit()
    send_alert(
        "task_failure",
        {
            "task_id": str(parent_task_id),
            "run_id": str(run_id),
            "error": str(exception),
            "celery_task_id": task_id,
        },
    )


@task_postrun.connect
def on_task_postrun(task_id: str | None = None, state: str | None = None, retval=None, **kwargs) -> None:
    if not task_id or state != "SUCCESS":
        return
    with db_conn() as conn:
        run_ref = lookup_run(conn, task_id)
        if not run_ref:
            return
        run_id, parent_task_id = run_ref
        update_status(
            conn,
            task_id=parent_task_id,
            run_id=run_id,
            status="success",
            result=retval if isinstance(retval, dict) else {"result": str(retval)},
            finish=True,
        )
        append_log(
            conn,
            task_id=parent_task_id,
            run_id=run_id,
            level="info",
            message="task completed",
        )
        conn.commit()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sample_echo_task(self, payload: dict) -> dict:
    time.sleep(1)
    if payload.get("force_fail"):
        raise RuntimeError("forced failure for retry test")
    return {"echo": payload, "task_id": self.request.id}


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sample_http_check_task(self, payload: dict) -> dict:
    url = payload.get("url", "http://api:8000/healthz")
    timeout = int(payload.get("timeout_sec", 5))
    resp = requests.get(url, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"http check failed: {resp.status_code}")
    return {"url": url, "status_code": resp.status_code, "task_id": self.request.id}
