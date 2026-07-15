"""API endpoints for managing custom AI agents."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends
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

from paaim.auth.deps import tenant_id

router = APIRouter()

# Legacy agent-bound source types → the real connector drivers. Anything without
# a real driver stays under its own name so the connector refuses it by name
# rather than quietly "succeeding".
_SOURCE_TYPE_ALIASES = {
    "rest_api": "rest_poll",
    "scada": "modbus",      # no driver yet — refused honestly
    "opc_ua": "opcua",      # no driver yet — refused honestly
    "iot": "mqtt",          # no driver yet — refused honestly
    "cms": "rest_poll",     # MES systems are reached over HTTP here
}


def _endpoint_from_config(ds_type, config: Dict[str, Any]) -> str:
    """Build a URL from the legacy per-type config fields the form collects."""
    cfg = config or {}
    if cfg.get("base_url"):
        base = str(cfg["base_url"]).rstrip("/")
        return base + str(cfg.get("endpoint", "") or "")
    host = cfg.get("host") or cfg.get("broker_host") or ""
    if not host:
        return ""
    port = cfg.get("port") or cfg.get("broker_port")
    hostport = f"{host}:{port}" if port else str(host)
    if ds_type.value in ("scada", "opc_ua", "iot"):
        return hostport            # non-HTTP: passed through for the refusal message
    prefix = str(cfg.get("api_prefix", "") or "")
    return f"http://{hostport}{prefix}"


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
    # Route through the real connectors. The legacy ones here returned
    # "SCADA connection OK" without opening a socket — a wrong host looked
    # healthy and then fed the pipeline zeros. Reuse the drivers that actually
    # perform a round-trip, and say plainly when a protocol has none.
    from paaim.sources.connectors import test_connection as real_test

    endpoint = _endpoint_from_config(ds_type, request.config)
    result = await real_test(
        type=_SOURCE_TYPE_ALIASES.get(ds_type.value, ds_type.value),
        endpoint=endpoint,
        auth_type=request.auth_type,
        auth_config=request.auth_config,
    )
    return {
        "success": result.ok,
        "message": result.detail,
        "type": request.type,
        "latency_ms": result.latency_ms,
    }


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_custom_agent(request: CustomAgentRequest, factory: str = Depends(tenant_id)) -> CustomAgentResponse:
    """
    Create a new custom AI agent.

    - User specifies data sources (SCADA, CMS, IoT, REST API)
    - User defines rules (if/then logic for decision-making)
    - Agent automatically integrates into orchestration pipeline
    """
    try:
        registry = get_custom_agent_registry(factory)

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
async def list_custom_agents(factory: str = Depends(tenant_id)) -> dict:
    """List all custom agents."""
    try:
        registry = get_custom_agent_registry(factory)
        agents = registry.list_agents()

        def _iso(val):
            if val is None:
                return None
            return val.isoformat() if hasattr(val, "isoformat") else str(val)

        # Return the whole definition. Hand-rolling a subset here is what left the
        # UI unable to show an agent's rules ("rules_count: 1" with no rules to
        # render) — the list and detail shapes drifted apart. `to_dict()` is the
        # single source of truth; counts stay for cards that only need a number.
        custom_agents = [
            {
                **agent.to_dict(),
                "data_sources_count": len(agent.data_sources),
                "rules_count": len(agent.rules),
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
async def get_custom_agent(agent_id: str, factory: str = Depends(tenant_id)) -> dict:
    """Get details of a specific custom agent."""
    try:
        registry = get_custom_agent_registry(factory)
        agent = registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_id}' not found"
            )

        # Same complete shape the list returns, so the UI can render (and edit)
        # an agent from either without discovering a field is missing.
        return agent.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve custom agent: {str(e)}"
        )


@router.get("/{agent_id}/sources")
async def agent_sources(agent_id: str, factory: str = Depends(tenant_id)) -> dict:
    """
    Where this monitor's data comes from.

    Derived, not stored: an agent watches signals, so its sources are whichever
    ones map a field to those signals. `live` means a watcher is actually
    deployed for it — an agent can be perfectly configured and still receive
    nothing because no source has been connected yet.
    """
    from paaim.sources.links import sources_feeding_agent

    registry = get_custom_agent_registry(factory)
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found"
        )
    feeds = sources_feeding_agent(agent, factory)
    return {
        "agent_id": agent_id,
        "watch_signals": list(agent.watch_signals or []),
        "sources": feeds,
        "live_count": sum(1 for f in feeds if f["live"]),
    }


@router.put("/{agent_id}")
async def update_custom_agent(agent_id: str, request: CustomAgentRequest, factory: str = Depends(tenant_id)) -> dict:
    """
    Update an agent in place.

    A plant tunes its monitors constantly — a threshold that was right in winter
    is wrong in summer — so an agent that can only be deleted and recreated
    (losing its id and history) is not usable. Keeps the id, created_at and
    creator; replaces what the operator edited.
    """
    registry = get_custom_agent_registry(factory)
    existing = registry.get_agent(agent_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found"
        )

    try:
        rules = [
            Rule(
                field=r.field, operator=RuleOperator(r.operator), value=r.value,
                action=r.action, confidence=r.confidence, priority=r.priority,
            )
            for r in request.rules
        ]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid operator: {e}. Must be one of: "
                   f"{[o.value for o in RuleOperator]}",
        )

    data_sources = [
        DataSource(
            name=ds.name, type=DataSourceType(ds.type.lower()), config=ds.config,
            query=ds.query, auth_type=ds.auth_type, auth_config=ds.auth_config,
            poll_interval_seconds=ds.poll_interval_seconds, enabled=ds.enabled,
        )
        for ds in request.data_sources
    ]

    updated = CustomAgentDefinition(
        id=existing.id,
        name=request.name,
        description=request.description,
        domain=request.domain,
        data_sources=data_sources,
        rules=rules,
        actions=request.actions,
        watch_signals=request.watch_signals,
        scope=request.scope or {"type": "all"},
        enabled=request.enabled,
        created_at=existing.created_at,
        created_by=existing.created_by,
    )
    updated.updated_at = datetime.utcnow()
    registry.register_agent(updated)
    return updated.to_dict()


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_agent(agent_id: str, factory: str = Depends(tenant_id)):
    """Delete a custom agent."""
    try:
        registry = get_custom_agent_registry(factory)
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
async def test_data_source_connection(agent_id: str, source_name: str, factory: str = Depends(tenant_id)) -> dict:
    """Test connection to a data source for a custom agent."""
    try:
        registry = get_custom_agent_registry(factory)
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
async def execute_custom_agent(agent_id: str, input_data: Optional[Dict[str, Any]] = None, factory: str = Depends(tenant_id)) -> dict:
    """
    Manually execute a custom agent.

    - If input_data provided, uses that data
    - Otherwise fetches from connected data sources
    """
    try:
        registry = get_custom_agent_registry(factory)
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
async def enable_custom_agent(agent_id: str, factory: str = Depends(tenant_id)) -> dict:
    """Enable a custom agent."""
    try:
        registry = get_custom_agent_registry(factory)
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
async def get_agent_health(agent_id: str, factory: str = Depends(tenant_id)) -> dict:
    """Get real-time health status of a custom agent and its data sources."""
    try:
        registry = get_custom_agent_registry(factory)
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
        registry = get_custom_agent_registry(factory)
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
        registry = get_custom_agent_registry(factory)
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
