# Custom AI Agent Framework - User Guide

## Overview

The Custom AI Agent Framework allows manufacturing teams to create intelligent agents without writing code. Users can:

1. **Connect to data sources** - SCADA systems, Manufacturing Execution Systems (CMS), IoT sensors, REST APIs
2. **Define decision rules** - if-then logic for automated decision-making
3. **Integrate seamlessly** - Custom agents run alongside built-in agents in the orchestration pipeline
4. **Monitor & test** - Test connections and manually execute agents

---

## Quick Start

### Step 1: Navigate to Custom Agents Builder

Go to: **http://localhost:3000/custom-agents**

### Step 2: Create a New Agent

Click **"+ Create Agent"** button

### Step 3: Fill in Agent Details

**Basic Information:**
- **Agent Name**: e.g., "Thermal Management Agent"
- **Description**: What this agent does
- **Domain**: The problem domain (thermal, vibration, pressure, etc.)

### Step 4: Configure Data Sources

Connect to manufacturing systems:

#### SCADA Systems
- **Source Type**: SCADA (Modbus/OPC-UA)
- **Config**:
  - `host`: SCADA server address
  - `port`: Modbus port (default: 502) or OPC-UA port (default: 4840)
  - `timeout`: Connection timeout in seconds

**Example SCADA Query:**
```
temperature_sensor,pressure_gauge,register:100-110
```

#### Manufacturing Execution Systems (CMS)
- **Source Type**: CMS
- **Config**:
  - `host`: CMS server address
  - `port`: REST API port
  - `username`: CMS API credentials
  - `password`: CMS API credentials

**Example CMS Query:**
```
orders
work_orders
equipment_status
```

#### IoT Sensors
- **Source Type**: IoT
- **Config**:
  - `broker_host`: MQTT broker address
  - `broker_port`: MQTT port (default: 1883)
  - `protocol`: mqtt or coap

**Example IoT Query:**
```
sensors/+/temperature,sensors/+/humidity,sensors/+/pressure
```

#### REST APIs
- **Source Type**: REST API
- **Config**:
  - `base_url`: API base URL
  - `timeout`: Request timeout

**Example REST Query:**
```
/api/production/status
/api/equipment/health
/api/inventory
```

### Step 5: Define Decision Rules

Add if-then rules:

**Rule Format:**
- **Field**: Data field to evaluate (e.g., `temperature`, `vibration_level`)
- **Operator**: ==, !=, >, <, >=, <=, in, not_in, contains, matches_regex
- **Value**: Threshold value (e.g., `80`, `high`)
- **Action**: Recommended action (e.g., `activate_cooling`, `schedule_maintenance`)

**Example Rules:**

| If Field | Operator | Value | Then Action | Priority |
|----------|----------|-------|-------------|----------|
| temperature | > | 80 | activate_cooling | 1 |
| vibration_level | >= | 5.5 | schedule_maintenance | 2 |
| pressure | > | 100 | reduce_load | 1 |
| error_code | == | 42 | request_safety_review | 1 |

### Step 6: Test Data Source Connections

Before running the agent, test connections:

1. Go to agent detail page
2. Click "Test Connection" for each data source
3. Verify the connection is working

### Step 7: Execute Agent

Option A: **Automatic** - Agent runs automatically when an event matches
- Integrated into orchestration pipeline alongside built-in agents
- Receives event data and connected source data

Option B: **Manual** - Execute for testing
1. Click "Execute" on agent detail page
2. Optional: Provide test data
3. View recommendations generated

---

## Data Connector Examples

### Example 1: Temperature Monitoring Agent

```json
{
  "name": "Thermal Alert Agent",
  "description": "Monitor temperature and recommend cooling actions",
  "domain": "thermal",
  "data_sources": [
    {
      "name": "plant_scada",
      "type": "SCADA",
      "config": {
        "host": "scada.plant.local",
        "port": 502
      },
      "query": "furnace_temp,chamber_temp,coolant_temp"
    }
  ],
  "rules": [
    {
      "field": "furnace_temp",
      "operator": ">",
      "value": 280,
      "action": "activate_emergency_cooling",
      "confidence": 0.95,
      "priority": 1
    },
    {
      "field": "chamber_temp",
      "operator": ">=",
      "value": 250,
      "action": "increase_airflow",
      "confidence": 0.85,
      "priority": 2
    }
  ],
  "actions": ["activate_emergency_cooling", "increase_airflow", "alert_operator"]
}
```

### Example 2: Production Schedule Agent

