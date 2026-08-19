"""Sign in endpoints.

Three calls: ask for a code, send it back, sign out. The app keeps the token it
gets from the second one and sends it from then on.

Rate limiting here is tighter than elsewhere and counts two things. Per address
stops one caller emailing the world. Per email address stops the world emailing
one person, which the first limit alone does not prevent.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from payments.accounts import (
    normalise_email,
    request_login_code,
    revoke_token,
    verify_login_code,
)
from payments.config import settings
from payments.db import get_session
from payments.email_sender import send_login_code
from payments.logging_config import fields, get_logger
from payments.rate_limit import SlidingWindowLimiter, client_key
from payments.schemas import (
    RequestCodeRequest,
    VerifyCodeRequest,
    VerifyCodeResponse,
)

logger = get_logger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])

BEARER_PREFIX = "bearer "
TOO_MANY_REQUESTS = 429

_by_caller = SlidingWindowLimiter(
    settings.auth_rate_limit_requests,
    settings.auth_rate_limit_window_seconds,
)
_by_email = SlidingWindowLimiter(
    settings.auth_rate_limit_requests,
    settings.auth_rate_limit_window_seconds,
)


def bearer_token(request: Request) -> str | None:
    """Pull the token out of an Authorization header, if there is one."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith(BEARER_PREFIX):
        return header[len(BEARER_PREFIX) :].strip() or None
    return None


def _too_many(retry_after: float) -> HTTPException:
    return HTTPException(
        status_code=TOO_MANY_REQUESTS,
        detail="Too many sign in attempts. Try again shortly.",
        headers={"Retry-After": str(max(1, int(retry_after) + 1))},
    )


@router.post(
    "/request-code",
    status_code=202,
    summary="Email a sign in code",
    responses={
        202: {"description": "Accepted. Sent whether or not an account exists."},
        429: {"description": "Too many requests."},
    },
)
def request_code(
    payload: RequestCodeRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_session),
) -> dict:
    """Send a code to the address given.

    Always answers 202, and always says the same thing. Reporting whether an
    account exists would turn this endpoint into a way of testing which of your
    customers' addresses are registered.

    The email goes out after the response rather than during it. A slow or
    broken email provider should not hold a request open, and the person can
    ask for another code either way.
    """
    address = normalise_email(payload.email)

    # Not behind rate_limit_enabled on purpose. That switch exists so the
    # general limits can be loosened if mobile customers behind one carrier
    # address start seeing 429s. Turning it off must not also leave an endpoint
    # that sends email to any address anyone types wide open.
    wait = _by_caller.check(client_key(request))
    if wait is not None:
        raise _too_many(wait)

    wait = _by_email.check(address)
    if wait is not None:
        logger.warning("sign in flooding one address %s", fields(email=address))
        raise _too_many(wait)

    code = request_login_code(db, address)
    background.add_task(send_login_code, address, code)

    return {"status": "sent"}


@router.post(
    "/verify-code",
    response_model=VerifyCodeResponse,
    summary="Exchange a code for a token",
    responses={
        200: {"description": "Signed in."},
        401: {"description": "Wrong, expired, already used, or too many tries."},
        429: {"description": "Too many requests."},
    },
)
def verify_code(
    payload: VerifyCodeRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> VerifyCodeResponse:
    """Check the code and hand back a token.

    Every failure returns the same 401 with the same message. Distinguishing
    "no code was requested" from "wrong code" from "expired" tells an attacker
    which addresses have accounts and how close they are getting.

    Sending device_id here is what links the phone to the account, and that is
    what makes an earlier purchase from this device findable afterwards.
    """
    wait = _by_caller.check(client_key(request))
    if wait is not None:
        raise _too_many(wait)

    signed_in = verify_login_code(
        db, payload.email, payload.code, payload.device_id, payload.name
    )
    if signed_in is None:
        raise HTTPException(status_code=401, detail="That code is not valid.")

    return VerifyCodeResponse(token=signed_in.token, name=signed_in.name)


@router.post(
    "/sign-out",
    status_code=204,
    summary="Revoke the current token",
    responses={
        204: {"description": "Signed out, or the token was already dead."},
    },
)
def sign_out(request: Request, db: Session = Depends(get_session)) -> Response:
    """Revoke the token being presented.

    Answers 204 either way. Whether the token was live is not something the
    caller needs to know, and saying so would confirm a guessed token exists.
    """
    token = bearer_token(request)
    if token:
        revoke_token(db, token)
    return Response(status_code=204)
