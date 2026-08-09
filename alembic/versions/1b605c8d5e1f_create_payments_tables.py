"""create payments tables

Two unique constraints carry the idempotency guarantees, and they are the
reason this migration exists rather than a create_all() call at startup:

    uq_processed_events_stripe_event_id
        Stripe redelivers an event until it receives a 2xx. This constraint is
        what turns the second delivery into a no-op.

    uq_unlocks_device_id
        The success redirect and the webhook both try to unlock the same
        device, and they race. This constraint is what makes them end up with
        one row instead of two.

Both are enforced by the database, so two simultaneous requests cannot slip
past them the way a read-then-write check in Python would.

Revision ID: 1b605c8d5e1f
Revises:
Create Date: 2026-08-09 05:55:43.107658

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1b605c8d5e1f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id", name="uq_processed_events_stripe_event_id"),
    )
    op.create_table(
        "unlocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=False),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("amount_total", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", name="uq_unlocks_device_id"),
    )


def downgrade() -> None:
    op.drop_table("unlocks")
    op.drop_table("processed_events")
