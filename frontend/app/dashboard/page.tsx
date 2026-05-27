'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
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
      [...result.decisions].reverse().forEach((d) => addDecision(d as any));
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
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg p-8"
      >
        <h1 className="text-4xl font-bold mb-2">Dashboard</h1>
        <p className="text-blue-100">
          Real-time incident tracking and decision monitoring for {selectedFactory}
        </p>
      </motion.div>

      {/* Stats Overview */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 md:grid-cols-4 gap-4"
      >
        {[
          { label: 'Active Incidents', value: filteredIncidents.length, color: 'bg-red-50 text-red-600' },
          { label: 'Decisions Made', value: decisions.length, color: 'bg-blue-50 text-blue-600' },
          { label: 'Approval Rate', value: '94%', color: 'bg-green-50 text-green-600' },
          { label: 'Avg Latency', value: '1.2s', color: 'bg-purple-50 text-purple-600' },
        ].map((stat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.05 }}
            className={`${stat.color} rounded-lg p-6 font-semibold`}
          >
            <div className="text-sm opacity-75 mb-1">{stat.label}</div>
            <div className="text-3xl font-bold">{stat.value}</div>
          </motion.div>
        ))}
      </motion.div>

      {/* Tabs */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="bg-white rounded-lg border border-gray-200"
      >
        <div className="flex border-b border-gray-200">
          {[
            { id: 'incidents', label: '📊 Live Incidents', count: filteredIncidents.length },
            { id: 'scenarios', label: '🎬 Test Scenarios', count: scenarios?.length || 0 },
            { id: 'decisions', label: '📋 Decisions', count: decisions.length },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex-1 px-6 py-4 font-semibold border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-600 border-blue-600 bg-blue-50'
                  : 'text-gray-600 border-transparent hover:text-gray-900'
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Incidents Tab */}
          {activeTab === 'incidents' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4"
            >
              {eventsLoading ? (
                <div className="text-center py-8 text-gray-500">
                  Loading incidents...
                </div>
              ) : filteredIncidents.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No active incidents. System is healthy.
                </div>
              ) : (
                filteredIncidents.map((incident: any, i: number) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
                    onClick={() => setActiveDecision(decisions[i])}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-bold text-gray-900">{incident.event_type}</h4>
                        <p className="text-sm text-gray-600 mt-1">
                          Signal: {incident.signal_name} = {incident.signal_value}
                        </p>
                        <p className="text-xs text-gray-500 mt-2">
                          {new Date(incident.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-gray-900">
                          {(incident.confidence * 100).toFixed(0)}% confidence
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Factory: {incident.factory_id}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          )}

          {/* Scenarios Tab */}
          {activeTab === 'scenarios' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4"
            >
              {scenariosLoading ? (
                <div className="text-center py-8 text-gray-500">Loading scenarios...</div>
              ) : (
                (scenarios || []).map((scenario: any) => (
                  <motion.div
                    key={scenario.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border border-gray-200 rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-bold text-gray-900">{scenario.name}</h4>
                        <p className="text-sm text-gray-600 mt-1">{scenario.description}</p>
                        <div className="flex gap-4 mt-3 text-xs text-gray-500">
                          <span>
                            Difficulty:{' '}
                            <span className="font-semibold">{scenario.difficulty}</span>
                          </span>
                          <span>
                            Events: <span className="font-semibold">{scenario.event_count}</span>
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleGenerateScenario(scenario.id)}
                        disabled={runningScenarioId === scenario.id}
                        className={`px-4 py-2 rounded font-semibold transition-colors ${
                          runningScenarioId === scenario.id
                            ? 'bg-gray-300 text-gray-600'
                            : 'bg-blue-600 hover:bg-blue-700 text-white'
                        }`}
                      >
                        {runningScenarioId === scenario.id ? '▶ Running...' : '▶ Run Test'}
                      </button>
                    </div>
                  </motion.div>
                ))
              )}
              {runError && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                  Error: {runError}
                </div>
              )}
            </motion.div>
          )}

          {/* Decisions Tab */}
          {activeTab === 'decisions' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4"
            >
              {decisions.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  Run a scenario to generate decisions
                </div>
              ) : (
                decisions.map((decision: any, i: number) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                      activeDecision?.decision_id === decision.decision_id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                    onClick={() => setActiveDecision(decision)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-bold text-gray-900">
                          {decision.orchestration_result?.selected_action || 'Pending'}
                        </h4>
                        <p className="text-sm text-gray-600 mt-1">
                          Decision ID: {decision.decision_id.slice(0, 16)}...
                        </p>
                        <div className="flex gap-4 mt-2 text-xs">
                          <span className="px-2 py-1 bg-gray-100 rounded">
                            {decision.analysis_layers?.agent_analyses?.length || 0} agents
                          </span>
                          <span className="px-2 py-1 bg-gray-100 rounded">
                            Approval:{' '}
                            {decision.orchestration_result?.approval_required
                              ? 'Required'
                              : 'Auto'}
                          </span>
                        </div>
                      </div>
                      <div className="text-right text-xs text-gray-500">
                        {new Date(decision.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* Decision Detail Panel */}
      {activeDecision && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-lg border border-gray-200 p-8"
        >
          <div className="flex justify-between items-start mb-6">
            <h2 className="text-2xl font-bold">Decision Details</h2>
            <button
              onClick={() => setActiveDecision(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-2 gap-6 mb-6">
            <div>
              <div className="text-sm text-gray-600 mb-1">Decision ID</div>
              <div className="font-mono text-sm">{activeDecision.decision_id}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600 mb-1">Selected Action</div>
              <div className="font-bold text-lg">
                {activeDecision.orchestration_result?.selected_action || 'None'}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div>
              <h3 className="font-bold text-lg mb-3">Agent Analyses</h3>
              <div className="space-y-2">
                {activeDecision.analysis_layers?.agent_analyses?.map(
                  (analysis: any, i: number) => (
                    <div
                      key={i}
                      className="bg-gray-50 rounded p-3 border border-gray-200"
                    >
                      <div className="font-semibold text-gray-900">{analysis.agent}</div>
                      {analysis.error ? (
                        <div className="text-red-600 text-sm mt-1">Error: {analysis.error}</div>
                      ) : (
                        <>
                          <div className="text-sm text-gray-600 mt-1">
                            Confidence: {(analysis.confidence * 100).toFixed(0)}%
                          </div>
                          {analysis.recommendations?.length > 0 && (
                            <div className="text-sm text-gray-700 mt-2">
                              Recommendations: {analysis.recommendations.length}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )
                ) || []}
              </div>
            </div>

            <div>
              <h3 className="font-bold text-lg mb-3">Approval Status</h3>
              <div className="bg-blue-50 rounded p-4 border border-blue-200">
                <div className="text-sm text-gray-600 mb-1">Approval Required</div>
                <div className="font-bold text-lg">
                  {activeDecision.orchestration_result?.approval_required
                    ? `Yes - ${activeDecision.orchestration_result.approval_route}`
                    : 'No - Auto Approved'}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
