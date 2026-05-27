"""Continuous agent execution with real-time data streaming."""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import logging

from paaim.connectors.realtime import (
    DataStreamManager,
    DataSnapshot,
    PollingDataConnector,
    MQTTStreamingConnector,
)
from paaim.agents.custom_framework import CustomAgentDefinition, CustomAgentExecutor

logger = logging.getLogger(__name__)


class RealtimeCustomAgentRunner:
    """Runs a custom agent continuously with real-time data."""

    def __init__(self, definition: CustomAgentDefinition):
        self.definition = definition
        self.executor = CustomAgentExecutor(definition)
        self.stream_manager = DataStreamManager(definition.name)
        self.logger = logging.getLogger(f"agent_runner.{definition.id}")

        # Setup data stream connectors based on data sources
        self._setup_connectors()

        self.is_running = False
        self._recommendations_queue: List[Dict[str, Any]] = []
        self._on_recommendation_callbacks: List[Callable] = []

    def _setup_connectors(self) -> None:
        """Create real-time connectors from data source definitions."""
        for data_source in self.definition.data_sources:
            if not data_source.enabled:
                continue

            # Choose connector type based on data source type
            if data_source.type.value == "SCADA":
                from paaim.connectors.realtime import SCADAPollingConnector

                connector = SCADAPollingConnector(
                    name=data_source.name,
                    config={
                        **data_source.config,
                        "poll_interval_seconds": data_source.poll_interval_seconds,
                        "fields": data_source.query.split(",") if data_source.query else [],
                    },
                )

            elif data_source.type.value == "CMS":
                from paaim.connectors.realtime import MESPollingConnector

                connector = MESPollingConnector(
                    name=data_source.name,
                    config={
                        **data_source.config,
                        "poll_interval_seconds": data_source.poll_interval_seconds,
                        "fields": data_source.query.split(",") if data_source.query else [],
                    },
                )

            elif data_source.type.value == "IoT":
                connector = MQTTStreamingConnector(
                    name=data_source.name,
                    config={
                        **data_source.config,
                        "topics": data_source.query.split(",") if data_source.query else [],
                    },
                )

            else:
                # Fallback to polling for REST API and others
                connector = PollingDataConnector(
                    name=data_source.name,
                    config={
                        **data_source.config,
                        "poll_interval_seconds": data_source.poll_interval_seconds,
                        "fields": data_source.query.split(",") if data_source.query else [],
                    },
                )

            self.stream_manager.register_connector(connector)
            self.logger.info(
                f"Registered real-time connector: {data_source.name} "
                f"({data_source.type.value})"
            )

    async def on_new_data(self, snapshot: DataSnapshot) -> None:
        """Called when new data arrives from any source."""
        try:
            # Convert snapshot to dictionary for rule evaluation
            data_dict = snapshot.to_dict()

            # Execute agent with new data
            recommendations = await self.executor.execute(data_dict)

            if recommendations:
                self.logger.info(
                    f"Agent generated {len(recommendations)} recommendations "
                    f"at {datetime.utcnow().isoformat()}"
                )

                # Store recommendations
                self._recommendations_queue.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "data_snapshot": data_dict,
                        "recommendations": recommendations,
                        "sources_health": {
                            "healthy": snapshot.sources_healthy,
                            "failed": snapshot.sources_failed,
                        },
                    }
                )

                # Notify subscribers
                for callback in self._on_recommendation_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(recommendations)
                        else:
                            callback(recommendations)
                    except Exception as e:
                        self.logger.error(f"Callback error: {e}")

        except Exception as e:
            self.logger.error(f"Error processing data snapshot: {e}")

    def subscribe_to_recommendations(self, callback: Callable) -> None:
        """Subscribe to recommendation events from this agent."""
        self._on_recommendation_callbacks.append(callback)

    async def start(self) -> None:
        """Start the agent runner and data streaming."""
        self.is_running = True
        self.logger.info(f"Starting agent runner for {self.definition.name}")

        # Subscribe to data updates
        await self.stream_manager.subscribe(self.on_new_data)

        # Initialize executor
        await self.executor.initialize()

        # Start all data streams
        await self.stream_manager.start()

    async def stop(self) -> None:
        """Stop the agent runner."""
        self.is_running = False
        await self.executor.cleanup()
        await self.stream_manager.stop()
        self.logger.info(f"Stopped agent runner for {self.definition.name}")

    def get_latest_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the latest recommendations."""
        return self._recommendations_queue[-limit:]

    async def get_health(self) -> Dict[str, Any]:
        """Get agent and data source health status."""
        latest = await self.stream_manager.get_latest()
        return {
            "agent_id": self.definition.id,
            "agent_name": self.definition.name,
            "is_running": self.is_running,
            "data_sources": {
                ds.name: {
                    "type": ds.type.value,
                    "enabled": ds.enabled,
                    "poll_interval": ds.poll_interval_seconds,
                }
                for ds in self.definition.data_sources
            },
            "sources_health": {
                "healthy": latest.sources_healthy if latest else [],
                "failed": latest.sources_failed if latest else [],
            },
            "latest_data": latest.to_dict() if latest else None,
            "recommendations_count": len(self._recommendations_queue),
        }
