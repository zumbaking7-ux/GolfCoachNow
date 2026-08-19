"""Give a user a name, for the greeting on the home screen.

Nullable on purpose. Email is the identity; a name is not required to sign in,
and everybody who signed in before this column existed has none. The apps fall
back to a generic greeting rather than refusing to render one.

Revision ID: b4d17e2a9c53
Revises: a7b3e9f12c84
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "b4d17e2a9c53"
down_revision: Union[str, Sequence[str], None] = "a7b3e9f12c84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAME_LENGTH = 80


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(NAME_LENGTH), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "name")
