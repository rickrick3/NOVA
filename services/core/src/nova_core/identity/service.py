"""Local account, password verification and sessions."""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nova_core.audit.service import AuditService
from nova_core.identity.models import AuthSession, User
from nova_core.identity.repository import IdentityRepository
from nova_core.kernel.clock import Clock
from nova_core.kernel.config import Settings
from nova_core.kernel.errors import NovaError
from nova_core.kernel.ids import new_id

_hasher = PasswordHasher()
# Checked when the username is unknown, so that both kinds of failure cost the same time.
_UNKNOWN_USER_HASH = _hasher.hash(secrets.token_urlsafe(32))


@dataclass(frozen=True)
class SessionGrant:
    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    user_id: str
    username: str
    csrf_token: str
    expires_at: datetime


class AlreadySetUpError(NovaError):
    def __init__(self) -> None:
        super().__init__("already_set_up", 409, "The local account already exists.")


class InvalidCredentialsError(NovaError):
    def __init__(self) -> None:
        super().__init__("invalid_credentials", 401, "Invalid username or password.")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


class IdentityService:
    def __init__(
        self, session: AsyncSession, audit: AuditService, clock: Clock, settings: Settings
    ) -> None:
        self._session = session
        self._identity = IdentityRepository(session)
        self._audit = audit
        self._clock = clock
        self._settings = settings

    async def is_setup(self) -> bool:
        return await self._identity.count_users() > 0

    async def setup(self, username: str, password: str) -> User:
        password_hash = await asyncio.to_thread(_hasher.hash, password)
        user = User(
            id=new_id(),
            username=username.strip().casefold(),
            password_hash=password_hash,
            singleton=1,
            created_at=self._clock.now(),
        )
        # No prior read: two simultaneous requests are settled by the unique constraint.
        self._identity.add_user(user)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            raise AlreadySetUpError() from None
        await self._audit.record(
            actor_type="user", actor_id=user.id, action="auth.setup", outcome="succeeded"
        )
        await self._session.commit()
        return user

    async def login(self, username: str, password: str) -> tuple[User, SessionGrant]:
        user = await self._identity.user_by_username(username.strip().casefold())
        password_hash = user.password_hash if user is not None else _UNKNOWN_USER_HASH
        matches = await asyncio.to_thread(_password_matches, password_hash, password)
        if user is None or not matches:
            await self._audit.record(
                actor_type="system",
                actor_id=None,
                action="auth.login_failed",
                outcome="failed",
                resource={"reason": "invalid_credentials"},
            )
            await self._session.commit()
            raise InvalidCredentialsError()

        now = self._clock.now()
        grant = SessionGrant(
            token=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(32),
            expires_at=now + timedelta(hours=self._settings.session_ttl_hours),
        )
        self._identity.add_session(
            AuthSession(
                id=new_id(),
                user_id=user.id,
                token_hash=hash_token(grant.token),
                csrf_token=grant.csrf_token,
                created_at=now,
                expires_at=grant.expires_at,
            )
        )
        await self._audit.record(
            actor_type="user", actor_id=user.id, action="auth.login", outcome="succeeded"
        )
        await self._session.commit()
        return user, grant

    async def authenticate(self, token: str) -> SessionContext | None:
        found = await self._identity.session_with_user(hash_token(token))
        if found is None:
            return None
        auth_session, user = found
        if auth_session.expires_at <= self._clock.now():
            return None
        return SessionContext(
            session_id=auth_session.id,
            user_id=user.id,
            username=user.username,
            csrf_token=auth_session.csrf_token,
            expires_at=auth_session.expires_at,
        )

    async def logout(self, session_id: str) -> None:
        auth_session = await self._identity.session_by_id(session_id)
        if auth_session is None:
            return
        await self._identity.delete_session(auth_session)
        await self._audit.record(
            actor_type="user",
            actor_id=auth_session.user_id,
            action="auth.logout",
            outcome="succeeded",
        )
        await self._session.commit()
