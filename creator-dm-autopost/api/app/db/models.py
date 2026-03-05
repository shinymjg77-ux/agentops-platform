from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="draft")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, server_default="discord")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tone: Mapped[str] = mapped_column(String(120), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    style_sample: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="draft")
    approved_by: Mapped[int | None] = mapped_column(BigInteger)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Recipient(Base):
    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "channel_user_id", name="uq_recipients_campaign_channel_user"),
        CheckConstraint("latest_opt_in_status IN ('opt_in', 'opt_out')", name="ck_recipients_opt_in_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    channel_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    latest_opt_in_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="opt_out")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RecipientConsent(Base):
    __tablename__ = "recipient_consents"
    __table_args__ = (
        CheckConstraint("status IN ('opt_in', 'opt_out')", name="ck_recipient_consents_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("recipients.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    consent_source: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_ref: Mapped[str | None] = mapped_column(Text)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_deliveries_idempotency_key"),
        CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed', 'retrying', 'cancelled')",
            name="ck_deliveries_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("recipients.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    error_code: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
