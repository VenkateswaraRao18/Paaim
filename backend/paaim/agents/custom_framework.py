"""Custom AI Agent Framework - No-Code Agent Creation"""

from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class DataSourceType(str, Enum):
    """Supported data source types."""
    SCADA = "scada"  # SCADA systems
    CMS = "cms"  # Manufacturing execution systems
    IoT = "iot"  # IoT sensor networks
    REST_API = "rest_api"  # Generic REST APIs
    DATABASE = "database"  # SQL databases
    MESSAGE_QUEUE = "message_queue"  # Kafka, RabbitMQ
    OPC_UA = "opc_ua"  # OPC Unified Architecture


class RuleOperator(str, Enum):
    """Rule operators for policy definition."""
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_OR_EQUAL = ">="
    LESS_OR_EQUAL = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    MATCHES_REGEX = "matches_regex"


@dataclass
class DataSource:
    """Data source configuration for custom agent."""
    name: str
    type: DataSourceType
    config: Dict[str, Any]
    query: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    poll_interval_seconds: int = 30
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type.value,
            "config": self.config,
            "query": self.query,
            "auth_type": self.auth_type,
            "poll_interval_seconds": self.poll_interval_seconds,
            "enabled": self.enabled,
        }


@dataclass
class Rule:
    """Policy rule for custom agent."""
    field: str  # Field to check (e.g., "temperature")
    operator: RuleOperator  # Comparison operator
    value: Any  # Value to compare against
    action: str  # Action to recommend if rule matches
    confidence: float = 0.8  # Confidence of recommendation
    priority: int = 1  # Priority level

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "action": self.action,
            "confidence": self.confidence,
            "priority": self.priority,
        }


