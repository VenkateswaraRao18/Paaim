'use client';

import { useCallback, useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

/**
 * API Client Hooks for PAAIM Backend
 * Handles all communication with FastAPI backend
 */

// Types for API responses
export interface Event {
  event_type: string;
  signal_name: string;
  signal_value: number;
  confidence: number;
  factory_id: string;
  machine_id?: string;
  context: Record<string, unknown>;
  timestamp: string;
}

export interface Decision {
  decision_id: string;
  event_id: string;
  factory_id: string;
  timestamp: string;
  event: Event;
  orchestration_result: {
    selected_action: string;
    approval_required: boolean;
    approval_route: string;
  };
  analysis_layers: {
    agent_analyses: unknown[];
    policy_evaluations: Record<string, unknown>;
    impact_estimates: Record<string, unknown>;
    red_team_reviews: Record<string, unknown>;
  };
  evidence_pack: unknown;
}

export interface Scenario {
  name: string;
  difficulty: 'easy' | 'medium' | 'hard';
  description: string;
  event_count: number;
}

// WebSocket streaming types
export type PipelineEventType =
  | 'orchestration_started'
  | 'orchestration_completed'
  | 'orchestration_error'
  | 'event_received'
  | 'agents_routing'
  | 'agents_analyzing'
  | 'agents_complete'
  | 'policy_checking'
  | 'policy_complete'
  | 'twin_simulating'
  | 'twin_complete'
  | 'red_team_challenging'
  | 'red_team_complete'
  | 'approval_routing'
  | 'approval_complete'
  | 'action_selected'
  | 'action_approved'
  | 'action_rejected';

export interface PipelineEvent {
  event_type: PipelineEventType;
  decision_id: string;
  layer: string;
  data: Record<string, unknown>;
  timestamp: string;
}


export function useEventsList(factoryId: string, limit = 100) {
  return useQuery({
    queryKey: ['events', factoryId, limit],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/events/list?factory_id=${factoryId}&limit=${limit}`);
      if (!res.ok) throw new Error('Failed to fetch events');
      return res.json();
    },
    refetchInterval: 5000, // Refresh every 5 seconds for near-real-time
  });
}

// ===== Scenario Endpoints =====

export function useScenarioCatalog() {
  return useQuery({
    queryKey: ['scenarios', 'catalog'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/events/scenarios/catalog`);
      if (!res.ok) throw new Error('Failed to fetch scenarios');
      const data = await res.json();
      return Object.entries(data).map(([key, info]: [string, any]) => ({
        id: key,
        ...info,
      }));
    },
  });
}

export function useGenerateScenario() {
  return useMutation({
    mutationFn: async (scenarioName: string) => {
      const res = await fetch(`${API_BASE}/events/scenarios/generate/${scenarioName}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to generate scenario');
      return res.json();
    },
  });
}

// ===== Orchestration Endpoints =====

export function useOrchestratEvent() {
  return useMutation({
    mutationFn: async (event: Event) => {
      const res = await fetch(`${API_BASE}/events/orchestrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(event),
      });
      if (!res.ok) throw new Error('Failed to orchestrate event');
      return res.json() as Promise<Decision>;
    },
  });
}

export interface ScenarioOrchestrationResult {
  scenario: string;
  event_count: number;
  decisions: Decision[];
}

