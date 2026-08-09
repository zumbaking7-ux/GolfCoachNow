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
        success_url=build_success_url(),
        cancel_url=build_cancel_url(),
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
