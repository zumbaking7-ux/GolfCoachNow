"""Logging setup for the payments package.

Log lines are plain key=value pairs so a single payment can be traced with
grep. Every line about a webhook carries its Stripe event ID.

Nothing here ever logs a Stripe payload. Those objects contain the customer's
email and billing address, and they do not belong in application logs.
"""

import logging

from payments.config import settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_configured = False


def configure_logging() -> None:
    """Attach a handler to the payments logger. Safe to call more than once."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger = logging.getLogger("payments")
    logger.setLevel(settings.log_level.upper())
    logger.addHandler(handler)
    logger.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"payments.{name}")


def fields(**pairs: object) -> str:
    """Render structured fields as key=value text.

    Keys with a value of None are dropped, so an optional field simply does not
    appear rather than logging the word "None".
    """
    return " ".join(f"{key}={value}" for key, value in pairs.items() if value is not None)