export function useOrchestratScenario() {
  return useMutation({
    mutationFn: async (scenarioName: string): Promise<ScenarioOrchestrationResult> => {
      const res = await fetch(`${API_BASE}/events/orchestrate/scenario/${scenarioName}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to orchestrate scenario');
      return res.json();
    },
  });
}

// ===== Individual Decision Retrieval =====

export function useDecision(decisionId: string | null) {
  return useQuery({
    queryKey: ['decision', decisionId],
    queryFn: async () => {
      if (!decisionId) return null;
      const res = await fetch(`${API_BASE}/events/decisions/${decisionId}`);
      if (!res.ok) return null;
      return res.json();
    },
    enabled: !!decisionId,
    staleTime: 10_000,
  });
}

// ===== Audit Log Endpoints =====

export interface AuditEntry {
  id: string;
  event_type: string;
  actor: string;
  action: string;
  details: Record<string, unknown>;
  timestamp: string;
  decision_id: string;
}

export function useAuditLog(
  factoryId: string,
  filters?: { event_type?: string; start_date?: string; end_date?: string; limit?: number; offset?: number },
) {
  return useQuery({
    queryKey: ['audit', factoryId, filters],
    queryFn: async () => {
      const params = new URLSearchParams({ factory_id: factoryId });
      if (filters?.event_type) params.set('event_type', filters.event_type);
      if (filters?.start_date) params.set('start_date', filters.start_date);
      if (filters?.end_date) params.set('end_date', filters.end_date);
      if (filters?.limit != null) params.set('limit', String(filters.limit));
      if (filters?.offset != null) params.set('offset', String(filters.offset));
      const res = await fetch(`${API_BASE}/events/audit/search?${params}`);
      if (!res.ok) throw new Error('Failed to fetch audit logs');
      return res.json() as Promise<{ logs: AuditEntry[]; total: number; factory_id: string }>;
    },
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}

export type PriorityLevel = 'L1' | 'L2' | 'L3';

export interface IncidentPriority {
  level: PriorityLevel;
  score: number;
  rationale: string;
  drivers: string[];
  factors: {
    exposure_usd: number;
    hours_to_due: number | null;
    safety: number;
    confidence: number;
    past_due: boolean;
    order_id: string | null;
    customer_name: string | null;
  };
}

export interface DecisionListItem {
  decision_id: string;
  event_id: string;
  factory_id: string;
  status: 'recommended' | 'approved' | 'rejected' | 'executed';
  recommended_action: {
    selected_action: string;
    approval_required: boolean;
    approval_route: string;
    confidence?: number;
    risk_level?: string;
  };
  approved_by: string | null;
  approval_timestamp: string | null;
  created_at: string;
  priority?: IncidentPriority;
}

export function useDecisionsList(factoryId: string, limit = 100, status?: string) {
  return useQuery({
    queryKey: ['decisions', 'list', factoryId, limit, status],
    queryFn: async () => {
      const params = new URLSearchParams({ factory_id: factoryId, limit: String(limit) });
      if (status) params.set('status', status);
      const res = await fetch(`${API_BASE}/events/decisions?${params}`);
      if (!res.ok) throw new Error('Failed to fetch decisions');
      return res.json() as Promise<{ decisions: DecisionListItem[]; count: number }>;
    },
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useApproveDecision() {
  return useMutation({
    mutationFn: async ({
      decisionId,
      action,
      approvedBy,
      notes,
    }: {
      decisionId: string;
      action: 'approve' | 'reject';
      approvedBy?: string;
      notes?: string;
    }) => {
      const res = await fetch(`${API_BASE}/events/decisions/${decisionId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, approved_by: approvedBy ?? 'operator', notes }),
      });
      if (!res.ok) throw new Error('Failed to submit approval');
      return res.json();
    },
  });
}

// ===== Agent Endpoints =====

