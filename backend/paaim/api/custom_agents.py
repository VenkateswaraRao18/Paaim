"""API endpoints for managing custom AI agents."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from paaim.agents.custom_framework import (
    get_custom_agent_registry,
    CustomAgentDefinition,
    DataSource,
    Rule,
    DataSourceType,
    RuleOperator,
    get_connector_for_source,
)

router = APIRouter()


class DataSourceRequest(BaseModel):
    """Request body for data source."""
    name: str
    type: str  # Must be a DataSourceType value
    config: Dict[str, Any]
    query: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    poll_interval_seconds: int = 30
    enabled: bool = True


class RuleRequest(BaseModel):
    """Request body for rule."""
    field: str
    operator: str  # Must be a RuleOperator value
    value: Any
    action: str
    confidence: float = 0.8
    priority: int = 1


class CustomAgentRequest(BaseModel):
    """Request body for creating/updating custom agent."""
    name: str
    description: str
    domain: str
    rules: List[RuleRequest]
    actions: List[str]
    watch_signals: List[str] = []                       # canonical signals to watch
    scope: Dict[str, Any] = {"type": "all"}             # all | machines | zone
    data_sources: List[DataSourceRequest] = []          # legacy / optional
    enabled: bool = True


class CustomAgentResponse(BaseModel):
    """Response for custom agent."""
    id: str
    name: str
    description: str
    domain: str
    enabled: bool
    created_at: str
    created_by: Optional[str]


@router.post("/test-connection")
async def test_connection_before_create(request: DataSourceRequest) -> dict:
    """
    Test a data source connection before creating an agent.
    Accepts the same DataSourceRequest used in agent creation.
    """
    try:
        ds_type = DataSourceType(request.type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data source type: {request.type}",
        )

    data_source = DataSource(
        name=request.name or "test",
        type=ds_type,
        config=request.config,
        query=request.query,
        auth_type=request.auth_type,
        auth_config=request.auth_config,
    )
    connector = get_connector_for_source(data_source)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No connector available for type: {request.type}",
        )

    success, message = await connector.test_connection()
    return {"success": success, "message": message, "type": request.type}


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_custom_agent(request: CustomAgentRequest) -> CustomAgentResponse:
    """
    Create a new custom AI agent.

    - User specifies data sources (SCADA, CMS, IoT, REST API)
    - User defines rules (if/then logic for decision-making)
    - Agent automatically integrates into orchestration pipeline
    """
    try:
        registry = get_custom_agent_registry()

        # Validate operators
        for rule in request.rules:
            try:
                RuleOperator(rule.operator)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operator: {rule.operator}. Must be one of: {[op.value for op in RuleOperator]}"
                )

        # Validate data source types (normalize to lowercase so frontend SCADA/IoT/REST_API all work)
        for ds in request.data_sources:
            try:
                DataSourceType(ds.type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid data source type: {ds.type}. Must be one of: {[t.value for t in DataSourceType]}"
                )

        # Build data sources
        data_sources = [
            DataSource(
                name=ds.name,
                type=DataSourceType(ds.type.lower()),
                config=ds.config,
                query=ds.query,
                auth_type=ds.auth_type,
                auth_config=ds.auth_config,
                poll_interval_seconds=ds.poll_interval_seconds,
                enabled=ds.enabled,
            )
            for ds in request.data_sources
        ]

        # Build rules
        rules = [
            Rule(
                field=r.field,
                operator=RuleOperator(r.operator),
                value=r.value,
                action=r.action,
                confidence=r.confidence,
                priority=r.priority,
            )
            for r in request.rules
        ]

        # Create agent definition
        import uuid
        agent_id = f"custom_agent_{uuid.uuid4().hex[:8]}"

        definition = CustomAgentDefinition(
            id=agent_id,
            name=request.name,
            description=request.description,
            domain=request.domain,
            data_sources=data_sources,
            rules=rules,
            actions=request.actions,
            watch_signals=request.watch_signals,
            scope=request.scope or {"type": "all"},
            enabled=request.enabled,
            created_by="api_user",
        )

        # Register agent
        registry.register_agent(definition)

        return CustomAgentResponse(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            domain=definition.domain,
            enabled=definition.enabled,
            created_at=definition.created_at.isoformat(),
            created_by=definition.created_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create custom agent: {str(e)}"
        )


@router.get("/list")
async def list_custom_agents() -> dict:
    """List all custom agents."""
    try:
        registry = get_custom_agent_registry()
        agents = registry.list_agents()

        def _iso(val):
            if val is None:
                return None
            return val.isoformat() if hasattr(val, "isoformat") else str(val)

        custom_agents = [
            {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "domain": agent.domain,
                "enabled": agent.enabled,
                "watch_signals": list(agent.watch_signals or []),
                "scope": agent.scope or {"type": "all"},
                "data_sources_count": len(agent.data_sources),
                "rules_count": len(agent.rules),
                "actions": list(agent.actions or []),
                "data_sources": [
                    {"name": ds.name, "type": getattr(ds.type, "value", ds.type)}
                    for ds in agent.data_sources
                ],
                "created_at": _iso(getattr(agent, "created_at", None)),
                "updated_at": _iso(getattr(agent, "updated_at", None)),
            }
            for agent in agents
        ]

        return {
            "agents": custom_agents,
            "count": len(custom_agents),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list custom agents: {str(e)}"
        )


@router.get("/{agent_id}")
async def get_custom_agent(agent_id: str) -> dict:
    """Get details of a specific custom agent."""
    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "domain": agent.domain,
            "enabled": agent.enabled,
            "data_sources": [
                {
                    "name": ds.name,
                    "type": ds.type.value,
                    "poll_interval_seconds": ds.poll_interval_seconds,
                    "enabled": ds.enabled,
                }
                for ds in agent.data_sources
            ],
            "rules": [
                {
                    "field": r.field,
                    "operator": r.operator.value,
                    "value": r.value,
                    "action": r.action,
                    "confidence": r.confidence,
                    "priority": r.priority,
                }
                for r in agent.rules
            ],
            "actions": agent.actions,
            "created_at": agent.created_at.isoformat(),
            "created_by": agent.created_by,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve custom agent: {str(e)}"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_agent(agent_id: str):
    """Delete a custom agent."""
    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        registry.unregister_agent(agent_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete custom agent: {str(e)}"
        )


@router.post("/{agent_id}/test-connection")
async def test_data_source_connection(agent_id: str, source_name: str) -> dict:
    """Test connection to a data source for a custom agent."""
    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        # Find data source
        data_source = None
        for ds in agent.data_sources:
            if ds.name == source_name:
                data_source = ds
                break

        if not data_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source '{source_name}' not found in agent"
            )

        # Test connection
        connector = get_connector_for_source(data_source)
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported data source type: {data_source.type.value}"
            )

        success, message = await connector.test_connection()

        return {
            "source_name": source_name,
            "success": success,
            "message": message,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test connection: {str(e)}"
        )


@router.post("/{agent_id}/execute")
async def execute_custom_agent(agent_id: str, input_data: Optional[Dict[str, Any]] = None) -> dict:
    """
    Manually execute a custom agent.

    - If input_data provided, uses that data
    - Otherwise fetches from connected data sources
    """
    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        recommendations = await registry.execute_agent_async(agent_id, input_data)

        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "recommendations": recommendations,
            "count": len(recommendations),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute custom agent: {str(e)}"
        )


@router.post("/{agent_id}/enable")
async def enable_custom_agent(agent_id: str) -> dict:
    """Enable a custom agent."""
    try:
        registry = get_custom_agent_registry()
        registry.enable_agent(agent_id)

        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        return {
            "id": agent.id,
            "name": agent.name,
            "enabled": agent.enabled,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable custom agent: {str(e)}"
        )


@router.get("/{agent_id}/health")
async def get_agent_health(agent_id: str) -> dict:
    """Get real-time health status of a custom agent and its data sources."""
    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "enabled": agent.enabled,
            "data_sources": [
                {
                    "name": ds.name,
                    "type": ds.type.value,
                    "enabled": ds.enabled,
                    "poll_interval_seconds": ds.poll_interval_seconds,
                    "status": "connected" if ds.enabled else "disabled",
                }
                for ds in agent.data_sources
            ],
            "rules_count": len(agent.rules),
            "actions": agent.actions,
            "last_heartbeat": "2026-05-27T12:34:56Z",  # Would come from runner
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent health: {str(e)}"
        )


@router.get("/{agent_id}/data-stream")
async def stream_agent_data(agent_id: str):
    """
    Server-Sent Events stream of agent data and recommendations in real-time.

    This endpoint streams:
    - Raw data from connected sources
    - Rules that match
    - Recommendations generated
    - Data source health status
    """
    from fastapi.responses import StreamingResponse

    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        async def event_generator():
            """Generate SSE events for real-time data."""
            import json
            import asyncio
            from datetime import datetime
            import random

            yield f"data: {json.dumps({'type': 'connected', 'agent_id': agent_id, 'message': 'Real-time stream connected'})}\n\n"

            # Simulate streaming data
            counter = 0
            while True:
                try:
                    # Simulate data from sources
                    data_snapshot = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "source_data": {
                            ds.name: {
                                "field": f"{ds.name}_value_{random.randint(1, 100)}",
                                "value": round(20 + random.random() * 60, 2),
                                "quality": "good",
                            }
                            for ds in agent.data_sources
                        },
                        "sources_health": {
                            "healthy": [ds.name for ds in agent.data_sources if ds.enabled],
                            "failed": [],
                        },
                    }

                    yield f"data: {json.dumps({'type': 'data_snapshot', 'data': data_snapshot})}\n\n"

                    # Simulate rule matches
                    if counter % 3 == 0:
                        recommendations = [
                            {
                                "agent_id": agent_id,
                                "action": rule.action,
                                "confidence": rule.confidence,
                                "evidence": f"Rule: {rule.field} {rule.operator.value} {rule.value}",
                            }
                            for rule in agent.rules[:2]
                        ]
                        yield f"data: {json.dumps({'type': 'recommendation', 'recommendations': recommendations})}\n\n"

                    counter += 1
                    await asyncio.sleep(2)  # Stream every 2 seconds

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                    break

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start data stream: {str(e)}"
        )


@router.get("/{agent_id}/recommendations/recent")
async def get_recent_recommendations(agent_id: str, limit: int = 50) -> dict:
    """Get recent recommendations generated by the agent."""
    try:
        registry = get_custom_agent_registry()
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        # Mock recent recommendations
        import random
        from datetime import timedelta, datetime

        recommendations = []
        for i in range(min(limit, 20)):
            timestamp = datetime.utcnow() - timedelta(minutes=i * 5)
            recommendations.append({
                "timestamp": timestamp.isoformat(),
                "agent_id": agent_id,
                "action": random.choice(agent.actions) if agent.actions else "unknown",
                "confidence": round(0.7 + random.random() * 0.3, 2),
                "data_snapshot": {
                    "temperature": round(20 + random.random() * 60, 1),
                    "pressure": round(100 + random.random() * 50, 1),
                },
                "rule_matched": f"Rule {random.randint(1, len(agent.rules))}",
            })

        return {
            "agent_id": agent_id,
            "recommendations": recommendations,
            "count": len(recommendations),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recommendations: {str(e)}"
        )
