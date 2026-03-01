from datetime import UTC, datetime
from threading import Lock
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="Alert Sink", version="0.1.0")
_events: list[dict[str, Any]] = []
_lock = Lock()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "alert-sink"}


@app.post("/events")
def ingest_event(payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        _events.append({"received_at": now_iso(), "payload": payload})
        count = len(_events)
    return {"accepted": True, "count": count}


@app.get("/events")
def list_events(limit: int = 100) -> list[dict[str, Any]]:
    safe_limit = min(max(limit, 1), 1000)
    with _lock:
        return _events[-safe_limit:]


@app.delete("/events")
def clear_events() -> dict[str, int]:
    with _lock:
        count = len(_events)
        _events.clear()
    return {"cleared": count}
