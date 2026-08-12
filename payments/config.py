"""Settings for the payments package, read from the environment.

The Settings object is built once when this module is first imported. Importing
the router therefore validates the whole configuration, so a missing or
malformed variable stops the process at startup rather than surfacing hours
later as a failed webhook.
"""

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_URL_SCHEMES = ("http://", "https://")

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

    public_base_url: str
    success_deep_link: str = "golfcoachnow://payment-success"
    cancel_deep_link: str = "golfcoachnow://payment-cancelled"

    database_url: str = "sqlite:///./payments.db"
    log_level: str = "INFO"

    # Applies only to the two endpoints the app calls. Generous on purpose:
    # mobile customers share carrier addresses, so a tight limit blocks buyers
    # before it blocks abuse. Set rate_limit_enabled to false to turn it off
    # without a code change.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

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