@dataclass
class CustomAgentDefinition:
    """Complete definition for custom agent."""
    id: str
    name: str
    description: str
    domain: str  # e.g., "thermal", "vibration", "pressure"
    data_sources: List[DataSource]
    rules: List[Rule]
    actions: List[str]  # Possible actions agent can recommend
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "data_sources": [ds.to_dict() for ds in self.data_sources],
            "rules": [r.to_dict() for r in self.rules],
            "actions": self.actions,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomAgentDefinition":
        """Create from dictionary."""
        data_sources = [
            DataSource(
                name=ds["name"],
                type=DataSourceType(ds["type"]),
                config=ds["config"],
                query=ds.get("query"),
                auth_type=ds.get("auth_type"),
                auth_config=ds.get("auth_config"),
                poll_interval_seconds=ds.get("poll_interval_seconds", 30),
            )
            for ds in data.get("data_sources", [])
        ]

        rules = [
            Rule(
                field=r["field"],
                operator=RuleOperator(r["operator"]),
                value=r["value"],
                action=r["action"],
                confidence=r.get("confidence", 0.8),
                priority=r.get("priority", 1),
            )
            for r in data.get("rules", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            domain=data["domain"],
            data_sources=data_sources,
            rules=rules,
            actions=data["actions"],
            enabled=data.get("enabled", True),
            created_by=data.get("created_by"),
        )


class CustomAgentExecutor:
    """Execute custom agent with rules against data from connected sources."""

    def __init__(self, definition: CustomAgentDefinition):
        """Initialize executor."""
        self.definition = definition
        self.logger = logging.getLogger(f"agent.{definition.id}")
        self.connectors: Dict[str, DataSourceConnector] = {}

    async def initialize(self) -> None:
        """Initialize data source connectors."""
        for data_source in self.definition.data_sources:
            if data_source.enabled:
                connector = get_connector_for_source(data_source)
                if connector:
                    if await connector.connect():
                        self.connectors[data_source.name] = connector
                        self.logger.info(f"Connected to data source: {data_source.name}")
                    else:
                        self.logger.warning(f"Failed to connect to data source: {data_source.name}")

    async def cleanup(self) -> None:
        """Cleanup data source connections."""
        for connector in self.connectors.values():
            await connector.disconnect()
        self.connectors.clear()

    async def fetch_source_data(self) -> Dict[str, Any]:
        """Fetch data from all connected sources."""
        combined_data = {}
        for data_source in self.definition.data_sources:
            if not data_source.enabled or data_source.name not in self.connectors:
                continue

            try:
                connector = self.connectors[data_source.name]
                source_data = await connector.fetch_data(data_source.query)
                combined_data.update(source_data)
            except Exception as e:
                self.logger.error(f"Failed to fetch from {data_source.name}: {e}")

        return combined_data

    def _evaluate_rule(
        self,
        rule: Rule,
        data: Dict[str, Any],
    ) -> bool:
        """Evaluate single rule against data."""
        if rule.field not in data:
            return False

        field_value = data[rule.field]

        if rule.operator == RuleOperator.EQUALS:
            return field_value == rule.value
        elif rule.operator == RuleOperator.NOT_EQUALS:
            return field_value != rule.value
        elif rule.operator == RuleOperator.GREATER_THAN:
            return field_value > rule.value
        elif rule.operator == RuleOperator.LESS_THAN:
            return field_value < rule.value
        elif rule.operator == RuleOperator.GREATER_OR_EQUAL:
            return field_value >= rule.value
        elif rule.operator == RuleOperator.LESS_OR_EQUAL:
            return field_value <= rule.value
        elif rule.operator == RuleOperator.IN:
            return field_value in rule.value
        elif rule.operator == RuleOperator.NOT_IN:
            return field_value not in rule.value
        elif rule.operator == RuleOperator.CONTAINS:
            return rule.value in str(field_value)
        elif rule.operator == RuleOperator.MATCHES_REGEX:
            import re
            return bool(re.search(rule.value, str(field_value)))

        return False

    async def execute(self, external_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute agent rules against data.

        Args:
            external_data: Optional external data to use instead of fetching from sources

        Returns:
            List of recommendations
        """
        # Fetch data from sources if not provided
        if external_data is None:
            data = await self.fetch_source_data()
        else:
            data = external_data

        recommendations = []

        # Sort rules by priority
        sorted_rules = sorted(self.definition.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if self._evaluate_rule(rule, data):
                recommendation = {
                    "agent_id": self.definition.id,
                    "agent_name": self.definition.name,
                    "action_name": rule.action,
                    "confidence": rule.confidence,
                    "evidence_signals": [f"{rule.field}={data.get(rule.field)}"],
                    "risk_level": "MEDIUM",
                    "reasoning": f"Rule matched: {rule.field} {rule.operator.value} {rule.value}",
                }
                recommendations.append(recommendation)
                self.logger.info(f"Rule matched: {rule.field} {rule.operator.value} {rule.value}")

        return recommendations


class CustomAgentRegistry:
    """Registry for managing custom agents."""

    def __init__(self):
        """Initialize registry."""
        self.agents: Dict[str, CustomAgentDefinition] = {}
        self.executors: Dict[str, CustomAgentExecutor] = {}
        self.logger = logging.getLogger(__name__)

    def register_agent(self, definition: CustomAgentDefinition) -> None:
        """Register custom agent."""
        self.agents[definition.id] = definition
        if definition.enabled:
            self.executors[definition.id] = CustomAgentExecutor(definition)
        self.logger.info(f"Registered custom agent: {definition.name} ({definition.id})")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister custom agent."""
        if agent_id in self.agents:
            del self.agents[agent_id]
        if agent_id in self.executors:
            del self.executors[agent_id]
        self.logger.info(f"Unregistered custom agent: {agent_id}")

    def enable_agent(self, agent_id: str) -> None:
        """Enable agent."""
        if agent_id in self.agents:
            self.agents[agent_id].enabled = True
            self.executors[agent_id] = CustomAgentExecutor(self.agents[agent_id])
            self.logger.info(f"Enabled agent: {agent_id}")

    def disable_agent(self, agent_id: str) -> None:
        """Disable agent."""
        if agent_id in self.agents:
            self.agents[agent_id].enabled = False
            if agent_id in self.executors:
                del self.executors[agent_id]
            self.logger.info(f"Disabled agent: {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[CustomAgentDefinition]:
        """Get agent definition."""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[CustomAgentDefinition]:
        """List all agents."""
        return list(self.agents.values())

    def execute_agent(
        self,
        agent_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute agent against data (sync wrapper, use execute_agent_async for async)."""
        import asyncio
        if agent_id not in self.executors:
            self.logger.warning(f"Agent not found or disabled: {agent_id}")
            return []

        executor = self.executors[agent_id]
        try:
            return asyncio.run(executor.execute(data))
        except RuntimeError:
            # Already in event loop, need to handle this differently
            self.logger.warning(f"Cannot run async execute from sync context for agent {agent_id}")
            return []

    async def execute_agent_async(
        self,
        agent_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Async execute agent against data."""
        if agent_id not in self.executors:
            self.logger.warning(f"Agent not found or disabled: {agent_id}")
            return []

        executor = self.executors[agent_id]
        return await executor.execute(data)

    def save_agents(self, filepath: str) -> None:
        """Save agents to JSON file."""
        data = {
            agent_id: agent.to_dict()
            for agent_id, agent in self.agents.items()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        self.logger.info(f"Saved {len(self.agents)} agents to {filepath}")

    def load_agents(self, filepath: str) -> None:
        """Load agents from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for agent_data in data.values():
                definition = CustomAgentDefinition.from_dict(agent_data)
                self.register_agent(definition)
            self.logger.info(f"Loaded {len(data)} agents from {filepath}")
        except FileNotFoundError:
            self.logger.warning(f"Agent file not found: {filepath}")


class DataSourceConnector:
    """Abstract base for data source connectors."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"connector.{config.get('name')}")

    async def connect(self) -> bool:
        """Establish connection to data source."""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Close connection to data source."""
        raise NotImplementedError

    async def fetch_data(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Fetch data from source."""
        raise NotImplementedError

    async def test_connection(self) -> Tuple[bool, str]:
        """Test if connection is valid."""
        raise NotImplementedError


class SCADAConnector(DataSourceConnector):
    """SCADA system connector (Modbus, OPC-UA protocol simulation)."""

    async def connect(self) -> bool:
        """Connect to SCADA system."""
        try:
            host = self.config.get("host", "localhost")
            port = self.config.get("port", 502)
            timeout = self.config.get("timeout", 5)
            self.logger.info(f"Connecting to SCADA at {host}:{port}")
            # In production, use pymodbus or opcua library
            return True
        except Exception as e:
            self.logger.error(f"SCADA connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from SCADA."""
        self.logger.info("Disconnected from SCADA")

    async def fetch_data(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Fetch tags/registers from SCADA."""
        try:
            # Parse query format: "tag1,tag2,register:100-110"
            if not query:
                return {}

            tags = query.split(",")
            data = {}
            for tag in tags:
                tag = tag.strip()
                if ":" in tag:
                    # Register range format
                    name, range_str = tag.split(":")
                    data[name] = {"range": range_str, "values": []}
                else:
                    # Single tag
                    data[tag] = 0.0  # Simulated value

            return data
        except Exception as e:
            self.logger.error(f"SCADA fetch failed: {e}")
            return {}

    async def test_connection(self) -> Tuple[bool, str]:
        """Test SCADA connection."""
        connected = await self.connect()
        await self.disconnect()
        return (connected, "SCADA connection OK" if connected else "SCADA connection failed")


class CMSConnector(DataSourceConnector):
    """Manufacturing Execution System (CMS) connector."""

    async def connect(self) -> bool:
        """Connect to CMS."""
        try:
            host = self.config.get("host", "localhost")
            port = self.config.get("port", 8080)
            username = self.config.get("username", "")
            self.logger.info(f"Connecting to CMS at {host}:{port}")
            # In production, use actual HTTP/SOAP calls
            return True
        except Exception as e:
            self.logger.error(f"CMS connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from CMS."""
        self.logger.info("Disconnected from CMS")

    async def fetch_data(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Fetch production orders, work orders, etc."""
        try:
            query_type = query or "orders"

            if query_type == "orders":
                return {
                    "orders": [
                        {"order_id": "ORD001", "status": "in_progress", "progress": 65},
                        {"order_id": "ORD002", "status": "queued", "progress": 0},
                    ]
                }
            elif query_type == "work_orders":
                return {
                    "work_orders": [
                        {"wo_id": "WO001", "type": "maintenance", "priority": "high"},
                    ]
                }
            else:
                return {}
        except Exception as e:
            self.logger.error(f"CMS fetch failed: {e}")
            return {}

    async def test_connection(self) -> Tuple[bool, str]:
        """Test CMS connection."""
        connected = await self.connect()
        await self.disconnect()
        return (connected, "CMS connection OK" if connected else "CMS connection failed")


class IoTConnector(DataSourceConnector):
    """IoT sensor network connector (MQTT, CoAP)."""

    async def connect(self) -> bool:
        """Connect to IoT broker."""
        try:
            host = self.config.get("broker_host", "localhost")
            port = self.config.get("broker_port", 1883)
            protocol = self.config.get("protocol", "mqtt")
            self.logger.info(f"Connecting to {protocol} broker at {host}:{port}")
            # In production, use paho-mqtt or similar
            return True
        except Exception as e:
            self.logger.error(f"IoT connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from IoT broker."""
        self.logger.info("Disconnected from IoT broker")

    async def fetch_data(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Fetch sensor data (subscribe to topics)."""
        try:
            topics = (query or "sensors/+/temperature").split(",")
            data = {}
            for topic in topics:
                data[topic.strip()] = {
                    "value": 25.5,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            return data
        except Exception as e:
            self.logger.error(f"IoT fetch failed: {e}")
            return {}

    async def test_connection(self) -> Tuple[bool, str]:
        """Test IoT connection."""
        connected = await self.connect()
        await self.disconnect()
        return (connected, "IoT connection OK" if connected else "IoT connection failed")


class RESTAPIConnector(DataSourceConnector):
    """Generic REST API connector."""

    async def connect(self) -> bool:
        """Test REST API connectivity."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                url = self.config.get("base_url", "http://localhost")
                response = await client.get(f"{url}/health")
                return response.status_code < 400
        except Exception as e:
            self.logger.error(f"REST API connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """REST API is stateless."""
        pass

    async def fetch_data(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Fetch data from REST API endpoint."""
        try:
            import httpx
            base_url = self.config.get("base_url", "http://localhost")
            endpoint = query or "/api/data"

            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{base_url}{endpoint}")
                if response.status_code == 200:
                    return response.json()
            return {}
        except Exception as e:
            self.logger.error(f"REST API fetch failed: {e}")
            return {}

    async def test_connection(self) -> Tuple[bool, str]:
        """Test REST API connection."""
        connected = await self.connect()
        return (connected, "REST API connection OK" if connected else "REST API connection failed")


def get_connector_for_source(data_source: DataSource) -> Optional[DataSourceConnector]:
    """Factory method to get appropriate connector for data source."""
    if data_source.type == DataSourceType.SCADA:
        return SCADAConnector(data_source.config)
    elif data_source.type == DataSourceType.CMS:
        return CMSConnector(data_source.config)
    elif data_source.type == DataSourceType.IoT:
        return IoTConnector(data_source.config)
    elif data_source.type == DataSourceType.REST_API:
        return RESTAPIConnector(data_source.config)
    return None


# Global registry instance
_registry: Optional[CustomAgentRegistry] = None


def get_custom_agent_registry() -> CustomAgentRegistry:
    """Get or create global custom agent registry."""
    global _registry
    if _registry is None:
        _registry = CustomAgentRegistry()
    return _registry


def reset_custom_agent_registry() -> None:
    """Reset registry (for testing)."""
    global _registry
    _registry = None
