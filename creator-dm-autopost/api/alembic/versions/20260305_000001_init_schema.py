"""initial schema

Revision ID: 20260305_000001
Revises:
Create Date: 2026-03-05 11:35:00

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260305_000001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("channel", sa.String(length=32), server_default="discord", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "creators",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.BigInteger(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tone", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("style_sample", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.BigInteger(), sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "recipients",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.BigInteger(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_user_id", sa.String(length=128), nullable=False),
        sa.Column("latest_opt_in_status", sa.String(length=16), server_default="opt_out", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("campaign_id", "channel_user_id", name="uq_recipients_campaign_channel_user"),
        sa.CheckConstraint("latest_opt_in_status IN ('opt_in', 'opt_out')", name="ck_recipients_opt_in_status"),
    )

    op.create_table(
        "recipient_consents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.BigInteger(), sa.ForeignKey("recipients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("consent_source", sa.String(length=64), nullable=False),
        sa.Column("proof_ref", sa.Text(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('opt_in', 'opt_out')", name="ck_recipient_consents_status"),
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.BigInteger(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), sa.ForeignKey("recipients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_deliveries_idempotency_key"),
        sa.CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed', 'retrying', 'cancelled')",
            name="ck_deliveries_status",
        ),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_deliveries_post_recipient", "deliveries", ["post_id", "recipient_id"])


def downgrade() -> None:
    op.drop_index("ix_deliveries_post_recipient", table_name="deliveries")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")

    op.drop_table("audit_logs")
    op.drop_table("deliveries")
    op.drop_table("recipient_consents")
    op.drop_table("recipients")
    op.drop_table("posts")
    op.drop_table("creators")
    op.drop_table("campaigns")
