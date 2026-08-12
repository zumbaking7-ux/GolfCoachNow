"""Reading Stripe subscription and invoice objects.

Parsing only. Nothing here touches the database, so every function can be
tested against real captured events without a session, and the tests that cover
it are the ones that would have caught both bugs described below.

Two fields moved in API version 2026-07-29, which is the version this account
sends. Both moves fail silently rather than loudly, which is why they get their
own module with their own tests instead of being read inline.

current_period_end is no longer on the subscription. It is on each subscription
item. Reading the old location returns nothing, so an expiry never gets stored,
nobody's access is ever extended, and no error is raised to say so.

invoice.subscription is no longer on the invoice. It is at
parent.subscription_details.subscription. Reading the old location returns None,
so a renewal cannot be matched to the subscription it renewed. Every Stripe
example still shows the old field.

Both were confirmed against real objects from this account, not from the
documentation, and the captured events are in tests/fixtures.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

PRODUCT_MARKER_KEY = "golf_coach_now"
PRODUCT_MARKER_VALUE = "wedge_unlock"

DEVICE_ID_KEY = "device_id"
USER_ID_KEY = "user_id"

# Statuses where the customer has paid for the period they are in.
#
# trialing counts: a trial is access we chose to give. past_due does too, and
# that is the one worth explaining. It means a renewal charge failed and Stripe
# is still retrying. Cutting access off at the first failed attempt would lock
# out people whose card expired over a weekend and who are about to pay
# successfully. Stripe gives up on its own schedule and then moves the
# subscription to canceled or unpaid, and those are the ones that end access.
ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})

INVOICE_PAID_STATUS = "paid"


@dataclass(frozen=True)
class SubscriptionState:
    """What a customer.subscription.* event tells us."""

    stripe_subscription_id: str
    stripe_customer_id: str
    status: str
    current_period_end: datetime | None
    cancel_at_period_end: bool
    device_id: str | None
    user_id: int | None
    is_ours: bool

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def can_apply(self) -> bool:
        """Whether this event identifies someone we can act on.

        A subscription with no device and no user cannot be applied to anybody,
        and one that is not ours belongs to another product on the same Stripe
        account. Neither is an error, so both are ignored rather than failed.
        """
        return self.is_ours and bool(self.stripe_subscription_id) and (
            self.device_id is not None or self.user_id is not None
        )


@dataclass(frozen=True)
class InvoicePayment:
    """What an invoice.paid or invoice.payment_failed event tells us."""

    invoice_id: str
    stripe_subscription_id: str | None
    stripe_customer_id: str | None
    period_end: datetime | None
    paid: bool
    device_id: str | None
    user_id: int | None
    is_ours: bool


def _field(source: Any, key: str) -> Any:
    """Read a key off a Stripe object or a plain dict.

    Stripe objects are not dict subclasses, so .get() raises AttributeError on
    them. Indexing works on both, and a missing key raises KeyError on both, so
    this is the one access pattern that behaves the same for a live object and
    a fixture loaded from JSON.

    Deliberately not imported from service.py. That module is being cleaned out
    for V1.2 by its owner, and depending on a private name in it would break
    quietly when that happens.
    """
    if source is None:
        return None
    try:
        return source[key]
    except (KeyError, IndexError):
        return None


def _epoch_to_datetime(epoch: Any) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc)


def _identifier(raw: Any) -> str | None:
    """Stripe sends a reference either as an ID string or an expanded object."""
    if isinstance(raw, str):
        return raw or None
    return _field(raw, "id")


def _user_id_from(metadata: Any) -> int | None:
    """Metadata values are always strings, so this has to survive junk."""
    raw = _field(metadata, USER_ID_KEY)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _period_end_from_items(subscription_obj: Any) -> datetime | None:
    """The current period end, read from the subscription's items.

    One item per subscription for this product, but the field is per item
    because Stripe allows a subscription to bill several things on different
    cycles. Taking the latest is the safe reading of "when does access end":
    while any item is still paid for, the customer has not lapsed.
    """
    items = _field(subscription_obj, "items")
    rows = _field(items, "data") or []

    ends = [
        _epoch_to_datetime(_field(row, "current_period_end"))
        for row in rows
    ]
    real = [end for end in ends if end is not None]
    return max(real) if real else None


def read_subscription_event(subscription_obj: Any) -> SubscriptionState:
    """Parse a customer.subscription.created/updated/deleted payload."""
    metadata = _field(subscription_obj, "metadata")

    return SubscriptionState(
        stripe_subscription_id=_field(subscription_obj, "id") or "",
        stripe_customer_id=_identifier(_field(subscription_obj, "customer")) or "",
        status=_field(subscription_obj, "status") or "",
        current_period_end=_period_end_from_items(subscription_obj),
        cancel_at_period_end=bool(_field(subscription_obj, "cancel_at_period_end")),
        device_id=_field(metadata, DEVICE_ID_KEY),
        user_id=_user_id_from(metadata),
        is_ours=_field(metadata, PRODUCT_MARKER_KEY) == PRODUCT_MARKER_VALUE,
    )


def read_invoice_event(invoice_obj: Any) -> InvoicePayment:
    """Parse an invoice.paid or invoice.payment_failed payload.

    Everything about the subscription now hangs off parent, including the
    metadata, so a renewal is still traceable to a person without a second call
    to Stripe.

    The period comes from the invoice line rather than the subscription. That
    is the period actually paid for by this invoice, which is the thing access
    should be granted until. Reading it off the subscription instead would be a
    second source of truth that can disagree.
    """
    parent = _field(invoice_obj, "parent")
    details = _field(parent, "subscription_details")
    metadata = _field(details, "metadata")

    lines = _field(_field(invoice_obj, "lines"), "data") or []
    period = _field(lines[0], "period") if lines else None

    return InvoicePayment(
        invoice_id=_field(invoice_obj, "id") or "",
        stripe_subscription_id=_identifier(_field(details, "subscription")),
        stripe_customer_id=_identifier(_field(invoice_obj, "customer")),
        period_end=_epoch_to_datetime(_field(period, "end")),
        # The boolean `paid` field is gone in this API version and reads as
        # None. Status is the one that still answers the question.
        paid=_field(invoice_obj, "status") == INVOICE_PAID_STATUS,
        device_id=_field(metadata, DEVICE_ID_KEY),
        user_id=_user_id_from(metadata),
        is_ours=_field(metadata, PRODUCT_MARKER_KEY) == PRODUCT_MARKER_VALUE,
    )
