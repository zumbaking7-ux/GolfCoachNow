"""Every call to Stripe lives here.

Keeping them in one module means the rest of the package can be tested without
touching the network, and there is one place to look when checking what this
service actually asks Stripe to do.
"""

import stripe

from payments.config import settings

stripe.api_key = settings.stripe_secret_key

# Stripe substitutes the real session ID for this literal string when it builds
# the redirect. It has to be passed through exactly as written.
CHECKOUT_SESSION_ID_TEMPLATE = "{CHECKOUT_SESSION_ID}"

CHECKOUT_MODE_ONE_TIME = "payment"
CHECKOUT_MODE_SUBSCRIPTION = "subscription"

PRODUCT_MARKER_KEY = "golf_coach_now"
PRODUCT_MARKER_VALUE = "wedge_unlock"

# Carried in subscription metadata so later events can be tied back to someone.
DEVICE_ID_KEY = "device_id"
USER_ID_KEY = "user_id"


def build_success_url() -> str:
    return (
        f"{settings.public_base_url}/payments/success"
        f"?session_id={CHECKOUT_SESSION_ID_TEMPLATE}"
    )


def build_cancel_url() -> str:
    return f"{settings.public_base_url}/payments/cancel"


def create_checkout_session(device_id: str) -> stripe.checkout.Session:
    """Open a Checkout Session for one unit of the configured price.

    client_reference_id is the whole reason this is created server-side rather
    than using a static payment link. It is what ties the payment to a device,
    and Stripe hands it back on the webhook event.
    """
    return stripe.checkout.Session.create(
        mode=CHECKOUT_MODE_ONE_TIME,
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        client_reference_id=device_id,
        metadata={PRODUCT_MARKER_KEY: PRODUCT_MARKER_VALUE},
        success_url=build_success_url(),
        cancel_url=build_cancel_url(),
    )


def create_subscription_checkout_session(
    device_id: str, user_id: int | None = None, customer_email: str | None = None
) -> stripe.checkout.Session:
    """Open a Checkout Session for the monthly plan.

    subscription_data.metadata is the important part, and it is not the same
    thing as the metadata argument below. Session metadata stays on the session:
    the invoice.paid and customer.subscription.* events that arrive every month
    afterwards have never seen it. Only what is set here is copied onto the
    subscription itself, and from there onto each invoice, so this is what makes
    a renewal twelve months from now traceable to a person.

    client_reference_id is still set because it costs nothing and keeps the
    first event readable the same way one-time checkout is. It is the
    subscription metadata that does the work after that.

    user_id is what a subscription should really hang off, since accounts
    outlive handsets. It is optional because someone can subscribe before ever
    signing in, and in that case the device is all we have.
    """
    subscription_metadata = {
        PRODUCT_MARKER_KEY: PRODUCT_MARKER_VALUE,
        DEVICE_ID_KEY: device_id,
    }
    if user_id is not None:
        subscription_metadata[USER_ID_KEY] = str(user_id)

    parameters = {
        "mode": CHECKOUT_MODE_SUBSCRIPTION,
        "line_items": [
            {"price": settings.stripe_subscription_price_id, "quantity": 1}
        ],
        "client_reference_id": device_id,
        "metadata": {PRODUCT_MARKER_KEY: PRODUCT_MARKER_VALUE},
        "subscription_data": {"metadata": subscription_metadata},
        "success_url": build_success_url(),
        "cancel_url": build_cancel_url(),
    }
    if customer_email:
        # Saves them retyping it, and keeps the Stripe customer matched to the
        # account they signed in with rather than whatever they type at checkout.
        parameters["customer_email"] = customer_email

    return stripe.checkout.Session.create(**parameters)


def create_billing_portal_session(customer_id: str) -> stripe.billing_portal.Session:
    """Open Stripe's own page for managing a subscription.

    Cancelling, updating a card and reading invoices all happen there rather
    than in code here. That is not laziness: those flows carry dunning rules,
    proration and tax handling that would have to be rebuilt and kept correct,
    and getting them wrong shows up as money.

    Whatever they change comes back to us as a webhook. This return trip is
    navigation only, so nothing is read from it.
    """
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=settings.portal_return_deep_link,
    )


def retrieve_checkout_session(session_id: str) -> stripe.checkout.Session:
    """Ask Stripe about a session.

    The success endpoint uses this instead of believing the redirect it was
    given. Anyone can open that URL; only Stripe can say whether it was paid.
    """
    return stripe.checkout.Session.retrieve(session_id)


def construct_event(payload: bytes, signature_header: str) -> stripe.Event:
    """Verify a webhook signature and return the parsed event.

    payload must be the exact bytes of the request body. Stripe signs those
    bytes, so parsing the JSON and re-serialising it changes key order and
    whitespace and the signature stops matching.

    Raises ValueError for malformed JSON and
    stripe.SignatureVerificationError when the signature does not match.
    """
    return stripe.Webhook.construct_event(
        payload, signature_header, settings.stripe_webhook_secret
    )
