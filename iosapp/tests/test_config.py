"""Startup configuration.

Importing the payments package validates its settings, which means a missing
Stripe variable stops the whole application from starting. That is deliberate,
and it is documented in docs/DEPLOYMENT.md, so it needs a test holding it in
place rather than relying on nobody changing it by accident.

These run in a subprocess with a clean environment. Settings are built at
import time, so they cannot be re-evaluated inside a process that has already
imported the module.
"""

import os
import subprocess
import sys

from conftest import PROJECT_ROOT

CONFIGURED = {
    "STRIPE_SECRET_KEY": "sk_test_not_a_real_key",
    "STRIPE_WEBHOOK_SECRET": "whsec_not_a_real_secret",
    "STRIPE_PRICE_ID": "price_not_a_real_price",
    "PUBLIC_BASE_URL": "https://api.example.com",
}


def import_payments_config(overrides: dict, tmp_path) -> subprocess.CompletedProcess:
    """Import payments.config in a fresh process with a controlled environment.

    The working directory is a temporary one so the developer's own .env file
    cannot leak in and quietly satisfy the settings being tested.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("STRIPE_") and key not in ("PUBLIC_BASE_URL", "DATABASE_URL")
    }
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env.update(overrides)

    return subprocess.run(
        [sys.executable, "-c", "import payments.config"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )


def test_complete_configuration_imports_cleanly(tmp_path):
    result = import_payments_config(CONFIGURED, tmp_path)

    assert result.returncode == 0, result.stderr


def test_missing_key_stops_startup_and_names_it(tmp_path):
    """The message has to be usable by whoever is looking at a downed site."""
    incomplete = {k: v for k, v in CONFIGURED.items() if k != "STRIPE_SECRET_KEY"}

    result = import_payments_config(incomplete, tmp_path)

    assert result.returncode != 0
    assert "will not start" in result.stderr
    assert "STRIPE_SECRET_KEY" in result.stderr
    assert "docs/DEPLOYMENT.md" in result.stderr


def test_deep_link_as_public_base_url_is_rejected(tmp_path):
    """PUBLIC_BASE_URL is this service's own origin, not the app's deep link.

    Stripe would accept the deep link, so the guard is here rather than there.
    Setting it would mean the browser never reaches the success endpoint, and
    no unlock would be written until the webhook arrived.
    """
    wrong = dict(CONFIGURED, PUBLIC_BASE_URL="golfcoachnow://payment-success")

    result = import_payments_config(wrong, tmp_path)

    assert result.returncode != 0
    assert "PUBLIC_BASE_URL must start with http:// or https://" in result.stderr
