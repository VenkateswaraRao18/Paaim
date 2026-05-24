'use client';

import { useState } from 'react';
import {
  useEventsList,
  useScenarioCatalog,
  useGenerateScenario,
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
} from '@/components/DashboardComponents';

export default function DashboardPage() {
  const selectedFactory = useSelectedFactory();
  const activeTab = useActiveTab();
  const filters = useFilters();
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);
  const setIncidents = useDashboardStore((s) => s.setIncidents);
  const addDecision = useDashboardStore((s) => s.addDecision);

  // Fetch incidents
  const { data: eventsList, isLoading: eventsLoading } = useEventsList(selectedFactory);

  // Fetch scenarios
  const { data: scenarios, isLoading: scenariosLoading } = useScenarioCatalog();

  // Mutations
  const generateScenario = useGenerateScenario('safety_quality');
  const orchestrateScenario = useOrchestratScenario('safety_quality');

  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);

  // Filtered incidents
  const incidents = eventsList?.events || [];
  const filteredIncidents = incidents.filter((event: any) => {
    if (filters.eventType && event.event_type !== filters.eventType) return false;
    return true;
  });

  const handleGenerateScenario = async (scenarioId: string) => {
    setSelectedScenario(scenarioId);
    try {
      await orchestrateScenario.mutateAsync();
    } catch (err) {
      console.error('Failed to orchestrate scenario:', err);
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
                        {orchestrateScenario.isPending
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
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Decision History
            </h2>
            <p className="text-gray-600">
              Click on an incident above or run a demo scenario to see decisions
            </p>
            <div className="mt-8 text-center py-8 bg-gray-50 rounded-lg">
              <p className="text-gray-500">Decisions will appear here</p>
            </div>
          </div>
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
