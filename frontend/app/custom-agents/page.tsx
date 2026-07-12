'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useCustomAgentMutation, useCustomAgents, useTestConnectionBeforeCreate } from '@/lib/api-client';
import { Eyebrow, SectionHeader, Card, SignalPill } from '@/components/ui';

// factory-stream (live sensor feed) + PAAIM backend (where watchers attach)
const STREAM_BASE = process.env.NEXT_PUBLIC_STREAM_URL || 'http://localhost:9100';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// The 5 always-on specialist monitors baked into the orchestrator
const BUILT_IN_MONITORS = [
  { name: 'Safety Monitor', watches: 'Hazards & danger zones' },
  { name: 'Quality Monitor', watches: 'Defects & scrap' },
  { name: 'Maintenance Monitor', watches: 'Early breakdown signs' },
  { name: 'Production Monitor', watches: 'Output & deadlines' },
  { name: 'Energy Monitor', watches: 'Power use & cost' },
];

type StreamAgentStatus = {
  key: string; machine_id: string; signal: string; label: string;
  connected: boolean; events_raised: number; last_status: string;
};
type SignalMeta = { machine_id: string; signal: string; label: string; unit: string };

// ─── Per-source-type config field definitions ─────────────────────────────────

type FieldDef = {
  key: string;
  label: string;
  placeholder: string;
  type?: 'text' | 'password' | 'number';
  required?: boolean;
};

const SOURCE_FIELDS: Record<string, FieldDef[]> = {
  SCADA: [
    { key: 'host', label: 'Host / IP', placeholder: '192.168.1.10', required: true },
    { key: 'port', label: 'Port', placeholder: '502 (Modbus) / 4840 (OPC-UA)', type: 'number' },
    { key: 'timeout', label: 'Timeout (s)', placeholder: '5', type: 'number' },
    { key: 'tags', label: 'Tag List (comma-separated)', placeholder: 'temperature,pressure,flow_rate' },
  ],
  CMS: [
    { key: 'host', label: 'Host / IP', placeholder: 'mes.factory.local', required: true },
    { key: 'port', label: 'Port', placeholder: '8080', type: 'number' },
    { key: 'username', label: 'Username', placeholder: 'api_user', required: true },
    { key: 'password', label: 'Password', placeholder: '••••••••', type: 'password' },
    { key: 'api_prefix', label: 'API Prefix', placeholder: '/api/v1' },
  ],
  IoT: [
    { key: 'broker_host', label: 'MQTT Broker Host', placeholder: 'mqtt.factory.local', required: true },
    { key: 'broker_port', label: 'Broker Port', placeholder: '1883', type: 'number' },
    { key: 'topics', label: 'Topics (comma-separated)', placeholder: 'sensors/+/temperature,sensors/+/pressure', required: true },
    { key: 'client_id', label: 'Client ID', placeholder: 'paaim-agent-001' },
    { key: 'username', label: 'Username (optional)', placeholder: 'mqtt_user' },
    { key: 'password', label: 'Password (optional)', placeholder: '••••••••', type: 'password' },
  ],
  REST_API: [
    { key: 'base_url', label: 'Base URL', placeholder: 'https://api.factory.com', required: true },
    { key: 'api_key', label: 'API Key', placeholder: 'Bearer token or key', type: 'password' },
    { key: 'endpoint', label: 'Data Endpoint', placeholder: '/api/sensors/latest' },
    { key: 'poll_interval', label: 'Poll Interval (s)', placeholder: '30', type: 'number' },
  ],
  DATABASE: [
    { key: 'connection_string', label: 'Connection String', placeholder: 'postgresql://user:pass@host:5432/db', required: true, type: 'password' },
    { key: 'query', label: 'SQL Query', placeholder: 'SELECT * FROM sensor_readings WHERE timestamp > NOW() - INTERVAL 1 MINUTE' },
    { key: 'poll_interval', label: 'Poll Interval (s)', placeholder: '60', type: 'number' },
  ],
};

const SOURCE_DESCRIPTIONS: Record<string, string> = {
  SCADA: 'Modbus TCP / OPC-UA — reads register tags from PLCs and DCS systems',
  CMS: 'Manufacturing Execution System — fetches production orders and work orders',
  IoT: 'MQTT / CoAP broker — subscribes to sensor topic streams in real time',
  REST_API: 'Generic HTTP polling — calls any JSON REST endpoint on a schedule',
  DATABASE: 'Direct SQL query — polls a time-series or relational database',
};

