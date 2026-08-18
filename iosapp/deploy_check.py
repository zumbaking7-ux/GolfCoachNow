"""Read-only diagnostic for the deployed backend.

Run from the project directory on the server:

    python3 deploy_check.py

Answers, in one pass, the questions that otherwise take a day of back and forth:
whether the video analysis dependencies are actually installed, whether the
sign in email provider is configured, which copy of the source is running, and
what state the database is in.

Changes nothing. Prints no secret values - only whether each one is set.
"""

import importlib
import os
import shutil
import sqlite3
import subprocess
import sys

# Names whose values must never be printed. Presence is reported instead.
SECRETS = {
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "RESEND_API_KEY",
    "DATABASE_URL",  # may embed a Postgres password
}

CORE_PACKAGES = [
    ("fastapi", "web framework"),
    ("stripe", "payments"),
    ("sqlalchemy", "database"),
    ("alembic", "migrations"),
    ("pydantic_settings", "configuration"),
    ("a2wsgi", "ASGI to WSGI wrapper, production only"),
    ("uvicorn", "local dev server, not needed in production"),
]

ANALYSIS_PACKAGES = [
    ("mediapipe", "Tier 1 pose tracking"),
    ("cv2", "Tier 2 motion analysis (opencv-python)"),
    ("numpy", "required by both tiers"),
]

ENV_VARS = [
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_ID",
    "STRIPE_SUBSCRIPTION_PRICE_ID",
    "PUBLIC_BASE_URL",
    "SUCCESS_DEEP_LINK",
    "CANCEL_DEEP_LINK",
    "PORTAL_RETURN_DEEP_LINK",
    "DATABASE_URL",
    "LOG_LEVEL",
    "RATE_LIMIT_ENABLED",
    "VIDEO_BASE_URL",
    "STRICT_ANALYSIS",
    "EMAIL_PROVIDER",
    "RESEND_API_KEY",
    "EMAIL_FROM",
]

TABLES = [
    "unlocks",
    "user_subscriptions",
    "daily_usage",
    "rep_results",
    "analytics_events",
    "users",
    "login_codes",
    "auth_tokens",
    "user_devices",
    "processed_events",
]

findings = []


def section(title):
    print()
    print(title)
    print("-" * len(title))


def check_packages(packages, label):
    section(label)
    missing = []
    for name, why in packages:
        try:
            mod = importlib.import_module(name)
            version = getattr(mod, "__version__", "")
            print("  present  {:22s} {:10s} {}".format(name, version, why))
        except Exception:
            missing.append(name)
            print("  MISSING  {:22s} {:10s} {}".format(name, "", why))
    return missing


def main():
    print("=" * 66)
    print("GolfCoachNow deployment diagnostic")
    print("=" * 66)

    section("Interpreter")
    print("  python   ", sys.version.split()[0])
    print("  executable", sys.executable)
    print("  cwd      ", os.getcwd())

    check_packages(CORE_PACKAGES, "Core dependencies")
    missing_analysis = check_packages(ANALYSIS_PACKAGES, "Video analysis dependencies")

    if missing_analysis:
        findings.append(
            "Video analysis packages missing ({}). Real swing analysis cannot "
            "run; every module falls back to metadata scoring, which does not "
            "look at the video.".format(", ".join(missing_analysis))
        )
    else:
        findings.append(
            "Video analysis packages are all present, so Tier 1/2 analysis can "
            "run for the swing module. Putt and short game are gated out in "
            "code regardless."
        )

    section("External tools")
    for tool in ("ffprobe", "ffmpeg"):
        path = shutil.which(tool)
        if path:
            print("  present  {:10s} {}".format(tool, path))
        else:
            print("  MISSING  {:10s} (metadata fallback degrades to file hashing)".format(tool))

    section("Environment variables (values never printed)")
    for name in ENV_VARS:
        raw = os.environ.get(name)
        if raw is None:
            state = "not set"
            detail = ""
        elif raw == "":
            state = "set but EMPTY"
            detail = ""
        elif name in SECRETS:
            state = "set"
            detail = "({} chars)".format(len(raw))
        else:
            state = "set"
            detail = "= {}".format(raw)
        print("  {:32s} {:14s} {}".format(name, state, detail))

    provider = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower()
    if provider != "resend":
        findings.append(
            "EMAIL_PROVIDER is {!r}, not 'resend'. Sign in codes are written to "
            "the log and no email is sent, so nobody can sign in.".format(
                provider or "unset (defaults to console)"
            )
        )
    elif not os.environ.get("RESEND_API_KEY"):
        findings.append(
            "EMAIL_PROVIDER is 'resend' but RESEND_API_KEY is empty. The app "
            "should have refused to start; check which settings it actually loaded."
        )
    else:
        findings.append("Sign in email delivery is configured.")

    if not (os.environ.get("STRIPE_SUBSCRIPTION_PRICE_ID") or "").strip():
        findings.append(
            "STRIPE_SUBSCRIPTION_PRICE_ID is empty, so /payments/subscribe "
            "answers 503 and the monthly plan cannot be sold."
        )

    section("Which source tree is running")
    try:
        server = importlib.import_module("server")
        exts = getattr(server, "ALLOWED_EXTENSIONS", set())
        print("  ALLOWED_EXTENSIONS:", sorted(exts))
        if "webm" in exts:
            print("  -> matches the iosapp/ copy (accepts webm from the web app)")
            findings.append("Deployed source matches the iosapp/ tree.")
        else:
            print("  -> matches the root copy (rejects webm, and does not pass")
            print("     the module through to analyze_video, so putt and short")
            print("     game uploads are scored against swing faults)")
            findings.append(
                "Deployed source matches the ROOT tree, which rejects webm "
                "uploads from the web app and mis-scores putt/short game."
            )
    except Exception as exc:
        print("  could not import server.py:", exc)
        print("  (run this from the directory containing server.py)")

    section("Database")
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite"):
        path = url.split("///")[-1]
        print("  engine    sqlite")
        print("  path      ", path)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print("  size      ", "{:,} bytes".format(size))
            try:
                conn = sqlite3.connect("file:{}?mode=ro".format(path), uri=True)
                for table in TABLES:
                    try:
                        n = conn.execute(
                            "select count(*) from {}".format(table)
                        ).fetchone()[0]
                        print("  {:22s} {:>8,} rows".format(table, n))
                    except sqlite3.OperationalError:
                        print("  {:22s} {:>8s}".format(table, "absent"))
                conn.close()
            except Exception as exc:
                print("  could not read database:", exc)
        else:
            print("  FILE DOES NOT EXIST at that path")
            findings.append(
                "The database file named by DATABASE_URL does not exist. If "
                "customers have paid, their unlock records are not where the "
                "app is looking."
            )
    elif url:
        print("  engine    not sqlite; inspect manually")
    else:
        print("  DATABASE_URL not set")

    section("Summary")
    for i, f in enumerate(findings, 1):
        print("  {}. {}".format(i, f))
    print()
    print("Nothing was modified by this script.")


if __name__ == "__main__":
    main()
