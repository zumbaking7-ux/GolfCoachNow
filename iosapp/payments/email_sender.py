"""Delivering login codes.

One public function behind a provider chosen by configuration, so the rest of
the package never knows or cares which service is sending mail.

Uses urllib from the standard library rather than adding an HTTP client to the
production dependencies. This makes exactly one POST with a JSON body; that is
not worth a new package on the server.

Sending never raises. A provider being down should mean one person asks for
another code, not a 500 on a sign in screen. The failure is logged loudly
instead, because a silent email outage looks identical to nobody trying to
sign in.
"""

import json
import urllib.error
import urllib.request

from payments.config import PROVIDER_CONSOLE, settings
from payments.logging_config import fields, get_logger

logger = get_logger("email")

RESEND_ENDPOINT = "https://api.resend.com/emails"
SEND_TIMEOUT_SECONDS = 10

SUBJECT = "Your Golf Coach Now sign in code"


def build_message(code: str) -> str:
    """The email body.

    The last line matters more than it looks. Anyone can type someone else's
    address into a passwordless login, so the recipient needs to be told that
    ignoring it is safe and costs them nothing.
    """
    return (
        f"Your sign in code is {code}\n"
        "\n"
        f"It expires in {settings.login_code_ttl_minutes} minutes and can only "
        "be used once.\n"
        "\n"
        "If you did not ask to sign in, you can ignore this email. Nothing has "
        "changed on your account.\n"
    )


def send_login_code(email: str, code: str) -> bool:
    """Deliver a code. Returns whether it went out, and never raises."""
    if settings.email_provider == PROVIDER_CONSOLE:
        return _send_to_console(email, code)

    try:
        return _send_via_resend(email, code)
    except Exception:
        # Deliberately broad. Whatever an HTTP client can do to a request
        # thread, it must not become an error on someone's sign in screen.
        logger.exception("login code send failed %s", fields(email=email))
        return False


def _send_to_console(email: str, code: str) -> bool:
    """Local development only. Writes the code to the log and sends nothing.

    Logged at warning so it is impossible to mistake for normal operation, and
    so a production deploy that forgot to set a real provider is visible in the
    log rather than silently failing to sign anybody in.
    """
    logger.warning(
        "EMAIL_PROVIDER is console, no email was sent. Code for %s is %s",
        email,
        code,
    )
    return True


def _send_via_resend(email: str, code: str) -> bool:
    payload = json.dumps(
        {
            "from": settings.email_from,
            "to": [email],
            "subject": SUBJECT,
            "text": build_message(code),
        }
    ).encode()

    request = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=SEND_TIMEOUT_SECONDS) as response:
            logger.info(
                "login code sent %s", fields(email=email, status=response.status)
            )
            return True
    except urllib.error.HTTPError as error:
        # The body usually says which field the provider rejected, and that is
        # the difference between a five minute fix and an afternoon. It cannot
        # contain the code, which is only ever in the payload we sent.
        detail = error.read().decode(errors="replace")[:200]
        logger.error(
            "login code rejected by provider %s",
            fields(email=email, status=error.code, detail=detail),
        )
        return False
