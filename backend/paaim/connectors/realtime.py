"""Real-time data source streaming for custom agents."""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, AsyncIterator
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    """Single data point from a source."""
    source_name: str
    field: str
    value: Any
    timestamp: datetime
    quality: str = "good"  # good, degraded, error


@dataclass
class DataSnapshot:
    """Complete snapshot of data from all sources at a point in time."""
    data_points: List[DataPoint]
    timestamp: datetime
    sources_healthy: List[str]
    sources_failed: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for rule evaluation."""
        result = {}
        for point in self.data_points:
            # Try to convert numeric values
            try:
                value = float(point.value)
            except (ValueError, TypeError):
                value = point.value

            result[point.field] = value
        return result


class DataStreamType(str, Enum):
    """How data is streamed from the source."""
    POLLING = "polling"  # Pull data at intervals
    MQTT = "mqtt"  # MQTT publish-subscribe
    WEBSOCKET = "websocket"  # WebSocket streaming
    OPC_UA = "opc_ua"  # OPC Unified Architecture
    HTTP_STREAMING = "http_streaming"  # HTTP chunked transfer


class RealTimeDataConnector:
    """Base class for real-time data streaming."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"connector.{name}")
        self.is_connected = False
        self._subscribers: List[Callable[[DataSnapshot], None]] = []

    async def connect(self) -> bool:
        """Establish connection to data source."""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Disconnect from data source."""
        raise NotImplementedError

    async def get_snapshot(self) -> DataSnapshot:
        """Get current data snapshot (point-in-time)."""
        raise NotImplementedError

    async def subscribe(
        self, callback: Callable[[DataSnapshot], None]
    ) -> None:
        """Subscribe to real-time data updates."""
        self._subscribers.append(callback)

    async def stream(self) -> AsyncIterator[DataSnapshot]:
        """Stream data continuously."""
        raise NotImplementedError

    def _notify_subscribers(self, snapshot: DataSnapshot) -> None:
        """Notify all subscribers of new data."""
        for callback in self._subscribers:
            try:
                # Call synchronously, don't wait for async
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(snapshot))
                else:
                    callback(snapshot)
            except Exception as e:
                self.logger.error(f"Subscriber error: {e}")


class PollingDataConnector(RealTimeDataConnector):
    """Poll data source at regular intervals."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.poll_interval = config.get("poll_interval_seconds", 5)
        self.fields = config.get("fields", [])  # List of fields to fetch

    async def connect(self) -> bool:
        """Establish connection and start polling loop."""
        try:
            self.logger.info(f"Connecting to polling source: {self.name}")
            # Simulate connection validation
            await asyncio.sleep(0.1)
            self.is_connected = True
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Stop polling."""
        self.is_connected = False
        self.logger.info(f"Disconnected from {self.name}")

    async def get_snapshot(self) -> DataSnapshot:
        """Fetch current data from source."""
        if not self.is_connected:
            return DataSnapshot(
                data_points=[],
                timestamp=datetime.utcnow(),
                sources_healthy=[],
                sources_failed=[self.name],
            )

        data_points = []
        try:
            # Simulate fetching data from actual source
            for field in self.fields:
                value = await self._fetch_field(field)
                data_points.append(
                    DataPoint(
                        source_name=self.name,
                        field=field,
                        value=value,
                        timestamp=datetime.utcnow(),
                    )
                )

            return DataSnapshot(
                data_points=data_points,
                timestamp=datetime.utcnow(),
                sources_healthy=[self.name],
                sources_failed=[],
            )
        except Exception as e:
            self.logger.error(f"Failed to fetch snapshot: {e}")
            return DataSnapshot(
                data_points=[],
                timestamp=datetime.utcnow(),
                sources_healthy=[],
                sources_failed=[self.name],
            )

    async def _fetch_field(self, field: str) -> Any:
        """Fetch a single field value from source."""
        # This would be implemented by subclasses
        # For demo, return simulated data
        import random

        if "temp" in field.lower():
            return 20 + random.random() * 60  # 20-80°C
        elif "pressure" in field.lower():
            return 100 + random.random() * 50  # 100-150 PSI
        elif "vibration" in field.lower():
            return random.random() * 10  # 0-10 Hz
        return random.random() * 100

    async def stream(self) -> AsyncIterator[DataSnapshot]:
        """Continuously stream data at polling interval."""
        while self.is_connected:
            snapshot = await self.get_snapshot()
            yield snapshot
            await asyncio.sleep(self.poll_interval)


class SCADAPollingConnector(PollingDataConnector):
    """Real SCADA connector with Modbus polling."""

    async def _fetch_field(self, field: str) -> Any:
        """Fetch from real SCADA system via Modbus."""
        # In production, use pymodbus library
        # from pymodbus.client.sync import ModbusTcpClient
        # client = ModbusTcpClient(host=self.config['host'], port=self.config['port'])
        # value = client.read_holding_registers(address, count)

        # For now, simulate
        import random

        await asyncio.sleep(0.01)  # Simulate network latency
        return round(20 + random.random() * 60, 2)


class MESPollingConnector(PollingDataConnector):
    """Real CMS/MES connector with REST API polling."""

    async def _fetch_field(self, field: str) -> Any:
        """Fetch from real MES system via REST API."""
        # In production, use httpx for async HTTP
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(f"{self.config['base_url']}/api/{field}")
        #     return response.json()

        # For now, simulate
        import random

        await asyncio.sleep(0.05)  # Simulate network latency
        return random.choice(["in_progress", "queued", "completed"])


class MQTTStreamingConnector(RealTimeDataConnector):
    """Real-time MQTT streaming connector."""

    async def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            # In production, use aiomqtt library
            # import aiomqtt
            # self.client = aiomqtt.Client(self.config['broker_host'])
            # await self.client.connect()

            self.logger.info(f"Connected to MQTT broker: {self.config['broker_host']}")
            self.is_connected = True
            return True
        except Exception as e:
            self.logger.error(f"MQTT connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        # if self.client:
        #     await self.client.disconnect()
        self.is_connected = False

    async def get_snapshot(self) -> DataSnapshot:
        """Get current values from retained MQTT messages."""
        # Would retrieve last retained message for each topic
        return DataSnapshot(
            data_points=[],
            timestamp=datetime.utcnow(),
            sources_healthy=[self.name] if self.is_connected else [],
            sources_failed=[] if self.is_connected else [self.name],
        )

    async def stream(self) -> AsyncIterator[DataSnapshot]:
        """Stream MQTT messages as they arrive."""
        import random

        # In production:
        # async with self.client.messages() as messages:
        #     async for message in messages:
        #         yield DataSnapshot(...)

        # For demo, simulate MQTT messages
        while self.is_connected:
            data_points = [
                DataPoint(
                    source_name=self.name,
                    field=f"sensor_{i}",
                    value=20 + random.random() * 60,
                    timestamp=datetime.utcnow(),
                )
                for i in range(3)
            ]
            yield DataSnapshot(
                data_points=data_points,
                timestamp=datetime.utcnow(),
                sources_healthy=[self.name],
                sources_failed=[],
            )
            await asyncio.sleep(1)  # MQTT messages arrive in real-time


class DataStreamManager:
    """Manages multiple real-time data sources for an agent."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.connectors: Dict[str, RealTimeDataConnector] = {}
        self.logger = logging.getLogger(f"stream_manager.{agent_name}")
        self._latest_snapshot: Optional[DataSnapshot] = None
        self._snapshot_lock = asyncio.Lock()
        self._subscribers: List[Callable[[DataSnapshot], None]] = []

    def register_connector(
        self,
        connector: RealTimeDataConnector,
    ) -> None:
        """Register a data source connector."""
        self.connectors[connector.name] = connector
        self.logger.info(f"Registered connector: {connector.name}")

    async def start(self) -> None:
        """Connect all sources and start streaming."""
        self.logger.info(f"Starting data streams for {self.agent_name}")

        # Connect all sources
        for connector in self.connectors.values():
            success = await connector.connect()
            if not success:
                self.logger.warning(f"Failed to connect: {connector.name}")

        # Start streaming tasks for each connector
        tasks = []
        for connector in self.connectors.values():
            if connector.is_connected:
                task = asyncio.create_task(self._stream_connector(connector))
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks)

    async def _stream_connector(self, connector: RealTimeDataConnector) -> None:
        """Stream data from a single connector."""
        try:
            async for snapshot in connector.stream():
                # Merge with existing data
                await self._merge_snapshot(snapshot)
        except Exception as e:
            self.logger.error(f"Streaming error from {connector.name}: {e}")
        finally:
            await connector.disconnect()

    async def _merge_snapshot(self, snapshot: DataSnapshot) -> None:
        """Merge new data with latest snapshot."""
        async with self._snapshot_lock:
            if self._latest_snapshot is None:
                self._latest_snapshot = snapshot
            else:
                # Merge data points
                existing_fields = {
                    dp.field: dp for dp in self._latest_snapshot.data_points
                }
                for dp in snapshot.data_points:
                    existing_fields[dp.field] = dp

                self._latest_snapshot = DataSnapshot(
                    data_points=list(existing_fields.values()),
                    timestamp=datetime.utcnow(),
                    sources_healthy=list(
                        set(self._latest_snapshot.sources_healthy)
                        | set(snapshot.sources_healthy)
                    ),
                    sources_failed=list(
                        set(self._latest_snapshot.sources_failed)
                        | set(snapshot.sources_failed)
                    ),
                )

            # Notify subscribers
            for callback in self._subscribers:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self._latest_snapshot)
                    else:
                        callback(self._latest_snapshot)
                except Exception as e:
                    self.logger.error(f"Subscriber error: {e}")

    async def subscribe(
        self, callback: Callable[[DataSnapshot], None]
    ) -> None:
        """Subscribe to data updates."""
        self._subscribers.append(callback)

    async def get_latest(self) -> Optional[DataSnapshot]:
        """Get latest data snapshot."""
        async with self._snapshot_lock:
            return self._latest_snapshot

    async def stop(self) -> None:
        """Stop all data streams."""
        for connector in self.connectors.values():
            await connector.disconnect()
        self.logger.info(f"Stopped data streams for {self.agent_name}")