export function useAgentsList() {
  return useQuery({
    queryKey: ['agents', 'list'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/agents/list`);
      if (!res.ok) throw new Error('Failed to fetch agents');
      return res.json();
    },
  });
}

// ===== Real-Time Event Stream Hook =====

export function useEventStream(factoryId: string) {
  const [events, setEvents] = useState<Event[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Note: This would connect to a WebSocket or Server-Sent Events endpoint
    // For MVP, simulating with polling
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/events/list?factory_id=${factoryId}&limit=10`);
        if (res.ok) {
          const data = await res.json();
          setEvents(data.events || []);
          setIsConnected(true);
          setError(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Connection error');
        setIsConnected(false);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [factoryId]);

  return { events, isConnected, error };
}

// ===== Real-Time Decision Stream =====

export function useDecisionStream(factoryId: string) {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  // Subscribe to new decisions via polling
  // In production, use WebSocket: new WebSocket(`ws://localhost:8000/ws/decisions/${factoryId}`)

  return { decisions, isConnected };
}

// ===== WebSocket Pipeline Stream =====

export function usePipelineStream(
  decisionId: string,
  onEvent?: (event: PipelineEvent) => void,
) {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!decisionId) return;

    // Derive WebSocket URL from the API base — handles any host/port combo
    const wsUrl = API_BASE
      .replace(/^http:/, 'ws:')
      .replace(/^https:/, 'wss:') + `/events/ws/orchestrate/${decisionId}`;

    let ws: WebSocket | null = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        let keepalive: ReturnType<typeof setInterval> | null = null;

        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
          // Send a ping every 20s to keep the connection alive
          keepalive = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) ws.send('ping');
          }, 20_000);
        };

        ws.onmessage = (event) => {
          if (event.data === 'pong') return;
          try {
            const data: PipelineEvent = JSON.parse(event.data);
            setEvents((prev) => [...prev, data]);
            onEvent?.(data);
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };

        ws.onerror = (err) => {
          console.error('WebSocket error:', err);
          setError('Connection error');
          setIsConnected(false);
        };

        ws.onclose = () => {
          if (keepalive) clearInterval(keepalive);
          setIsConnected(false);
        };
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect');
        setIsConnected(false);
      }
    };

    connect();

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [decisionId, onEvent]);

  const clear = useCallback(() => {
    setEvents([]);
  }, []);

  return { events, isConnected, error, clear };
}

// ===== Custom Agents Endpoints =====

export function useCustomAgents() {
  return useQuery({
    queryKey: ['custom-agents', 'list'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/custom-agents/list`);
      if (!res.ok) throw new Error('Failed to fetch custom agents');
      return res.json();
    },
  });
}

export function useCustomAgentMutation() {
  return useMutation({
    mutationFn: async (agentData: {
      name: string;
      description: string;
      domain: string;
      watch_signals?: string[];
      scope?: { type: string; machines?: string[]; zone?: string };
      data_sources?: Array<{
        name: string;
        type: string;
        config: Record<string, unknown>;
      }>;
      rules: Array<{
        field: string;
        operator: string;
        value: unknown;
        action: string;
      }>;
      actions: string[];
    }) => {
      const res = await fetch(`${API_BASE}/custom-agents/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agentData),
      });
      if (!res.ok) throw new Error('Failed to create custom agent');
      return res.json();
    },
  });
}

export function useTestConnectionBeforeCreate() {
  return useMutation({
    mutationFn: async (payload: { name: string; type: string; config: Record<string, string> }) => {
      const res = await fetch(`${API_BASE}/custom-agents/test-connection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Connection test failed');
      return res.json() as Promise<{ success: boolean; message: string; type: string }>;
    },
  });
}

export function useTestDataSourceConnection() {
  return useMutation({
    mutationFn: async ({
      agentId,
      sourceName,
    }: {
      agentId: string;
      sourceName: string;
    }) => {
      const res = await fetch(
        `${API_BASE}/custom-agents/${agentId}/test-connection?source_name=${sourceName}`,
        {
          method: 'POST',
        }
      );
      if (!res.ok) throw new Error('Failed to test connection');
      return res.json();
    },
  });
}

export function useExecuteCustomAgent() {
  return useMutation({
    mutationFn: async ({
      agentId,
      inputData,
    }: {
      agentId: string;
      inputData?: Record<string, unknown>;
    }) => {
      const res = await fetch(`${API_BASE}/custom-agents/${agentId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputData || {}),
      });
      if (!res.ok) throw new Error('Failed to execute custom agent');
      return res.json();
    },
  });
}

// ─── Analytics hooks ─────────────────────────────────────────────

export interface AnalyticsSummary {
  total_events: number;
  total_decisions: number;
  approval_rate: number;
  auto_approved: number;
  human_approved: number;
  rejected: number;
  avg_latency_ms: number;
  estimated_cost_savings_usd: number;
  uptime_hours: number;
  days: number;
  is_demo: boolean;
}

export interface TimelinePoint {
  date: string;
  safety: number;
  quality: number;
  maintenance: number;
  production: number;
  energy: number;
  total: number;
}

