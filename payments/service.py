"""One-time purchases: reading a Checkout Session and recording an unlock.

Subscriptions are not here. They live in subscriptions.py for parsing and
subscription_service.py for storage, and the docstring this replaced described
a subscription path that was reverted before launch and removed in the commit
that added the real one.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payments.logging_config import fields, get_logger
from payments.models import ProcessedEvent, Unlock, utcnow
from payments.stripe_gateway import PRODUCT_MARKER_KEY, PRODUCT_MARKER_VALUE

logger = get_logger("service")

PAYMENT_STATUS_PAID = "paid"

SOURCE_WEBHOOK = "webhook"
SOURCE_SUCCESS_REDIRECT = "success_redirect"

@dataclass(frozen=True)
class CheckoutDetails:
    session_id: str
    device_id: str | None
    paid: bool
    is_ours: bool
    amount_total: int
    currency: str
    payment_intent_id: str | None
    customer_email: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None

    @property
    def can_unlock(self) -> bool:
        return self.paid and bool(self.device_id) and self.is_ours


def _field(source: Any, key: str) -> Any:
    if source is None:
        return None
    try:
        return source[key]
    except KeyError:
        return None


def _payment_intent_id(raw: Any) -> str | None:
    if isinstance(raw, str):
        return raw
    return _field(raw, "id")


def _subscription_id(raw: Any) -> str | None:
    if isinstance(raw, str):
        return raw
    return _field(raw, "id")


def _customer_id(raw: Any) -> str | None:
    if isinstance(raw, str):
        return raw
    return _field(raw, "id")


def _epoch_to_datetime(epoch: Any) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc)


def read_checkout_session(checkout_session: Any) -> CheckoutDetails:
    customer_details = _field(checkout_session, "customer_details")
    metadata = _field(checkout_session, "metadata")
    return CheckoutDetails(
        session_id=_field(checkout_session, "id") or "",
        device_id=_field(checkout_session, "client_reference_id"),
        paid=_field(checkout_session, "payment_status") == PAYMENT_STATUS_PAID,
        is_ours=_field(metadata, PRODUCT_MARKER_KEY) == PRODUCT_MARKER_VALUE,
        amount_total=_field(checkout_session, "amount_total") or 0,
        currency=_field(checkout_session, "currency") or "",
        payment_intent_id=_payment_intent_id(_field(checkout_session, "payment_intent")),
        customer_email=_field(customer_details, "email"),
        stripe_customer_id=_customer_id(_field(checkout_session, "customer")),
        stripe_subscription_id=_subscription_id(_field(checkout_session, "subscription")),
    )


def find_unlock(session: Session, device_id: str) -> Unlock | None:
    return session.scalars(select(Unlock).where(Unlock.device_id == device_id)).first()


def is_device_active(session: Session, device_id: str) -> tuple[bool, Subscription | None]:
    sub = find_subscription(session, device_id)
    if sub and sub.status in ACTIVE_STATUSES:
        return True, sub
    unlock = find_unlock(session, device_id)
    if unlock:
        return True, None
    return False, None


def grant_unlock(session: Session, checkout: CheckoutDetails, source: str) -> bool:
    if not checkout.paid:
        raise ValueError(f"refusing to unlock an unpaid session {checkout.session_id}")
    if not checkout.device_id:
        raise ValueError(f"session {checkout.session_id} has no client_reference_id")
    if not checkout.is_ours:
        raise ValueError(f"session {checkout.session_id} was not created by this service")

    session.add(
        Unlock(
            device_id=checkout.device_id,
            checkout_session_id=checkout.session_id,
            payment_intent_id=checkout.payment_intent_id,
            amount_total=checkout.amount_total,
            currency=checkout.currency,
            customer_email=checkout.customer_email,
            status=PAYMENT_STATUS_PAID,
            source=source,
        )
    )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        logger.info(
            "unlock already present %s",
            fields(device_id=checkout.device_id, session_id=checkout.session_id, source=source),
        )
        return False

    logger.info(
        "unlock written %s",
        fields(device_id=checkout.device_id, session_id=checkout.session_id, source=source),
    )
    return True


def claim_event(session: Session, event_id: str, event_type: str) -> ProcessedEvent | None:
    existing = session.scalars(
        select(ProcessedEvent).where(ProcessedEvent.stripe_event_id == event_id)
    ).first()

    if existing is not None:
        if existing.processed_at is not None:
            logger.info("event already processed %s", fields(event_id=event_id))
            return None
        logger.warning("retrying event left unfinished %s", fields(event_id=event_id))
        return existing

    claimed = ProcessedEvent(stripe_event_id=event_id, event_type=event_type)
    session.add(claimed)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        logger.info("event claimed by a concurrent delivery %s", fields(event_id=event_id))
        return None

    return claimed


def mark_event_processed(session: Session, event: ProcessedEvent) -> None:
    event.processed_at = utcnow()
    session.commit()
