"""Unlock logic. The only module that writes to the unlocks table.

Two rules hold everything together:

1. A device is unlocked when a row exists in `unlocks` for it. Nothing else
   counts, and nothing the client sends can create that row on its own.

2. Both writers - the success redirect and the webhook - go through
   `grant_unlock`, which inserts and lets the database reject the duplicate.
   Reading first and inserting second would let two concurrent requests both
   find an empty table and both insert.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payments.logging_config import fields, get_logger
from payments.models import ProcessedEvent, Unlock, utcnow

logger = get_logger("service")

PAYMENT_STATUS_PAID = "paid"

SOURCE_WEBHOOK = "webhook"
SOURCE_SUCCESS_REDIRECT = "success_redirect"


@dataclass(frozen=True)
class CheckoutDetails:
    """The fields worth keeping from a Stripe Checkout Session.

    Pulled out into a plain object so the rest of the module never has to know
    whether it is holding a live Stripe response or a saved test payload.
    """

    session_id: str
    device_id: str | None
    paid: bool
    amount_total: int
    currency: str
    payment_intent_id: str | None
    customer_email: str | None


def _field(source: Any, key: str) -> Any:
    """Read one field from either a Stripe response object or a plain dict.

    Stripe's objects support source["key"] but not source.get("key") - they are
    not dict subclasses, and attribute lookups for anything that is not a field
    raise AttributeError. A fixture loaded from JSON, meanwhile, is an ordinary
    dict. Indexing with a caught KeyError is the one access pattern that
    behaves the same on both, which is what lets the tests run the same code
    production does.
    """
    if source is None:
        return None
    try:
        return source[key]
    except KeyError:
        return None


def _payment_intent_id(raw: Any) -> str | None:
    """Stripe sends the payment intent as a bare ID or as a nested object."""
    if isinstance(raw, str):
        return raw
    return _field(raw, "id")


def read_checkout_session(checkout_session: Any) -> CheckoutDetails:
    """Flatten a Checkout Session into the fields this service uses."""
    customer_details = _field(checkout_session, "customer_details")
    return CheckoutDetails(
        session_id=_field(checkout_session, "id") or "",
        device_id=_field(checkout_session, "client_reference_id"),
        paid=_field(checkout_session, "payment_status") == PAYMENT_STATUS_PAID,
        amount_total=_field(checkout_session, "amount_total") or 0,
        currency=_field(checkout_session, "currency") or "",
        payment_intent_id=_payment_intent_id(_field(checkout_session, "payment_intent")),
        customer_email=_field(customer_details, "email"),
    )


def find_unlock(session: Session, device_id: str) -> Unlock | None:
    return session.scalars(select(Unlock).where(Unlock.device_id == device_id)).first()


def grant_unlock(session: Session, checkout: CheckoutDetails, source: str) -> bool:
    """Record the unlock for a paid checkout.

    Returns True when this call created the row and False when it was already
    there. Callers use that to decide what to log, not to decide whether the
    device is unlocked - either way, it is.

    The insert runs unconditionally. If a concurrent request gets there first,
    the unique index on device_id raises IntegrityError and this call reports
    the row as pre-existing. The database makes that decision while holding a
    lock, which is why it is safe and a read-then-write would not be.
    """
    if not checkout.paid:
        raise ValueError(f"refusing to unlock an unpaid session {checkout.session_id}")
    if not checkout.device_id:
        raise ValueError(f"session {checkout.session_id} has no client_reference_id")

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
    """Take ownership of a webhook event before doing any work for it.

    Returns the row to work on, or None when there is nothing left to do.

    Three cases, in the order they are checked:

    - A row exists and has a processed_at: a previous delivery finished this
      event. Nothing to do.
    - A row exists with processed_at still NULL: an earlier attempt claimed the
      event and then died. Hand it back so this delivery can finish the job.
    - No row: insert one. If a concurrent delivery inserts first, the unique
      index on stripe_event_id rejects this one and that other request owns it.
    """
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
