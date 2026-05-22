import pytest
from fastapi.testclient import TestClient
from paaim.main import app
from paaim.agents.registry import get_registry

client = TestClient(app)


def test_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_list_agents():
    """Test agent listing endpoint."""
    response = client.get("/api/agents/list")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "count" in data
    assert data["count"] == 5  # 5 built-in agents


def test_agent_schema():
    """Test agent schema endpoint."""
    response = client.get("/api/agents/safety_agent/schema")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "safety_agent"
    assert "schema" in data


def test_agent_registry():
    """Test agent registry."""
    registry = get_registry()

    # Check built-in agents are registered
    assert registry.get_agent("safety_agent") is not None
    assert registry.get_agent("quality_agent") is not None
    assert registry.get_agent("maintenance_agent") is not None
    assert registry.get_agent("production_agent") is not None
    assert registry.get_agent("energy_agent") is not None

    # Check total count
    agents = registry.list_agents()
    assert len(agents) == 5


def test_get_agents_for_event_type():
    """Test getting agents for specific event types."""
    registry = get_registry()

    safety_agents = registry.get_agents_for_event_type("safety")
    assert len(safety_agents) == 1
    assert safety_agents[0].name == "safety_agent"

    quality_agents = registry.get_agents_for_event_type("quality")
    assert len(quality_agents) == 1
    assert quality_agents[0].name == "quality_agent"
