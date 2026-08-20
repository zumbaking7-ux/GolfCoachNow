"""Settings for the payments package, read from the environment.

The Settings object is built once when this module is first imported. Importing
the router therefore validates the whole configuration, so a missing or
malformed variable stops the process at startup rather than surfacing hours
later as a failed webhook.
"""

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_URL_SCHEMES = ("http://", "https://")
PRICE_ID_PREFIX = "price_"

PROVIDER_CONSOLE = "console"
PROVIDER_RESEND = "resend"
EMAIL_PROVIDERS = frozenset({PROVIDER_CONSOLE, PROVIDER_RESEND})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_id: str

    # The recurring price for the monthly plan.
    #
    # Every other Stripe setting here is required, because a payment service
    # missing one should refuse to start rather than fail on a customer's card.
    # This one is deliberately not, and the reason is worth writing down.
    #
    # The one-time product is live and selling today. If this were required,
    # deploying the subscription code before the recurring price exists would
    # take the running service down and stop the sales that already work. A
    # missing price here costs nobody their purchase; it means the subscribe
    # endpoint is not open yet, which is exactly what is true.
    #
    # So: unset is a legal state, the subscribe endpoint answers 503 while it
    # lasts, and startup says so in the log rather than silently looking fine.
    stripe_subscription_price_id: str = ""

    public_base_url: str
    success_deep_link: str = "golfcoachnow://payment-success"
    cancel_deep_link: str = "golfcoachnow://payment-cancelled"

    # Where Stripe sends the browser back after someone finishes in the billing
    # portal. Unlike the checkout success URL this points straight at the app,
    # because there is nothing to record on the way back. Cancellations and card
    # changes reach us as webhook events; the return trip is only navigation.
    portal_return_deep_link: str = "golfcoachnow://subscription-updated"

    database_url: str = "sqlite:///./payments.db"
    log_level: str = "INFO"

    # Applies only to the two endpoints the app calls. Generous on purpose:
    # mobile customers share carrier addresses, so a tight limit blocks buyers
    # before it blocks abuse. Set rate_limit_enabled to false to turn it off
    # without a code change.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # --- The un-gated allowance -----------------------------------------
    # How many reps a device may complete before it has to sign in. Exists for
    # the launch window: a journalist handed a link should see the product work
    # before being asked for anything.
    #
    # Keyed to the device id, which is a value the caller supplies, so it is
    # deliberately weak. It buys a first impression; it is not a paywall, and
    # it is not meant to outlive the press coverage.
    #
    # Set UNGATED_REPS=0 to close it. That is an environment change and a
    # reload, not a release across three app stores, which is the whole reason
    # it is configuration rather than a code path.
    ungated_reps: int = 1

    # --- Accounts -------------------------------------------------------
    # How login codes are delivered. "console" writes the code to the log and
    # sends nothing, which is for local work only. Production must set a real
    # provider or nobody can sign in.
    email_provider: str = "console"
    email_from: str = "Golf Coach Now <onboarding@resend.dev>"
    resend_api_key: str = ""

    # Six digits is short enough to type from a notification and long enough
    # that guessing is pointless once attempts are capped.
    login_code_length: int = 6
    login_code_ttl_minutes: int = 10
    login_code_max_attempts: int = 5

    # Much tighter than the general limit, because this endpoint sends email.
    # Counted per caller and separately per email address, so neither one
    # person can mail the world nor the world mail one person.
    auth_rate_limit_requests: int = 5
    auth_rate_limit_window_seconds: int = 300

    # --- Share and Connect ----------------------------------------------
    # Where "connect with the founder" messages land. Configuration rather
    # than a constant in three apps, because changing it should not mean
    # shipping a release on iOS, Android and web.
    founder_email: str = "zumba.king7@gmail.com"

    # The link a golfer sends a friend. Empty is a legal state and means the
    # invite is not open yet: /share/invite answers 503 and everything else
    # keeps working, the same way an unset subscription price is handled.
    # Nothing should be emailing people a link that does not exist yet.
    app_share_url: str = ""

    # Sending mail to an address someone typed is the most abusable thing this
    # service does, so these are tighter still than the sign in limits.
    share_rate_limit_requests: int = 3
    share_rate_limit_window_seconds: int = 3600

    @property
    def sharing_enabled(self) -> bool:
        """Whether there is a link worth sending anybody."""
        return bool(self.app_share_url)

    @field_validator("email_provider")
    @classmethod
    def must_be_a_known_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider not in EMAIL_PROVIDERS:
            raise ValueError(
                f"EMAIL_PROVIDER must be one of {', '.join(sorted(EMAIL_PROVIDERS))}"
            )
        return provider

    @model_validator(mode="after")
    def resend_needs_a_key(self) -> "Settings":
        """Fail at startup rather than on the first person trying to sign in.

        A provider selected without its credentials is the same class of
        problem as a missing Stripe key: everything looks fine until someone
        real is stuck at a login screen.
        """
        if self.email_provider == PROVIDER_RESEND and not self.resend_api_key:
            raise ValueError("RESEND_API_KEY is required when EMAIL_PROVIDER is resend")
        return self

    @field_validator("stripe_price_id", "stripe_subscription_price_id")
    @classmethod
    def must_look_like_a_price(cls, value: str) -> str:
        """Catch a product or payment link pasted in where a price belongs.

        Easy mistake to make from the dashboard, and without this the error
        arrives as a Stripe rejection at the moment a customer tries to pay.
        Empty is allowed here; whether empty is acceptable is decided per field.
        """
        value = value.strip()
        if value and not value.startswith(PRICE_ID_PREFIX):
            raise ValueError(
                f"expected a Stripe price ID starting with {PRICE_ID_PREFIX!r}, "
                f"got {value[:12]!r}"
            )
        return value

    @property
    def subscriptions_enabled(self) -> bool:
        """Whether the monthly plan can be sold yet."""
        return bool(self.stripe_subscription_price_id)

    @field_validator("public_base_url")
    @classmethod
    def must_be_a_web_url(cls, value: str) -> str:
        """This is the public origin of this service, so it has to be a web URL.

        Stripe will happily accept the app's deep link as a redirect target, so
        it is worth being explicit about why this is not that. Checkout sends
        the browser here first, the success endpoint confirms the payment with
        Stripe and records the unlock, and only then is the app handed control.
        Pointing Stripe straight at the deep link would skip all of it.
        """
        if not value.startswith(ALLOWED_URL_SCHEMES):
            raise ValueError("PUBLIC_BASE_URL must start with http:// or https://")
        return value.rstrip("/")


