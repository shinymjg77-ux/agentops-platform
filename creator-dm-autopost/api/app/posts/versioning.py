from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class PostRevision:
    version: int
    content: str
    edited_by: str
    edited_at: str


class InMemoryPostVersionStore:
    def __init__(self) -> None:
        self._storage: dict[str, list[PostRevision]] = {}

    def create_initial(self, post_id: str, content: str, edited_by: str) -> PostRevision:
        if post_id in self._storage:
            raise ValueError("post_already_exists")

        revision = PostRevision(
            version=1,
            content=content,
            edited_by=edited_by,
            edited_at=datetime.now(UTC).isoformat(),
        )
        self._storage[post_id] = [revision]
        return revision

    def append_revision(self, post_id: str, content: str, edited_by: str) -> PostRevision:
        revisions = self._storage.get(post_id)
        if not revisions:
            raise KeyError("post_not_found")

        revision = PostRevision(
            version=revisions[-1].version + 1,
            content=content,
            edited_by=edited_by,
            edited_at=datetime.now(UTC).isoformat(),
        )
        revisions.append(revision)
        return revision

    def get_revisions(self, post_id: str) -> list[dict[str, str | int]]:
        revisions = self._storage.get(post_id)
        if not revisions:
            raise KeyError("post_not_found")
        return [asdict(item) for item in revisions]


post_version_store = InMemoryPostVersionStore()