type ConnStatus = 'idle' | 'testing' | 'ok' | 'failed';

type DatasourceEntry = {
  name: string;
  type: string;
  config: Record<string, string>;
  connStatus: ConnStatus;
  connMessage: string;
};

export default function CustomAgentBuilder() {
  const [step, setStep] = useState<'list' | 'create' | 'detail'>('list');
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [formData, setFormData] = useState<{
    name: string;
    description: string;
    domain: string;
    datasources: DatasourceEntry[];
    watchSignals: string[];
    scope: { type: 'all' | 'machines' | 'zone'; machines: string[]; zone: string };
    rules: { field: string; operator: string; value: string; action: string; priority: number }[];
    actions: string[];
  }>({
    name: '',
    description: '',
    domain: '',
    datasources: [{ name: '', type: 'SCADA', config: {}, connStatus: 'idle', connMessage: '' }],
    watchSignals: [],
    scope: { type: 'all', machines: [], zone: '' },
    rules: [{ field: '', operator: '>', value: '', action: '', priority: 1 }],
    actions: [],
  });

  const { data: agentsData, refetch, isLoading } = useCustomAgents();
  const createMutation = useCustomAgentMutation();
  const testConnMutation = useTestConnectionBeforeCreate();

  const agents = agentsData?.agents || [];

  // ── Live signal watchers (stream agents) — attach a monitor to a signal ──
  const [signals, setSignals] = useState<SignalMeta[]>([]);
  const [streamAgents, setStreamAgents] = useState<Record<string, StreamAgentStatus>>({});
  const [attachBusy, setAttachBusy] = useState(false);

  useEffect(() => {
    fetch(`${STREAM_BASE}/signals`).then((r) => r.json())
      .then((d) => setSignals(d.signals ?? [])).catch(() => {});
  }, []);
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch(`${API_BASE}/stream-agents`);
        const d = await r.json();
        if (!alive) return;
        const map: Record<string, StreamAgentStatus> = {};
        for (const a of d.agents ?? []) map[a.key] = a;
        setStreamAgents(map);
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // Canonical signals (for agents to watch) + machines (for scope)
  const [vocabSignals, setVocabSignals] = useState<{ signal: string; unit: string; event_type: string }[]>([]);
  const [machines, setMachines] = useState<{ id: string; name: string; zone_id?: string }[]>([]);
  useEffect(() => {
    fetch(`${API_BASE}/normalization/vocab`).then((r) => r.json()).then((d) => setVocabSignals(d.signals ?? [])).catch(() => {});
    fetch(`${API_BASE}/knowledge/context/factory_001/machines`).then((r) => r.json()).then((d) => setMachines(d.machines ?? [])).catch(() => {});
  }, []);
  const zones = Array.from(new Set(machines.map((m) => m.zone_id).filter(Boolean))) as string[];

  const attachWatcher = async (machine_id: string, signal: string) => {
    setAttachBusy(true);
    try { await fetch(`${API_BASE}/stream-agents/connect?machine_id=${machine_id}&signal=${signal}&trigger_level=warning`, { method: 'POST' }); } catch {}
    setAttachBusy(false);
  };
  const detachWatcher = async (machine_id: string, signal: string) => {
    setAttachBusy(true);
    try { await fetch(`${API_BASE}/stream-agents/disconnect/${machine_id}/${signal}`, { method: 'POST' }); } catch {}
    setAttachBusy(false);
  };
  const attachAll = async () => {
    setAttachBusy(true);
    try { await fetch(`${API_BASE}/stream-agents/auto-connect?trigger_level=warning`, { method: 'POST' }); } catch {}
    setAttachBusy(false);
  };

  const handleAddDataSource = () => {
    setFormData({
      ...formData,
      datasources: [
        ...formData.datasources,
        { name: '', type: 'SCADA', config: {}, connStatus: 'idle', connMessage: '' },
      ],
    });
  };

  const handleDsTypeChange = (idx: number, newType: string) => {
    const newDs = [...formData.datasources];
    newDs[idx] = { ...newDs[idx], type: newType, config: {}, connStatus: 'idle', connMessage: '' };
    setFormData({ ...formData, datasources: newDs });
  };

  const handleDsConfigChange = (idx: number, key: string, value: string) => {
    const newDs = [...formData.datasources];
    newDs[idx] = {
      ...newDs[idx],
      config: { ...newDs[idx].config, [key]: value },
      connStatus: 'idle',
      connMessage: '',
    };
    setFormData({ ...formData, datasources: newDs });
  };

  const handleTestConnection = async (idx: number) => {
    const ds = formData.datasources[idx];
    const newDs = [...formData.datasources];
    newDs[idx] = { ...newDs[idx], connStatus: 'testing', connMessage: '' };
    setFormData((prev) => ({ ...prev, datasources: newDs }));

    try {
      const result = await testConnMutation.mutateAsync({
        name: ds.name || 'test',
        type: ds.type,
        config: ds.config,
      });
      setFormData((prev) => {
        const updated = [...prev.datasources];
        updated[idx] = {
          ...updated[idx],
          connStatus: result.success ? 'ok' : 'failed',
          connMessage: result.message,
        };
        return { ...prev, datasources: updated };
      });
    } catch {
      setFormData((prev) => {
        const updated = [...prev.datasources];
        updated[idx] = { ...updated[idx], connStatus: 'failed', connMessage: 'Connection test failed' };
        return { ...prev, datasources: updated };
      });
    }
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

    if (!formData.name || !formData.domain || formData.watchSignals.length === 0) {
      alert('Give the agent a name, a domain, and at least one signal to watch');
      return;
    }

    const scope =
      formData.scope.type === 'machines' ? { type: 'machines', machines: formData.scope.machines }
      : formData.scope.type === 'zone' ? { type: 'zone', zone: formData.scope.zone }
      : { type: 'all' };

    try {
      await createMutation.mutateAsync({
        name: formData.name,
        description: formData.description,
        domain: formData.domain,
        watch_signals: formData.watchSignals,
        scope,
        data_sources: [],
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
        datasources: [{ name: '', type: 'SCADA', config: {}, connStatus: 'idle', connMessage: '' }],
        watchSignals: [],
        scope: { type: 'all', machines: [], zone: '' },
        rules: [{ field: '', operator: '>', value: '', action: '', priority: 1 }],
        actions: [],
      });
    } catch (err) {
      console.error('Failed to create agent:', err);
      alert('Failed to create agent');
    }
  };

  if (step === 'list') {
    const attachedList = Object.values(streamAgents);
    const connectedCount = attachedList.filter((a) => a.connected).length;
    const totalRaised = attachedList.reduce((n, a) => n + (a.events_raised || 0), 0);
    const key = (m: string, s: string) => `${m}::${s}`;

    return (
      <div className="max-w-[1180px] space-y-8">
        {/* Header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <Eyebrow>The watchers</Eyebrow>
            <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Monitors</h1>
            <p className="text-[13px] text-dim mt-0.5">Every watchdog on your factory — built-in specialists, live-signal watchers, and your own custom monitors.</p>
          </div>
          <button onClick={() => setStep('create')} className="btn-primary flex items-center gap-1.5 px-4 py-2 text-[13px]">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New custom monitor
          </button>
        </div>

        {/* ── Built-in monitors ── */}
        <section>
          <SectionHeader eyebrow="Always on" title="Built-in" accent="specialist monitors" sub="Five core watchers that review every incident through the orchestration pipeline." />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {BUILT_IN_MONITORS.map((m) => (
              <Card key={m.name} className="p-3.5">
                <div className="flex items-center justify-between mb-2">
                  <span className="relative flex w-1.5 h-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pine-2 opacity-50" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-pine-2" />
                  </span>
                  <span className="font-mono text-[9px] text-pine-2 uppercase tracking-wide">Live</span>
                </div>
                <p className="text-[13px] font-bold text-ink leading-tight">{m.name.replace(' Monitor', '')}</p>
                <p className="text-[11px] text-dim mt-1 leading-snug">{m.watches}</p>
              </Card>
            ))}
          </div>
        </section>

        {/* ── Live signal watchers (attach to signal) ── */}
        <section>
          <SectionHeader
            eyebrow="Live signal watchers"
            title="Attach a watcher"
            accent="to a live signal"
            sub="Point a watcher at a streaming sensor. It fires an event into the pipeline the moment the signal breaches its threshold."
            right={
              <div className="flex items-center gap-2">
                <SignalPill tone={connectedCount ? 'ok' : 'neutral'}>{connectedCount} watching · {totalRaised} raised</SignalPill>
                <button onClick={attachAll} disabled={attachBusy} className="btn-ghost px-3 py-1.5 text-[12px] disabled:opacity-50">Attach all</button>
              </div>
            }
          />
          {signals.length === 0 ? (
            <Card className="p-6 text-center">
              <p className="text-[13px] text-dim">No live signals — start <span className="font-mono">factory-stream</span> on {STREAM_BASE.replace(/^https?:\/\//, '')} to attach watchers.</p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {signals.map((s) => {
                const a = streamAgents[key(s.machine_id, s.signal)];
                const on = a?.connected;
                return (
                  <Card key={key(s.machine_id, s.signal)} className="p-3.5 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-ink truncate">{s.label}</p>
                      <p className="font-mono text-[11px] text-dim truncate">{s.machine_id}</p>
                    </div>
                    {on ? (
                      <div className="flex items-center gap-2 shrink-0">
                        <SignalPill tone="ok">{a.events_raised} raised</SignalPill>
                        <button onClick={() => detachWatcher(s.machine_id, s.signal)} disabled={attachBusy} className="text-[12px] font-semibold text-dim hover:text-coral disabled:opacity-50">Detach</button>
                      </div>
                    ) : (
                      <button onClick={() => attachWatcher(s.machine_id, s.signal)} disabled={attachBusy} className="btn-ghost px-3 py-1.5 text-[12px] shrink-0 disabled:opacity-50">Attach</button>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </section>

        {/* ── Custom monitors ── */}
        <section>
          <SectionHeader eyebrow="Your monitors" title="Custom" accent="monitors" sub="No-code watchdogs you build from your own data sources and rules." />
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-44 bg-card border border-line rounded-card animate-pulse" />)}
            </div>
          ) : agents.length === 0 ? (
            <Card className="p-12 text-center">
              <h3 className="text-[14px] font-bold text-ink mb-1">No custom monitors yet</h3>
              <p className="text-[13px] text-dim mb-5 max-w-sm mx-auto">Connect SCADA, MES, MQTT or REST sources, define if/then rules, and let PAAIM govern the decisions.</p>
              <button onClick={() => setStep('create')} className="btn-primary px-6 py-2.5 text-[13px]">Create first monitor</button>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map((agent: any) => {
                const sourceTypes = (agent.data_sources || []).map((s: any) => s.type?.toUpperCase()).filter(Boolean);
                return (
                  <Card key={agent.id} className="p-5 hover:border-moss transition-colors cursor-pointer group" onClick={() => { setSelectedAgent(agent); setStep('detail'); }}>
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-surface-ok border border-moss shrink-0 font-mono text-[13px] font-bold text-pine-2">
                          {(agent.name || '?').slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-[14px] font-bold text-ink group-hover:text-pine-2 transition-colors leading-tight truncate">{agent.name}</h3>
                          <p className="font-mono text-[10px] text-dim mt-0.5 uppercase tracking-wide">{agent.domain}</p>
                        </div>
                      </div>
                      <SignalPill tone={agent.enabled ? 'ok' : 'neutral'}>{agent.enabled ? 'Active' : 'Off'}</SignalPill>
                    </div>

                    <p className="text-[12px] text-dim mb-4 line-clamp-2 leading-relaxed">{agent.description}</p>

                    <div className="grid grid-cols-3 gap-2 mb-3">
                      {[
                        { v: agent.data_sources_count || 0, l: 'Sources' },
                        { v: agent.rules_count || 0, l: 'Rules' },
                        { v: agent.actions?.length || 0, l: 'Actions' },
                      ].map((x) => (
                        <div key={x.l} className="bg-paper border border-line rounded-lg p-2 text-center">
                          <p className="font-mono text-[15px] font-bold text-ink">{x.v}</p>
                          <p className="font-mono text-[9px] text-dim uppercase tracking-wide">{x.l}</p>
                        </div>
                      ))}
                    </div>

                    {sourceTypes.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-3">
                        {sourceTypes.slice(0, 3).map((t: string) => (
                          <span key={t} className="font-mono text-[10px] font-bold text-dim bg-paper border border-line px-1.5 py-0.5 rounded uppercase tracking-wide">{t}</span>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-3 border-t border-line">
                      <span className="font-mono text-[10px] text-dim uppercase tracking-wide">
                        {agent.enabled ? 'Running' : 'Paused'}
                      </span>
                      <span className="text-[12px] text-pine-2 font-semibold group-hover:underline">Configure →</span>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </section>
      </div>
    );
  }

  if (step === 'detail' && selectedAgent) {
    const agent = selectedAgent;
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <button
              onClick={() => { setStep('list'); setSelectedAgent(null); }}
              className="text-pine-2 hover:text-pine-2 font-semibold mb-2 inline-flex items-center gap-1.5 text-sm"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
              Back to Agents
            </button>
            <p className="text-sm text-dim">{agent.description}</p>
          </div>
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${agent.enabled ? 'bg-surface-ok text-pine-2 border-moss' : 'bg-paper text-dim border-line'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${agent.enabled ? 'bg-surface-ok0' : 'bg-paper'}`} />
            {agent.enabled ? 'Active' : 'Disabled'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Info */}
          <div className="bg-white border border-line rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-line bg-paper/60">
              <h2 className="text-sm font-semibold text-ink">Agent Info</h2>
            </div>
            <div className="p-5 space-y-3">
            {[
              { label: 'ID', value: agent.id },
              { label: 'Domain', value: agent.domain },
              { label: 'Data Sources', value: agent.data_sources_count ?? agent.data_sources?.length ?? 0 },
              { label: 'Rules', value: agent.rules_count ?? agent.rules?.length ?? 0 },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between text-sm border-b border-line pb-2 last:border-0">
                <span className="text-dim font-medium">{label}</span>
                <span className="text-ink font-semibold font-mono text-xs">{String(value)}</span>
              </div>
            ))}
            </div>
          </div>

          {/* Data Sources */}
          <div className="bg-white border border-line rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-line bg-paper/60">
              <h2 className="text-sm font-semibold text-ink">Data Sources</h2>
            </div>
            <div className="p-5">
            {agent.data_sources && agent.data_sources.length > 0 ? (
              <div className="space-y-2">
                {agent.data_sources.map((ds: any, i: number) => (
                  <div key={i} className="flex items-center justify-between bg-paper border border-line rounded-lg px-3 py-2 text-sm">
                    <span className="font-medium text-ink">{ds.name}</span>
                    <span className="bg-surface-ok text-pine-2 border border-moss px-2 py-0.5 rounded text-xs font-semibold uppercase">{ds.type}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-dim text-sm">No data source details available</p>
            )}
            </div>
          </div>

          {/* Rules */}
          <div className="bg-white border border-line rounded-xl shadow-sm overflow-hidden md:col-span-2">
            <div className="px-5 py-3 border-b border-line bg-paper/60">
              <h2 className="text-sm font-semibold text-ink">Decision Rules</h2>
            </div>
            <div className="p-5">
            {agent.rules && agent.rules.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line bg-paper/60 text-left text-dim">
                      <th className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide">Field</th>
                      <th className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide">Op</th>
                      <th className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide">Value</th>
                      <th className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide">Action</th>
                      <th className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide text-right">Confidence</th>
                      <th className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide text-right">Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agent.rules.map((rule: any, i: number) => (
                      <tr key={i} className="border-b border-line last:border-0 hover:bg-paper/60">
                        <td className="px-3 py-2 font-mono text-pine-2 text-xs">{rule.field}</td>
                        <td className="px-3 py-2 font-mono text-dim text-xs">{rule.operator}</td>
                        <td className="px-3 py-2 font-mono text-ink text-xs">{String(rule.value)}</td>
                        <td className="px-3 py-2 font-semibold text-ink text-xs">{rule.action}</td>
                        <td className="px-3 py-2 text-right text-pine-2 font-semibold text-xs">{((rule.confidence ?? 0.8) * 100).toFixed(0)}%</td>
                        <td className="px-3 py-2 text-right text-dim text-xs">{rule.priority ?? 1}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-dim text-sm">No rule details available</p>
            )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => setStep('list')}
          className="text-pine-2 hover:text-pine-2 font-semibold mb-3 inline-flex items-center gap-1.5 text-sm"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
          Back to Agents
        </button>
        <p className="text-sm text-dim">
          Connect to manufacturing systems and define intelligent decision rules
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Section 1: Basic Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl border border-line shadow-sm overflow-hidden"
        >
          <div className="px-5 py-3 border-b border-line bg-paper/60 flex items-center gap-3">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-pine-2 text-white text-xs font-bold shrink-0">1</span>
            <h2 className="text-sm font-semibold text-ink">Basic Information</h2>
          </div>
          <div className="p-5">

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-ink mb-2">
                Agent Name <span className="text-coral">*</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Thermal Management Agent"
                className="w-full border border-line rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-pine-2/30"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-ink mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="What does this agent do?"
                rows={3}
                className="w-full border border-line rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-pine-2/30"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-ink mb-2">
                Domain <span className="text-coral">*</span>
              </label>
              <select
                value={formData.domain}
                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                className="w-full border border-line rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-pine-2/30"
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
          </div>
        </motion.div>

        {/* Section 2: What to watch (signals + scope) */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-xl border border-line shadow-sm overflow-hidden"
        >
          <div className="px-5 py-3 border-b border-line bg-paper/60 flex items-center gap-3">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-pine-2 text-white text-xs font-bold shrink-0">2</span>
            <div>
              <h2 className="text-sm font-semibold text-ink">What to watch</h2>
              <p className="text-[10px] text-dim mt-0.5">Pick the canonical signals and which machines. One agent covers the whole fleet — no need to duplicate per machine.</p>
            </div>
          </div>
          <div className="p-5 space-y-5">
            {/* Signals */}
            <div>
              <label className="block font-mono text-[10px] text-dim uppercase tracking-wide mb-2">Signals to watch <span className="text-coral">*</span></label>
              <div className="flex flex-wrap gap-2">
                {vocabSignals.map((v) => {
                  const on = formData.watchSignals.includes(v.signal);
                  return (
                    <button
                      key={v.signal}
                      type="button"
                      onClick={() => setFormData((f) => ({ ...f, watchSignals: on ? f.watchSignals.filter((s) => s !== v.signal) : [...f.watchSignals, v.signal] }))}
                      className={`font-mono text-[12px] px-2.5 py-1 rounded-lg border transition-colors ${on ? 'bg-pine-2 text-white border-pine-2' : 'bg-card text-dim border-line hover:border-moss'}`}
                    >
                      {v.signal}<span className={`ml-1 ${on ? 'text-sage' : 'text-dim'}`}>{v.unit}</span>
                    </button>
                  );
                })}
                {vocabSignals.length === 0 && <span className="text-[12px] text-dim">Loading signals… (start the backend)</span>}
              </div>
            </div>

            {/* Scope */}
            <div>
              <label className="block font-mono text-[10px] text-dim uppercase tracking-wide mb-2">Across which machines</label>
              <div className="flex gap-2 mb-3">
                {([['all', 'All machines'], ['machines', 'Specific machines'], ['zone', 'A zone']] as const).map(([t, label]) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setFormData((f) => ({ ...f, scope: { ...f.scope, type: t } }))}
                    className={`text-[13px] font-semibold px-3 py-1.5 rounded-lg border transition-colors ${formData.scope.type === t ? 'bg-surface-ok text-pine-2 border-moss' : 'bg-card text-dim border-line hover:border-moss'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {formData.scope.type === 'all' && (
                <p className="text-[12px] text-dim">This agent watches the selected signals on <span className="font-semibold text-pine-2">every machine</span>, now and any added later.</p>
              )}

              {formData.scope.type === 'machines' && (
                <div className="flex flex-wrap gap-2">
                  {machines.map((m) => {
                    const on = formData.scope.machines.includes(m.id);
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setFormData((f) => ({ ...f, scope: { ...f.scope, machines: on ? f.scope.machines.filter((x) => x !== m.id) : [...f.scope.machines, m.id] } }))}
                        className={`text-[12px] px-2.5 py-1 rounded-lg border transition-colors ${on ? 'bg-pine-2 text-white border-pine-2' : 'bg-card text-dim border-line hover:border-moss'}`}
                      >
                        {m.name} <span className="font-mono opacity-70">{m.id}</span>
                      </button>
                    );
                  })}
                  {machines.length === 0 && <span className="text-[12px] text-dim">No machines loaded.</span>}
                </div>
              )}

              {formData.scope.type === 'zone' && (
                <select
                  value={formData.scope.zone}
                  onChange={(e) => setFormData((f) => ({ ...f, scope: { ...f.scope, zone: e.target.value } }))}
                  className="border border-line rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss"
                >
                  <option value="">Select a zone…</option>
                  {zones.map((z) => <option key={z} value={z}>{z}</option>)}
                </select>
              )}
            </div>
          </div>
        </motion.div>

        {/* Section 3: Decision Rules */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-xl border border-line shadow-sm overflow-hidden"
        >
          <div className="px-5 py-3 border-b border-line bg-paper/60 flex items-center gap-3">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-pine-2 text-white text-xs font-bold shrink-0">3</span>
            <div>
              <h2 className="text-sm font-semibold text-ink">Define Decision Rules</h2>
              <p className="text-[10px] text-dim mt-0.5">If [field] [operator] [value] → then [action]</p>
            </div>
          </div>
          <div className="p-5">
          <div className="space-y-4">
            {formData.rules.map((rule, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="border border-line rounded-lg p-6 bg-paper"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="font-semibold text-ink">Rule {idx + 1}</h3>
                  {formData.rules.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveRule(idx)}
                      className="text-coral hover:text-coral text-sm font-semibold"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <select
                    value={rule.field}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].field = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="border border-line rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-pine-2/30"
                  >
                    <option value="">Signal…</option>
                    {formData.watchSignals.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>

                  <select
                    value={rule.operator}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].operator = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="border border-line rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pine-2/30"
                  >
                    <option value="==">=</option>
                    <option value="!=">!=</option>
                    <option value=">">&gt;</option>
                    <option value="<">&lt;</option>
                    <option value=">=">&gt;=</option>
                    <option value="<=">&lt;=</option>
                    <option value="outside_normal">outside learned normal</option>
                    <option value="above_normal">above learned normal</option>
                  </select>

                  <input
                    type="text"
                    placeholder={rule.operator.includes('normal') ? 'σ (blank = learned band)' : 'Value'}
                    value={rule.value}
                    onChange={(e) => {
                      const newRules = [...formData.rules];
                      newRules[idx].value = e.target.value;
                      setFormData({ ...formData, rules: newRules });
                    }}
                    className="border border-line rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pine-2/30"
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
                    className="col-span-2 md:col-span-1 border border-line rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pine-2/30"
                  />
                </div>
              </motion.div>
            ))}
          </div>

          <button
            type="button"
            onClick={handleAddRule}
            className="mt-4 text-pine-2 hover:text-pine-2 font-semibold text-sm inline-flex items-center gap-2"
          >
            + Add Another Rule
          </button>
          </div>
        </motion.div>

        {/* Section 4: Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-white rounded-xl border border-line shadow-sm overflow-hidden"
        >
          <div className="px-5 py-3 border-b border-line bg-paper/60 flex items-center gap-3">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-pine-2 text-white text-xs font-bold shrink-0">4</span>
            <div>
              <h2 className="text-sm font-semibold text-ink">Possible Actions</h2>
              <p className="text-[10px] text-dim mt-0.5">All actions this agent can recommend</p>
            </div>
          </div>
          <div className="p-5">
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              id="actionInput"
              placeholder="e.g., activate_cooling"
              className="flex-1 border border-line rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/30"
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
              className="bg-pine-2 hover:bg-pine text-white font-semibold px-6 py-2 rounded-lg"
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
                className="bg-surface-ok text-pine-2 px-4 py-2 rounded-full flex items-center gap-2 font-semibold"
              >
                {action}
                <button
                  type="button"
                  onClick={() => handleRemoveAction(action)}
                  className="text-pine-2 hover:text-pine-2 font-bold"
                >
                  ✕
                </button>
              </motion.div>
            ))}
          </div>
          </div>
        </motion.div>

        {/* Submit Buttons */}
        <div className="flex gap-3 pb-4">
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-pine-2 hover:bg-pine disabled:opacity-60 text-white font-semibold py-2.5 px-6 rounded-lg text-sm transition-colors shadow-sm"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Agent'}
          </button>
          <button
            type="button"
            onClick={() => setStep('list')}
            className="bg-paper hover:bg-line text-ink font-semibold py-2.5 px-6 rounded-lg text-sm transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
