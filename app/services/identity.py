"""Account identity, session resolution and role provisioning."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.errors import ServiceUnavailableError
from app.core.oauth import fetch_manus_user
from app.core.security import verify_local_session, verify_preview_jwt
from app.db.base import session_scope
from app.db.models import AdminUser
from app.db.repositories import UserRepository

logger = logging.getLogger(__name__)

PREVIEW_SOURCE: str = "preview"
LOCAL_SOURCE: str = "local"
OAUTH_SOURCE: str = "oauth"
ADMIN_ROLE: str = "admin"
VIEWER_ROLE: str = "viewer"
DEFAULT_USER_NAME: str = "Manus Administrator"
NAME_MAX_LENGTH: int = 191
EMAIL_MAX_LENGTH: int = 320


@dataclass(frozen=True, slots=True)
class Identity:
    """The account behind a session token, before roles are applied."""

    open_id: str
    name: str
    email: str
    source: str


@dataclass(frozen=True, slots=True)
class UserProfile:
    """A registered account together with the role it holds."""

    open_id: str
    name: str
    email: str
    role: str


class IdentityService:
    """Resolve session tokens and register the accounts behind them."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def current_user(self, token: str) -> UserProfile | None:
        """Return the signed-in account for a session token, or ``None``."""

        identity = await self.resolve_identity(token)
        if identity is None:
            return None
        try:
            return self._load_user(identity)
        except Exception:
            logger.exception("Identity persistence unavailable")
            return None

    async def resolve_identity(self, token: str) -> Identity | None:
        """Return the identity behind a session token, or ``None`` when invalid."""

        preview_claims = verify_preview_jwt(token, self._settings)
        if preview_claims:
            display_name = (
                preview_claims.get("name") or preview_claims.get("displayName") or DEFAULT_USER_NAME
            )
            return Identity(
                open_id=str(preview_claims["openId"]),
                name=str(display_name)[:NAME_MAX_LENGTH],
                email=str(preview_claims.get("email") or "")[:EMAIL_MAX_LENGTH],
                source=PREVIEW_SOURCE,
            )
        local_claims = verify_local_session(token, self._settings)
        if local_claims:
            return Identity(
                open_id=local_claims["open_id"],
                name=local_claims["name"],
                email=local_claims["email"],
                source=LOCAL_SOURCE,
            )
        try:
            profile = await fetch_manus_user(token, self._settings)
        except (httpx.HTTPError, ValueError, RuntimeError, ServiceUnavailableError):
            return None
        return Identity(
            open_id=profile["open_id"],
            name=profile["name"],
            email=profile["email"],
            source=OAUTH_SOURCE,
        )

    def provision_user(self, identity: Identity) -> UserProfile:
        """Register an account; the first account becomes the administrator."""

        with session_scope() as session:
            repository = UserRepository(session)
            user = repository.find_by_open_id(identity.open_id)
            if user is None:
                user = self._create_user(session, repository, identity)
            return _to_profile(user)

    def _load_user(self, identity: Identity) -> UserProfile | None:
        """Return the stored account of an identity, registering preview accounts."""

        with session_scope() as session:
            repository = UserRepository(session)
            user = repository.find_by_open_id(identity.open_id)
            if user is None:
                if identity.source != PREVIEW_SOURCE:
                    return None
                user = self._create_user(session, repository, identity)
            return _to_profile(user)

    def _create_user(self, session: Session, repository: UserRepository, identity: Identity) -> AdminUser:
        """Insert a new account, keeping the first one as the administrator."""

        user = AdminUser(
            open_id=identity.open_id,
            email=identity.email or None,
            name=identity.name or DEFAULT_USER_NAME,
            role=ADMIN_ROLE if repository.count() == 0 else VIEWER_ROLE,
        )
        repository.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = repository.find_by_open_id(identity.open_id)
            if existing is None:
                raise
            return existing
        return user


def _to_profile(user: AdminUser) -> UserProfile:
    """Convert a stored account into a :class:`UserProfile`."""

    return UserProfile(
        open_id=user.open_id,
        name=user.name,
        email=user.email or "",
        role=user.role,
    )
