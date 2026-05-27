'use client';

import { motion } from 'framer-motion';

export default function AuditPage() {
  // Mock data for demo
  const auditEntries = [
    {
      id: 'audit_001',
      timestamp: new Date(Date.now() - 5 * 60000),
      eventType: 'decision_approved',
      agent: 'SafetyAgent',
      action: 'activate_e_stop',
      approver: 'John Smith (Operator)',
      status: 'approved',
      confidence: 0.98,
    },
    {
      id: 'audit_002',
      timestamp: new Date(Date.now() - 15 * 60000),
      eventType: 'decision_pending',
      agent: 'QualityAgent',
      action: 'hold_batch',
      approver: 'Pending (Supervisor)',
      status: 'pending',
      confidence: 0.85,
    },
    {
      id: 'audit_003',
      timestamp: new Date(Date.now() - 30 * 60000),
      eventType: 'decision_rejected',
      agent: 'ProductionAgent',
      action: 'increase_throughput',
      approver: 'Mary Johnson (Manager)',
      status: 'rejected',
      confidence: 0.72,
    },
    {
      id: 'audit_004',
      timestamp: new Date(Date.now() - 60 * 60000),
      eventType: 'decision_approved',
      agent: 'MaintenanceAgent',
      action: 'schedule_maintenance',
      approver: 'Auto (Policy)',
      status: 'approved',
      confidence: 0.91,
    },
    {
      id: 'audit_005',
      timestamp: new Date(Date.now() - 120 * 60000),
      eventType: 'decision_approved',
      agent: 'EnergyAgent',
      action: 'shift_load',
      approver: 'Auto (Policy)',
      status: 'approved',
      confidence: 0.88,
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'bg-green-100 text-green-700 border-green-300';
      case 'rejected':
        return 'bg-red-100 text-red-700 border-red-300';
      case 'pending':
        return 'bg-yellow-100 text-yellow-700 border-yellow-300';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-300';
    }
  };

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
      },
    },
  };

  const item = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-4xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-gray-600 mt-2">
          Complete evidence trail for compliance and transparency
        </p>
      </motion.div>

      {/* Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 md:grid-cols-4 gap-4"
      >
        {[
          { label: 'Total Decisions', value: '247', color: 'bg-blue-50 text-blue-600' },
          { label: 'Approved', value: '238', color: 'bg-green-50 text-green-600' },
          { label: 'Rejected', value: '6', color: 'bg-red-50 text-red-600' },
          { label: 'Compliance Rate', value: '97.2%', color: 'bg-purple-50 text-purple-600' },
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

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white rounded-lg border border-gray-200 p-6"
      >
        <h3 className="font-bold text-gray-900 mb-4">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <input
            type="date"
            placeholder="Start Date"
            className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="date"
            placeholder="End Date"
            className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">All Status</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="pending">Pending</option>
          </select>
          <select className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">All Agents</option>
            <option value="safety">SafetyAgent</option>
            <option value="quality">QualityAgent</option>
            <option value="maintenance">MaintenanceAgent</option>
          </select>
        </div>
      </motion.div>

      {/* Audit Entries */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="space-y-4"
      >
        {auditEntries.map((entry) => (
          <motion.div
            key={entry.id}
            variants={item}
            className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="font-bold text-lg text-gray-900">{entry.action}</h3>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(
                      entry.status
                    )}`}
                  >
                    {entry.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-gray-600 text-sm">
                  Agent: <span className="font-semibold">{entry.agent}</span>
                </p>
              </div>

              <div className="text-right">
                <div className="text-sm text-gray-500 mb-2">
                  {entry.timestamp.toLocaleString()}
                </div>
                <div className="text-lg font-bold text-gray-900">
                  {(entry.confidence * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-600">Confidence</div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 py-4 border-t border-gray-200">
              <div>
                <div className="text-xs text-gray-600 uppercase font-semibold">Approver</div>
                <div className="text-sm text-gray-900 mt-1">{entry.approver}</div>
              </div>

              <div>
                <div className="text-xs text-gray-600 uppercase font-semibold">Event Type</div>
                <div className="text-sm text-gray-900 mt-1 capitalize">
                  {entry.eventType.replace(/_/g, ' ')}
                </div>
              </div>

              <div>
                <div className="text-xs text-gray-600 uppercase font-semibold">Decision ID</div>
                <div className="text-sm font-mono text-gray-900 mt-1">{entry.id}</div>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t border-gray-200">
              <button className="flex-1 text-blue-600 hover:text-blue-700 font-semibold py-2 text-sm rounded hover:bg-blue-50 transition-colors">
                View Evidence Pack
              </button>
              <button className="flex-1 text-gray-600 hover:text-gray-900 font-semibold py-2 text-sm rounded hover:bg-gray-50 transition-colors">
                Download
              </button>
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Pagination */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="flex justify-center items-center gap-2 mt-8"
      >
        <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
          ← Previous
        </button>
        {[1, 2, 3, 4, 5].map((page) => (
          <button
            key={page}
            className={`px-4 py-2 rounded-lg ${
              page === 1
                ? 'bg-blue-600 text-white'
                : 'border border-gray-300 hover:bg-gray-50'
            }`}
          >
            {page}
          </button>
        ))}
        <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
          Next →
        </button>
      </motion.div>
    </div>
  );
}