```json
{
  "name": "Production CMS Agent",
  "description": "Monitor production orders and recommend schedule adjustments",
  "domain": "production",
  "data_sources": [
    {
      "name": "production_cms",
      "type": "CMS",
      "config": {
        "host": "cms.plant.local",
        "port": 8080,
        "username": "api_user"
      },
      "query": "orders"
    }
  ],
  "rules": [
    {
      "field": "status",
      "operator": "==",
      "value": "at_risk",
      "action": "escalate_to_supervisor",
      "confidence": 0.9,
      "priority": 1
    }
  ],
  "actions": ["escalate_to_supervisor", "adjust_schedule", "notify_team"]
}
```

### Example 3: IoT Sensor Network Agent

```json
{
  "name": "Vibration Monitor Agent",
  "description": "Monitor vibration sensors and predict maintenance needs",
  "domain": "vibration",
  "data_sources": [
    {
      "name": "machine_iot",
      "type": "IoT",
      "config": {
        "broker_host": "mqtt.plant.local",
        "broker_port": 1883,
        "protocol": "mqtt"
      },
      "query": "machines/+/vibration,machines/+/temperature"
    }
  ],
  "rules": [
    {
      "field": "vibration",
      "operator": ">",
      "value": 5.5,
      "action": "schedule_bearing_replacement",
      "confidence": 0.88,
      "priority": 1
    }
  ],
  "actions": ["schedule_bearing_replacement", "increase_monitoring", "alert_maintenance"]
}
```

---

## How Custom Agents Integrate

When an event occurs:

```
Event (e.g., high temperature alert)
    ↓
Orchestrator routes to agents:
  ├→ SafetyAgent (built-in)
  ├→ MaintenanceAgent (built-in)
  ├→ CustomAgent_ThermalManagement (your custom agent)
    ↓
  All agents provide recommendations
    ↓
  Policy Engine checks each recommendation
    ↓
  Decision Twin simulates impacts
    ↓
  Red-Team challenges risky actions
    ↓
  Approval Gate routes to appropriate human
    ↓
  Decision recorded in audit trail
```

Custom agents contribute to the full orchestration pipeline - they're first-class citizens, not afterthoughts.

---

## API Reference

### Create Custom Agent
```bash
POST /api/custom-agents/create
Content-Type: application/json

{
  "name": "Agent Name",
  "description": "...",
  "domain": "...",
  "data_sources": [...],
  "rules": [...],
  "actions": [...]
}
```

### List Custom Agents
```bash
GET /api/custom-agents/list
```

### Get Agent Details
```bash
GET /api/custom-agents/{agent_id}
```

### Delete Agent
```bash
DELETE /api/custom-agents/{agent_id}
```

### Test Data Source Connection
```bash
POST /api/custom-agents/{agent_id}/test-connection?source_name=plant_scada
```

### Execute Agent
```bash
POST /api/custom-agents/{agent_id}/execute
Content-Type: application/json

{
  "temperature": 85,
  "pressure": 110
}
```

### Enable Agent
```bash
POST /api/custom-agents/{agent_id}/enable
```

### Disable Agent
```bash
POST /api/custom-agents/{agent_id}/disable
```

---

## Troubleshooting

### Connection Fails
- **Check**: Network connectivity to data source
- **Check**: Firewall rules allow connection
- **Check**: Credentials are correct
- **Try**: Test connection button in UI first

### Rules Not Triggering
- **Check**: Field names match data source exactly
- **Check**: Operator is correct (case-sensitive)
- **Check**: Value type matches field (string vs number)
- **Debug**: Execute agent with test data to see which rules match

### Agent Not Running
- **Check**: Agent is enabled (toggle in UI)
- **Check**: Data sources are connected
- **Check**: At least one rule is defined
- **Check**: Actions list is not empty

---

## Best Practices

1. **Start Simple** - Begin with 1-2 data sources and 2-3 rules
2. **Test First** - Always test data connections before deployment
3. **Clear Naming** - Use descriptive names for fields, actions, agents
4. **Gradual Rollout** - Test custom agent on single factory first
5. **Monitor Results** - Review audit logs to see how agent recommendations perform
6. **Iterate** - Refine rules based on production feedback

---

## Next Steps

- [x] Build custom agent framework
- [ ] Deploy to staging environment
- [ ] Create 3-5 domain-specific agents
- [ ] Integrate with real manufacturing systems
- [ ] Train operations team on builder UI
- [ ] Monitor agent performance metrics
