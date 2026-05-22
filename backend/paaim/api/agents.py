from fastapi import APIRouter
from paaim.agents.registry import get_registry

router = APIRouter()


@router.get("/list")
async def list_agents():
    """List all available agents (built-in and custom)."""
    registry = get_registry()
    agents = registry.list_agents()

    return {
        "agents": agents,
        "count": len(agents),
        "categories": {
            "safety": ["safety_agent"],
            "quality": ["quality_agent"],
            "maintenance": ["maintenance_agent"],
            "production": ["production_agent"],
            "energy": ["energy_agent"],
            "custom": [name for name in agents.keys() if name not in [
                "safety_agent", "quality_agent", "maintenance_agent",
                "production_agent", "energy_agent"
            ]]
        }
    }


@router.get("/{agent_name}/schema")
async def get_agent_schema(agent_name: str):
    """Get detailed schema for a specific agent."""
    registry = get_registry()
    agent = registry.get_agent(agent_name)

    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}

    return {
        "name": agent_name,
        "schema": agent.get_schema()
    }
