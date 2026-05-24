'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  useActiveDecision,
  useDashboardStore,
} from '@/lib/store';
import {
  DecisionFlow,
  ImpactEstimate,
  ApprovalWorkflow,
  AuditTimeline,
} from '@/components/DashboardComponents';

export default function DecisionDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const activeDecision = useActiveDecision();
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);

  // Mock decision for demo (in production, would fetch from API)
  const decision = activeDecision || {
    decision_id: params.id,
    event_id: 'evt_20260522_0001',
    factory_id: 'factory_001',
    timestamp: new Date().toISOString(),
    event: {
      event_type: 'safety',
      signal_name: 'zone_intrusion',
      signal_value: 1.0,
      confidence: 0.98,
      factory_id: 'factory_001',
      timestamp: new Date().toISOString(),
      context: { zone_id: 'restricted_zone_a', worker_id: 'W123' },
    },
    orchestration_result: {
      selected_action: 'stop_line',
      approval_required: true,
      approval_route: 'safety_officer',
    },
    analysis_layers: {
      agent_analyses: [
        {
          agent: 'safety_agent',
          confidence: 0.98,
          reasoning: 'Critical safety hazard detected',
          recommendations: [
            {
              action_name: 'stop_line',
              description: 'Stop production line due to safety zone intrusion',
              risk_level: 'critical',
              confidence: 0.99,
            },
          ],
        },
      ],
      policy_evaluations: {
        stop_line: {
          policy_decision: 'allowed',
          approval_level: 'safety_officer',
          reason: 'Action stop_line requires safety_officer approval',
        },
      },
      impact_estimates: {
        stop_line: {
          downtime_hours: 0.5,
          scrap_units: 0,
          cost_impact: -2000,
          safety_improvement: 'critical',
          oee_impact: -5.0,
          impact_score: 0.92,
        },
      },
      red_team_reviews: {
        stop_line: {
          risk_factors: [
            'Verify zone intrusion not false positive',
            'Sudden line stop may cause material waste',
          ],
          assumptions_challenged: ['Zone intrusion sensor calibrated'],
          suggested_alternatives: ['Alert operator first'],
          confidence_adjustment: -0.05,
          overall_risk_assessment: 'acceptable',
          should_escalate: false,
        },
      },
    },
    evidence_pack: {},
  };

  const [approvalStatus, setApprovalStatus] = useState<'pending' | 'approved' | 'rejected'>(
    'pending'
  );

  const handleApprove = () => {
    setApprovalStatus('approved');
  };

  const handleReject = () => {
    setApprovalStatus('rejected');
  };

  // Extract layers for DecisionFlow component
  const layers = {
    agents:
      decision.analysis_layers.agent_analyses.map((a: any) => ({
        agent: a.agent,
        confidence: a.confidence,
      })) || [],
    policy: {
      decision: decision.orchestration_result.selected_action,
      approvalLevel: decision.orchestration_result.approval_route,
    },
    twin: {
      impacts:
        decision.analysis_layers.impact_estimates[decision.orchestration_result.selected_action] || {},
    },
    redTeam: {
      riskFactors:
        decision.analysis_layers.red_team_reviews[decision.orchestration_result.selected_action]
          ?.risk_factors || [],
    },
    approval: {
      route: decision.orchestration_result.approval_route,
      deadline: 60,
    },
  };

  const impact = decision.analysis_layers.impact_estimates[decision.orchestration_result.selected_action] || {};

  const auditEvents = [
    {
      timestamp: decision.timestamp,
      action: 'Event Detected',
      actor: 'System',
      details: `${decision.event.event_type} event: ${decision.event.signal_name}`,
    },
    {
      timestamp: new Date(new Date(decision.timestamp).getTime() + 100).toISOString(),
      action: 'Agents Analyzed',
      actor: 'SafetyAgent',
      details: 'Recommended stop_line (99% confidence)',
    },
    {
      timestamp: new Date(new Date(decision.timestamp).getTime() + 200).toISOString(),
      action: 'Policy Evaluated',
      actor: 'PolicyEngine',
      details: 'Action allowed, requires safety_officer approval',
    },
    {
      timestamp: new Date(new Date(decision.timestamp).getTime() + 300).toISOString(),
      action: 'Impact Simulated',
      actor: 'DecisionTwin',
      details: '0.5h downtime, critical safety improvement',
    },
    {
      timestamp: new Date(new Date(decision.timestamp).getTime() + 400).toISOString(),
      action: 'Red-Team Challenge',
      actor: 'RedTeamAgent',
      details: 'Risk assessment: acceptable, sensor confidence verified',
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center gap-4 mb-4">
            <button
              onClick={() => setActiveTab('incidents')}
              className="text-blue-600 hover:text-blue-700 font-medium"
            >
              ← Back to Incidents
            </button>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Decision Detail</h1>
          <p className="text-gray-600 mt-1">
            ID: {decision.decision_id}
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Column */}
          <div className="lg:col-span-2 space-y-8">
            {/* Event Summary */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Event Summary
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-600 uppercase">Event Type</p>
                  <p className="text-lg font-semibold text-gray-900 capitalize">
                    {decision.event.event_type}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600 uppercase">Signal</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {decision.event.signal_name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600 uppercase">Confidence</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {(decision.event.confidence * 100).toFixed(0)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600 uppercase">Timestamp</p>
                  <p className="text-sm text-gray-700">
                    {new Date(decision.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            {/* Decision Flow */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Orchestration Pipeline
              </h2>
              <DecisionFlow layers={layers} />
            </div>

            {/* Impact Estimates */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Impact Estimates
              </h2>
              <ImpactEstimate
                downtime={impact.downtime_hours || 0}
                scrap={impact.scrap_units || 0}
                cost={impact.cost_impact || 0}
                safety={impact.safety_improvement}
                quality={impact.quality_improvement}
              />
            </div>

            {/* Audit Trail */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Decision Timeline
              </h2>
              <AuditTimeline events={auditEvents} />
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Selected Action */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="font-semibold text-blue-900 mb-2">Recommended Action</h3>
              <p className="text-lg font-bold text-blue-700 mb-3">
                {decision.orchestration_result.selected_action}
              </p>
              <div className="text-sm text-blue-700">
                <p className="mb-2">
                  <strong>Status:</strong> Requires Approval
                </p>
                <p>
                  <strong>Route:</strong> {decision.orchestration_result.approval_route}
                </p>
              </div>
            </div>

            {/* Approval Workflow */}
            <ApprovalWorkflow
              requiredApprovers={[decision.orchestration_result.approval_route]}
              currentApprover={decision.orchestration_result.approval_route}
              status={approvalStatus}
              deadline={60}
              onApprove={handleApprove}
              onReject={handleReject}
            />

            {/* Quick Stats */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h4 className="font-semibold text-gray-900 mb-3">Quick Stats</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Impact Score:</span>
                  <span className="font-medium text-gray-900">
                    {(impact.impact_score || 0).toFixed(2)}/1.0
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Processing Time:</span>
                  <span className="font-medium text-gray-900">~400ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Agents Analyzed:</span>
                  <span className="font-medium text-gray-900">
                    {decision.analysis_layers.agent_analyses.length}
                  </span>
                </div>
              </div>
            </div>

            {/* Risk Assessment */}
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <h4 className="font-semibold text-orange-900 mb-3">Risk Assessment</h4>
              <div className="space-y-1 text-sm">
                {layers.redTeam.riskFactors.map((factor, i) => (
                  <p key={i} className="text-orange-700">
                    • {factor}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
