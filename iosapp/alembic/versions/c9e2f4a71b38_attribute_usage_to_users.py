"""Attribute usage, history and analytics to the person, not the handset.

Everything on the usage path was keyed to device_id, which is a value the
client supplies. Three consequences, all of them quiet:

  - free reps reset on a new phone, so the daily cap leaked
  - a golfer's swing history did not follow them off the device
  - analytics counted handsets and called them people

user_devices already recorded which devices belong to whom; nothing read it.
This adds the column that lets the rest of the code do so.

Nullable on purpose, and it stays nullable. A rep can legitimately happen
before anyone signs in - the launch allowance lets a stranger take one - so a
row with no user is a real state and not a gap to be filled later. The reading
code falls back to device_id whenever the column is null, which is what makes
this deployable without a flag day and reversible until the fallback is
removed.

The backfill claims rows for devices that are already linked to an account. It
cannot claim rows from devices nobody ever signed in on, and it should not try:
those reps genuinely belong to no one.

No foreign key. These tables already hold production rows, and SQLite cannot
ALTER a constraint into an existing table - the only route is copy-and-rebuild,
which is real risk against a live database for almost no gain, since SQLite
does not enforce foreign keys unless the connection asks it to and this one
does not. The relationship is maintained in code and covered by tests.

daily_usage is the exception, and is rebuilt. Its unique constraint was
(device_id, module, usage_date) - one row per handset per day - which cannot
represent two accounts sharing a phone. The second golfer to sign in inherited
the first one's spent reps: rarer than the other faults here and worse than all
of them, because it takes access away from somebody holding a valid
credential. The constraint now includes user_id.

One trade-off, stated rather than discovered later: SQLite treats NULLs as
distinct in a unique constraint, so rows with no user are no longer protected
from a duplicate by the database. The find-then-create in entitlement.py still
guards the ordinary path, and the failure mode of a lost race is one extra free
rep for a signed-out golfer - in their favour, and far cheaper than the fault
being fixed here.

Revision ID: c9e2f4a71b38
Revises: b4d17e2a9c53
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "c9e2f4a71b38"
down_revision: Union[str, Sequence[str], None] = "b4d17e2a9c53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SIMPLE_TABLES = ("analytics_events", "rep_results")
OLD_UNIQUE = "uq_daily_usage_device_module_date"
NEW_UNIQUE = "uq_daily_usage_device_user_module_date"

BACKFILL = """
    UPDATE {table}
       SET user_id = (
            SELECT ud.user_id
              FROM user_devices ud
             WHERE ud.device_id = {table}.device_id
          ORDER BY ud.linked_at ASC, ud.id ASC
             LIMIT 1
       )
     WHERE user_id IS NULL
"""


def upgrade() -> None:
    for table in SIMPLE_TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_index("ix_%s_user_id" % table, table, ["user_id"])

    # Rebuilt rather than altered, because the unique constraint has to change
    # and SQLite has no other way to do it.
    with op.batch_alter_table("daily_usage", schema=None) as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.drop_constraint(OLD_UNIQUE, type_="unique")
        batch.create_unique_constraint(
            NEW_UNIQUE, ["device_id", "user_id", "module", "usage_date"]
        )
    op.create_index("ix_daily_usage_user_id", "daily_usage", ["user_id"])

    # Backfill last, so it runs against the finished shape.
    #
    # A device linked to more than one account is possible - a shared phone, or
    # somebody signing in with a second address - so the oldest link wins. An
    # arbitrary rule for an ambiguous case, chosen because it is stable:
    # running this twice gives the same answer, which matters more here than
    # which of the two accounts has the better claim.
    for table in SIMPLE_TABLES + ("daily_usage",):
        op.execute(sa.text(BACKFILL.format(table=table)))


def downgrade() -> None:
    for table in SIMPLE_TABLES:
        op.drop_index("ix_%s_user_id" % table, table_name=table)
        op.drop_column(table, "user_id")

    # The new shape can hold something the old one cannot: two accounts on one
    # handset, on the same day, in the same module. Going back has to decide
    # what happens to the second row, and the rebuild fails outright if nothing
    # does - which is the worst time to discover it, since a downgrade only
    # runs when something has already gone wrong.
    #
    # The largest count survives. Not the newest, and not the sum: this is the
    # number that decides whether somebody may take another free rep, and the
    # safe direction to round an ambiguous answer is the one that does not hand
    # out reps nobody paid for. It is lossy, deliberately, and the code that
    # reads it afterwards is the old device-keyed code that never knew the
    # difference.
    op.execute(
        sa.text(
            """
            DELETE FROM daily_usage
             WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY device_id, module, usage_date
                                   ORDER BY rep_count DESC, id ASC
                               ) AS rank
                          FROM daily_usage
                    ) ranked
                     WHERE rank = 1
             )
            """
        )
    )

    op.drop_index("ix_daily_usage_user_id", table_name="daily_usage")
    with op.batch_alter_table("daily_usage", schema=None) as batch:
        batch.drop_constraint(NEW_UNIQUE, type_="unique")
        batch.create_unique_constraint(OLD_UNIQUE, ["device_id", "module", "usage_date"])
        batch.drop_column("user_id")
