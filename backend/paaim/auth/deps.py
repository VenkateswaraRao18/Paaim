"""
FastAPI auth dependencies — the one place a request becomes a tenant.

Before this, PAAIM had a login screen and ~95 unprotected routes. The token was
issued, stored, and never checked: every endpoint read `factory_id` from a query
parameter defaulting to "factory_001", so any caller could read or write any
factory's data by typing its id — or by typing nothing at all.

`current_user` is the gate. `tenant_id` is the answer to "whose data is this?",
and it comes from the signed token, never from the request. That distinction is
the whole of multi-tenancy: a factory_id a caller can supply is not a scope, it
is a suggestion.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.auth.service import AuthService, AuthConfig, Permissions, UserRole
from paaim.config import settings
from paaim.models import UserModel, get_db

logger = logging.getLogger(__name__)

_auth = AuthService(AuthConfig(
    secret_key=settings.SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM,
    access_token_expire_minutes=settings.JWT_EXPIRE_MINUTES,
))


def get_auth_service() -> AuthService:
    return _auth


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


async def current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    """
    The authenticated user, or 401.

    The user is re-read from the database rather than trusted from the token:
    a token is valid for its whole lifetime, so a user deactivated or moved to
    another factory five minutes ago would otherwise keep their old access until
    it expired.
    """
    token = _bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _auth.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (await db.execute(
        select(UserModel).where(UserModel.id == payload.sub)
    )).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="This account no longer exists or is disabled.")
    return user


async def tenant_id(user: UserModel = Depends(current_user)) -> str:
    """
    The factory this request may touch — from the token, never the request.

    A platform admin has no factory of their own; rather than silently handing
    them someone else's, they are told to pick one explicitly. Defaulting here
    is how "admin looked at the dashboard" becomes "admin edited the wrong
    plant's vocabulary".
    """
    if not user.factory_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("This account is not bound to a factory. Platform admins must "
                    "select one explicitly rather than defaulting into a tenant."),
        )
    return user.factory_id


def require(permission: str):
    """
    Dependency factory: 403 unless the caller's role carries `permission`.

    Usage:  _: UserModel = Depends(require("decisions:approve"))
    """
    async def _dep(user: UserModel = Depends(current_user)) -> UserModel:
        try:
            role = UserRole(user.role)
        except ValueError:
            raise HTTPException(status_code=403, detail=f"Unknown role '{user.role}'.")
        if not Permissions.has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({user.role}) cannot {permission}.",
            )
        return user
    return _dep


async def assert_tenant(requested: Optional[str], user: UserModel) -> str:
    """
    Reconcile a factory_id a caller asked for against the one they own.

    Kept for the endpoints that still take `factory_id` as a parameter: rather
    than quietly ignoring it (which makes a caller think they read factory B
    when they read factory A), a mismatch is refused outright.
    """
    if user.role == UserRole.ADMIN.value and requested:
        return requested
    if requested and requested != user.factory_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to factory '{requested}'.",
        )
    if not user.factory_id:
        raise HTTPException(status_code=400, detail="This account is not bound to a factory.")
    return user.factory_id
