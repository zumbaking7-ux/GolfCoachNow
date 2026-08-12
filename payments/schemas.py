"""Request and response bodies.

FastAPI turns these into the OpenAPI schema served at /docs, which is the
contract the mobile app is written against. The examples below show up there.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEVICE_ID_MAX_LENGTH = 255


def looks_like_an_email(value: str) -> str:
    """Catch obvious rubbish, nothing more.

    Deliberately not full RFC validation, which would mean adding a dependency
    to reject addresses that are legal but undeliverable anyway. The only real
    test of an address is whether the code arrives, and that test runs a second
    later. This is here to turn a typo into a clear 422 instead of a code sent
    into nowhere.
    """
    address = value.strip()
    local, separator, domain = address.partition("@")
    if not separator or not local or "." not in domain or domain.startswith("."):
        raise ValueError("not a valid email address")
    if any(character.isspace() for character in address):
        raise ValueError("not a valid email address")
    return address


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


class RequestCodeRequest(BaseModel):
    """Ask for a sign in code."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "golfer@example.com", "device_id": "8f14e45fceea167a"}
        }
    )

    email: str = Field(
        min_length=3, max_length=320, description="Where to send the six digit code."
    )
    device_id: str | None = Field(
        default=None,
        max_length=DEVICE_ID_MAX_LENGTH,
        description=(
            "The calling device. Optional here, but sending it means the "
            "device is linked to the account on the next step, which is what "
            "makes an earlier purchase findable."
        ),
    )

    _check_email = field_validator("email")(looks_like_an_email)


class VerifyCodeRequest(BaseModel):
    """Send the code back to prove the address belongs to you."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "golfer@example.com",
                "code": "418302",
                "device_id": "8f14e45fceea167a",
            }
        }
    )

    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=4, max_length=12)
    device_id: str | None = Field(default=None, max_length=DEVICE_ID_MAX_LENGTH)

    _check_email = field_validator("email")(looks_like_an_email)


class VerifyCodeResponse(BaseModel):
    """What the app stores and sends from then on."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"token": "Zx8kQ2p7vB1nR4wS9tY6uH3jL5aD0fG7cE2mN8qX1oI"}
        }
    )

    token: str = Field(
        description=(
            "Send as 'Authorization: Bearer <token>'. Keep it in the secure "
            "store on the device, Keychain on iOS and EncryptedSharedPreferences "
            "on Android, not alongside ordinary settings."
        )
    )


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
