from enum import StrEnum


class PostStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


POST_TRANSITIONS: dict[PostStatus, set[PostStatus]] = {
    PostStatus.DRAFT: {PostStatus.PENDING_APPROVAL},
    PostStatus.PENDING_APPROVAL: {PostStatus.APPROVED, PostStatus.CANCELLED},
    PostStatus.APPROVED: {PostStatus.SCHEDULED, PostStatus.CANCELLED},
    PostStatus.SCHEDULED: {PostStatus.SENDING, PostStatus.CANCELLED},
    PostStatus.SENDING: {PostStatus.SENT, PostStatus.FAILED, PostStatus.CANCELLED},
    PostStatus.SENT: set(),
    PostStatus.FAILED: set(),
    PostStatus.CANCELLED: set(),
}

DELIVERY_TRANSITIONS: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.QUEUED: {DeliveryStatus.SENDING, DeliveryStatus.FAILED, DeliveryStatus.CANCELLED},
    DeliveryStatus.SENDING: {DeliveryStatus.SENT, DeliveryStatus.FAILED, DeliveryStatus.RETRYING},
    DeliveryStatus.RETRYING: {DeliveryStatus.QUEUED, DeliveryStatus.FAILED},
    DeliveryStatus.SENT: set(),
    DeliveryStatus.FAILED: set(),
    DeliveryStatus.CANCELLED: set(),
}


def validate_post_transition(current: str, target: str) -> None:
    try:
        current_status = PostStatus(current)
        target_status = PostStatus(target)
    except ValueError as exc:
        raise ValueError("invalid_status") from exc

    allowed_targets = POST_TRANSITIONS[current_status]
    if target_status not in allowed_targets:
        raise ValueError("invalid_state_transition")


def validate_delivery_transition(current: str, target: str) -> None:
    try:
        current_status = DeliveryStatus(current)
        target_status = DeliveryStatus(target)
    except ValueError as exc:
        raise ValueError("invalid_status") from exc

    allowed_targets = DELIVERY_TRANSITIONS[current_status]
    if target_status not in allowed_targets:
        raise ValueError("invalid_state_transition")
