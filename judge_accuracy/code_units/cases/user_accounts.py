"""Sign-up, sign-in and password reset for the shop's customer accounts."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[a-z]{2,24}$", re.IGNORECASE)
MIN_PASSWORD_LENGTH = 12
RESET_TOKEN_LIFETIME = timedelta(minutes=30)
MAX_FAILED_SIGN_INS = 5
LOCKOUT = timedelta(minutes=15)
TOKEN_SIGNING_KEY = os.environ["ACCOUNT_TOKEN_SIGNING_KEY"].encode()


class AccountStore(Protocol):
    """The account table, behind the database the app wires in."""

    async def find_by_email(self, email: str) -> dict | None: ...

    async def insert(self, email: str, password_hash: str, name: str) -> int: ...

    async def update_password(self, account_id: int, password_hash: str) -> None: ...

    async def record_failed_sign_in(self, account_id: int, at: datetime) -> int: ...

    async def clear_failed_sign_ins(self, account_id: int) -> None: ...

    async def save_reset_token(
        self, account_id: int, token_hash: str, expires_at: datetime
    ) -> None: ...

    async def find_reset_token(self, token_hash: str) -> dict | None: ...

    async def delete_reset_tokens(self, account_id: int) -> None: ...


class Mailer(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class AccountError(Exception):
    """A request about an account was refused; the message is safe to show."""


@dataclass(frozen=True)
class SignUpRequest:
    email: str
    password: str
    name: str


@dataclass(frozen=True)
class SignInResult:
    account_id: int
    session_token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_email(email: str) -> str:
    """Return ``email`` normalized; raise AccountError when it is not an address."""
    normalized = normalize_email(email)
    if not EMAIL_PATTERN.match(normalized):
        raise AccountError("Enter a valid email address")
    return normalized


def check_password(password: str, email: str) -> None:
    """Raise AccountError when ``password`` is too weak for ``email``'s account."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"Use at least {MIN_PASSWORD_LENGTH} characters")
    if password.lower() in email:
        raise AccountError("The password must not be part of the email address")
    if len(set(password)) < 5:
        raise AccountError("Use more different characters")


def check_name(name: str) -> str:
    stripped = " ".join(name.split())
    if not 1 <= len(stripped) <= 80:
        raise AccountError("Enter a name of 1 to 80 characters")
    return stripped