def _setting_name(detail: dict) -> str:
    """Name the setting at fault.

    A field validator reports which field it was. A validator that checks the
    whole model, like the one pairing a provider with its key, reports no
    location at all. Fall back to a label rather than crashing while trying to
    explain a configuration problem.
    """
    location = detail.get("loc") or ()
    return str(location[0]).upper() if location else "CONFIGURATION"


def _configuration_error(error: ValidationError) -> str:
    """Turn a validation failure into something a person can act on.

    Whoever hits this is usually looking at a service that will not start,
    often during a deploy, so the message has to say which variables are wrong
    and where to set them without anyone having to read this file.
    """
    problems = "\n".join(
        f"  - {_setting_name(detail)}: {detail['msg']}" for detail in error.errors()
    )
    return (
        "\n\nPayments configuration is incomplete, so the application will not "
        "start.\n\n"
        f"{problems}\n\n"
        "Set these in the environment, or in a .env file next to the project, "
        "then reload.\nSee docs/DEPLOYMENT.md for the full list and what each "
        "one is for.\n\n"
        "This check runs at startup deliberately. A payment service should not "
        "run half\nconfigured and discover the problem on a customer's card.\n"
    )


try:
    settings = Settings()
except ValidationError as error:
    # `from None` hides the pydantic traceback so the instructions above are
    # the first thing in the log rather than the last.
    raise RuntimeError(_configuration_error(error)) from None
