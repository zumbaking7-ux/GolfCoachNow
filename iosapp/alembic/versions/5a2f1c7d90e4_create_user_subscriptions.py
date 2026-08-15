"""create user_subscriptions

Chained behind the accounts migration rather than behind the payments one, so
there is a single head. Two migrations sharing a parent gives Alembic two heads
and `upgrade head` fails at deploy time, which is the failure mode being
avoided here and the reason issue #5 asks the other author to chain behind this
revision as well.

Creates only this table. Autogenerate would also propose subscriptions,
daily_usage, analytics_events and rep_results, which are declared in models.py
but were created directly on the server and already exist in production.
Including them would fail the deploy. Do not regenerate this file blindly.

Revision ID: 5a2f1c7d90e4
Revises: 3c8fcbc240e5
"""

from alembic import op
import sqlalchemy as sa

revision = "5a2f1c7d90e4"
down_revision = "3c8fcbc240e5"
branch_labels = None
depends_on = None

ID_LENGTH = 255
STATUS_LENGTH = 32


def upgrade() -> None:
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.String(length=ID_LENGTH), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=ID_LENGTH), nullable=False),
        sa.Column(
            "stripe_subscription_id", sa.String(length=ID_LENGTH), nullable=False
        ),
        sa.Column("status", sa.String(length=STATUS_LENGTH), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # The whole idempotency story for subscriptions rests on this one
        # index. Without it a retried webhook creates a second row and the
        # customer has two subscriptions where they bought one.
        sa.UniqueConstraint(
            "stripe_subscription_id", name="uq_user_subscriptions_stripe_id"
        ),
    )
    op.create_index(
        "ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"]
    )
    op.create_index(
        "ix_user_subscriptions_device_id", "user_subscriptions", ["device_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_subscriptions_device_id", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
