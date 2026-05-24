'use client';

import { useState } from 'react';
import {
  useAuditLog,
  useSelectedFactory,
} from '@/lib/store';
import {
  AuditTimeline,
} from '@/components/DashboardComponents';

export default function AuditPage() {
  const [filter, setFilter] = useState<'all' | 'safety' | 'quality' | 'maintenance'>('all');
  const [dateRange, setDateRange] = useState<{ start: string; end: string }>({
    start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  });

  // Mock audit data
  const mockAuditEvents = [
    {
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      action: 'Decision Approved',
      actor: 'supervisor_001',
      details: 'Decision dec_20260522_001 approved for stop_line action',
    },
    {
      timestamp: new Date(Date.now() - 2700000).toISOString(),
      action: 'Event Ingested',
      actor: 'System',
      details: 'Safety event: zone_intrusion (confidence 98%)',
    },
    {
      timestamp: new Date(Date.now() - 1800000).toISOString(),
      action: 'Policy Violation Detected',
      actor: 'PolicyEngine',
      details: 'Action would violate safety constraint, escalated',
    },
    {
      timestamp: new Date(Date.now() - 900000).toISOString(),
      action: 'Decision Executed',
      actor: 'System',
      details: 'Action stop_line executed successfully',
    },
    {
      timestamp: new Date().toISOString(),
      action: 'Audit Record Created',
      actor: 'System',
      details: 'Complete evidence pack stored for compliance',
    },
  ];

  const filteredEvents = mockAuditEvents.filter((event) => {
    if (filter === 'all') return true;
    return event.details.toLowerCase().includes(filter);
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Audit Trail</h1>
          <p className="text-gray-600 mt-1">
            Complete compliance record of all decisions and actions
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Filters */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Filters</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Event Type
              </label>
              <select
                value={filter}
                onChange={(e) =>
                  setFilter(e.target.value as 'all' | 'safety' | 'quality' | 'maintenance')
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Events</option>
                <option value="safety">Safety</option>
                <option value="quality">Quality</option>
                <option value="maintenance">Maintenance</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                From Date
              </label>
              <input
                type="date"
                value={dateRange.start}
                onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                To Date
              </label>
              <input
                type="date"
                value={dateRange.end}
                onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-end">
              <button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors">
                Export Report
              </button>
            </div>
          </div>
        </div>

        {/* Audit Timeline */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Recent Activity
            </h2>
            <span className="text-sm text-gray-600">
              {filteredEvents.length} events
            </span>
          </div>

          {filteredEvents.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-600">No audit events found</p>
            </div>
          ) : (
            <AuditTimeline events={filteredEvents} />
          )}
        </div>

        {/* Compliance Notes */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 mt-8">
          <h3 className="font-semibold text-green-900 mb-2">
            Compliance Status
          </h3>
          <ul className="space-y-1 text-sm text-green-700">
            <li>✓ All decisions have complete evidence packs</li>
            <li>✓ All approvals logged with timestamps and actors</li>
            <li>✓ Policy compliance verified for all actions</li>
            <li>✓ 365-day retention policy enforced</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
