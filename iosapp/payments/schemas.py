"""Request and response bodies.

FastAPI turns these into the OpenAPI schema served at /docs, which is the
contract the mobile app is written against. The examples below show up there.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


def as_utc_iso(value: datetime | None) -> str | None:
    """Serialise a timestamp as UTC with an explicit Z.

    Every datetime in this package is stored in UTC, but SQLite hands them back
    without a timezone attached, and pydantic then renders them bare:

        2026-09-12T17:12:50        instead of        2026-09-12T17:12:50Z

    That is not a cosmetic difference. A reader cannot tell whether it means
    UTC or the server's local time, and strict ISO 8601 parsers reject it -
    Swift's ISO8601DateFormatter returns nil rather than a wrong answer, and
    Kotlin's Instant.parse throws.

    Both apps currently declare these fields as String and never parse them, so
    nothing breaks today. It breaks the first time somebody builds a screen
    that says when a subscription renews, which is a screen this milestone
    exists to make possible.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


class SubscribeRequest(BaseModel):
    """Sent by the app when the user taps subscribe.

    Same device_id as the one-time flow. Send the bearer token too if the
    person is signed in: a subscription belongs to an account rather than to a
    handset, so a signed in subscriber can restore on a new phone and one who
    was not can only be found by the device that paid.
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"device_id": "8f14e45fceea167a"}}
    )

    device_id: str = Field(
        min_length=1,
        max_length=DEVICE_ID_MAX_LENGTH,
        description="The device's own identifier, same as the one-time flow.",
    )


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
    name: str | None = Field(
        default=None,
        max_length=80,
        description=(
            "What to call this person on the home screen. Optional: sending it "
            "again with a different value corrects it, sending nothing leaves "
            "whatever is already stored alone."
        ),
    )

    _check_email = field_validator("email")(looks_like_an_email)


class VerifyCodeResponse(BaseModel):
    """What the app stores and sends from then on."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "Zx8kQ2p7vB1nR4wS9tY6uH3jL5aD0fG7cE2mN8qX1oI",
                "name": "John",
            }
        }
    )

    token: str = Field(
        description=(
            "Send as 'Authorization: Bearer <token>'. Keep it in the secure "
            "store on the device, Keychain on iOS and EncryptedSharedPreferences "
            "on Android, not alongside ordinary settings."
        )
    )
    name: str | None = Field(
        default=None,
        description=(
            "What to call this person, for the greeting. Null when the account "
            "has no name stored, which is the case for anybody who signed in "
            "before names existed. Fall back to a generic greeting rather than "
            "showing an empty one."
        ),
    )


class SetNameRequest(BaseModel):
    """What to call this person, sent once they are signed in."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "John"}}
    )

    name: str = Field(
        min_length=1,
        max_length=80,
        description="Shown on the home screen. Trimmed, and truncated at 80.",
    )


class NameResponse(BaseModel):
    """The name as it was actually stored."""

    model_config = ConfigDict(json_schema_extra={"example": {"name": "John"}})

    name: str | None = Field(
        default=None,
        description="What the account is called now, after trimming.",
    )


class BillingPortalRequest(BaseModel):
    """Ask for a link to Stripe's subscription management page."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"device_id": "8f14e45fceea167a"}}
    )

    device_id: str | None = Field(
        default=None,
        max_length=DEVICE_ID_MAX_LENGTH,
        description=(
            "Optional when a bearer token is sent. One of the two is required, "
            "since the server has to know whose subscription to open."
        ),
    )


class BillingPortalResponse(BaseModel):
    """Where to send them to manage their subscription."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"portal_url": "https://billing.stripe.com/p/session/test_abc123"}
        }
    )

    portal_url: str = Field(
        description=(
            "Open in a browser. Single use and short lived, so request a fresh "
            "one each time rather than caching it."
        )
    )


PLAN_NONE = "none"
PLAN_LIFETIME = "lifetime"
PLAN_MONTHLY = "monthly"


class UnlockStatusResponse(BaseModel):
    """The authoritative answer to whether someone has access.

    Three fields are new for subscriptions and all three are additions. The
    meaning of `unlocked` is unchanged - it still answers "may this person use
    the paid features right now" - so the version of the app already in the
    store keeps working the day this deploys, reading the one field it knows
    about and ignoring the rest.

    Changing the shape instead would have been tidier and would have broken
    every installed copy at once, which is not a trade worth making to avoid
    three fields.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "8f14e45fceea167a",
                "unlocked": True,
                "unlocked_at": "2026-08-09T18:24:11Z",
                "plan": "monthly",
                "expires_at": "2026-09-09T18:24:11Z",
                "cancel_at_period_end": False,
            }
        }
    )

    device_id: str
    unlocked: bool = Field(
        description=(
            "May this person use the paid features right now. True for a "
            "one-time purchase, and for a subscription whose paid period has "
            "not run out. Read this, not plan or expires_at, to decide what to "
            "show."
        )
    )
    unlocked_at: datetime | None = Field(
        default=None, description="When the unlock was recorded. Null when not unlocked."
    )
    plan: str = Field(
        default=PLAN_NONE,
        description=(
            "'lifetime' for the one-time purchase, 'monthly' for a "
            "subscription, 'none' when there is no access. Use it for what the "
            "billing screen says, not for whether to unlock anything."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "When monthly access runs out unless it renews. Null for lifetime "
            "and for no access, because neither one expires."
        ),
    )
    cancel_at_period_end: bool = Field(
        default=False,
        description=(
            "They have cancelled but already paid for the period they are in, "
            "so access continues until expires_at. Worth saying so on the "
            "billing screen rather than letting it end without warning."
        ),
    )

    @field_serializer("unlocked_at", "expires_at")
    def _timestamps_as_utc(self, value: datetime | None) -> str | None:
        return as_utc_iso(value)