export interface DistributionItem {
  event_type: string;
  count: number;
  percentage: number;
}

export interface ActionItem {
  action: string;
  count: number;
  avg_confidence: number;
}

export interface AgentPerf {
  agent: string;
  recommendations: number;
  auto_approved_rate: number;
  accuracy_score: number;
}

export interface LatencyLayer {
  layer: string;
  avg_ms: number;
}

export function useAnalyticsSummary(factoryId = 'factory_001', days = 30) {
  return useQuery({
    queryKey: ['analytics', 'summary', factoryId, days],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/analytics/summary?factory_id=${factoryId}&days=${days}`
      );
      if (!res.ok) throw new Error('Failed to fetch analytics summary');
      return res.json() as Promise<AnalyticsSummary>;
    },
    staleTime: 30_000,
  });
}

export function useAnalyticsTimeline(factoryId = 'factory_001', days = 14) {
  return useQuery({
    queryKey: ['analytics', 'timeline', factoryId, days],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/analytics/timeline?factory_id=${factoryId}&days=${days}`
      );
      if (!res.ok) throw new Error('Failed to fetch analytics timeline');
      const data = await res.json();
      return data as { timeline: TimelinePoint[]; is_demo: boolean };
    },
    staleTime: 30_000,
  });
}

export function useAnalyticsDistribution(factoryId = 'factory_001', days = 30) {
  return useQuery({
    queryKey: ['analytics', 'distribution', factoryId, days],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/analytics/distribution?factory_id=${factoryId}&days=${days}`
      );
      if (!res.ok) throw new Error('Failed to fetch event distribution');
      const data = await res.json();
      return data as { distribution: DistributionItem[]; is_demo: boolean };
    },
    staleTime: 30_000,
  });
}

export function useAnalyticsActions(factoryId = 'factory_001', days = 30) {
  return useQuery({
    queryKey: ['analytics', 'actions', factoryId, days],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/analytics/actions?factory_id=${factoryId}&days=${days}`
      );
      if (!res.ok) throw new Error('Failed to fetch top actions');
      const data = await res.json();
      return data as { actions: ActionItem[]; is_demo: boolean };
    },
    staleTime: 30_000,
  });
}

export function useAnalyticsAgents() {
  return useQuery({
    queryKey: ['analytics', 'agents'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/analytics/agents`);
      if (!res.ok) throw new Error('Failed to fetch agent performance');
      const data = await res.json();
      return data as { agents: AgentPerf[]; is_demo: boolean };
    },
    staleTime: 60_000,
  });
}

export function useAnalyticsLatency() {
  return useQuery({
    queryKey: ['analytics', 'latency'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/analytics/latency`);
      if (!res.ok) throw new Error('Failed to fetch latency breakdown');
      const data = await res.json();
      return data as { latency: LatencyLayer[]; is_demo: boolean };
    },
    staleTime: 60_000,
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ['analytics', 'health'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/analytics/health`);
      if (!res.ok) throw new Error('Failed to fetch system health');
      return res.json();
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

// ─── Knowledge Model hooks ────────────────────────────────────────

export interface KpiDefinition {
  id: string;
  name: string;
  description: string;
  unit: string;
  target: number;
  warning_threshold: number;
  critical_threshold: number;
  higher_is_better: boolean;
  category: string;
}

export interface KpiSnapshot {
  kpi_id: string;
  name: string;
  value: number;
  unit: string;
  status: 'on_target' | 'at_risk' | 'critical';
  target: number;
  factory_id: string;
}

export function useFactoryModel(factoryId = 'factory_001') {
  return useQuery({
    queryKey: ['knowledge', 'factory', factoryId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/knowledge/factory/${factoryId}`);
      if (!res.ok) throw new Error('Failed to fetch factory model');
      return res.json();
    },
    staleTime: 60_000,
  });
}

