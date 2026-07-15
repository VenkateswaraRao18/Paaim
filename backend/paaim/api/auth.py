"""
Authentication — login, refresh, and who am I.

Logins were previously resolved by an if/elif on the email address: anything
ending `@paaim.local` with the password `password` was admitted and handed
factory_001. There were no users, nothing was hashed, and nothing was checked.

Note the single `AuthService`, imported from paaim.auth.deps. This module used
to build its own from `JWT_SECRET_KEY` while the rest of the app verified with
`settings.SECRET_KEY` — two different secrets, so every token this endpoint
issued would have failed verification everywhere it was used.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.auth.deps import current_user, get_auth_service
from paaim.auth.service import LoginRequest, TokenResponse, UserResponse, UserRole
from paaim.config import settings
from paaim.models import FactoryModel, UserModel, get_db

logger = logging.getLogger(__name__)

router = APIRouter()
auth_service = get_auth_service()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate against the users table and issue a tenant-scoped token."""
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user = (await db.execute(
        select(UserModel).where(UserModel.email == request.email.strip().lower())
    )).scalar_one_or_none()

    # One message for "no such user" and "wrong password", and the hash is
    # verified either way — a fast 401 for unknown addresses tells an attacker
    # which of your customers' emails are real.
    dummy = "$2b$12$" + "." * 53
    ok = auth_service.verify_password(request.password, user.password_hash if user else dummy)
    if not user or not ok:
        logger.warning("Failed login for %s", request.email)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")

    user.last_login_at = datetime.utcnow()
    db.add(user)

    try:
        role = UserRole(user.role)
    except ValueError:
        raise HTTPException(status_code=500, detail=f"Account has an unknown role '{user.role}'.")

    return TokenResponse(
        access_token=auth_service.create_access_token(
            user_id=user.id, role=role, factory_id=user.factory_id,
        ),
        refresh_token=auth_service.create_refresh_token(user_id=user.id),
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(authorization: Optional[str] = Header(None),
                        db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    parts = (authorization or "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Refresh token required.")

    payload = auth_service.decode_token(parts[1])
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a valid refresh token.")

    # Re-read the user: their factory or role may have changed, and a refresh
    # that reissues the old claims would keep stale access alive indefinitely.
    user = (await db.execute(
        select(UserModel).where(UserModel.id == payload["sub"])
    )).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="This account no longer exists or is disabled.")

    return TokenResponse(
        access_token=auth_service.create_access_token(
            user_id=user.id, role=UserRole(user.role), factory_id=user.factory_id,
        ),
        refresh_token=auth_service.create_refresh_token(user_id=user.id),
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get("/me")
async def me(user: UserModel = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """The signed-in user and the factory they belong to — what the UI renders."""
    factory = None
    if user.factory_id:
        f = (await db.execute(
            select(FactoryModel).where(FactoryModel.id == user.factory_id)
        )).scalar_one_or_none()
        if f:
            factory = {"id": f.id, "name": f.name, "location": f.location,
                       "industry": f.industry, "vocabulary_pack": f.vocabulary_pack}

    return {
        "user": UserResponse(
            id=user.id, email=user.email, full_name=user.full_name,
            role=user.role, factory_id=user.factory_id, is_active=user.is_active,
        ).dict(),
        "factory": factory,
    }


@router.get("/verify")
async def verify(user: UserModel = Depends(current_user)):
    """Cheap liveness check for the frontend's stored token."""
    return {"valid": True, "user_id": user.id, "factory_id": user.factory_id, "role": user.role}
