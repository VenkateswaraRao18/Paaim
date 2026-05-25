"""JWT-based authentication and RBAC for PAAIM."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from functools import lru_cache
from enum import Enum

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRole(str, Enum):
    """User roles in PAAIM."""
    VIEWER = "viewer"  # Read-only access
    OPERATOR = "operator"  # Can view and acknowledge decisions
    SUPERVISOR = "supervisor"  # Can approve decisions
    ADMIN = "admin"  # Full access


class Permissions:
    """Role-based permissions."""

    ROLE_PERMISSIONS = {
        UserRole.VIEWER: [
            "events:read",
            "decisions:read",
            "audit:read",
        ],
        UserRole.OPERATOR: [
            "events:read",
            "decisions:read",
            "decisions:acknowledge",
            "audit:read",
        ],
        UserRole.SUPERVISOR: [
            "events:read",
            "decisions:read",
            "decisions:approve",
            "decisions:reject",
            "audit:read",
        ],
        UserRole.ADMIN: [
            "events:read",
            "events:write",
            "decisions:read",
            "decisions:approve",
            "decisions:reject",
            "audit:read",
            "audit:write",
            "users:read",
            "users:write",
            "connectors:read",
            "connectors:write",
            "config:read",
            "config:write",
        ],
    }

    @classmethod
    def has_permission(cls, role: UserRole, permission: str) -> bool:
        """Check if role has permission."""
        return permission in cls.ROLE_PERMISSIONS.get(role, [])

    @classmethod
    def get_permissions(cls, role: UserRole) -> list:
        """Get all permissions for a role."""
        return cls.ROLE_PERMISSIONS.get(role, [])


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # Subject (user ID)
    exp: datetime
    iat: datetime
    role: UserRole
    factory_id: Optional[str] = None


class User(BaseModel):
    """User model."""
    id: str
    email: str
    full_name: str
    role: UserRole
    factory_id: Optional[str] = None
    is_active: bool = True


class AuthConfig(BaseModel):
    """Authentication configuration."""
    secret_key: str = Field(..., description="JWT secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=60, description="Token expiration")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token expiration")


class AuthService:
    """Handle authentication and token management."""

    def __init__(self, config: AuthConfig):
        """Initialize auth service."""
        self.config = config

    def hash_password(self, password: str) -> str:
        """Hash password."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password."""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        user_id: str,
        role: UserRole,
        factory_id: Optional[str] = None,
    ) -> str:
        """Create JWT access token."""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.config.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expire,
            "role": role.value,
            "factory_id": factory_id,
        }

        encoded = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

        logger.info(f"Created access token for user {user_id} with role {role.value}")
        return encoded

    def create_refresh_token(
        self,
        user_id: str,
    ) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        expire = now + timedelta(days=self.config.refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expire,
            "type": "refresh",
        }

        encoded = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

        return encoded

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and verify JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            return None

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify token and return payload."""
        payload = self.decode_token(token)
        if not payload:
            return None

        try:
            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                role=UserRole(payload["role"]),
                factory_id=payload.get("factory_id"),
            )
        except Exception as e:
            logger.error(f"Error parsing token payload: {e}")
            return None


class RBACMiddleware:
    """Middleware for role-based access control."""

    def __init__(self, auth_service: AuthService):
        """Initialize RBAC middleware."""
        self.auth_service = auth_service

    def extract_token(self, authorization_header: str) -> Optional[str]:
        """Extract token from Authorization header."""
        if not authorization_header:
            return None

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    def verify_permission(
        self,
        token: str,
        required_permission: str,
    ) -> Optional[TokenPayload]:
        """
        Verify token and check permission.

        Args:
            token: JWT token
            required_permission: Required permission string

        Returns:
            TokenPayload if authorized, None otherwise
        """
        payload = self.auth_service.verify_token(token)
        if not payload:
            return None

        # Check permission
        if not Permissions.has_permission(payload.role, required_permission):
            logger.warning(
                f"User {payload.sub} lacks permission: {required_permission}"
            )
            return None

        return payload

    def verify_factory_access(
        self,
        token: str,
        factory_id: str,
        required_permission: str,
    ) -> Optional[TokenPayload]:
        """
        Verify token and check factory-scoped access.

        Args:
            token: JWT token
            factory_id: Factory ID being accessed
            required_permission: Required permission

        Returns:
            TokenPayload if authorized, None otherwise
        """
        payload = self.verify_permission(token, required_permission)
        if not payload:
            return None

        # Check factory access (admins can access any factory)
        if payload.role != UserRole.ADMIN and payload.factory_id != factory_id:
            logger.warning(
                f"User {payload.sub} does not have access to factory {factory_id}"
            )
            return None

        return payload


class LoginRequest(BaseModel):
    """Login request."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User response."""
    id: str
    email: str
    full_name: str
    role: str
    factory_id: Optional[str] = None
    is_active: bool
