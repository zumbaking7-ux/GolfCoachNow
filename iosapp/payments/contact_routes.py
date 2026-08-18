"""The two lower buttons on the front door: Share, and Connect.

Both send an email on somebody's behalf, which makes them the most abusable
endpoints in the service: they take an address a stranger typed and mail it.
That shapes everything here.

  - Sending happens in the background, so a slow provider cannot hold a request
    open on a screen someone is looking at.
  - Both answer 202 and say the same thing whatever happened, so neither can be
    used to find out which addresses exist.
  - Limits are counted per caller and separately per recipient, so one person
    cannot mail the world and the world cannot mail one person.

Neither endpoint spends a coaching rep. Telling a friend about the app is not
practice.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from payments.accounts import normalise_email
from payments.config import settings
from payments.email_sender import send_email
from payments.logging_config import fields, get_logger
from payments.rate_limit import SlidingWindowLimiter, client_key
from payments.schemas import looks_like_an_email

router = APIRouter(tags=["contact"])
logger = get_logger("contact")

TOO_MANY_REQUESTS = 429
SERVICE_UNAVAILABLE = 503

MAX_MESSAGE_LENGTH = 4000

_by_caller = SlidingWindowLimiter(
    settings.share_rate_limit_requests,
    settings.share_rate_limit_window_seconds,
)
_by_recipient = SlidingWindowLimiter(
    settings.share_rate_limit_requests,
    settings.share_rate_limit_window_seconds,
)

ACCEPTED = {"status": "sent"}


class ShareInviteRequest(BaseModel):
    """Who the golfer wants to send the app to."""

    email: str = Field(
        min_length=3, max_length=320, description="Where to send the app link."
    )
    device_id: str = Field(default="", max_length=128)

    _check_email = field_validator("email")(looks_like_an_email)


class FounderMessageRequest(BaseModel):
    """A note for the founder, written in the app."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    # Optional, and only so the founder can reply. Nothing depends on it.
    email: str | None = Field(default=None, max_length=320)
    device_id: str = Field(default="", max_length=128)

    @field_validator("email")
    @classmethod
    def check_email_if_given(cls, value: str | None) -> str | None:
        """Blank is fine here; a malformed address is not.

        Requiring an address would stop somebody sending feedback, which is the
        opposite of what this button is for.
        """
        if value is None or not value.strip():
            return None
        return looks_like_an_email(value)


def _too_many(retry_after: float) -> HTTPException:
    return HTTPException(
        status_code=TOO_MANY_REQUESTS,
        detail="That has been sent a few times already. Try again a little later.",
        headers={"Retry-After": str(max(1, int(retry_after) + 1))},
    )


def _guard(request: Request, recipient: str) -> None:
    """Refuse if either this caller or this address has had enough for now."""
    wait = _by_caller.check(client_key(request))
    if wait is not None:
        raise _too_many(wait)

    wait = _by_recipient.check(recipient)
    if wait is not None:
        logger.warning("one address is being mailed repeatedly %s", fields(to=recipient))
        raise _too_many(wait)


def build_invite(share_url: str) -> str:
    """The email a golfer's friend receives.

    Written to read like a person passed it on, because one did. The last line
    matters: anyone can type anyone's address into a form like this, so the
    recipient is told plainly that ignoring it costs them nothing.
    """
    return (
        "Someone thought you'd like Golf Coach Now.\n"
        "\n"
        "It films your swing, putt or short game and gives you one correction "
        "to work on, straight away.\n"
        "\n"
        f"{share_url}\n"
        "\n"
        "If this doesn't mean anything to you, you can ignore it. Nothing has "
        "been set up in your name.\n"
    )


def build_founder_message(message: str, sender: str | None, device_id: str) -> str:
    """What lands in the founder's inbox.

    The device id is included because it is the only way to connect a message
    to what that person actually did in the app, and support questions are
    unanswerable without it.
    """
    lines = ["A message from inside the app:", "", message.strip(), "", "---"]
    lines.append(f"From: {sender}" if sender else "From: not provided")
    lines.append(f"Device: {device_id or 'not provided'}")
    return "\n".join(lines) + "\n"


@router.post(
    "/share/invite",
    status_code=202,
    summary="Email the app link to a friend",
    responses={
        202: {"description": "Accepted. Answered the same way whether or not it sent."},
        429: {"description": "Too many requests."},
        503: {"description": "Sharing is not switched on yet."},
    },
)
def share_with_a_friend(
    payload: ShareInviteRequest,
    request: Request,
    background: BackgroundTasks,
) -> dict:
    """Send the app link to the address a golfer typed.

    The invite goes to their friend and nowhere else; nothing about it comes
    back to the founder.
    """
    if not settings.sharing_enabled:
        raise HTTPException(
            SERVICE_UNAVAILABLE,
            "Sharing isn't available yet. Please try again soon.",
        )

    recipient = normalise_email(payload.email)
    _guard(request, recipient)

    background.add_task(
        send_email,
        recipient,
        "Someone shared Golf Coach Now with you",
        build_invite(settings.app_share_url),
    )
    logger.info("invite queued %s", fields(device_id=payload.device_id))

    return ACCEPTED


@router.post(
    "/connect/founder",
    status_code=202,
    summary="Send a message to the founder",
    responses={
        202: {"description": "Accepted. Answered the same way whether or not it sent."},
        429: {"description": "Too many requests."},
    },
)
def connect_with_the_founder(
    payload: FounderMessageRequest,
    request: Request,
    background: BackgroundTasks,
) -> dict:
    """Deliver a free-form note to the founder's mailbox."""
    sender = normalise_email(payload.email) if payload.email else None

    # Limited by the sender rather than the destination here. The destination is
    # always the same mailbox, so limiting on it would let one person silence
    # everybody else's messages.
    wait = _by_caller.check(client_key(request))
    if wait is not None:
        raise _too_many(wait)

    background.add_task(
        send_email,
        settings.founder_email,
        "Golf Coach Now — a message from the app",
        build_founder_message(payload.message, sender, payload.device_id),
        sender or "",
    )
    logger.info("founder message queued %s", fields(device_id=payload.device_id))

    return ACCEPTED
