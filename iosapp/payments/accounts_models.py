"""Database tables for accounts.

Kept in their own module rather than added to models.py, which is actively
edited for the entitlement and analytics work. Same declarative Base, so
Alembic sees these exactly as if they lived there, and neither of us has to
merge the other's changes to get work done.

Why accounts exist at all: an unlock is currently tied to a device ID, and
those do not survive a reinstall. iOS changes identifierForVendor when the
last app from a vendor is deleted, and Android changes ANDROID_ID on a
factory reset. For a one-time purchase that loses someone their unlock. For a
subscription it means they keep being charged while locked out, which turns
into refunds and chargebacks.

An account gives a person an identity that outlives the hardware.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from payments.models import Base

EMAIL_LENGTH = 320
HASH_LENGTH = 64
DEVICE_ID_LENGTH = 255


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """One row per person, identified by email.

    Email is the only identifier because it is the only thing a person still
    has after losing the phone. It is stored lowercased so the same address
    cannot become two accounts.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class LoginCode(Base):
    """A short-lived code emailed to someone proving they own the address.

    Only the hash is stored. The database should never contain anything that
    grants access on its own, for the same reason passwords are not stored in
    plain text.

    attempts exists so a six digit code cannot be brute forced. Without it,
    a million guesses beats any expiry short enough to still be usable.

    Rows are keyed by email rather than by user, because the person may not
    have an account yet when they ask for their first code.
    """

    __tablename__ = "login_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(HASH_LENGTH), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AuthToken(Base):
    """What the app sends instead of signing in again every time.

    Opaque random bytes rather than a signed token, and only the hash is
    stored. Both choices are about revocation: a stolen token can be killed by
    deleting one row, which a self-contained signed token does not allow
    without building a blocklist to check anyway.
    """

    __tablename__ = "auth_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(HASH_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserDevice(Base):
    """Links a device to the person who signed in on it.

    This is what makes restore purchase work. Payments are recorded against a
    device ID, so to answer "has this person paid" we need to know every
    device they have ever signed in on. Sign in on a new phone and the old
    purchase is found through the old device.

    Unique on device_id: a phone belongs to at most one account. Signing in as
    someone else moves the device rather than sharing it, which stops one
    purchase being spread across accounts.
    """

    __tablename__ = "user_devices"
    __table_args__ = (UniqueConstraint("device_id", name="uq_user_devices_device_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(String(DEVICE_ID_LENGTH), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