def sign_token(account_id: int, issued_at: datetime) -> str:
    """Return a session token for the account, signed with the app's key."""
    payload = f"{account_id}.{int(issued_at.timestamp())}"
    signature = hmac.new(TOKEN_SIGNING_KEY, payload.encode(), hashlib.sha256)
    return f"{payload}.{signature.hexdigest()}"


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AccountService:
    """Signs customers up and in, and resets their passwords.

    Every message an AccountError carries is safe to show to the customer:
    it never says whether another customer's email is registered.
    """

    def __init__(
        self, store: AccountStore, hasher: PasswordHasher, mailer: Mailer
    ) -> None:
        self._store = store
        self._hasher = hasher
        self._mailer = mailer

    async def sign_up(self, request: SignUpRequest) -> int:
        """Create an account and send a welcome email; return the account's ID.

        Raises AccountError when a field is not valid or the email is taken.
        """
        email = check_email(request.email)
        check_password(request.password, email)
        name = check_name(request.name)
        if await self._store.find_by_email(email) is not None:
            raise AccountError("An account with this email already exists")
        account_id = await self._store.insert(
            email, self._hasher.hash(request.password), name
        )
        await self._mailer.send(email, "Welcome", f"Hello {name}, welcome to the shop.")
        logger.info("Account %s signed up", account_id)
        return account_id

    async def sign_in(self, email: str, password: str, now: datetime) -> SignInResult:
        """Return a session for the account; AccountError when the sign-in fails.

        An account is locked for LOCKOUT after MAX_FAILED_SIGN_INS failures.
        """
        account = await self._store.find_by_email(normalize_email(email))
        if account is None:
            raise AccountError("The email or the password is wrong")
        locked_until = account.get("locked_until")
        if locked_until is not None and locked_until > now:
            raise AccountError("Too many attempts; try again in a few minutes")
        if not self._hasher.verify(account["password_hash"], password):
            failures = await self._store.record_failed_sign_in(account["id"], now)
            logger.info("Failed sign-in %s for account %s", failures, account["id"])
            raise AccountError("The email or the password is wrong")
        await self._store.clear_failed_sign_ins(account["id"])
        return SignInResult(
            account_id=account["id"], session_token=sign_token(account["id"], now)
        )

    async def request_password_reset(self, email: str, now: datetime) -> None:
        """Email a reset link when the account exists; say nothing either way."""
        try:
            normalized = check_email(email)
        except AccountError:
            return
        account = await self._store.find_by_email(normalized)
        if account is None:
            logger.info("Password reset asked for an unknown email")
            return
        token = secrets.token_urlsafe(32)
        await self._store.save_reset_token(
            account["id"], hash_reset_token(token), now + RESET_TOKEN_LIFETIME
        )
        await self._mailer.send(
            normalized,
            "Reset your password",
            f"Use this link within 30 minutes: https://shop.example/reset/{token}",
        )

    async def reset_password(self, token: str, new_password: str, now: datetime) -> None:
        """Set a new password with a reset token; AccountError when it is not valid."""
        record = await self._store.find_reset_token(hash_reset_token(token))
        if record is None or record["expires_at"] < now:
            raise AccountError("This reset link has expired; ask for a new one")
        check_password(new_password, record["email"])
        await self._store.update_password(
            record["account_id"], self._hasher.hash(new_password)
        )
        await self._store.delete_reset_tokens(record["account_id"])
        await self._store.clear_failed_sign_ins(record["account_id"])
        logger.info("Account %s reset its password", record["account_id"])

    async def change_password(
        self, account_id: int, email: str, old_password: str, new_password: str
    ) -> None:
        """Change a signed-in customer's password, checking the old one first."""
        account = await self._store.find_by_email(normalize_email(email))
        if account is None or account["id"] != account_id:
            raise AccountError("The account was not found")
        if not self._hasher.verify(account["password_hash"], old_password):
            raise AccountError("The current password is wrong")
        check_password(new_password, account["email"])
        await self._store.update_password(account_id, self._hasher.hash(new_password))
        await self._mailer.send(
            account["email"],
            "Your password was changed",
            "If you did not change it, reset it now and contact us.",
        )


async def handle_sign_up(service: AccountService, body: dict) -> tuple[int, dict]:
    """Answer the sign-up endpoint: the status code and the JSON body to send.

    The body's fields are checked for type before the service sees them, and
    an unexpected failure is logged and answered with a generic message.
    """
    fields = {}
    for key in ("email", "password", "name"):
        value = body.get(key)
        if not isinstance(value, str):
            return 400, {"error": f"'{key}' must be a string"}
        fields[key] = value
    try:
        account_id = await service.sign_up(SignUpRequest(**fields))
    except AccountError as error:
        return 422, {"error": str(error)}
    except Exception:
        logger.exception("Sign-up failed")
        return 500, {"error": "Something went wrong; please try again"}
    return 201, {"account_id": account_id}


async def handle_sign_in(service: AccountService, body: dict) -> tuple[int, dict]:
    """Answer the sign-in endpoint: the status code and the JSON body to send."""
    email = body.get("email")
    password = body.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return 400, {"error": "'email' and 'password' must be strings"}
    try:
        result = await service.sign_in(email, password, datetime.now(timezone.utc))
    except AccountError as error:
        return 401, {"error": str(error)}
    except Exception:
        logger.exception("Sign-in failed")
        return 500, {"error": "Something went wrong; please try again"}
    return 200, {"account_id": result.account_id, "token": result.session_token}
