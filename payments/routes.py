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
from payments.accounts import unlock_for_user, user_for_token
from payments.auth_routes import bearer_token
from payments.config import settings
from payments.db import get_session
from payments.logging_config import fields, get_logger
from payments.rate_limit import rate_limit
from payments.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscribeRequest,
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
from payments.subscriptions import read_invoice_event, read_subscription_event

logger = get_logger("routes")

router = APIRouter(prefix="/payments", tags=["payments"])

CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"
INVOICE_PAID = "invoice.paid"
INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
SUBSCRIPTION_UPDATED = "customer.subscription.updated"
SUBSCRIPTION_DELETED = "customer.subscription.deleted"

CHECKOUT_MODE_SUBSCRIPTION = "subscription"

SEE_OTHER = status.HTTP_303_SEE_OTHER
STRIPE_SIGNATURE_HEADER = "stripe-signature"


@router.post(
    "/checkout-session",
    response_model=CheckoutSessionResponse,
    summary="Start a payment for one device",
    dependencies=[Depends(rate_limit)],
    responses={
        429: {"description": "Too many requests from this address."},
        502: {"description": "Stripe could not be reached."},
    },
)
def open_checkout_session(payload: CheckoutSessionRequest) -> CheckoutSessionResponse:
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


@router.post(
    "/subscribe",
    response_model=CheckoutSessionResponse,
    summary="Start a monthly subscription",
    dependencies=[Depends(rate_limit)],
    responses={
        429: {"description": "Too many requests from this address."},
        502: {"description": "Stripe could not be reached."},
        503: {"description": "No recurring price is configured yet."},
    },
)
def open_subscription(
    payload: SubscribeRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> CheckoutSessionResponse:
    """Open Checkout for the monthly plan.

    A bearer token is optional but changes what the subscription is attached
    to. Signed in, it hangs off the account and follows the person to a new
    phone. Not signed in, the device is the only handle we have, and losing the
    device loses the subscription. The app should ask for sign in before this
    screen rather than after.

    503 rather than 500 when no price is configured. Nothing is broken; the
    plan is not on sale yet, and that is a different thing to tell a customer.
    """
    if not settings.subscriptions_enabled:
        logger.error("subscribe called with no recurring price configured")
        raise HTTPException(
            status_code=503,
            detail="Subscriptions are not available yet.",
        )

    user = user_for_token(db, bearer_token(request))

    try:
        checkout_session = stripe_gateway.create_subscription_checkout_session(
            device_id=payload.device_id,
            user_id=user.id if user else None,
            customer_email=user.email if user else None,
        )
    except stripe.StripeError as error:
        logger.error(
            "could not create subscription session %s",
            fields(device_id=payload.device_id, error=type(error).__name__),
        )
        raise HTTPException(status_code=502, detail="Could not reach Stripe.") from error

    logger.info(
        "subscription session created %s",
        fields(
            device_id=payload.device_id,
            user_id=user.id if user else None,
            session_id=checkout_session.id,
        ),
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

    if is_subscription_checkout(checkout_session):
        # They paid, so they still go back into the app. What must not happen
        # is a permanent unlock: this is a month, not the product. The webhook
        # is what records subscription access.
        logger.info(
            "subscription checkout returned through the redirect %s",
            fields(session_id=session_id),
        )
        return RedirectResponse(settings.success_deep_link, status_code=SEE_OTHER)

    checkout = read_checkout_session(checkout_session)
    if checkout.can_unlock:
        grant_unlock(db, checkout, SOURCE_SUCCESS_REDIRECT)
    else:
        logger.warning(
            "success redirect for a session that cannot be unlocked %s",
            fields(
                session_id=session_id,
                paid=checkout.paid,
                has_device_id=bool(checkout.device_id),
                ours=checkout.is_ours,
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
    return RedirectResponse(settings.cancel_deep_link, status_code=SEE_OTHER)


@router.get(
    "/unlock-status",
    response_model=UnlockStatusResponse,
    summary="Has this device paid?",
    dependencies=[Depends(rate_limit)],
    responses={429: {"description": "Too many requests from this address."}},
)
def unlock_status(
    request: Request,
    device_id: str | None = None,
    db: Session = Depends(get_session),
) -> UnlockStatusResponse:
    """Answer for the signed in person if there is one, otherwise the device.

    A signed in answer covers every device that person has ever linked, which
    is what makes a purchase survive a reinstall.

    The device path is unchanged. A request with no token behaves exactly as it
    did before accounts existed, so the shipped app keeps working and the login
    screens can arrive whenever the app team is ready.
    """
    user = user_for_token(db, bearer_token(request))
    if user is not None:
        unlock = unlock_for_user(db, user)
        return UnlockStatusResponse(
            device_id=device_id or "",
            unlocked=unlock is not None,
            unlocked_at=unlock.created_at if unlock else None,
        )

    if not device_id:
        raise HTTPException(
            status_code=422,
            detail="Send device_id, or an Authorization bearer token.",
        )

    unlock = find_unlock(db, device_id)
    return UnlockStatusResponse(
        device_id=device_id,
        unlocked=unlock is not None,
        unlocked_at=unlock.created_at if unlock else None,
    )


def is_subscription_checkout(checkout_session) -> bool:
    """Whether this session bought a month rather than the app.

    Two code paths act on a completed checkout: this webhook and the success
    redirect. Both call grant_unlock, so both have to ask this question, and
    getting it right in only one of them is the same bug with half the surface.
    That is not hypothetical - it is what happened, and it took a real payment
    through the redirect to find it, because the first fix only covered the
    webhook and its test only fired the webhook.
    """
    mode = checkout_session["mode"] if "mode" in checkout_session else None
    return mode == CHECKOUT_MODE_SUBSCRIPTION


def _handle_checkout_completed(db: Session, event_id: str, obj) -> None:
    """A checkout finished. Which kind decides everything that follows.

    Both kinds arrive as this one event type, both say payment_status paid, and
    both carry a device ID. The only thing separating a customer who bought the
    app outright from one who paid for a single month is `mode`.

    Getting this wrong in the direction of the one-time path is the expensive
    direction: an Unlock row has no expiry, so a monthly subscriber would own
    the app forever after their first payment and cancelling would take nothing
    away. That is why the check is on subscription mode explicitly rather than
    on a one-time mode, and why anything unrecognised falls through to a
    warning instead of being unlocked.
    """
    if is_subscription_checkout(obj):
        _handle_subscription_checkout(db, event_id, obj)
        return

    checkout = read_checkout_session(obj)
    if checkout.can_unlock:
        grant_unlock(db, checkout, SOURCE_WEBHOOK)
        return

    logger.warning(
        "event carried nothing to unlock %s",
        fields(
            event_id=event_id,
            paid=checkout.paid,
            has_device_id=bool(checkout.device_id),
            ours=checkout.is_ours,
        ),
    )


def _handle_subscription_checkout(db: Session, event_id: str, obj) -> None:
    """Someone started a monthly plan.

    Nothing is recorded yet, and that is deliberate rather than unfinished. The
    subscription tables are not in the schema, and the table name is still with
    the owner of models.py. Granting the permanent unlock in the meantime would
    be worse than recording nothing.

    Nothing reaches here in production either, because the subscribe endpoint
    is closed until a recurring price is configured. If this line ever appears
    in the log it means that changed and the storage did not follow.
    """
    logger.warning(
        "subscription checkout completed, not yet recorded %s",
        fields(
            event_id=event_id,
            session_id=obj["id"] if "id" in obj else None,
            subscription=obj["subscription"] if "subscription" in obj else None,
        ),
    )


def _handle_invoice(db: Session, event_id: str, obj) -> None:
    """A renewal was paid, or failed to be."""
    payment = read_invoice_event(obj)
    logger.warning(
        "subscription invoice received, not yet recorded %s",
        fields(
            event_id=event_id,
            invoice=payment.invoice_id,
            subscription=payment.stripe_subscription_id,
            paid=payment.paid,
            ours=payment.is_ours,
        ),
    )


def _handle_subscription_change(db: Session, event_id: str, obj) -> None:
    """A subscription changed status, or ended."""
    state = read_subscription_event(obj)
    logger.warning(
        "subscription change received, not yet recorded %s",
        fields(
            event_id=event_id,
            subscription=state.stripe_subscription_id,
            status=state.status,
            active=state.is_active,
            cancelling=state.cancel_at_period_end,
        ),
    )


# One handler per event type, and the set of types we accept is taken from the
# keys. Adding an event to the map is the only thing needed to start handling
# it, and there is no second list to forget to update.
EVENT_HANDLERS = {
    CHECKOUT_SESSION_COMPLETED: _handle_checkout_completed,
    INVOICE_PAID: _handle_invoice,
    INVOICE_PAYMENT_FAILED: _handle_invoice,
    SUBSCRIPTION_UPDATED: _handle_subscription_change,
    SUBSCRIPTION_DELETED: _handle_subscription_change,
}


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

    if event_type not in EVENT_HANDLERS:
        logger.info("event type not handled %s", fields(event_id=event_id, type=event_type))
        return Response(status_code=200)

    claimed = claim_event(db, event_id, event_type)
    if claimed is None:
        return Response(status_code=200)

    try:
        EVENT_HANDLERS[event_type](db, event_id, event["data"]["object"])
        mark_event_processed(db, claimed)
    except Exception:
        db.rollback()
        logger.exception("failed to process event %s", fields(event_id=event_id))
        return Response(status_code=500)

    return Response(status_code=200)
