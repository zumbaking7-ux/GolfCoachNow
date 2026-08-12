"""Reading and writing subscription state.

Kept apart from subscriptions.py, which only parses Stripe payloads and never
touches a session. Splitting them means a parsing test cannot fail for a
database reason and vice versa.
"""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payments.accounts_models import User, UserDevice
from payments.logging_config import fields, get_logger
from payments.subscription_models import UserSubscription
from payments.subscriptions import ACTIVE_STATUSES, InvoicePayment, SubscriptionState

logger = get_logger("subscriptions")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes even for timezone-aware columns."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def has_access(subscription: UserSubscription) -> bool:
    """Whether this subscription entitles someone to the product right now.

    Two conditions, and both are needed for different reasons.

    The status has to be one Stripe considers current. That covers a card that
    failed and is being retried, which is not a reason to lock somebody out.

    The paid period also has to still be running. Status alone is not enough,
    because a status is only as fresh as the last webhook that arrived. Miss a
    cancellation and the row says active forever. A date cannot go stale that
    way: it either has not been reached yet or it has.
    """
    if subscription.status not in ACTIVE_STATUSES:
        return False

    period_end = _as_utc(subscription.current_period_end)
    if period_end is None:
        # No invoice has been seen yet, which happens between checkout and the
        # first invoice event. Trust the status for that short window rather
        # than deny access to somebody who has just paid.
        return True

    return period_end > _now()


def device_ids_for_user(session: Session, user: User) -> list[str]:
    return list(
        session.scalars(
            select(UserDevice.device_id).where(UserDevice.user_id == user.id)
        ).all()
    )


def find_subscriptions(
    session: Session, user: User | None = None, device_id: str | None = None
) -> list[UserSubscription]:
    """Every subscription belonging to this person or this device.

    Signed in, that means all of their devices as well as the account, which is
    what lets a subscription started on a lost phone be found from a new one.
    """
    conditions = []

    if user is not None:
        conditions.append(UserSubscription.user_id == user.id)
        linked = device_ids_for_user(session, user)
        if linked:
            conditions.append(UserSubscription.device_id.in_(linked))

    if device_id:
        conditions.append(UserSubscription.device_id == device_id)

    if not conditions:
        return []

    return list(
        session.scalars(
            select(UserSubscription)
            .where(or_(*conditions))
            .order_by(UserSubscription.id.desc())
        ).all()
    )


def active_subscription(
    session: Session, user: User | None = None, device_id: str | None = None
) -> UserSubscription | None:
    """The live subscription for this person or device, if there is one.

    Rows accumulate, so somebody who cancelled and came back has several and
    only one of them is current. Newest first, first with access wins.
    """
    for subscription in find_subscriptions(session, user=user, device_id=device_id):
        if has_access(subscription):
            return subscription
    return None


def _by_stripe_id(session: Session, stripe_subscription_id: str) -> UserSubscription | None:
    """Its own function so the tests can force the race in record_subscription."""
    return session.scalars(
        select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        )
    ).first()


def _resolve_user_id(session: Session, state: SubscriptionState) -> int | None:
    """Who this subscription belongs to.

    The user ID in the metadata is what checkout put there. If it is absent,
    the device may since have been linked to an account by somebody signing in,
    so the link table is worth asking before giving up. That is what lets a
    subscription started before sign in end up attached to the person anyway.
    """
    if state.user_id is not None:
        return state.user_id

    if not state.device_id:
        return None

    link = session.scalars(
        select(UserDevice).where(UserDevice.device_id == state.device_id)
    ).first()
    return link.user_id if link else None


