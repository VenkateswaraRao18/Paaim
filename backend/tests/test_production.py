"""Comprehensive test suite for PAAIM."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Auth tests
from paaim.auth.service import AuthService, AuthConfig, UserRole, Permissions, RBACMiddleware


class TestAuthService:
    """Test authentication service."""

    @pytest.fixture
    def auth_service(self):
        """Create auth service."""
        config = AuthConfig(secret_key="test_secret_key")
        return AuthService(config)

    def test_password_hashing(self, auth_service):
        """Password should be hashed correctly."""
        password = "secure_password_123"
        hashed = auth_service.hash_password(password)
        assert hashed != password
        assert auth_service.verify_password(password, hashed)

    def test_access_token_creation(self, auth_service):
        """Should create valid access token."""
        token = auth_service.create_access_token(
            user_id="user_001",
            role=UserRole.ADMIN,
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_verification(self, auth_service):
        """Should verify valid token."""
        token = auth_service.create_access_token(
            user_id="user_001",
            role=UserRole.SUPERVISOR,
            factory_id="factory_001",
        )
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload.sub == "user_001"
        assert payload.role == UserRole.SUPERVISOR
        assert payload.factory_id == "factory_001"

    def test_expired_token(self, auth_service):
        """Should reject expired token."""
        config = AuthConfig(
            secret_key="test_secret",
            access_token_expire_minutes=-1,  # Already expired
        )
        service = AuthService(config)
        token = service.create_access_token(
            user_id="user_001",
            role=UserRole.OPERATOR,
        )
        # Token should be expired
        payload = auth_service.verify_token(token)
        assert payload is None

    def test_invalid_token(self, auth_service):
        """Should reject invalid token."""
        payload = auth_service.verify_token("invalid.token.here")
        assert payload is None


class TestPermissions:
    """Test RBAC permissions."""

    def test_viewer_permissions(self):
        """Viewer should have read-only permissions."""
        assert Permissions.has_permission(UserRole.VIEWER, "events:read")
        assert Permissions.has_permission(UserRole.VIEWER, "decisions:read")
        assert not Permissions.has_permission(UserRole.VIEWER, "decisions:approve")
        assert not Permissions.has_permission(UserRole.VIEWER, "config:write")

    def test_operator_permissions(self):
        """Operator should have acknowledge permissions."""
        assert Permissions.has_permission(UserRole.OPERATOR, "decisions:acknowledge")
        assert Permissions.has_permission(UserRole.OPERATOR, "decisions:read")
        assert not Permissions.has_permission(UserRole.OPERATOR, "decisions:approve")

    def test_supervisor_permissions(self):
        """Supervisor should have approval permissions."""
        assert Permissions.has_permission(UserRole.SUPERVISOR, "decisions:approve")
        assert Permissions.has_permission(UserRole.SUPERVISOR, "decisions:reject")
        assert not Permissions.has_permission(UserRole.SUPERVISOR, "config:write")

    def test_admin_permissions(self):
        """Admin should have all permissions."""
        permissions = Permissions.get_permissions(UserRole.ADMIN)
        assert "events:read" in permissions
        assert "decisions:approve" in permissions
        assert "config:write" in permissions
        assert "users:write" in permissions


class TestRBACMiddleware:
    """Test RBAC middleware."""

    @pytest.fixture
    def middleware(self):
        """Create middleware."""
        config = AuthConfig(secret_key="test_secret")
        auth_service = AuthService(config)
        return RBACMiddleware(auth_service)

    def test_extract_valid_token(self, middleware):
        """Should extract valid bearer token."""
        header = "Bearer valid.jwt.token"
        token = middleware.extract_token(header)
        assert token == "valid.jwt.token"

    def test_extract_invalid_header(self, middleware):
        """Should reject invalid authorization header."""
        assert middleware.extract_token("Invalid header") is None
        assert middleware.extract_token("") is None
        assert middleware.extract_token(None) is None

    def test_verify_permission(self, middleware):
        """Should verify permission correctly."""
        config = AuthConfig(secret_key="test_secret")
        auth_service = AuthService(config)
        token = auth_service.create_access_token(
            user_id="user_001",
            role=UserRole.ADMIN,
        )

        # Admin should have config:write permission
        payload = middleware.verify_permission(token, "config:write")
        assert payload is not None
        assert payload.sub == "user_001"

        # Create operator token
        op_token = auth_service.create_access_token(
            user_id="user_002",
            role=UserRole.OPERATOR,
        )
        # Operator should not have config:write permission
        op_payload = middleware.verify_permission(op_token, "config:write")
        assert op_payload is None

    def test_verify_factory_access(self, middleware):
        """Should verify factory-scoped access."""
        config = AuthConfig(secret_key="test_secret")
        auth_service = AuthService(config)

        # Operator with factory_001 access
        token = auth_service.create_access_token(
            user_id="user_001",
            role=UserRole.OPERATOR,
            factory_id="factory_001",
        )

        # Should allow access to own factory
        payload = middleware.verify_factory_access(
            token,
            "factory_001",
            "decisions:read",
        )
        assert payload is not None

        # Should deny access to other factory
        payload = middleware.verify_factory_access(
            token,
            "factory_002",
            "decisions:read",
        )
        assert payload is None

        # Admin should access any factory
        admin_token = auth_service.create_access_token(
            user_id="admin_001",
            role=UserRole.ADMIN,
        )
        payload = middleware.verify_factory_access(
            admin_token,
            "factory_any",
            "config:write",
        )
        assert payload is not None


# Orchestrator integration tests
@pytest.mark.asyncio
class TestOrchestrationIntegration:
    """Test full orchestration pipeline."""

    async def test_orchestration_completes(self):
        """Full orchestration should complete successfully."""
        from paaim.models import EventData, EventType
        from paaim.orchestrator import get_orchestrator

        event = EventData(
            event_type=EventType.SAFETY,
            source_agent="safety_agent",
            factory_id="factory_001",
            machine_id="machine_001",
            signal_value=1.0,
            signal_name="zone_intrusion",
            confidence=0.98,
            timestamp=datetime.utcnow(),
            context={"zone_id": "restricted_zone_a"},
        )

        orchestrator = get_orchestrator()
        decision = await orchestrator.orchestrate(event)

        assert decision is not None
        assert "decision_id" in decision
        assert "orchestration_result" in decision


# Performance tests
@pytest.mark.asyncio
class TestPerformance:
    """Test performance metrics."""

    async def test_orchestration_latency(self):
        """Orchestration should meet SLA (<2 seconds)."""
        from paaim.models import EventData, EventType
        from paaim.orchestrator import get_orchestrator
        import time

        event = EventData(
            event_type=EventType.QUALITY,
            source_agent="quality_agent",
            factory_id="factory_001",
            machine_id="machine_001",
            signal_value=8.5,
            signal_name="defect_detection",
            confidence=0.92,
            timestamp=datetime.utcnow(),
            context={"batch_id": "B001"},
        )

        orchestrator = get_orchestrator()

        start = time.time()
        decision = await orchestrator.orchestrate(event)
        latency = time.time() - start

        assert latency < 2.0  # SLA: <2 seconds
        assert decision is not None
