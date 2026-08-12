"""Accounts: proving someone owns an email, then remembering them.

The flow is deliberately small. Ask for a code, type it back, get a token. No
passwords, so nothing to reset, nothing to forget, and no password database to
lose.

Three things do the security work here, and it is worth being clear about which
does what:

- Expiry. A code is useless ten minutes later.
- Single use. A code that has been accepted cannot be accepted again.
- An attempt cap. Six digits is a million possibilities, which a script tries
  in seconds. The cap is what makes the space large enough to matter.

Hashing the code is the fourth, and it is the weakest of them. It stops a
leaked database snapshot containing live credentials and stops one rainbow
table working across every user, but a six digit space is small enough to
brute force offline. That is why the three above carry the real weight.

Tokens are different: 32 random bytes is far beyond guessing, so hashing them
is genuinely one way.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payments.accounts_models import AuthToken, LoginCode, User, UserDevice, utcnow
from payments.config import settings
from payments.logging_config import fields, get_logger
from payments.models import Unlock

logger = get_logger("accounts")

DIGITS = "0123456789"

# Writing last_used_at on every authenticated request would be one database
# write per call for information nobody reads that precisely. An hour is
# enough to answer "is this token still in use" without the write traffic.
TOUCH_INTERVAL = timedelta(hours=1)


def normalise_email(email: str) -> str:
    """One address must not become two accounts through capitals or spaces."""
    return email.strip().lower()


def _hash_code(email: str, code: str) -> str:
    """Salted by email so one precomputed table cannot cover every user."""
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_code() -> str:
    """secrets, not random. The latter is predictable from previous output."""
    return "".join(secrets.choice(DIGITS) for _ in range(settings.login_code_length))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes even for timezone-aware columns."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def request_login_code(session: Session, email: str) -> str:
    """Issue a fresh code and return it in plain text for sending.

    Any outstanding codes for this address are retired first, so only the most
    recent one works. Without that, every code someone ever requested would
    stay valid until its own expiry.

    The plaintext is returned rather than stored, and the caller hands it
    straight to the email sender. It exists nowhere else.
    """
    address = normalise_email(email)

    outstanding = session.scalars(
        select(LoginCode).where(LoginCode.email == address, LoginCode.used_at.is_(None))
    ).all()
    for code_row in outstanding:
        code_row.used_at = _now()

    code = _generate_code()
    session.add(
        LoginCode(
            email=address,
            code_hash=_hash_code(address, code),
            expires_at=_now() + timedelta(minutes=settings.login_code_ttl_minutes),
        )
    )
    session.commit()

    logger.info("login code issued %s", fields(email=address, retired=len(outstanding)))
    return code


def verify_login_code(
    session: Session, email: str, code: str, device_id: str | None
) -> str | None:
    """Check a code and hand back a token, or None if it does not check out.

    One return value for every kind of failure on purpose. Telling the caller
    apart - no code requested, wrong code, expired, too many attempts - tells
    an attacker which addresses have accounts and how close they are.
    """
    address = normalise_email(email)

    pending = session.scalars(
        select(LoginCode)
        .where(LoginCode.email == address, LoginCode.used_at.is_(None))
        .order_by(LoginCode.id.desc())
    ).first()

    if pending is None:
        logger.info("verify failed, no code outstanding %s", fields(email=address))
        return None

    if _as_utc(pending.expires_at) < _now():
        logger.info("verify failed, code expired %s", fields(email=address))
        return None

    if pending.attempts >= settings.login_code_max_attempts:
        pending.used_at = _now()
        session.commit()
        logger.warning("verify failed, attempts exhausted %s", fields(email=address))
        return None

    # Constant time: a comparison that returns early on the first wrong
    # character leaks the answer through how long it took.
    if not hmac.compare_digest(pending.code_hash, _hash_code(address, code)):
        pending.attempts += 1
        session.commit()
        logger.info(
            "verify failed, wrong code %s",
            fields(email=address, attempt=pending.attempts),
        )
        return None

    pending.used_at = _now()
    user = _find_or_create_user(session, address)
    if device_id:
        _link_device(session, user, device_id)

    token = secrets.token_urlsafe(32)
    session.add(AuthToken(user_id=user.id, token_hash=_hash_token(token)))
    session.commit()

    logger.info("signed in %s", fields(user_id=user.id, device_id=device_id))
    return token


def _find_or_create_user(session: Session, address: str) -> User:
    user = session.scalars(select(User).where(User.email == address)).first()
    if user:
        return user

    user = User(email=address)
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        # Two codes verified at the same moment. The unique index decided
        # which one wins; read back the row the other request created.
        session.rollback()
        user = session.scalars(select(User).where(User.email == address)).first()

    return user


def _link_device(session: Session, user: User, device_id: str) -> None:
    """Attach this phone to the account, moving it if it belonged elsewhere.

    Moving rather than sharing is deliberate. If a device could belong to two
    accounts, one purchase would unlock both.
    """
    existing = session.scalars(
        select(UserDevice).where(UserDevice.device_id == device_id)
    ).first()

    if existing is None:
        session.add(UserDevice(user_id=user.id, device_id=device_id))
        return

    if existing.user_id != user.id:
        logger.info(
            "device moved between accounts %s",
            fields(device_id=device_id, was=existing.user_id, now=user.id),
        )
        existing.user_id = user.id
        existing.linked_at = utcnow()


def user_for_token(session: Session, token: str | None) -> User | None:
    """Resolve a bearer token to a person, or None."""
    if not token:
        return None

    row = session.scalars(
        select(AuthToken).where(AuthToken.token_hash == _hash_token(token))
    ).first()

    if row is None or row.revoked_at is not None:
        return None

    last_used = _as_utc(row.last_used_at)
    if last_used is None or _now() - last_used > TOUCH_INTERVAL:
        row.last_used_at = _now()
        session.commit()

    return session.get(User, row.user_id)


def revoke_token(session: Session, token: str) -> bool:
    """Sign out. Returns whether there was a live token to revoke."""
    row = session.scalars(
        select(AuthToken).where(AuthToken.token_hash == _hash_token(token))
    ).first()

    if row is None or row.revoked_at is not None:
        return False

    row.revoked_at = _now()
    session.commit()
    logger.info("token revoked %s", fields(user_id=row.user_id))
    return True


def unlock_for_user(session: Session, user: User) -> Unlock | None:
    """The unlock belonging to any device this person has signed in on.

    This is what restore purchase actually is. Payments are recorded against
    the device that made them, so answering "has this person paid" means
    looking at every device they have ever linked, including the one they no
    longer have.
    """
    device_ids = list(
        session.scalars(
            select(UserDevice.device_id).where(UserDevice.user_id == user.id)
        ).all()
    )
    if not device_ids:
        return None

    return session.scalars(
        select(Unlock).where(Unlock.device_id.in_(device_ids)).order_by(Unlock.id)
    ).first()
