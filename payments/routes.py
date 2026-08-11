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
from payments.rate_limit import rate_limit
from payments.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    UnlockStatusResponse,
)
from payments.service import (
    SOURCE_SUCCESS_REDIRECT,
    SOURCE_WEBHOOK,
    claim_event,
    grant_subscription,
    is_device_active,
    mark_event_processed,
    read_checkout_session,
    read_subscription_event,
    update_subscription_status,
)

logger = get_logger("routes")

router = APIRouter(prefix="/payments", tags=["payments"])

CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"
CUSTOMER_SUBSCRIPTION_UPDATED = "customer.subscription.updated"
CUSTOMER_SUBSCRIPTION_DELETED = "customer.subscription.deleted"
INVOICE_PAYMENT_SUCCEEDED = "invoice.payment_succeeded"
INVOICE_PAYMENT_FAILED = "invoice.payment_failed"

HANDLED_EVENT_TYPES = frozenset({
    CHECKOUT_SESSION_COMPLETED,
    CUSTOMER_SUBSCRIPTION_UPDATED,
    CUSTOMER_SUBSCRIPTION_DELETED,
    INVOICE_PAYMENT_SUCCEEDED,
    INVOICE_PAYMENT_FAILED,
})

SEE_OTHER = status.HTTP_303_SEE_OTHER
STRIPE_SIGNATURE_HEADER = "stripe-signature"


@router.post(
    "/checkout-session",
    response_model=CheckoutSessionResponse,
    summary="Start a subscription for one device",
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

    checkout = read_checkout_session(checkout_session)
    if checkout.can_unlock:
        grant_subscription(db, checkout, SOURCE_SUCCESS_REDIRECT)
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
    summary="Is this device's subscription active?",
    dependencies=[Depends(rate_limit)],
    responses={429: {"description": "Too many requests from this address."}},
)
def unlock_status(
    device_id: str, db: Session = Depends(get_session)
) -> UnlockStatusResponse:
    active, sub = is_device_active(db, device_id)
    return UnlockStatusResponse(
        device_id=device_id,
        unlocked=active,
        unlocked_at=sub.created_at if sub else None,
        subscription_status=sub.status if sub else None,
        current_period_end=sub.current_period_end if sub else None,
    )


def _handle_checkout_completed(db: Session, event_data: dict, source: str) -> None:
    checkout = read_checkout_session(event_data)
    if checkout.can_unlock:
        grant_subscription(db, checkout, source)
    else:
        logger.warning(
            "checkout event carried nothing to unlock %s",
            fields(
                paid=checkout.paid,
                has_device_id=bool(checkout.device_id),
                ours=checkout.is_ours,
            ),
        )


def _handle_subscription_event(db: Session, event_data: dict) -> None:
    update = read_subscription_event(event_data)
    if not update.is_ours:
        logger.info("subscription event not ours %s", fields(sub_id=update.stripe_subscription_id))
        return
    update_subscription_status(db, update)


def _handle_invoice_event(db: Session, event_data: dict, event_type: str) -> None:
    subscription_id = event_data.get("subscription")
    if not subscription_id:
        return
    sub_status = "active" if event_type == INVOICE_PAYMENT_SUCCEEDED else "past_due"
    from payments.service import SubscriptionUpdate, _epoch_to_datetime
    lines = event_data.get("lines", {})
    line_data = lines.get("data", []) if isinstance(lines, dict) else []
    period_end = None
    if line_data:
        period = line_data[0].get("period", {})
        period_end = _epoch_to_datetime(period.get("end"))
    update = SubscriptionUpdate(
        stripe_subscription_id=subscription_id if isinstance(subscription_id, str) else subscription_id.get("id", ""),
        stripe_customer_id=event_data.get("customer", ""),
        status=sub_status,
        current_period_end=period_end,
        device_id=None,
        customer_email=event_data.get("customer_email"),
        is_ours=True,
    )
    update_subscription_status(db, update)


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

    if event_type not in HANDLED_EVENT_TYPES:
        logger.info("event type not handled %s", fields(event_id=event_id, type=event_type))
        return Response(status_code=200)

    claimed = claim_event(db, event_id, event_type)
    if claimed is None:
        return Response(status_code=200)

    try:
        event_data = event["data"]["object"]

        if event_type == CHECKOUT_SESSION_COMPLETED:
            _handle_checkout_completed(db, event_data, SOURCE_WEBHOOK)
        elif event_type in (CUSTOMER_SUBSCRIPTION_UPDATED, CUSTOMER_SUBSCRIPTION_DELETED):
            _handle_subscription_event(db, event_data)
        elif event_type in (INVOICE_PAYMENT_SUCCEEDED, INVOICE_PAYMENT_FAILED):
            _handle_invoice_event(db, event_data, event_type)

        mark_event_processed(db, claimed)
    except Exception:
        db.rollback()
        logger.exception("failed to process event %s", fields(event_id=event_id))
        return Response(status_code=500)

    return Response(status_code=200)
