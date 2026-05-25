'use client';

import { useState } from 'react';
import { useCustomAgentMutation, useCustomAgents } from '@/lib/api-client';

export default function CustomAgentBuilder() {
  const [step, setStep] = useState<'list' | 'create' | 'detail'>('list');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    domain: '',
    datasources: [{ name: '', type: 'REST_API', config: {} }],
    rules: [{ field: '', operator: '==', value: '', action: '' }],
    actions: [],
  });

  const { data: agents, refetch } = useCustomAgents();
  const createMutation = useCustomAgentMutation();

  const handleAddDataSource = () => {
    setFormData({
      ...formData,
      datasources: [...formData.datasources, { name: '', type: 'REST_API', config: {} }],
    });
  };

  const handleAddRule = () => {
    setFormData({
      ...formData,
      rules: [...formData.rules, { field: '', operator: '==', value: '', action: '' }],
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

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
        rules: formData.rules.map((r) => ({
          field: r.field,
          operator: r.operator,
          value: r.value,
          action: r.action,
        })),
        actions: formData.actions,
      });

      refetch();
      setStep('list');
      setFormData({
        name: '',
        description: '',
        domain: '',
        datasources: [{ name: '', type: 'REST_API', config: {} }],
        rules: [{ field: '', operator: '==', value: '', action: '' }],
        actions: [],
      });
    } catch (err) {
      console.error('Failed to create agent:', err);
    }
  };

  if (step === 'list') {
    return (
      <div className="p-6">
        <div className="mb-6 flex justify-between items-center">
          <h1 className="text-3xl font-bold">Custom AI Agents</h1>
          <button
            onClick={() => setStep('create')}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            + Create Agent
          </button>
        </div>

        <div className="grid gap-4">
          {agents?.agents?.map((agent: any) => (
            <div key={agent.id} className="border rounded-lg p-4 bg-white shadow">
              <h3 className="font-bold text-lg">{agent.name}</h3>
              <p className="text-gray-600 text-sm">{agent.description}</p>
              <div className="mt-2 flex gap-4 text-sm text-gray-500">
                <span>Domain: {agent.domain}</span>
                <span>Data Sources: {agent.data_sources_count}</span>
                <span>Rules: {agent.rules_count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (step === 'create') {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <button
          onClick={() => setStep('list')}
          className="mb-4 text-blue-600 hover:underline"
        >
          ← Back to Agents
        </button>

        <h1 className="text-3xl font-bold mb-6">Create Custom Agent</h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold mb-4">Basic Information</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium">Agent Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full border rounded px-3 py-2 mt-1"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full border rounded px-3 py-2 mt-1"
                  rows={3}
                />
              </div>

              <div>
                <label className="block text-sm font-medium">Domain</label>
                <select
                  value={formData.domain}
                  onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                  className="w-full border rounded px-3 py-2 mt-1"
                >
                  <option value="">Select Domain</option>
                  <option value="thermal">Thermal Management</option>
                  <option value="vibration">Vibration Monitoring</option>
                  <option value="pressure">Pressure Control</option>
                  <option value="custom">Custom Domain</option>
                </select>
              </div>
            </div>
          </div>

          {/* Data Sources */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold mb-4">Data Sources</h2>
            <p className="text-gray-600 text-sm mb-4">
              Connect to manufacturing systems (SCADA, CMS, IoT, REST APIs)
            </p>

            <div className="space-y-4">
              {formData.datasources.map((ds, idx) => (
                <div key={idx} className="border rounded p-4 bg-gray-50">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium">Source Name</label>
                      <input
                        type="text"
                        placeholder="e.g., Production_SCADA"
                        value={ds.name}
                        onChange={(e) => {
                          const newDs = [...formData.datasources];
                          newDs[idx].name = e.target.value;
                          setFormData({ ...formData, datasources: newDs });
                        }}
                        className="w-full border rounded px-3 py-2 mt-1"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium">Source Type</label>
                      <select
                        value={ds.type}
                        onChange={(e) => {
                          const newDs = [...formData.datasources];
                          newDs[idx].type = e.target.value;
                          setFormData({ ...formData, datasources: newDs });
                        }}
                        className="w-full border rounded px-3 py-2 mt-1"
                      >
                        <option value="SCADA">SCADA (Modbus/OPC-UA)</option>
                        <option value="CMS">Manufacturing Execution System (CMS)</option>
                        <option value="IoT">IoT Sensors (MQTT/CoAP)</option>
                        <option value="REST_API">REST API</option>
                        <option value="DATABASE">SQL Database</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={handleAddDataSource}
              className="mt-4 text-blue-600 hover:underline text-sm"
            >
              + Add Data Source
            </button>
          </div>

          {/* Rules */}
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold mb-4">Decision Rules</h2>
            <p className="text-gray-600 text-sm mb-4">
              Define if-then rules: if field operator value, then action
            </p>

            <div className="space-y-4">
              {formData.rules.map((rule, idx) => (
                <div key={idx} className="border rounded p-4 bg-gray-50">
                  <div className="grid grid-cols-5 gap-2">
                    <div>
                      <label className="block text-xs font-medium">Field</label>
                      <input
                        type="text"
                        placeholder="e.g., temperature"
                        value={rule.field}
                        onChange={(e) => {
                          const newRules = [...formData.rules];
                          newRules[idx].field = e.target.value;
                          setFormData({ ...formData, rules: newRules });
                        }}
                        className="w-full border rounded px-2 py-1 mt-1 text-sm"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium">Operator</label>
                      <select
                        value={rule.operator}
                        onChange={(e) => {
                          const newRules = [...formData.rules];
                          newRules[idx].operator = e.target.value;
                          setFormData({ ...formData, rules: newRules });
                        }}
                        className="w-full border rounded px-2 py-1 mt-1 text-sm"
                      >
                        <option value="==">=</option>
                        <option value="!=">!=</option>
                        <option value=">">></option>
                        <option value="<">&lt;</option>
                        <option value=">=">&gt;=</option>
                        <option value="<=">&lt;=</option>
                        <option value="in">in</option>
                        <option value="not_in">not in</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-medium">Value</label>
                      <input
                        type="text"
                        placeholder="e.g., 80"
                        value={rule.value}
                        onChange={(e) => {
                          const newRules = [...formData.rules];
                          newRules[idx].value = e.target.value;
                          setFormData({ ...formData, rules: newRules });
                        }}
                        className="w-full border rounded px-2 py-1 mt-1 text-sm"
                      />
                    </div>

                    <div className="col-span-2">
                      <label className="block text-xs font-medium">Action</label>
                      <input
                        type="text"
                        placeholder="e.g., activate_cooling"
                        value={rule.action}
                        onChange={(e) => {
                          const newRules = [...formData.rules];
                          newRules[idx].action = e.target.value;
                          setFormData({ ...formData, rules: newRules });
                        }}
                        className="w-full border rounded px-2 py-1 mt-1 text-sm"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={handleAddRule}
              className="mt-4 text-blue-600 hover:underline text-sm"
            >
              + Add Rule
            </button>
          </div>

          {/* Submit */}
          <div className="flex gap-4">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700 disabled:bg-gray-400"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Agent'}
            </button>
            <button
              type="button"
              onClick={() => setStep('list')}
              className="bg-gray-300 text-gray-800 px-6 py-2 rounded hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    );
  }

  return null;
}