export function useKpiCatalogue() {
  return useQuery({
    queryKey: ['knowledge', 'kpis'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/knowledge/kpis`);
      if (!res.ok) throw new Error('Failed to fetch KPI catalogue');
      return res.json() as Promise<{ kpis: KpiDefinition[]; total: number; categories: string[] }>;
    },
    staleTime: 60_000,
  });
}

export function useKpiSnapshot(factoryId = 'factory_001') {
  return useQuery({
    queryKey: ['knowledge', 'kpi-snapshot', factoryId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/knowledge/kpis/snapshot/${factoryId}`);
      if (!res.ok) throw new Error('Failed to fetch KPI snapshot');
      return res.json() as Promise<{ factory_id: string; snapshot: KpiSnapshot[]; evaluated_at: string }>;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

// ── Factory Context Layer hooks ────────────────────────────────────────────────

export interface MachineAsset {
  id: string;
  name: string;
  asset_type: string;
  zone_id: string;
  criticality: string;
  status: string;
  hourly_production_value_usd: number;
  last_maintenance_date: string | null;
  next_scheduled_maintenance: string | null;
  mtbf_hours: number;
  mttr_hours: number;
}

export interface WorkOrder {
  id: string;
  machine_id: string;
  product_name: string;
  product_id: string;
  customer_order_id: string | null;
  customer_name: string | null;
  quantity_planned: number;
  quantity_completed: number;
  quantity_scrapped: number;
  completion_pct: number;
  status: string;
  priority: string;
  scheduled_end: string | null;
}

export interface CustomerOrder {
  id: string;
  customer_name: string;
  product_id: string;
  quantity: number;
  quantity_delivered: number;
  promised_delivery: string;
  hours_until_delivery: number;
  status: string;
  priority: string;
  late_delivery_penalty_usd: number;
  contract_value_usd: number;
  is_at_risk: boolean;
}

export interface NCRRecord {
  id: string;
  machine_id: string;
  product_id: string;
  defect_type: string;
  severity: string;
  quantity_affected: number;
  disposition: string;
  root_cause: string;
  status: string;
  opened_at: string;
  recurrence_count: number;
  cost_impact_usd: number;
}

export interface ContextSummary {
  factory_id: string;
  machines: { total: number; running: number; fault: number };
  work_orders: { active: number; urgent: number };
  customer_orders: { open: number; at_risk: number; total_penalty_exposure_usd: number };
  quality: { open_ncrs: number; critical_ncrs: number };
}

export function useContextSummary(factoryId = 'factory_001') {
  return useQuery({
    queryKey: ['context', 'summary', factoryId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/knowledge/context/${factoryId}/summary`);
      if (!res.ok) return null;
      return res.json() as Promise<ContextSummary>;
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useMachineAssets(factoryId = 'factory_001') {
  return useQuery({
    queryKey: ['context', 'machines', factoryId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/knowledge/context/${factoryId}/machines`);
      if (!res.ok) return { machines: [], count: 0 };
      return res.json() as Promise<{ machines: MachineAsset[]; count: number }>;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useWorkOrders(factoryId = 'factory_001', status?: string) {
  return useQuery({
    queryKey: ['context', 'work-orders', factoryId, status],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      const res = await fetch(`${API_BASE}/knowledge/context/${factoryId}/work-orders?${params}`);
      if (!res.ok) return { work_orders: [], count: 0 };
      return res.json() as Promise<{ work_orders: WorkOrder[]; count: number }>;
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useCustomerOrders(factoryId = 'factory_001', status?: string) {
  return useQuery({
    queryKey: ['context', 'customer-orders', factoryId, status],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      const res = await fetch(`${API_BASE}/knowledge/context/${factoryId}/customer-orders?${params}`);
      if (!res.ok) return { customer_orders: [], count: 0 };
      return res.json() as Promise<{ customer_orders: CustomerOrder[]; count: number }>;
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useNCRRecords(factoryId = 'factory_001', status = 'open') {
  return useQuery({
    queryKey: ['context', 'ncrs', factoryId, status],
    queryFn: async () => {
      const params = new URLSearchParams({ status });
      const res = await fetch(`${API_BASE}/knowledge/context/${factoryId}/ncrs?${params}`);
      if (!res.ok) return { ncrs: [], count: 0 };
      return res.json() as Promise<{ ncrs: NCRRecord[]; count: number }>;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

