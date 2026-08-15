"""The schema Alembic builds and the models Alembic knows about must agree.

This exists because of one specific failure, and the failure is quiet.

Autogenerate compares the live database against Base.metadata. A model module
that alembic/env.py never imports does not register its tables there, so
autogenerate finds the table in the database, cannot find it in the metadata,
and writes a migration that drops it. Nobody typed "drop"; the tool inferred it
from a missing import. One routine command then deletes every row in it.

Everything here runs in a subprocess, and that detail is the whole test rather
than an implementation nicety. The first version of this file imported every
model module itself before comparing, which made the metadata complete no
matter what env.py did, so it passed just as happily with the import removed. A
test that cannot fail is worse than no test, because it is read as coverage.

A subprocess starts with an empty module table, so the only imports that count
are the ones env.py performs. That is exactly the thing being checked.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent

# Nothing. daily_usage, analytics_events and rep_results were declared in
# models.py with no migration to create them, which is why a fresh database
# could not serve a request. a7b3e9f12c84 fixed that, so this list is empty and
# the check below now protects every model rather than excusing four of them.
#
# Deliberately kept as an empty set rather than deleted. A future table added
# directly to a server would belong here, briefly, with a note saying who is
# writing the migration and when.
TABLES_WITHOUT_MIGRATIONS: set[str] = set()

# The other direction: created by a migration, declared by no model.
#
# subscriptions is the legacy table from the reverted V1.0 scaffold. Production
# still has it, so a7b3e9f12c84 recreates it for fresh databases rather than
# letting the two diverge. Its model was deleted along with the dead code that
# used it, and no code touches the table now.
#
# So autogenerate sees a table nothing declares and proposes dropping it. That
# is correct behaviour from Alembic and the wrong action to take, since the
# production copy may hold rows nobody has looked at. Naming it here says the
# gap is known and deliberate, which is the difference between a documented
# decision and drift.
#
# It leaves this set the day somebody confirms the production table is empty
# and writes a migration to drop it properly.
LEGACY_TABLES_WITHOUT_MODELS = {"subscriptions"}

# Runs inside a fresh interpreter. Builds a throwaway database from the real
# migrations, then asks Alembic what it would still change, importing nothing
# except what env.py imports.
PROBE = """
import json, os, pathlib, sys
sys.path.insert(0, {root!r})
database = pathlib.Path({database!r})
database.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + database.as_posix()

from alembic.config import Config
from alembic import command
from alembic.autogenerate import produce_migrations
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

config = Config({ini!r})
command.upgrade(config, "head")

# Import env.py the way Alembic does, and take the metadata it exposes. Nothing
# else in this process has imported any model module.
import importlib.util
spec = importlib.util.spec_from_file_location("alembic_env", {env!r})
module = importlib.util.module_from_spec(spec)
sys.argv = ["alembic"]
try:
    spec.loader.exec_module(module)
except Exception:
    # env.py runs migrations when executed outside Alembic. The imports at the
    # top have already happened by then, which is all this needs.
    pass

from payments.models import Base

engine = create_engine("sqlite:///" + database.as_posix())
with engine.connect() as connection:
    context = MigrationContext.configure(connection)
    operations = produce_migrations(context, Base.metadata).upgrade_ops.as_diffs()

result = [
    [operation[0], operation[1].name]
    for operation in operations
    if operation[0] in ("add_table", "remove_table")
]
engine.dispose()
database.unlink(missing_ok=True)
print("RESULT:" + json.dumps(result))
"""


@pytest.fixture(scope="module")
def differences(tmp_path_factory) -> list[list[str]]:
    """Table level drift, measured in a clean interpreter."""
    database = tmp_path_factory.mktemp("schema") / "probe.db"
    script = PROBE.format(
        root=str(PROJECT_ROOT),
        database=str(database),
        ini=str(PROJECT_ROOT / "alembic.ini"),
        env=str(PROJECT_ROOT / "alembic" / "env.py"),
    )

    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    marker = "RESULT:"
    line = next(
        (l for l in completed.stdout.splitlines() if l.startswith(marker)), None
    )
    assert line is not None, (
        "the schema probe did not report a result.\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    return json.loads(line[len(marker) :])


def test_autogenerate_would_not_drop_a_live_table(differences):
    """The one that matters.

    A table the migrations create but no imported model declares looks to
    Alembic like a leftover. The next autogenerate proposes dropping it, and
    whoever runs it has no reason to think that line is wrong.
    """
    doomed = sorted(
        name
        for kind, name in differences
        if kind == "remove_table" and name not in LEGACY_TABLES_WITHOUT_MODELS
    )

    assert not doomed, (
        f"autogenerate would propose DROP TABLE for {doomed}. The migrations "
        f"create these but no model imported by alembic/env.py declares them, "
        f"so Alembic reads them as leftovers. Either add the model module to "
        f"the imports at the top of alembic/env.py, or if the table is "
        f"deliberately unmodelled, name it in LEGACY_TABLES_WITHOUT_MODELS "
        f"with the reason."
    )


def test_the_legacy_exemption_still_describes_something_real(differences):
    """An exemption nobody revisits becomes a lie.

    If the legacy table stops being proposed for removal - because somebody
    modelled it, or dropped it properly - the entry here is stale and should
    go. This fails when that happens, so the list cannot quietly outlive its
    reason.
    """
    proposed = {name for kind, name in differences if kind == "remove_table"}
    stale = sorted(LEGACY_TABLES_WITHOUT_MODELS - proposed)

    assert not stale, (
        f"{stale} are listed as legacy tables without models, but autogenerate "
        f"no longer proposes dropping them. Whatever made them an exception "
        f"has been resolved, so remove them from LEGACY_TABLES_WITHOUT_MODELS."
    )


def test_no_model_table_is_missing_from_the_migrations(differences):
    """A table in the models but not in the schema is an unwritten migration."""
    missing = sorted(
        name
        for kind, name in differences
        if kind == "add_table" and name not in TABLES_WITHOUT_MIGRATIONS
    )

    assert not missing, (
        f"these tables are declared in models but no migration creates them: "
        f"{missing}. Deploying would leave the code querying tables that do "
        f"not exist."
    )
