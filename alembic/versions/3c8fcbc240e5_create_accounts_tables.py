"""create accounts tables

Four tables so a person has an identity that outlives their phone: users,
login_codes, auth_tokens and user_devices.

Deliberately trimmed after autogenerate. Alembic also proposed creating
subscriptions, daily_usage, analytics_events and rep_results, because those
are declared in models.py but were created directly on the server rather than
through a migration. They already exist in production, so creating them here
would fail the deploy.

Adopting those four into Alembic is a separate job and needs migrations that
check before creating. It is tracked in the repository issues and is not this
change.

Revision ID: 3c8fcbc240e5
Revises: 1b605c8d5e1f
Create Date: 2026-08-12 06:52:42.323467

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3c8fcbc240e5"
down_revision: Union[str, Sequence[str], None] = "1b605c8d5e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users first: the other three reference it.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "login_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("login_codes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_login_codes_email"), ["email"], unique=False
        )

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Only the hash is ever stored, and it is unique so a lookup by token
        # is one indexed read rather than a scan.
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    with op.batch_alter_table("auth_tokens", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_auth_tokens_user_id"), ["user_id"], unique=False
        )

    op.create_table(
        "user_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # A phone belongs to one account. Signing in as someone else moves the
        # device rather than sharing it, so one purchase cannot be spread
        # across several accounts.
        sa.UniqueConstraint("device_id", name="uq_user_devices_device_id"),
    )
    with op.batch_alter_table("user_devices", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_user_devices_user_id"), ["user_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("user_devices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_devices_user_id"))
    op.drop_table("user_devices")

    with op.batch_alter_table("auth_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auth_tokens_user_id"))
    op.drop_table("auth_tokens")

    with op.batch_alter_table("login_codes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_login_codes_email"))
    op.drop_table("login_codes")

    op.drop_table("users")