def record_subscription(session: Session, state: SubscriptionState) -> UserSubscription | None:
    """Write what Stripe just told us about a subscription.

    Events for one subscription arrive repeatedly and out of order: a renewal
    and a cancellation can cross, and Stripe retries anything that did not get
    a 2xx. So this is an upsert keyed on Stripe's own subscription ID, with the
    unique index as the thing that actually enforces one row rather than a
    check that another request can slip between.

    Returns None when the event names nobody we can act on, which is not an
    error - another product on the same Stripe account looks exactly like that.
    """
    if not state.can_apply:
        logger.info(
            "subscription event names nobody to apply it to %s",
            fields(
                subscription=state.stripe_subscription_id,
                ours=state.is_ours,
                has_device=bool(state.device_id),
                has_user=state.user_id is not None,
            ),
        )
        return None

    existing = _by_stripe_id(session, state.stripe_subscription_id)

    if existing is None:
        subscription = UserSubscription(
            user_id=_resolve_user_id(session, state),
            device_id=state.device_id,
            stripe_customer_id=state.stripe_customer_id,
            stripe_subscription_id=state.stripe_subscription_id,
            status=state.status,
            current_period_end=state.current_period_end,
            cancel_at_period_end=state.cancel_at_period_end,
        )
        try:
            # Savepoint rather than a bare flush. Two deliveries of the same
            # event arriving together means one loses the unique index, and a
            # plain rollback would discard the caller's whole transaction
            # including the processed_events row that stops the retry.
            with session.begin_nested():
                session.add(subscription)
        except IntegrityError:
            existing = _by_stripe_id(session, state.stripe_subscription_id)
            if existing is None:
                raise
        else:
            session.commit()
            logger.info(
                "subscription recorded %s",
                fields(
                    subscription=state.stripe_subscription_id,
                    status=state.status,
                    user_id=subscription.user_id,
                    device_id=state.device_id,
                ),
            )
            return subscription

    return _apply_update(session, existing, state)


def _apply_update(
    session: Session, subscription: UserSubscription, state: SubscriptionState
) -> UserSubscription:
    """Update an existing row, refusing to move the period end backwards.

    Out of order delivery is normal. A cancellation event carries the period
    end that was current when it fired, and if it arrives after a renewal it
    would otherwise rewind the paid period and lock out somebody who has paid
    for the month. Status and the cancellation flag are always taken from the
    newest event; the date only ever moves forward.
    """
    subscription.status = state.status
    subscription.cancel_at_period_end = state.cancel_at_period_end
    subscription.stripe_customer_id = (
        state.stripe_customer_id or subscription.stripe_customer_id
    )

    if subscription.user_id is None:
        subscription.user_id = _resolve_user_id(session, state)
    if subscription.device_id is None:
        subscription.device_id = state.device_id

    incoming = state.current_period_end
    current = _as_utc(subscription.current_period_end)
    if incoming is not None and (current is None or incoming > current):
        subscription.current_period_end = incoming

    subscription.updated_at = _now()
    session.commit()

    logger.info(
        "subscription updated %s",
        fields(
            subscription=subscription.stripe_subscription_id,
            status=subscription.status,
            cancelling=subscription.cancel_at_period_end,
            until=subscription.current_period_end,
        ),
    )
    return subscription


def record_invoice(session: Session, payment: InvoicePayment) -> UserSubscription | None:
    """Extend access when a renewal is paid.

    Only the paid period moves here. Status belongs to the
    customer.subscription.* events, which carry Stripe's own view of it; an
    invoice says what was paid for, not what state the subscription is in.

    A failed payment deliberately changes nothing. Stripe keeps retrying and
    moves the subscription to past_due, and cutting access off at the first
    failed attempt would lock out somebody whose card expired over a weekend.
    """
    if not payment.stripe_subscription_id or not payment.paid:
        return None

    subscription = _by_stripe_id(session, payment.stripe_subscription_id)
    if subscription is None:
        # The invoice can beat customer.subscription.created. Nothing to
        # extend yet; the subscription event will bring the period with it.
        logger.info(
            "invoice for a subscription not recorded yet %s",
            fields(
                invoice=payment.invoice_id,
                subscription=payment.stripe_subscription_id,
            ),
        )
        return None

    incoming = payment.period_end
    current = _as_utc(subscription.current_period_end)
    if incoming is not None and (current is None or incoming > current):
        subscription.current_period_end = incoming
        subscription.updated_at = _now()
        session.commit()
        logger.info(
            "access extended by a paid invoice %s",
            fields(
                subscription=subscription.stripe_subscription_id,
                until=incoming,
            ),
        )

    return subscription
