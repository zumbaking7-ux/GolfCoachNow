"""Request and response bodies.

FastAPI turns these into the OpenAPI schema served at /docs, which is the
contract the mobile app is written against. The examples below show up there.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

DEVICE_ID_MAX_LENGTH = 255


class CheckoutSessionRequest(BaseModel):
    """Sent by the app when the user taps buy."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"device_id": "8f14e45fceea167a"}}
    )

    device_id: str = Field(
        min_length=1,
        max_length=DEVICE_ID_MAX_LENGTH,
        description=(
            "The device's own identifier. Android ANDROID_ID or iOS "
            "identifierForVendor. Stored on the Checkout Session as "
            "client_reference_id and used later to decide who to unlock."
        ),
    )


class CheckoutSessionResponse(BaseModel):
    """Where to send the user to pay."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_a1b2c3",
                "session_id": "cs_test_a1b2c3",
            }
        }
    )

    checkout_url: str = Field(description="Open this in a browser. Expires after 24 hours.")
    session_id: str = Field(description="Stripe Checkout Session ID, useful for support.")


class UnlockStatusResponse(BaseModel):
    """The authoritative answer to whether a device has paid."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "8f14e45fceea167a",
                "unlocked": True,
                "unlocked_at": "2026-08-09T18:24:11Z",
            }
        }
    )

    device_id: str
    unlocked: bool = Field(description="True only when a paid payment is recorded for this device.")
    unlocked_at: datetime | None = Field(
        default=None, description="When the unlock was recorded. Null when not unlocked."
    )
