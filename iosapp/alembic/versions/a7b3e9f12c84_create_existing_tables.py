"""create daily_usage, analytics_events, rep_results, subscriptions

These four tables were created directly on the production server and already
exist there. They were never tracked by Alembic, so a fresh database built
from migrations could not serve any request except payments.

Every CREATE uses IF NOT EXISTS so the migration is safe on both the live
database (where the tables are already present) and a clean checkout (where
they are not).

The subscriptions table here is the legacy one from the original V1.0
scaffold. It is not the same as user_subscriptions created in 5a2f1c7d90e4.
Production still has it, so the migration must account for it.

Revision ID: a7b3e9f12c84
Revises: 5a2f1c7d90e4
"""

from alembic import op
import sqlalchemy as sa

revision = "a7b3e9f12c84"
down_revision = "5a2f1c7d90e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id VARCHAR(255) NOT NULL,
            module VARCHAR(32) NOT NULL,
            usage_date DATE NOT NULL,
            rep_count INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_daily_usage_device_module_date UNIQUE (device_id, module, usage_date)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id VARCHAR(255) NOT NULL,
            event_name VARCHAR(64) NOT NULL,
            module VARCHAR(32),
            platform VARCHAR(16),
            payload TEXT,
            created_at DATETIME NOT NULL
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_analytics_events_device_id
            ON analytics_events (device_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_analytics_events_event_name
            ON analytics_events (event_name)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_analytics_events_created_at
            ON analytics_events (created_at)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS rep_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id VARCHAR(255) NOT NULL,
            module VARCHAR(32) NOT NULL,
            dominant_fault VARCHAR(64) NOT NULL,
            correction TEXT NOT NULL,
            scores_json TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_rep_results_device_id
            ON rep_results (device_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_rep_results_module
            ON rep_results (module)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_rep_results_created_at
            ON rep_results (created_at)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id VARCHAR(255) NOT NULL UNIQUE,
            stripe_subscription_id VARCHAR(255),
            stripe_customer_id VARCHAR(255),
            status VARCHAR(32) NOT NULL DEFAULT 'inactive',
            current_period_end DATETIME,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS rep_results")
    op.execute("DROP TABLE IF EXISTS analytics_events")
    op.execute("DROP TABLE IF EXISTS daily_usage")
