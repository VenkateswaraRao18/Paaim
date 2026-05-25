"""Authentication endpoints for user login and token management."""

from fastapi import APIRouter, HTTPException, Depends, Header
from datetime import datetime
import logging

from paaim.auth.service import (
    AuthService,
    AuthConfig,
    RBACMiddleware,
    LoginRequest,
    TokenResponse,
    UserResponse,
    UserRole,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize auth service (in production, load secret from environment)
import os
secret_key = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
auth_config = AuthConfig(secret_key=secret_key)
auth_service = AuthService(auth_config)
rbac = RBACMiddleware(auth_service)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT tokens.

    In production, validate credentials against database.
    For now, accept any email with password 'password'.
    """
    # TODO: In production, validate against database
    if not request.email or not request.password:
        raise HTTPException(
            status_code=400,
            detail="Email and password required",
        )

    # Temporary: Accept demo user
    if request.email == "admin@paaim.local" and request.password == "password":
        user_id = "user_001"
        role = UserRole.ADMIN
        factory_id = None
    elif request.email.endswith("@paaim.local") and request.password == "password":
        user_id = f"user_{request.email.split('@')[0]}"
        role = UserRole.OPERATOR
        factory_id = "factory_001"
    else:
        logger.warning(f"Failed login attempt for {request.email}")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    access_token = auth_service.create_access_token(
        user_id=user_id,
        role=role,
        factory_id=factory_id,
    )
    refresh_token = auth_service.create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=auth_config.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(authorization: str = Header(None)):
    """Refresh access token using refresh token."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="No authorization header",
        )

    token = rbac.extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    payload = auth_service.decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    # Create new access token
    user_id = payload["sub"]
    # TODO: Load role from database
    access_token = auth_service.create_access_token(
        user_id=user_id,
        role=UserRole.OPERATOR,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=token,
        expires_in=auth_config.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(authorization: str = Header(None)):
    """Get current authenticated user."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="No authorization header",
        )

    token = rbac.extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    # TODO: Load full user details from database
    return UserResponse(
        id=payload.sub,
        email=f"{payload.sub}@paaim.local",
        full_name=payload.sub,
        role=payload.role.value,
        factory_id=payload.factory_id,
        is_active=True,
    )


@router.get("/verify")
async def verify_token(authorization: str = Header(None)):
    """Verify token validity."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="No authorization header",
        )

    token = rbac.extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    return {
        "valid": True,
        "user_id": payload.sub,
        "role": payload.role.value,
        "expires_at": payload.exp.isoformat(),
    }
