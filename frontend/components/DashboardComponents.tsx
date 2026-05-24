'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';

/**
 * PAAIM Dashboard Components
 * Reusable UI components for the dashboard
 */

// ===== IncidentCard =====

export interface IncidentCardProps {
  id: string;
  eventType: string;
  signalName: string;
  confidence: number;
  timestamp: string;
  onClick?: () => void;
}

export function IncidentCard({
  id,
  eventType,
  signalName,
  confidence,
  timestamp,
  onClick,
}: IncidentCardProps) {
  const riskColor = {
    safety: 'bg-red-50 border-red-200',
    quality: 'bg-yellow-50 border-yellow-200',
    maintenance: 'bg-blue-50 border-blue-200',
    production: 'bg-orange-50 border-orange-200',
    energy: 'bg-green-50 border-green-200',
    compliance: 'bg-purple-50 border-purple-200',
  }[eventType] || 'bg-gray-50 border-gray-200';

  const riskBadge = {
    safety: 'bg-red-100 text-red-800',
    quality: 'bg-yellow-100 text-yellow-800',
    maintenance: 'bg-blue-100 text-blue-800',
    production: 'bg-orange-100 text-orange-800',
    energy: 'bg-green-100 text-green-800',
    compliance: 'bg-purple-100 text-purple-800',
  }[eventType] || 'bg-gray-100 text-gray-800';

  return (
    <div
      onClick={onClick}
      className={`${riskColor} border rounded-lg p-4 cursor-pointer hover:shadow-md transition-shadow`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{signalName}</h3>
          <p className="text-sm text-gray-600">ID: {id.slice(0, 12)}...</p>
        </div>
        <span className={`${riskBadge} text-xs font-medium px-2.5 py-0.5 rounded`}>
          {eventType.toUpperCase()}
        </span>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-600">
          Confidence: <span className="font-medium">{(confidence * 100).toFixed(0)}%</span>
        </span>
        <span className="text-xs text-gray-500">{new Date(timestamp).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}

// ===== DecisionFlow =====

export interface DecisionFlowProps {
  layers: {
    agents: Array<{ agent: string; confidence: number }>;
    policy: { decision: string; approvalLevel: string };
    twin: { impacts: Record<string, number> };
    redTeam: { riskFactors: string[] };
    approval: { route: string; deadline: number };
  };
}

export function DecisionFlow({ layers }: DecisionFlowProps) {
  return (
    <div className="space-y-4">
      {/* Agent Layer */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">Agent Analysis</h4>
        <div className="space-y-2">
          {layers.agents.map((agent, i) => (
            <div key={i} className="text-sm">
              <span className="text-blue-700">{agent.agent}</span>
              <span className="ml-2 text-blue-600">
                Confidence: {(agent.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Policy Layer */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="font-semibold text-purple-900 mb-2">Policy Evaluation</h4>
        <div className="flex justify-between items-center">
          <span className="text-sm text-purple-700">{layers.policy.decision}</span>
          <span className="text-sm font-medium text-purple-900">
            {layers.policy.approvalLevel}
          </span>
        </div>
      </div>

      {/* Impact Layer */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="font-semibold text-green-900 mb-2">Impact Estimates</h4>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(layers.twin.impacts).map(([key, value]) => (
            <div key={key} className="text-sm">
              <span className="text-green-700">{key}:</span>
              <span className="ml-1 font-medium text-green-900">
                {typeof value === 'number' ? value.toFixed(2) : value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Red-Team Layer */}
      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <h4 className="font-semibold text-orange-900 mb-2">Red-Team Review</h4>
        <div className="space-y-1">
          {layers.redTeam.riskFactors.slice(0, 3).map((factor, i) => (
            <div key={i} className="text-sm text-orange-700">
              • {factor}
            </div>
          ))}
        </div>
      </div>

      {/* Approval Layer */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
        <h4 className="font-semibold text-indigo-900 mb-2">Approval Route</h4>
        <div className="flex justify-between items-center">
          <span className="text-sm text-indigo-700">{layers.approval.route}</span>
          <span className="text-sm font-medium text-indigo-900">
            {layers.approval.deadline}s deadline
          </span>
        </div>
      </div>
    </div>
  );
}

// ===== ImpactEstimate =====

export interface ImpactEstimateProps {
  downtime: number;
  scrap: number;
  cost: number;
  safety?: string;
  quality?: string;
}

export function ImpactEstimate({
  downtime,
  scrap,
  cost,
  safety,
  quality,
}: ImpactEstimateProps) {
  const getCostColor = (value: number) => {
    if (value < 0) return 'text-green-600'; // Savings
    if (value > 1000) return 'text-red-600';
    return 'text-yellow-600';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-gradient-to-br from-orange-50 to-orange-100 border border-orange-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-orange-900 mb-1">Downtime</h4>
        <p className="text-2xl font-bold text-orange-700">{downtime.toFixed(1)}h</p>
        <p className="text-xs text-orange-600 mt-1">Production impact</p>
      </div>

      <div className="bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-red-900 mb-1">Scrap Risk</h4>
        <p className="text-2xl font-bold text-red-700">{scrap} units</p>
        <p className="text-xs text-red-600 mt-1">Quality impact</p>
      </div>

      <div className={`bg-gradient-to-br ${cost < 0 ? 'from-green-50 to-green-100 border-green-200' : 'from-blue-50 to-blue-100 border-blue-200'} border rounded-lg p-4`}>
        <h4 className="text-sm font-semibold mb-1">Cost Impact</h4>
        <p className={`text-2xl font-bold ${getCostColor(cost)}`}>
          ${Math.abs(cost).toFixed(0)}
        </p>
        <p className="text-xs text-gray-600 mt-1">{cost < 0 ? 'Savings' : 'Cost'}</p>
      </div>

      {(safety || quality) && (
        <div className="col-span-1 md:col-span-3 bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="grid grid-cols-2 gap-4">
            {safety && (
              <div>
                <h5 className="text-sm font-semibold text-gray-900">Safety Impact</h5>
                <p className="text-sm text-gray-700 capitalize">{safety}</p>
              </div>
            )}
            {quality && (
              <div>
                <h5 className="text-sm font-semibold text-gray-900">Quality Impact</h5>
                <p className="text-sm text-gray-700 capitalize">{quality}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ===== ApprovalWorkflow =====

export interface ApprovalWorkflowProps {
  requiredApprovers: string[];
  currentApprover?: string;
  status: 'pending' | 'approved' | 'rejected';
  deadline?: number;
  onApprove?: () => void;
  onReject?: () => void;
}

export function ApprovalWorkflow({
  requiredApprovers,
  currentApprover,
  status,
  deadline,
  onApprove,
  onReject,
}: ApprovalWorkflowProps) {
  const statusColor = {
    pending: 'bg-yellow-50 border-yellow-200',
    approved: 'bg-green-50 border-green-200',
    rejected: 'bg-red-50 border-red-200',
  };

  const statusTextColor = {
    pending: 'text-yellow-900',
    approved: 'text-green-900',
    rejected: 'text-red-900',
  };

  const statusBadgeColor = {
    pending: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
  };

  return (
    <div className={`${statusColor[status]} border rounded-lg p-4`}>
      <div className="flex items-center justify-between mb-4">
        <h4 className={`font-semibold ${statusTextColor[status]}`}>Approval Workflow</h4>
        <span className={`text-xs font-medium px-2.5 py-0.5 rounded ${statusBadgeColor[status]}`}>
          {status.toUpperCase()}
        </span>
      </div>

      <div className="space-y-2 mb-4">
        {requiredApprovers.map((approver, i) => (
          <div key={i} className="flex items-center">
            <div className="flex-1 text-sm font-medium capitalize text-gray-700">
              {approver}
            </div>
            {currentApprover === approver && (
              <span className="text-xs text-blue-600 font-semibold">PENDING</span>
            )}
          </div>
        ))}
      </div>

      {deadline && (
        <p className="text-xs text-gray-600 mb-4">Deadline: {deadline} seconds</p>
      )}

      {status === 'pending' && (
        <div className="flex gap-2">
          <button
            onClick={onApprove}
            className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-medium py-2 px-4 rounded transition-colors"
          >
            Approve
          </button>
          <button
            onClick={onReject}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white text-sm font-medium py-2 px-4 rounded transition-colors"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

// ===== AuditTimeline =====

export interface AuditEvent {
  timestamp: string;
  action: string;
  actor: string;
  details?: string;
}

export interface AuditTimelineProps {
  events: AuditEvent[];
}

export function AuditTimeline({ events }: AuditTimelineProps) {
  return (
    <div className="space-y-4">
      {events.map((event, i) => (
        <div key={i} className="flex gap-4">
          <div className="flex flex-col items-center">
            <div className="w-3 h-3 bg-blue-600 rounded-full mt-1.5"></div>
            {i < events.length - 1 && <div className="w-0.5 h-12 bg-gray-300 mt-2"></div>}
          </div>
          <div className="flex-1 pb-4">
            <p className="text-sm font-semibold text-gray-900">{event.action}</p>
            <p className="text-xs text-gray-600">
              {event.actor} • {new Date(event.timestamp).toLocaleString()}
            </p>
            {event.details && <p className="text-xs text-gray-700 mt-1">{event.details}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ===== Loading States =====

export function IncidentCardSkeleton() {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-3"></div>
      <div className="h-3 bg-gray-200 rounded w-1/2 mb-3"></div>
      <div className="h-3 bg-gray-200 rounded w-full"></div>
    </div>
  );
}

export function DecisionFlowSkeleton() {
  return (
    <div className="space-y-4">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-4 animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-3"></div>
          <div className="h-3 bg-gray-200 rounded w-full"></div>
        </div>
      ))}
    </div>
  );
}
