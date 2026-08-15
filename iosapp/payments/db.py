"""Database engine and the per-request session dependency.

The only thing that changes between SQLite and Postgres is DATABASE_URL. The
unique constraints, the migrations, and the idempotency logic behave the same
on both.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from payments.config import settings

SQLITE_SCHEME = "sqlite"


def _engine_options(database_url: str) -> dict:
    """SQLite refuses to reuse a connection across threads unless told to.

    FastAPI runs plain `def` endpoints in a worker threadpool, so a connection
    opened on one thread gets used on another. Postgres has no such rule, hence
    the branch.
    """
    if database_url.startswith(SQLITE_SCHEME):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    **_engine_options(settings.database_url),
)

if settings.database_url.startswith(SQLITE_SCHEME):

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(connection, _record) -> None:
        """SQLite ignores foreign keys unless each connection asks it not to.

        Off by default for backward compatibility, and the setting is per
        connection rather than per database, so it has to be set here rather
        than once in a migration.

        Without it every ForeignKey in this package is a comment. A
        subscription could point at a user ID that was never created and
        nothing would object until someone tried to read it back and found
        nobody there.
        """
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding one session per request."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
