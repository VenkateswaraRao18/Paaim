'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useCustomAgentMutation, useCustomAgents, useTestConnectionBeforeCreate } from '@/lib/api-client';
import { Eyebrow, SectionHeader, Card, SignalPill } from '@/components/ui';

// PAAIM backend. Note there is no feed URL here: the browser must never talk to
// a plant's SCADA directly, and a hardcoded one made this page list machines
// from a plant nobody had connected.
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
  key: string; machine_id: string; signal: string; label: string; source_id: string;
  connected: boolean; events_raised: number; last_status: string;
  last_value: number | null; unit: string; judged_by: string;
};

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

/** Say an agent's scope the way an operator would. */
function scopeText(scope: any): string {
  const t = scope?.type ?? 'all';
  if (t === 'machines') {
    const m = scope?.machines ?? [];
    return m.length ? m.join(', ') : 'No machines selected';
  }
  if (t === 'zone') return scope?.zone ? `Zone: ${scope.zone}` : 'No zone selected';
  return 'Every machine in the plant';
}

export default function CustomAgentBuilder() {
  const [step, setStep] = useState<'list' | 'create' | 'detail'>('list');
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  // Set while editing an existing agent; drives PUT-vs-POST on save.
  const [editingId, setEditingId] = useState<string | null>(null);
  // Which sources actually reach the open agent (derived server-side).
  const [agentSources, setAgentSources] = useState<any>(null);
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

  // ── Live signal watchers — read-only ──
  // Watchers are not created here. They are derived from a data source's
  // confirmed mapping: tick a field to watch on Data Sources and one appears.
  // This page used to offer an "Attach" button that made a watcher directly
  // from the feed's tag list, skipping the mapping — so it had nothing to
  // translate its raw tag with, and silently dropped every event it judged.
  const [streamAgents, setStreamAgents] = useState<Record<string, StreamAgentStatus>>({});

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

    const body = {
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
    };

    try {
      if (editingId) {
        // Edit in place — keeps the agent's id and history.
        const r = await fetch(`${API_BASE}/custom-agents/${editingId}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...body, enabled: true }),
        });
        if (!r.ok) throw new Error(await r.text());
      } else {
        await createMutation.mutateAsync(body);
      }

      refetch();
      setEditingId(null);
      setSelectedAgent(null);
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
      console.error('Failed to save agent:', err);
      alert(editingId ? 'Failed to update monitor' : 'Failed to create agent');
    }
  };

  /** An agent names signals, not sources — ask the backend which sources
   *  actually reach it, so "where does my data come from" is answerable. */
  const openAgent = (agent: any) => {
    setSelectedAgent(agent);
    setAgentSources(null);
    setStep('detail');
    fetch(`${API_BASE}/custom-agents/${agent.id}/sources`)
      .then((r) => r.json()).then(setAgentSources).catch(() => {});
  };

  /** Load an existing agent back into the builder so it can be tuned. */
  const startEdit = (agent: any) => {
    setEditingId(agent.id);
    setFormData({
      name: agent.name ?? '',
      description: agent.description ?? '',
      domain: agent.domain ?? '',
      datasources: [{ name: '', type: 'SCADA', config: {}, connStatus: 'idle', connMessage: '' }],
      watchSignals: agent.watch_signals ?? [],
      scope: {
        type: agent.scope?.type ?? 'all',
        machines: agent.scope?.machines ?? [],
        zone: agent.scope?.zone ?? '',
      },
      rules: (agent.rules?.length ? agent.rules : [{ field: '', operator: '>', value: '', action: '', priority: 1 }])
        .map((r: any) => ({
          field: r.field ?? '', operator: r.operator ?? '>',
          value: String(r.value ?? ''), action: r.action ?? '', priority: r.priority ?? 1,
        })),
      actions: agent.actions ?? [],
    });
    setStep('create');
  };

  if (step === 'list') {
    const attachedList = Object.values(streamAgents);
    const connectedCount = attachedList.filter((a) => a.connected).length;
    const totalRaised = attachedList.reduce((n, a) => n + (a.events_raised || 0), 0);

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

        {/* ── Live signal watchers — derived from your data sources, read-only ── */}
        <section>
          <SectionHeader
            eyebrow="Live signal watchers"
            title="Watching"
            accent="your connected sources"
            sub="One watcher per field you ticked to watch on a data source. They judge each reading against the machine's own normal — no AI, no rules. A breach is what wakes the monitors below."
            right={<SignalPill tone={connectedCount ? 'ok' : 'neutral'}>{connectedCount} watching · {totalRaised} raised</SignalPill>}
          />
          {attachedList.length === 0 ? (
            <Card className="p-8 text-center">
              <p className="text-[14px] font-semibold text-ink">No watchers yet</p>
              <p className="text-[13px] text-dim mt-1 max-w-md mx-auto">
                Watchers aren&apos;t created here — they appear when you connect a data source
                and tick which of its fields to watch.
              </p>
              <a href="/data-sources" className="btn-primary inline-flex px-4 py-2 text-[13px] mt-4">
                Connect a data source
              </a>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {attachedList.map((a) => {
                const tone = a.last_status === 'critical' ? 'bad'
                  : a.last_status === 'warning' ? 'warn'
                  : a.connected ? 'ok' : 'neutral';
                return (
                  <Card key={a.key} className="p-3.5">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="min-w-0">
                        <p className="text-[13px] font-semibold text-ink truncate">{a.label}</p>
                        <p className="font-mono text-[11px] text-dim truncate">{a.machine_id} · {a.signal}</p>
                      </div>
                      <SignalPill tone={tone}>{a.connected ? (a.last_status ?? 'live') : 'offline'}</SignalPill>
                    </div>
                    <div className="flex items-end justify-between">
                      <span className="font-mono text-[18px] font-semibold text-ink">
                        {a.last_value ?? '—'}<span className="text-[12px] text-dim ml-0.5">{a.unit}</span>
                      </span>
                      <span className="text-[11px] text-dim">{a.events_raised} raised</span>
                    </div>
                    {/* Which yardstick — a fresh plant has no learned normal yet,
                        and that is worth seeing rather than discovering later. */}
                    <p className="text-[10px] text-dim mt-2 font-mono truncate">
                      via {a.source_id} · judged by {a.judged_by}
                    </p>
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
                  <Card key={agent.id} className="p-5 hover:border-moss transition-colors cursor-pointer group" onClick={() => openAgent(agent)}>
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
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={() => startEdit(agent)} className="btn-ghost px-3.5 py-1.5 text-[13px]">
              Edit monitor
            </button>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${agent.enabled ? 'bg-surface-ok text-pine-2 border-moss' : 'bg-paper text-dim border-line'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${agent.enabled ? 'bg-surface-ok0' : 'bg-paper'}`} />
              {agent.enabled ? 'Active' : 'Disabled'}
            </span>
          </div>
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
              { label: 'Scope', value: scopeText(agent.scope) },
              { label: 'Rules', value: agent.rules_count ?? agent.rules?.length ?? 0 },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between text-sm border-b border-line pb-2 last:border-0">
                <span className="text-dim font-medium">{label}</span>
                <span className="text-ink font-semibold font-mono text-xs">{String(value)}</span>
              </div>
            ))}
            </div>
          </div>

          {/* What it watches — an agent is defined by its signals and scope, not
              by a data source: any source mapped to these signals feeds it. */}
          <div className="bg-white border border-line rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-line bg-paper/60">
              <h2 className="text-sm font-semibold text-ink">What it watches</h2>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-2">Signals</p>
                {agent.watch_signals?.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {agent.watch_signals.map((s: string) => (
                      <span key={s} className="font-mono text-[12px] bg-surface-ok text-pine-2 border border-moss px-2 py-0.5 rounded">{s}</span>
                    ))}
                  </div>
                ) : <p className="text-dim text-sm">No signals selected — this agent will never fire.</p>}
              </div>
              <div>
                <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-1">Machines</p>
                <p className="text-[13px] text-ink">{scopeText(agent.scope)}</p>
              </div>
              <div>
                <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-2">Actions it may recommend</p>
                {agent.actions?.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {agent.actions.map((a: string) => (
                      <span key={a} className="font-mono text-[12px] bg-paper text-dim border border-line px-2 py-0.5 rounded">{a}</span>
                    ))}
                  </div>
                ) : <p className="text-dim text-sm">Any allowed action (none restricted).</p>}
              </div>
            </div>
          </div>

          {/* Fed by — the source→signal link is derived, so show it rather than
              leaving the operator to guess where the data comes from. */}
          <div className="bg-white border border-line rounded-xl shadow-sm overflow-hidden md:col-span-2">
            <div className="px-5 py-3 border-b border-line bg-paper/60 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">Fed by</h2>
              {agentSources && (
                <SignalPill tone={agentSources.live_count > 0 ? 'ok' : 'warn'}>
                  {agentSources.live_count > 0 ? `${agentSources.live_count} live` : 'nothing live'}
                </SignalPill>
              )}
            </div>
            <div className="p-5">
              {!agentSources ? (
                <p className="text-dim text-sm">Loading…</p>
              ) : agentSources.sources?.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line bg-paper/60 text-left text-dim">
                        {['Source', 'Arrives as', 'Becomes', 'On machines', 'Status'].map((h) => (
                          <th key={h} className="px-3 pb-2 pt-1 font-semibold text-xs uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {agentSources.sources.map((s: any, i: number) => (
                        <tr key={i} className="border-b border-line last:border-0">
                          <td className="px-3 py-2 font-mono text-xs text-ink">{s.source_id}</td>
                          <td className="px-3 py-2 font-mono text-xs text-dim">{s.raw_field}</td>
                          <td className="px-3 py-2 font-mono text-xs text-pine-2">{s.signal}</td>
                          <td className="px-3 py-2 text-xs text-dim">{s.machines?.length ? s.machines.join(', ') : '—'}</td>
                          <td className="px-3 py-2">
                            <SignalPill tone={s.live ? 'ok' : 'warn'}>{s.live ? 'live' : 'not watched'}</SignalPill>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-dim text-sm">
                  No connected source maps to {agent.watch_signals?.length ? agent.watch_signals.join(' or ') : 'these signals'} yet —
                  this monitor will not fire until one does. Connect a source on Data Sources.
                </p>
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
          onClick={() => { setStep('list'); setEditingId(null); }}
          className="text-pine-2 hover:text-pine-2 font-semibold mb-3 inline-flex items-center gap-1.5 text-sm"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
          Back to Agents
        </button>
        <p className="text-sm text-dim">
          {editingId ? 'Tune this monitor — signals, scope, thresholds and actions' : 'Connect to manufacturing systems and define intelligent decision rules'}
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
            {createMutation.isPending ? 'Saving...' : editingId ? 'Save changes' : 'Create Agent'}
          </button>
          <button
            type="button"
            onClick={() => { setStep('list'); setEditingId(null); }}
            className="bg-paper hover:bg-line text-ink font-semibold py-2.5 px-6 rounded-lg text-sm transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
