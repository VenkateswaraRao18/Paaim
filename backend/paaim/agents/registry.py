from typing import Dict, List, Optional, Any
import json
from pathlib import Path
from paaim.agents.base import BaseAgent, SafetyAgent, QualityAgent, MaintenanceAgent, ProductionAgent, EnergyAgent


class AgentRegistry:
    """Registry and loader for all agents (built-in and custom)."""

    def __init__(self, custom_agents_path: Optional[str] = None):
        """
        Initialize agent registry.

        Args:
            custom_agents_path: Path to custom agent definitions directory
        """
        self._agents: Dict[str, BaseAgent] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self.custom_agents_path = custom_agents_path

        # Load built-in agents
        self._load_builtin_agents()

    def _load_builtin_agents(self):
        """Load all built-in agents."""
        builtin_agents = [
            SafetyAgent(),
            QualityAgent(),
            MaintenanceAgent(),
            ProductionAgent(),
            EnergyAgent(),
        ]

        for agent in builtin_agents:
            self.register(agent)

    def register(self, agent: BaseAgent):
        """Register an agent in the registry."""
        self._agents[agent.name] = agent
        self._schemas[agent.name] = agent.get_schema()

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        return self._agents.get(name)

    def get_agents_for_event_type(self, event_type: str) -> List[BaseAgent]:
        """Get all agents that handle a specific event type."""
        return [agent for agent in self._agents.values() if event_type in agent.event_types]

    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all registered agents and their schemas."""
        return self._schemas.copy()

    def load_custom_agent_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Load custom agent definitions from YAML/JSON files.

        Expected format:
        {
            "name": "custom_humidity_monitor",
            "role": "Monitor humidity levels",
            "event_types": ["custom"],
            "input_signals": ["humidity_sensor"],
            "output_actions": ["alert_operator", "trigger_dehumidifier"],
            "approval_required": "operator",
            "tools": [
                {
                    "type": "rest_api",
                    "endpoint": "http://sensor-api:8080/humidity",
                    "method": "GET"
                }
            ]
        }

        Returns:
            Dictionary of custom agent definitions loaded
        """
        custom_definitions = {}

        if not self.custom_agents_path:
            return custom_definitions

        custom_path = Path(self.custom_agents_path)
        if not custom_path.exists():
            return custom_definitions

        # Load all YAML/JSON files in custom agents directory
        for config_file in custom_path.glob("*.json"):
            try:
                with open(config_file, "r") as f:
                    definition = json.load(f)
                    agent_name = definition.get("name", config_file.stem)
                    custom_definitions[agent_name] = definition
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading custom agent config {config_file}: {e}")

        return custom_definitions

    def validate_custom_agent_definition(self, definition: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate a custom agent definition.

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["name", "role", "event_types", "output_actions"]

        for field in required_fields:
            if field not in definition:
                return False, f"Missing required field: {field}"

        if not isinstance(definition.get("event_types"), list):
            return False, "event_types must be a list"

        if not isinstance(definition.get("output_actions"), list):
            return False, "output_actions must be a list"

        return True, ""


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get or create the global agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def initialize_registry(custom_agents_path: Optional[str] = None):
    """Initialize the global agent registry."""
    global _registry
    _registry = AgentRegistry(custom_agents_path=custom_agents_path)
