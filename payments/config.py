"""Settings for the payments package, read from the environment.

The Settings object is built once when this module is first imported. Importing
the router therefore validates the whole configuration, so a missing or
malformed variable stops the process at startup rather than surfacing hours
later as a failed webhook.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_URL_SCHEMES = ("http://", "https://")


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

    @field_validator("public_base_url")
    @classmethod
    def must_be_a_web_url(cls, value: str) -> str:
        """Stripe rejects anything that is not http or https for redirect URLs.

        This is why the app's deep link cannot be handed to Stripe directly.
        Checkout returns the browser to this origin, and the endpoint here
        redirects on to the custom scheme.
        """
        if not value.startswith(ALLOWED_URL_SCHEMES):
            raise ValueError("PUBLIC_BASE_URL must start with http:// or https://")
        return value.rstrip("/")


settings = Settings()
