"""Shared test setup.

The environment variables are set before anything from `payments` is imported,
because payments.config builds its Settings object at import time and
payments.db opens the engine from it. Importing first and configuring after
would give every test the developer's real .env.

No test in this suite reaches the network. Webhook tests sign their payloads
locally with the same HMAC scheme Stripe uses, so signature verification is
genuinely exercised rather than stubbed out.
"""

import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import pytest

TEST_DATABASE_PATH = Path(__file__).parent / "test_payments.db"
TEST_WEBHOOK_SECRET = "whsec_test_secret_used_only_by_the_test_suite"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

os.environ["STRIPE_SECRET_KEY"] = "sk_test_not_a_real_key"
os.environ["STRIPE_WEBHOOK_SECRET"] = TEST_WEBHOOK_SECRET
os.environ["STRIPE_PRICE_ID"] = "price_test_wedge_module"
os.environ["PUBLIC_BASE_URL"] = "https://api.example.com"
os.environ["SUCCESS_DEEP_LINK"] = "golfcoachnow://payment-success"
os.environ["CANCEL_DEEP_LINK"] = "golfcoachnow://payment-cancelled"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from payments.db import SessionFactory, engine  # noqa: E402
from payments.models import ProcessedEvent, Unlock  # noqa: E402
from payments.routes import router as payments_router  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent


def build_payments_app() -> FastAPI:
    """Mount the payments router on an app of its own.

    These tests deliberately do not import server.py. They cover this package,
    so they should pass or fail for reasons that live in this folder rather
    than in the wedge engine or the video pipeline sitting next to it. It also
    means the package can be dropped into any FastAPI project and its tests
    still run unchanged.
    """
    app = FastAPI()
    app.include_router(payments_router)
    return app


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the test database with the real migrations, not create_all.

    Running Alembic here means the tests check the schema that actually ships,
    including the two unique constraints everything else depends on.
    """
    TEST_DATABASE_PATH.unlink(missing_ok=True)

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(config, "head")

    yield

    # Windows will not delete a file that still has an open handle, and the
    # connection pool holds one until the engine is disposed.
    engine.dispose()
    TEST_DATABASE_PATH.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def clean_tables():
    """Give every test an empty database without rebuilding the schema."""
    with SessionFactory() as session:
        session.query(Unlock).delete()
        session.query(ProcessedEvent).delete()
        session.commit()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


@pytest.fixture
def db_session():
    with SessionFactory() as session:
        yield session


def load_event(name: str = "checkout_session_completed") -> dict:
    """Read a saved Stripe event payload.

    These files are captured from real test-mode payments, not written by hand.
    The only edited field is the buyer's email and name, replaced with
    placeholders. Everything else is exactly what Stripe sent, so the tests run
    against the real shape of the payload rather than against assumptions about
    it. docs/TESTING.md explains how to recapture one.
    """
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


# Identifiers taken from the fixture rather than repeated by hand, so
# refreshing it from a newer capture does not mean editing every test.
_FIXTURE = load_event()
EVENT_ID = _FIXTURE["id"]
SESSION_ID = _FIXTURE["data"]["object"]["id"]
DEVICE_ID = _FIXTURE["data"]["object"]["client_reference_id"]
PAYMENT_INTENT_ID = _FIXTURE["data"]["object"]["payment_intent"]


def sign_payload(payload: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Build a Stripe-Signature header the way Stripe does.

    The signed string is the timestamp, a dot, then the exact request body.
    Stripe rejects timestamps outside a five minute window, so this uses the
    current time rather than a constant.

    This is the whole reason the webhook handler must read raw bytes: change
    one space in the body and this HMAC no longer matches.
    """
    timestamp = int(time.time())
    signed_content = b"%d.%s" % (timestamp, payload)
    signature = hmac.new(secret.encode(), signed_content, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def post_webhook(client: TestClient, event: dict, secret: str = TEST_WEBHOOK_SECRET):
    """Deliver an event to the webhook endpoint with a valid signature."""
    payload = json.dumps(event).encode()
    return client.post(
        "/payments/webhook",
        content=payload,
        headers={
            "stripe-signature": sign_payload(payload, secret),
            "content-type": "application/json",
        },
    )
