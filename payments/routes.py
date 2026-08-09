"""HTTP endpoints for payments.

The mobile app talks to three of these: it creates a Checkout Session, it is
sent through the success redirect by the browser, and it asks for unlock status
on launch. The webhook is Stripe talking to us and is never called by the app.
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from payments import stripe_gateway
from payments.config import settings
from payments.db import get_session
from payments.logging_config import fields, get_logger
from payments.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    UnlockStatusResponse,
)
from payments.service import (
    SOURCE_SUCCESS_REDIRECT,
    SOURCE_WEBHOOK,
    claim_event,
    find_unlock,
    grant_unlock,
    mark_event_processed,
    read_checkout_session,
)

logger = get_logger("routes")

router = APIRouter(prefix="/payments", tags=["payments"])

CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"

# Stripe is told to send only this event type. Anything else that arrives is
# acknowledged and ignored, which is how you stop Stripe resending it.
HANDLED_EVENT_TYPES = frozenset({CHECKOUT_SESSION_COMPLETED})

SEE_OTHER = status.HTTP_303_SEE_OTHER
STRIPE_SIGNATURE_HEADER = "stripe-signature"


@router.post(
    "/checkout-session",
    response_model=CheckoutSessionResponse,
    summary="Start a payment for one device",
    responses={502: {"description": "Stripe could not be reached."}},
)
def open_checkout_session(payload: CheckoutSessionRequest) -> CheckoutSessionResponse:
    """Create a Checkout Session bound to the calling device.

    The device ID is stored on the session as client_reference_id. That is the
    only link between the payment and the device, and it is set here rather
    than sent by the browser so the client cannot choose it later.
    """
    try:
        checkout_session = stripe_gateway.create_checkout_session(payload.device_id)
    except stripe.StripeError as error:
        logger.error(
            "could not create checkout session %s",
            fields(device_id=payload.device_id, error=type(error).__name__),
        )
        raise HTTPException(status_code=502, detail="Could not reach Stripe.") from error

    logger.info(
        "checkout session created %s",
        fields(device_id=payload.device_id, session_id=checkout_session.id),
    )
    return CheckoutSessionResponse(
        checkout_url=checkout_session.url,
        session_id=checkout_session.id,
    )


@router.get(
    "/success",
    response_class=RedirectResponse,
    status_code=SEE_OTHER,
    summary="Where Stripe sends the browser after payment",
    responses={
        303: {"description": "Redirect to the app's success deep link."},
        400: {"description": "The session_id is not a session Stripe knows about."},
    },
)
def payment_success(
    session_id: str, db: Session = Depends(get_session)
) -> RedirectResponse:
    """Confirm the payment with Stripe, record the unlock, then hand off to the app.

    Being called proves nothing - anyone can open this URL with any session ID.
    The unlock is written only because Stripe, asked directly, says the session
    is paid.

    The redirect happens either way. The app does not read its unlock state
    from the deep link, it asks /unlock-status, so there is nothing to gain by
    sending different links for paid and unpaid.
    """
    try:
        checkout_session = stripe_gateway.retrieve_checkout_session(session_id)
    except stripe.InvalidRequestError as error:
        logger.warning("success redirect with unknown session %s", fields(session_id=session_id))
        raise HTTPException(status_code=400, detail="Unknown checkout session.") from error
    except stripe.StripeError as error:
        logger.error(
            "could not retrieve checkout session %s",
            fields(session_id=session_id, error=type(error).__name__),
        )
        raise HTTPException(status_code=502, detail="Could not reach Stripe.") from error

    checkout = read_checkout_session(checkout_session)
    if checkout.paid and checkout.device_id:
        grant_unlock(db, checkout, SOURCE_SUCCESS_REDIRECT)
    else:
        logger.warning(
            "success redirect for a session that cannot be unlocked %s",
            fields(
                session_id=session_id,
                paid=checkout.paid,
                has_device_id=bool(checkout.device_id),
            ),
        )

    return RedirectResponse(settings.success_deep_link, status_code=SEE_OTHER)


@router.get(
    "/cancel",
    response_class=RedirectResponse,
    status_code=SEE_OTHER,
    summary="Where Stripe sends the browser if the user backs out",
)
def payment_cancelled() -> RedirectResponse:
    """Mirrors the success route: the browser lands here, then goes to the app."""
    return RedirectResponse(settings.cancel_deep_link, status_code=SEE_OTHER)


@router.get(
    "/unlock-status",
    response_model=UnlockStatusResponse,
    summary="Has this device paid?",
)
def unlock_status(
    device_id: str, db: Session = Depends(get_session)
) -> UnlockStatusResponse:
    """The app's source of truth, called on launch and after the deep link.

    Always answers, including for devices that have never paid, so the app does
    not have to treat "no" as an error.
    """
    unlock = find_unlock(db, device_id)
    return UnlockStatusResponse(
        device_id=device_id,
        unlocked=unlock is not None,
        unlocked_at=unlock.created_at if unlock else None,
    )


@router.post(
    "/webhook",
    summary="Stripe event delivery",
    responses={
        200: {"description": "Handled, duplicate, or an event type we ignore."},
        400: {"description": "Signature did not verify. Stripe will not retry."},
        500: {"description": "Handled event that failed. Stripe will retry."},
    },
)
async def stripe_webhook(request: Request, db: Session = Depends(get_session)) -> Response:
    """Receive an event from Stripe and unlock the device it belongs to.

    The status code is the reply to Stripe about whether to send this event
    again, so each return below is a deliberate instruction:

    400  the signature failed, so this did not come from Stripe. No retry.
    200  handled, already handled, or an event type we do not care about.
    500  we should have handled it and could not. Please retry.

    This is `async def` on purpose. Signature verification needs the exact
    bytes of the body, and `await request.body()` is how to get them before
    anything parses the JSON.
    """
    payload = await request.body()
    signature = request.headers.get(STRIPE_SIGNATURE_HEADER, "")

    try:
        event = stripe_gateway.construct_event(payload, signature)
    except stripe.SignatureVerificationError:
        logger.warning("rejected webhook, signature did not verify")
        return Response(status_code=400)
    except ValueError:
        logger.warning("rejected webhook, body was not valid JSON")
        return Response(status_code=400)

    event_id = event["id"]
    event_type = event["type"]
    logger.info("event received %s", fields(event_id=event_id, type=event_type))

    if event_type not in HANDLED_EVENT_TYPES:
        logger.info("event type not handled %s", fields(event_id=event_id, type=event_type))
        return Response(status_code=200)

    claimed = claim_event(db, event_id, event_type)
    if claimed is None:
        return Response(status_code=200)

    try:
        checkout = read_checkout_session(event["data"]["object"])
        if checkout.paid and checkout.device_id:
            grant_unlock(db, checkout, SOURCE_WEBHOOK)
        else:
            logger.warning(
                "event carried nothing to unlock %s",
                fields(
                    event_id=event_id,
                    paid=checkout.paid,
                    has_device_id=bool(checkout.device_id),
                ),
            )
        mark_event_processed(db, claimed)
    except Exception:
        db.rollback()
        # processed_at stays NULL, so Stripe's retry picks the event back up.
        logger.exception("failed to process event %s", fields(event_id=event_id))
        return Response(status_code=500)

    return Response(status_code=200)
