'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useCustomAgentMutation, useCustomAgents } from '@/lib/api-client';

export default function CustomAgentBuilder() {
  const [step, setStep] = useState<'list' | 'create'>('list');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    domain: '',
    datasources: [{ name: '', type: 'SCADA', config: {} }],
    rules: [{ field: '', operator: '==', value: '', action: '', priority: 1 }],
    actions: [],
  });

  const { data: agentsData, refetch, isLoading } = useCustomAgents();
  const createMutation = useCustomAgentMutation();

  const agents = agentsData?.agents || [];

  const handleAddDataSource = () => {
    setFormData({
      ...formData,
      datasources: [...formData.datasources, { name: '', type: 'SCADA', config: {} }],
    });
  };

  const handleRemoveDataSource = (idx: number) => {
    setFormData({
      ...formData,
      datasources: formData.datasources.filter((_, i) => i !== idx),
    });
  };

  const handleAddRule = () => {
    setFormData({
      ...formData,
      rules: [
        ...formData.rules,
        { field: '', operator: '==', value: '', action: '', priority: 1 },
      ],
    });
  };

  const handleRemoveRule = (idx: number) => {
    setFormData({
      ...formData,
      rules: formData.rules.filter((_, i) => i !== idx),
    });
  };

  const handleAddAction = (action: string) => {
    if (action && !formData.actions.includes(action)) {
      setFormData({
        ...formData,
        actions: [...formData.actions, action],
      });
    }
  };

  const handleRemoveAction = (action: string) => {
    setFormData({
      ...formData,
      actions: formData.actions.filter((a) => a !== action),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name || !formData.domain || formData.datasources.length === 0) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      await createMutation.mutateAsync({
        name: formData.name,
        description: formData.description,
        domain: formData.domain,
        data_sources: formData.datasources.map((ds) => ({
          name: ds.name,
          type: ds.type,
          config: ds.config,
        })),
        rules: formData.rules
          .filter((r) => r.field && r.action)
          .map((r) => ({
            field: r.field,
            operator: r.operator,
            value: isNaN(Number(r.value)) ? r.value : Number(r.value),
            action: r.action,
            priority: r.priority,
          })),
        actions: formData.actions,
      });

      refetch();
      setStep('list');
      setFormData({
        name: '',
        description: '',
        domain: '',
        datasources: [{ name: '', type: 'SCADA', config: {} }],
        rules: [{ field: '', operator: '==', value: '', action: '', priority: 1 }],
        actions: [],
      });
    } catch (err) {
      console.error('Failed to create agent:', err);
      alert('Failed to create agent');
    }
  };

  if (step === 'list') {
    return (
      <div className="space-y-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex justify-between items-start"
        >
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Custom Agents</h1>
            <p className="text-gray-600 mt-2">
              No-code builder for intelligent manufacturing agents
            </p>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setStep('create')}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition-colors"
          >
            + Create Agent
          </motion.button>
        </motion.div>

        {/* Agent Grid */}
        {isLoading ? (
          <div className="text-center py-12 text-gray-500">Loading agents...</div>
        ) : agents.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-12 text-center"
          >
            <div className="text-4xl mb-4">⚡</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">No Agents Yet</h3>
            <p className="text-gray-600 mb-6">
              Create your first custom agent to connect to manufacturing systems
            </p>
            <button
              onClick={() => setStep('create')}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg inline-block"
            >
              Create First Agent
            </button>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {agents.map((agent: any, i: number) => (
              <motion.div
                key={agent.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">{agent.name}</h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Domain: <span className="font-semibold">{agent.domain}</span>
                    </p>
                  </div>
                  {agent.enabled ? (
                    <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-semibold">
                      ✓ Enabled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-xs font-semibold">
                      Disabled
                    </span>
                  )}
                </div>

                <p className="text-gray-600 text-sm mb-4 line-clamp-2">
                  {agent.description}
                </p>

                <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-gray-600">Data Sources</div>
                    <div className="font-bold text-gray-900">
                      {agent.data_sources_count}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-gray-600">Rules</div>
                    <div className="font-bold text-gray-900">{agent.rules_count}</div>
                  </div>
                </div>

                <button className="w-full bg-blue-50 hover:bg-blue-100 text-blue-600 font-semibold py-2 rounded transition-colors">
                  View Details
                </button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <button
          onClick={() => setStep('list')}
          className="text-blue-600 hover:text-blue-700 font-semibold mb-4 inline-flex items-center gap-2"
        >
          ← Back to Agents
        </button>
        <h1 className="text-4xl font-bold text-gray-900">Create Custom Agent</h1>
        <p className="text-gray-600 mt-2">
          Connect to manufacturing systems and define intelligent decision rules
        </p>
      </motion.div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Section 1: Basic Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-lg border border-gray-200 p-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-bold">
              1
            </span>
            Basic Information
          </h2>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Agent Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Thermal Management Agent"
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="What does this agent do?"
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Domain <span className="text-red-500">*</span>
              </label>
              <select
                value={formData.domain}
                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select a domain</option>
                <option value="thermal">Thermal Management</option>
                <option value="vibration">Vibration Monitoring</option>
                <option value="pressure">Pressure Control</option>
                <option value="production">Production Scheduling</option>
                <option value="quality">Quality Assurance</option>
                <option value="custom">Custom Domain</option>
              </select>
            </div>
          </div>
        </motion.div>

        {/* Section 2: Data Sources */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-lg border border-gray-200 p-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-bold">
              2
            </span>
            Connect Data Sources
          </h2>

          <p className="text-gray-600 mb-6">
            Connect to your manufacturing systems: SCADA, CMS (MES), IoT sensors, or REST APIs
          </p>

          <div className="space-y-4">
            {formData.datasources.map((ds, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="border border-gray-200 rounded-lg p-6 bg-gray-50"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="font-semibold text-gray-900">Data Source {idx + 1}</h3>
                  {formData.datasources.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveDataSource(idx)}
                      className="text-red-600 hover:text-red-700 text-sm font-semibold"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-gray-900 mb-2">
                      Source Name
                    </label>
                    <input
                      type="text"
                      placeholder="e.g., Plant_SCADA"
                      value={ds.name}
                      onChange={(e) => {
                        const newDs = [...formData.datasources];
                        newDs[idx].name = e.target.value;
                        setFormData({ ...formData, datasources: newDs });
                      }}
                      className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-900 mb-2">
                      Source Type
                    </label>
                    <select
                      value={ds.type}
                      onChange={(e) => {
                        const newDs = [...formData.datasources];
                        newDs[idx].type = e.target.value;
                        setFormData({ ...formData, datasources: newDs });
                      }}
                      className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="SCADA">SCADA (Modbus/OPC-UA)</option>
                      <option value="CMS">CMS/MES</option>
                      <option value="IoT">IoT (MQTT/CoAP)</option>
                      <option value="REST_API">REST API</option>
                      <option value="DATABASE">Database</option>
                    </select>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <button
            type="button"
            onClick={handleAddDataSource}
            className="mt-4 text-blue-600 hover:text-blue-700 font-semibold text-sm inline-flex items-center gap-2"
          >
            + Add Another Source
          </button>
        </motion.div>

        {/* Section 3: Decision Rules */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-lg border border-gray-200 p-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-bold">
              3
            </span>
            Define Decision Rules
          </h2>

          <p className="text-gray-600 mb-6">
            Create if-then rules: if [field] [operator] [value], then [action]
          </p>

          <div className="space-y-4">
            {formData.rules.map((rule, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="border border-gray-200 rounded-lg p-6 bg-gray-50"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="font-semibold text-gray-900">Rule {idx + 1}</h3>
                  {formData.rules.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveRule(idx)}
                      className="text-red-600 hover:text-red-700 text-sm font-semibold"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <input
                    type="text"
                    placeholder="Field"
                    value={rule.field}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].field = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />

                  <select
                    value={rule.operator}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].operator = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="==">=</option>
                    <option value="!=">!=</option>
                    <option value=">">></option>
                    <option value="<">&lt;</option>
                    <option value=">=">&gt;=</option>
                    <option value="<=">&lt;=</option>
                  </select>

                  <input
                    type="text"
                    placeholder="Value"
                    value={rule.value}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].value = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />

                  <input
                    type="text"
                    placeholder="Action"
                    value={rule.action}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].action = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="col-span-2 md:col-span-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </motion.div>
            ))}
          </div>

          <button
            type="button"
            onClick={handleAddRule}
            className="mt-4 text-blue-600 hover:text-blue-700 font-semibold text-sm inline-flex items-center gap-2"
          >
            + Add Another Rule
          </button>
        </motion.div>

        {/* Section 4: Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-white rounded-lg border border-gray-200 p-8"
        >
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-bold">
              4
            </span>
            Possible Actions
          </h2>

          <p className="text-gray-600 mb-6">
            List all actions this agent can recommend
          </p>

          <div className="flex gap-2 mb-4">
            <input
              type="text"
              id="actionInput"
              placeholder="e.g., activate_cooling"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                const input = document.getElementById('actionInput') as HTMLInputElement;
                if (input.value) {
                  handleAddAction(input.value);
                  input.value = '';
                }
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2 rounded-lg"
            >
              Add
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {formData.actions.map((action) => (
              <motion.div
                key={action}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-blue-100 text-blue-700 px-4 py-2 rounded-full flex items-center gap-2 font-semibold"
              >
                {action}
                <button
                  type="button"
                  onClick={() => handleRemoveAction(action)}
                  className="text-blue-600 hover:text-blue-900 font-bold"
                >
                  ✕
                </button>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Submit Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="flex gap-4"
        >
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-3 px-8 rounded-lg transition-colors shadow-lg"
          >
            {createMutation.isPending ? '⏳ Creating...' : '✓ Create Agent'}
          </button>
          <button
            type="button"
            onClick={() => setStep('list')}
            className="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-3 px-8 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </motion.div>
      </form>
    </div>
  );
}
