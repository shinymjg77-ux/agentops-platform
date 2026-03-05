from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.workflow.state_machine import PostStatus, validate_post_transition


@dataclass(slots=True)
class PostState:
    post_id: str
    status: str
    updated_at: str
    approved_by: str | None = None
    approved_at: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)


class InMemoryPostWorkflowStore:
    def __init__(self) -> None:
        self._storage: dict[str, PostState] = {}

    def ensure_initialized(self, post_id: str) -> PostState:
        existing = self._storage.get(post_id)
        if existing:
            return existing

        now = datetime.now(UTC).isoformat()
        state = PostState(
            post_id=post_id,
            status=PostStatus.DRAFT,
            updated_at=now,
            history=[{"from": "", "to": PostStatus.DRAFT, "at": now}],
        )
        self._storage[post_id] = state
        return state

    def transition(self, post_id: str, target_status: str, actor_id: str) -> PostState:
        current = self._storage.get(post_id)
        if not current:
            raise KeyError("post_not_found")

        validate_post_transition(current.status, target_status)

        now = datetime.now(UTC).isoformat()
        current.history.append({"from": current.status, "to": target_status, "at": now, "actor": actor_id})
        current.status = target_status
        current.updated_at = now

        if target_status == PostStatus.APPROVED:
            current.approved_by = actor_id
            current.approved_at = now

        return current

    def get(self, post_id: str) -> PostState:
        current = self._storage.get(post_id)
        if not current:
            raise KeyError("post_not_found")
        return current


post_workflow_store = InMemoryPostWorkflowStore()
