'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useEventsList,
  useScenarioCatalog,
  useOrchestratScenario,
} from '@/lib/api-client';
import {
  useDashboardStore,
  useSelectedFactory,
  useActiveTab,
  useFilters,
} from '@/lib/store';
import {
  IncidentCard,
  IncidentCardSkeleton,
  DecisionFlow,
  ImpactEstimate,
  ApprovalWorkflow,
} from '@/components/DashboardComponents';

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const selectedFactory = useSelectedFactory();
  const activeTab = useActiveTab();
  const filters = useFilters();
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);
  const addDecision = useDashboardStore((s) => s.addDecision);
  const decisions = useDashboardStore((s) => s.decisions);
  const activeDecision = useDashboardStore((s) => s.activeDecision);
  const setActiveDecision = useDashboardStore((s) => s.setActiveDecision);

  const { data: eventsList, isLoading: eventsLoading } = useEventsList(selectedFactory);
  const { data: scenarios, isLoading: scenariosLoading } = useScenarioCatalog();
  const orchestrateScenario = useOrchestratScenario();

  const [runningScenarioId, setRunningScenarioId] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const incidents = eventsList?.events || [];
  const filteredIncidents = incidents.filter((event: any) => {
    if (filters.eventType && event.event_type !== filters.eventType) return false;
    return true;
  });

  const handleGenerateScenario = async (scenarioId: string) => {
    setRunningScenarioId(scenarioId);
    setRunError(null);
    try {
      const result = await orchestrateScenario.mutateAsync(scenarioId);
      // Push each returned decision into the store (oldest first so newest stays on top).
      [...result.decisions].reverse().forEach((d) => addDecision(d as any));
      // Refresh the events list immediately rather than waiting for the next 5s poll.
      queryClient.invalidateQueries({ queryKey: ['events', selectedFactory] });
      setActiveTab('decisions');
    } catch (err) {
      console.error('Failed to orchestrate scenario:', err);
      setRunError(err instanceof Error ? err.message : 'Failed to run scenario');
    } finally {
      setRunningScenarioId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">PAAIM Dashboard</h1>
          <p className="text-gray-600 mt-1">
            Manufacturing Decision Orchestration System
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex gap-4 mb-8 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('incidents')}
            className={`py-2 px-4 font-medium ${
              activeTab === 'incidents'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Live Incidents
          </button>
          <button
            onClick={() => setActiveTab('decisions')}
            className={`py-2 px-4 font-medium ${
              activeTab === 'decisions'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Decisions
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`py-2 px-4 font-medium ${
              activeTab === 'audit'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Audit Trail
          </button>
        </div>

        {activeTab === 'incidents' && (
          <div className="space-y-8">
            {/* Demo Scenarios */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Demo Scenarios
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                Run realistic manufacturing incident scenarios through the orchestration pipeline
              </p>

              {runError && (
                <div className="mb-4 bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg p-3">
                  {runError}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {scenariosLoading ? (
                  [...Array(3)].map((_, i) => (
                    <div
                      key={i}
                      className="bg-gray-50 border border-gray-200 rounded-lg p-4 animate-pulse"
                    >
                      <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                      <div className="h-3 bg-gray-200 rounded w-full mb-4"></div>
                      <div className="h-8 bg-gray-200 rounded"></div>
                    </div>
                  ))
                ) : (
                  scenarios?.slice(0, 3).map((scenario: any) => (
                    <div
                      key={scenario.id}
                      className="bg-gray-50 border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                    >
                      <h3 className="font-semibold text-gray-900 mb-2">
                        {scenario.name}
                      </h3>
                      <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                        {scenario.description}
                      </p>
                      <div className="flex items-center justify-between mb-4">
                        <span className="text-xs font-medium bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded">
                          {scenario.difficulty.toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-600">
                          {scenario.event_count} events
                        </span>
                      </div>
                      <button
                        onClick={() => handleGenerateScenario(scenario.id)}
                        disabled={orchestrateScenario.isPending}
                        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white text-sm font-medium py-2 px-4 rounded transition-colors"
                      >
                        {runningScenarioId === scenario.id
                          ? 'Running...'
                          : 'Run Scenario'}
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Live Incidents */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Live Incidents
                </h2>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm text-gray-600">
                    {filteredIncidents.length} active
                  </span>
                </div>
              </div>

              {eventsLoading ? (
                <div className="grid gap-4">
                  {[...Array(3)].map((_, i) => (
                    <IncidentCardSkeleton key={i} />
                  ))}
                </div>
              ) : filteredIncidents.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-600">No incidents yet</p>
                  <p className="text-sm text-gray-500">
                    Run a demo scenario to see incidents
                  </p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {filteredIncidents.map((incident: any) => (
                    <IncidentCard
                      key={incident.id}
                      id={incident.id}
                      eventType={incident.event_type}
                      signalName={incident.signal_name}
                      confidence={incident.confidence}
                      timestamp={incident.created_at}
                      onClick={() => {
                        const match = decisions.find(
                          (d: any) => d.event_id === incident.id,
                        );
                        if (match) setActiveDecision(match);
                        setActiveTab('decisions');
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'decisions' && (
          <DecisionsPanel
            decisions={decisions}
            activeDecision={activeDecision}
            onSelect={(d) => setActiveDecision(d)}
          />
        )}

        {activeTab === 'audit' && (
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Audit Trail
            </h2>
            <p className="text-gray-600 mb-4">
              Complete audit log of all decisions and approvals
            </p>
            <div className="text-center py-8 bg-gray-50 rounded-lg">
              <p className="text-gray-500">Audit events will appear here</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface DecisionsPanelProps {
  decisions: any[];
  activeDecision: any | null;
  onSelect: (d: any) => void;
}

function DecisionsPanel({ decisions, activeDecision, onSelect }: DecisionsPanelProps) {
  if (decisions.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Decision History</h2>
        <div className="mt-8 text-center py-8 bg-gray-50 rounded-lg">
          <p className="text-gray-500">No decisions yet</p>
          <p className="text-sm text-gray-400 mt-1">
            Run a demo scenario from the Live Incidents tab to generate decisions.
          </p>
        </div>
      </div>
    );
  }

  const current = activeDecision ?? decisions[0];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Sidebar list */}
      <div className="lg:col-span-1 bg-white rounded-lg border border-gray-200 p-4 max-h-[80vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Decisions ({decisions.length})
        </h2>
        <ul className="space-y-2">
          {decisions.map((d: any) => {
            const isActive = current && current.decision_id === d.decision_id;
            const eventType = d.event?.type || d.event?.event_type || 'event';
            return (
              <li key={d.decision_id}>
                <button
                  onClick={() => onSelect(d)}
                  className={`w-full text-left p-3 rounded border transition-colors ${
                    isActive
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-900 truncate">
                      {d.orchestration_result?.selected_action || 'No action'}
                    </span>
                    <span className="text-[10px] font-medium uppercase bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">
                      {eventType}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {d.event?.signal_name}
                  </div>
                  <div className="text-[11px] text-gray-400 mt-1">
                    {new Date(d.timestamp).toLocaleTimeString()}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Detail panel */}
      <div className="lg:col-span-2 space-y-6">
        <DecisionDetail decision={current} />
      </div>
    </div>
  );
}

function DecisionDetail({ decision }: { decision: any }) {
  if (!decision) return null;

  const layers = decision.analysis_layers || {};
  const agentAnalyses: any[] = layers.agent_analyses || [];
  const impactEstimates: Record<string, any> = layers.impact_estimates || {};
  const policyEvaluations: Record<string, any> = layers.policy_evaluations || {};
  const redTeamReviews: Record<string, any> = layers.red_team_reviews || {};

  const selectedAction = decision.orchestration_result?.selected_action;
  const approvalRoute = decision.orchestration_result?.approval_route || 'auto';
  const approvalRequired = !!decision.orchestration_result?.approval_required;

  const selectedImpact = selectedAction ? impactEstimates[selectedAction] : undefined;
  const selectedPolicy = selectedAction ? policyEvaluations[selectedAction] : undefined;
  const selectedRedTeam = selectedAction ? redTeamReviews[selectedAction] : undefined;

  const flowLayers = {
    agents: agentAnalyses.map((a) => ({
      agent: String(a.agent ?? ''),
      confidence: Number(a.confidence ?? 0),
    })),
    policy: {
      decision: String(selectedPolicy?.policy_decision ?? 'n/a'),
      approvalLevel: String(selectedPolicy?.approval_level ?? approvalRoute),
    },
    twin: {
      impacts: {
        'Downtime (h)': Number(selectedImpact?.downtime_hours ?? 0),
        'Scrap units': Number(selectedImpact?.scrap_units ?? 0),
        'OEE impact (%)': Number(selectedImpact?.oee_impact ?? 0),
        'Cost impact ($)': Number(selectedImpact?.cost_impact ?? 0),
      } as Record<string, number>,
    },
    redTeam: {
      riskFactors: (selectedRedTeam?.risk_factors ?? []) as string[],
    },
    approval: {
      route: approvalRoute,
      deadline: 60,
    },
  };

  return (
    <>
      {/* Summary card */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {selectedAction || 'No action selected'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {decision.event?.signal_name} ·{' '}
              <span className="font-mono text-xs">{decision.decision_id}</span>
            </p>
          </div>
          <span
            className={`text-xs font-medium px-2.5 py-0.5 rounded ${
              approvalRequired
                ? 'bg-yellow-100 text-yellow-800'
                : 'bg-green-100 text-green-800'
            }`}
          >
            {approvalRequired ? 'APPROVAL REQUIRED' : 'AUTO-APPROVED'}
          </span>
        </div>
      </div>

      {/* Impact estimates */}
      {selectedImpact && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Impact Estimate</h3>
          <ImpactEstimate
            downtime={selectedImpact.downtime_hours ?? 0}
            scrap={selectedImpact.scrap_units ?? 0}
            cost={selectedImpact.cost_impact ?? 0}
            safety={selectedImpact.safety_improvement}
          />
        </div>
      )}

      {/* Pipeline layers */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-md font-semibold text-gray-900 mb-4">Orchestration Pipeline</h3>
        <DecisionFlow layers={flowLayers} />
      </div>

      {/* Approval workflow */}
      {approvalRequired && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Approval</h3>
          <ApprovalWorkflow
            requiredApprovers={[approvalRoute]}
            status="pending"
            deadline={60}
          />
        </div>
      )}
    </>
  );
}
