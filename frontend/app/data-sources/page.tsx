'use client';

import { useEffect, useState } from 'react';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar } from '@/components/ui';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Vocab = { signal: string; unit: string; event_type: string; higher_is_worse?: boolean; description?: string };
type Pack = { pack_id: string; label: string; description: string; signal_count: number; signals: string[]; active: boolean };
type Row = {
  raw: string; signal: string; unit: string; transform: string; resolved_by: string;
  confidence: number; watch?: boolean;
  // What the source said this field is in, and what came of comparing that to
  // the signal's unit. A mapping is only right if the number arrives in the
  // unit the signal is defined in.
  source_unit?: string; unit_status?: string; unit_note?: string;
};
type SourceType = { type: string; label: string; endpoint_hint: string; supported: boolean; description: string; requires?: string };
type TestResult = { ok: boolean; detail: string; latency_ms?: number | null };

const SAMPLE = `{
  "device_id": "cnc_mill_01",
  "MTR03_TORQUE": 68.9,
  "temp_c": 42.1,
  "SpindleSpeed": 1412,
  "vib": 3.2,
  "tool_life": 226,
  "power_kw": 12.4,
  "aux_flag_7": 1
}`;

const tierTone = (by: string) => by === 'llm' ? 'warn' : by === 'heuristic' ? 'neutral' : 'ok';

// A mapping is only correct if the number arrives in the unit the signal is
// defined in. 'conflict' is the one verdict a human has to settle.
const unitTone = (s?: string) =>
  s === 'conflict' ? 'bad' : s === 'converted' ? 'ok' : s === 'unknown' ? 'warn' : 'neutral';

export default function DataSourcesPage() {
  const [vocab, setVocab] = useState<Vocab[]>([]);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [packBusy, setPackBusy] = useState(false);
  const [packWarning, setPackWarning] = useState<string | null>(null);
  const [saved, setSaved] = useState<any[]>([]);
  // Connected sources incl. their derived 'feeds' links.
  const [sources, setSources] = useState<any[]>([]);

  // connection (step 1)
  const [types, setTypes] = useState<SourceType[]>([]);
  const [connType, setConnType] = useState('sse_stream');
  const [endpoint, setEndpoint] = useState('http://localhost:9100');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [connected, setConnected] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoverNote, setDiscoverNote] = useState<string | null>(null);

  // onboarding form
  const [sourceId, setSourceId] = useState('factory_stream');
  const [machineField, setMachineField] = useState('machine_id');
  const [sampleText, setSampleText] = useState(SAMPLE);
  const [useLlm, setUseLlm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Units the source declared at discovery, carried into propose. Without them
  // the mapper can only assume the source already speaks the vocabulary's units.
  const [fieldUnits, setFieldUnits] = useState<Record<string, string>>({});

  // proposed/edited mapping
  const [rows, setRows] = useState<Row[] | null>(null);
  const [machineStrategy, setMachineStrategy] = useState('static');
  const [machineValue, setMachineValue] = useState('unknown');
  const [confirmed, setConfirmed] = useState(false);

  // ingest
  const [ingestSource, setIngestSource] = useState('');
  const [ingestText, setIngestText] = useState(SAMPLE);
  const [ingestResult, setIngestResult] = useState<any>(null);
  const [ingestBusy, setIngestBusy] = useState(false);

  const loadVocab = () => {
    fetch(`${API_BASE}/normalization/vocab`).then(r => r.json()).then(d => setVocab(d.signals ?? [])).catch(() => {});
    fetch(`${API_BASE}/normalization/vocab/packs`).then(r => r.json()).then(d => setPacks(d.packs ?? [])).catch(() => {});
  };

  /** Adopt a starter vocabulary. A plant that makes food should not be stuck
   *  with a machine shop's signals — and should never wait on a release. */
  const applyPack = async (pack_id: string) => {
    setPackBusy(true); setPackWarning(null);
    try {
      const r = await fetch(`${API_BASE}/normalization/vocab/pack`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack_id }),
      });
      const d = await r.json();
      // Mappings the operator already confirmed are never rewritten, so a pack
      // that drops a signal leaves them pointing at nothing. Say so.
      if (d.warning) {
        const which = (d.orphaned_mappings ?? []).slice(0, 3)
          .map((o: any) => `${o.raw_field} → ${o.signal}`).join(', ');
        setPackWarning(`${d.warning}${which ? ` (${which})` : ''}`);
      }
      loadVocab(); loadSaved();
    } catch {}
    setPackBusy(false);
  };

  const loadSaved = () => {
    fetch(`${API_BASE}/normalization/mappings`).then(r => r.json()).then(d => setSaved(d.mappings ?? [])).catch(() => {});
    fetch(`${API_BASE}/sources`).then(r => r.json()).then(d => setSources(d.sources ?? [])).catch(() => {});
  };
  useEffect(() => {
    loadVocab();
    fetch(`${API_BASE}/sources/types`).then(r => r.json()).then(d => setTypes(d.types ?? [])).catch(() => {});
    loadSaved();
  }, []);

  const activeType = types.find((t) => t.type === connType);
  const needsEndpoint = connType !== 'rest_push';

  /** Reach the source for real; nothing is saved unless it answers. */
  const testConnection = async () => {
    setTesting(true); setTestResult(null); setConnected(false); setDiscoverNote(null);
    try {
      const r = await fetch(`${API_BASE}/sources/test-connection`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: connType, endpoint }),
      });
      setTestResult(await r.json());
    } catch { setTestResult({ ok: false, detail: 'Could not reach the backend — is it running on :8000?' }); }
    setTesting(false);
  };

  /** Save the verified connection, then pull a live sample so the mapping is
   *  made against what the source actually sends. */
  const connectAndDiscover = async () => {
    setDiscovering(true); setErr(null); setDiscoverNote(null);
    try {
      const c = await fetch(`${API_BASE}/sources/connect`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, type: connType, endpoint }),
      });
      if (!c.ok) { const e = await c.json(); setErr(e.detail ?? 'Connection failed'); setDiscovering(false); return; }
      setConnected(true); loadSaved();

      const r = await fetch(`${API_BASE}/sources/discover`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: connType, endpoint }),
      });
      const d = await r.json();
      if (d.ok) {
        setSampleText(JSON.stringify(d.sample_payload, null, 2));
        if (d.machine_id_field) setMachineField(d.machine_id_field);
        setFieldUnits(d.field_units ?? {});
        setDiscoverNote(`${d.detail} Fields were read from the source — no typing needed.`);
      } else {
        setDiscoverNote(d.detail);
      }
    } catch { setErr('Could not reach the backend — is it running on :8000?'); }
    setDiscovering(false);
  };

  const propose = async () => {
    setErr(null); setConfirmed(false); setBusy(true); setRows(null);
    let payload: any;
    try { payload = JSON.parse(sampleText); } catch { setErr('Sample payload is not valid JSON'); setBusy(false); return; }
    try {
      const r = await fetch(`${API_BASE}/normalization/propose`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: sourceId, sample_payload: payload,
          machine_id_field: machineField || null, use_llm: useLlm,
          field_units: fieldUnits,
        }),
      });
      const d = await r.json();
      setMachineStrategy(d.machine_id_strategy); setMachineValue(d.machine_id_value);
      const mapped: Row[] = Object.values(d.fields || {}).map((f: any) => ({ ...f }));
      const unmapped: Row[] = (d.unmapped || []).map((raw: string) => ({ raw, signal: '', unit: '', transform: 'identity', resolved_by: 'unmapped', confidence: 0 }));
      setRows([...mapped, ...unmapped].sort((a, b) => a.raw.localeCompare(b.raw)));
    } catch { setErr('Could not reach the backend — is it running on :8000?'); }
    setBusy(false);
  };

  /** Re-settle the unit whenever the operator picks a different signal. The
   *  transform belongs to the pair (source unit, signal unit) — carrying the old
   *  one onto a new signal is how °C ends up converted into Kelvin twice, or
   *  not at all. The backend owns the conversion table. */
  const changeSignal = async (raw: string, signal: string) => {
    const v = vocab.find((x) => x.signal === signal);
    setRows((rs) => rs!.map((r) => r.raw !== raw ? r : {
      ...r, signal, unit: v?.unit ?? '',
      resolved_by: signal ? 'manual' : 'unmapped', confidence: signal ? 1 : 0,
    }));
    if (!signal) return;
    try {
      const res = await fetch(`${API_BASE}/normalization/reconcile`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal, source_unit: fieldUnits[raw] ?? '' }),
      });
      const d = await res.json();
      setRows((rs) => rs!.map((r) => r.raw !== raw ? r : {
        ...r, unit: d.unit, transform: d.transform,
        source_unit: d.source_unit, unit_status: d.unit_status, unit_note: d.unit_note,
      }));
    } catch {}
  };

  const confirm = async () => {
    setErr(null); setBusy(true);
    const fields: Record<string, Row> = {};
    const unmapped: string[] = [];
    rows!.forEach((r) => { if (r.signal) fields[r.raw] = r; else unmapped.push(r.raw); });
    const mapping = { source_id: sourceId, machine_id_strategy: machineStrategy, machine_id_value: machineValue, fields, unmapped, confirmed: true };
    try {
      const r = await fetch(`${API_BASE}/normalization/confirm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mapping }) });
      if (!r.ok) throw new Error();
      setConfirmed(true); setIngestSource(sourceId); loadSaved();
    } catch { setErr('Failed to save mapping'); }
    setBusy(false);
  };

  const runIngest = async () => {
    setIngestBusy(true); setIngestResult(null);
    let payload: any;
    try { payload = JSON.parse(ingestText); } catch { setIngestResult({ error: 'Invalid JSON' }); setIngestBusy(false); return; }
    try {
      const r = await fetch(`${API_BASE}/normalization/ingest`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source_id: ingestSource, payload }) });
      setIngestResult(await r.json());
    } catch { setIngestResult({ error: 'Ingest failed' }); }
    setIngestBusy(false);
  };

  const mappedCount = rows?.filter((r) => r.signal).length ?? 0;
  const unmappedCount = rows?.filter((r) => !r.signal).length ?? 0;
  const conflictCount = rows?.filter((r) => r.signal && r.unit_status === 'conflict').length ?? 0;
  const noUnitCount = rows?.filter((r) => r.signal && r.unit_status === 'unknown').length ?? 0;

  return (
    <div className="max-w-[1180px] space-y-6">
      <div>
        <Eyebrow>Ingestion · onboarding</Eyebrow>
        <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Data Sources</h1>
        <p className="text-[13px] text-dim mt-0.5">Connect a source, teach PAAIM its vocabulary <span className="text-pine-2 font-semibold">once</span> — then ingest forever with zero AI.</p>
      </div>

      {/* The plant's vocabulary. Sits above the steps because it is what every
          mapping resolves INTO — a machine shop and a filling line share almost
          no signals, so this must be theirs to choose, not ours to ship. */}
      <Card className="p-5">
        <SectionHeader eyebrow="Your plant" title="Signal" accent="vocabulary"
          sub="What your tags get translated into. Pick the closest starting point, then add your own signals — no code, no release." />
        <div className="flex flex-wrap gap-2">
          {packs.map((p) => (
            <button key={p.pack_id} onClick={() => applyPack(p.pack_id)} disabled={packBusy || p.active}
              title={p.description}
              className={`text-left px-3 py-2 rounded-lg border transition-colors ${
                p.active ? 'bg-surface-ok border-moss' : 'bg-card border-line hover:border-moss'}`}>
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold text-ink">{p.label}</span>
                {p.active && <SignalPill tone="ok">in use</SignalPill>}
              </div>
              <span className="font-mono text-[10px] text-dim uppercase tracking-wide">{p.signal_count} signals</span>
            </button>
          ))}
        </div>
        {packWarning && (
          <div className="mt-3">
            <AlertBar tone="warn" title="Some saved mappings no longer match this vocabulary">
              {packWarning}
            </AlertBar>
          </div>
        )}
        {vocab.length > 0 && (
          <div className="mt-4 pt-4 border-t border-line">
            <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-2">
              {vocab.length} signals · a fault is flagged when the reading goes the marked way
            </p>
            <div className="flex flex-wrap gap-1.5">
              {vocab.map((v) => (
                <span key={v.signal} title={`${v.description || v.signal} · routes to ${v.event_type}`}
                  className="font-mono text-[11px] bg-paper border border-line rounded px-2 py-0.5 text-ink">
                  {v.signal}
                  <span className="text-dim"> {v.unit}</span>
                  <span className={v.higher_is_worse ? 'text-coral' : 'text-pine-2'}>
                    {' '}{v.higher_is_worse ? '↑' : '↓'}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Step 1 — connect */}
      <Card className="p-5">
        <SectionHeader eyebrow="Step 1" title="Connect the" accent="data source"
          sub="Point PAAIM at the system. Nothing is saved until it actually answers." />
        <div className="grid md:grid-cols-3 gap-4">
          <div className="space-y-3">
            <div>
              <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Source ID</label>
              <input value={sourceId} onChange={(e) => setSourceId(e.target.value)}
                className="mt-1 w-full font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" />
            </div>
            <div>
              <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Type</label>
              <select value={connType} onChange={(e) => { setConnType(e.target.value); setTestResult(null); setConnected(false); }}
                className="mt-1 w-full text-sm border border-line rounded-lg px-3 py-2 bg-card focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss">
                {types.map((t) => (
                  <option key={t.type} value={t.type} disabled={!t.supported}>
                    {t.label}{t.supported ? '' : ' — not available'}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="md:col-span-2 space-y-3">
            {needsEndpoint && (
              <div>
                <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Endpoint</label>
                <input value={endpoint} onChange={(e) => { setEndpoint(e.target.value); setTestResult(null); setConnected(false); }}
                  placeholder={activeType?.endpoint_hint}
                  className="mt-1 w-full font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" />
              </div>
            )}
            {activeType && <p className="text-[12px] text-dim leading-snug">{activeType.description}</p>}
            <div className="flex items-center gap-2">
              <button onClick={testConnection} disabled={testing || (needsEndpoint && !endpoint)}
                className="btn-ghost px-3.5 py-1.5 text-[13px] disabled:opacity-40">
                {testing ? 'Testing…' : 'Test connection'}
              </button>
              <button onClick={connectAndDiscover} disabled={!testResult?.ok || discovering}
                className="btn-primary px-3.5 py-1.5 text-[13px] disabled:opacity-40">
                {discovering ? 'Connecting…' : 'Connect & discover fields'}
              </button>
              {connected && <SignalPill tone="ok">Connected</SignalPill>}
            </div>
            {testResult && (
              <AlertBar tone={testResult.ok ? 'ok' : 'bad'} title={testResult.ok ? 'Source reachable' : 'Cannot connect'}>
                {testResult.detail}{testResult.latency_ms != null && ` (${testResult.latency_ms} ms)`}
              </AlertBar>
            )}
            {discoverNote && <AlertBar tone="ok" title="Fields discovered">{discoverNote}</AlertBar>}
          </div>
        </div>
      </Card>

      {/* Step 2 — sample */}
      <Card className="p-5">
        <SectionHeader eyebrow="Step 2" title="Confirm the" accent="sample payload" sub="Read live from the source above. The resolver maps its fields to the canonical vocabulary." />
        <div className="grid md:grid-cols-3 gap-4">
          <div className="md:col-span-1 space-y-3">
            <div>
              <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Source ID</label>
              <input value={sourceId} onChange={(e) => setSourceId(e.target.value)} className="mt-1 w-full font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" />
            </div>
            <div>
              <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Machine ID field (optional)</label>
              <input value={machineField} onChange={(e) => setMachineField(e.target.value)} placeholder="e.g. device_id" className="mt-1 w-full font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" />
            </div>
            <label className="flex items-center gap-2 text-[13px] text-ink cursor-pointer">
              <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} className="accent-pine-2" />
              Use AI (Tier 4) for leftover fields
            </label>
            <button onClick={propose} disabled={busy} className="btn-primary w-full py-2 text-sm disabled:opacity-50">{busy ? 'Resolving…' : 'Propose mapping'}</button>
            {err && <AlertBar tone="bad" title={err} />}
          </div>
          <div className="md:col-span-2">
            <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Sample payload (JSON)</label>
            <textarea value={sampleText} onChange={(e) => setSampleText(e.target.value)} rows={11} className="mt-1 w-full font-mono text-[12.5px] border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" />
          </div>
        </div>
      </Card>

      {/* Step 3 — review mapping. Always present: a step that appears from nowhere
          reads as a broken page, so hold its place until a proposal exists. */}
      {!rows && (
        <Card className="p-5 opacity-60">
          <SectionHeader eyebrow="Step 3" title="Review the" accent="proposed mapping"
            sub="Waiting on a proposal — run Step 2 and the resolver's suggestions will appear here for you to approve." />
        </Card>
      )}
      {rows && (
        <Card className="p-5">
          <SectionHeader eyebrow="Step 3" title="Review the" accent="proposed mapping"
            sub="Each field mapped to a canonical signal, in what unit, and how it was resolved. Edit any row, then confirm."
            right={<div className="flex gap-2">
              <SignalPill tone="ok">{mappedCount} mapped</SignalPill>
              {unmappedCount > 0 && <SignalPill tone="warn">{unmappedCount} unmapped</SignalPill>}
              {conflictCount > 0 && <SignalPill tone="bad">{conflictCount} unit conflict</SignalPill>}
            </div>} />
          {conflictCount > 0 && (
            <div className="mb-3">
              <AlertBar tone="bad" title="A unit here cannot be reconciled">
                {conflictCount} field{conflictCount > 1 ? 's' : ''} send a unit this signal cannot be converted
                into. Detection would still fire, but every number the agents reason about would be wrong —
                pick a signal in the source&apos;s unit, or change that signal&apos;s unit in your vocabulary.
              </AlertBar>
            </div>
          )}
          {noUnitCount > 0 && conflictCount === 0 && (
            <div className="mb-3">
              <AlertBar tone="warn" title="Some units are assumed, not verified">
                {noUnitCount} field{noUnitCount > 1 ? 's' : ''} arrive without a declared unit, so PAAIM is
                assuming they already match the signal. If your source measures any of them differently,
                say so in your vocabulary — nothing downstream can detect the difference.
              </AlertBar>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="border-b border-line text-left">
                {['Raw field', 'Canonical signal', 'Unit', 'Resolved by', 'Confidence'].map((h) => <th key={h} className="pb-2 font-mono text-[10px] font-semibold text-dim uppercase tracking-wide">{h}</th>)}
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.raw} className="border-b border-line last:border-0">
                    <td className="py-2.5 font-mono text-[12px] text-ink">{r.raw}</td>
                    <td className="py-2.5">
                      <select value={r.signal} onChange={(e) => changeSignal(r.raw, e.target.value)}
                        className={`font-mono text-[12px] border rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-pine-2/20 ${r.signal ? 'border-line text-pine-2 font-semibold' : 'border-amber/40 text-[#9A6B15] bg-surface-warn'}`}>
                        <option value="">(unmapped)</option>
                        {vocab.map((v) => <option key={v.signal} value={v.signal}>{v.signal}</option>)}
                      </select>
                    </td>
                    {/* Source unit → signal unit. The arrow is the whole point:
                        a tag in °C mapped onto a Kelvin signal is not a mapping,
                        it is a 273-degree error that every number downstream
                        inherits while still looking plausible. */}
                    <td className="py-2.5">
                      {!r.signal ? <span className="font-mono text-[12px] text-dim">—</span> : (
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-[12px] text-dim whitespace-nowrap">
                            {r.unit_status === 'converted'
                              ? <><span className="text-[#9A6B15]">{r.source_unit}</span> → <span className="text-pine-2 font-semibold">{r.unit}</span></>
                              : r.unit_status === 'conflict'
                                ? <><span className="text-coral">{r.source_unit}</span> ✗ <span className="text-coral">{r.unit}</span></>
                                : (r.unit || '—')}
                          </span>
                          {r.unit_status && r.unit_status !== 'match' && (
                            <span title={r.unit_note}><SignalPill tone={unitTone(r.unit_status)}>{r.unit_status}</SignalPill></span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5">{r.resolved_by === 'unmapped' ? <span className="text-[12px] text-dim">—</span> : <SignalPill tone={tierTone(r.resolved_by)}>{r.resolved_by}</SignalPill>}</td>
                    <td className="py-2.5 font-mono text-[12px] text-dim">{r.confidence ? `${Math.round(r.confidence * 100)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-3 mt-4">
            <button onClick={confirm} disabled={busy} className="btn-primary px-5 py-2 text-sm disabled:opacity-50">Confirm & save mapping</button>
            {confirmed && <SignalPill tone="ok">Saved · runtime uses this now (no AI)</SignalPill>}
          </div>
        </Card>
      )}

      {/* Step 3 — test ingest */}
      <Card className="p-5">
        <SectionHeader eyebrow="Step 4" title="Test" accent="ingestion"
          sub="Push a raw payload through a saved mapping. Canonical events publish to the pipeline — check the Operations queue." />
        <div className="grid md:grid-cols-3 gap-4">
          <div className="md:col-span-1 space-y-3">
            <div>
              <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Saved source</label>
              <select value={ingestSource} onChange={(e) => setIngestSource(e.target.value)} className="mt-1 w-full font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20">
                <option value="">Select a source…</option>
                {saved.map((m) => <option key={m.source_id} value={m.source_id}>{m.source_id} ({Object.keys(m.fields || {}).length} fields)</option>)}
              </select>
            </div>
            <button onClick={runIngest} disabled={ingestBusy || !ingestSource} className="btn-primary w-full py-2 text-sm disabled:opacity-50">{ingestBusy ? 'Ingesting…' : 'Ingest payload'}</button>
            {ingestResult?.error && <AlertBar tone="bad" title={ingestResult.error} />}
            {ingestResult?.published != null && (
              <AlertBar tone="ok" title={`${ingestResult.published} canonical events published`}>Flowed into the pipeline — see Operations.</AlertBar>
            )}
          </div>
          <div className="md:col-span-2">
            <label className="font-mono text-[10px] text-dim uppercase tracking-wide">Raw payload (JSON)</label>
            <textarea value={ingestText} onChange={(e) => setIngestText(e.target.value)} rows={8} className="mt-1 w-full font-mono text-[12.5px] border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" />
            {ingestResult?.readings?.length > 0 && (
              <div className="mt-3 space-y-1">
                <Eyebrow dim>Canonical readings produced</Eyebrow>
                {ingestResult.readings.map((r: any, i: number) => (
                  <div key={i} className="font-mono text-[12px] text-ink flex gap-2"><span className="text-pine-2">{r.signal_name}</span> = {r.value} {r.unit} <span className="text-dim">← {r.raw_field}</span></div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Connected sources — show what each one actually reaches, so the
          source → signal → monitor chain is legible from this end too. */}
      {sources.length > 0 && (
        <div>
          <SectionHeader eyebrow="Onboarded" title="Connected" accent="sources"
            sub="Confirmed mappings — deterministic runtime, no AI." />
          <div className="grid md:grid-cols-2 gap-3">
            {sources.map((s) => (
              <Card key={s.source_id} className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-[13px] font-bold text-ink">{s.source_id}</span>
                  <SignalPill tone={s.connection ? 'ok' : 'warn'}>
                    {s.connection ? s.connection.type : 'no connection'}
                  </SignalPill>
                </div>
                {s.connection?.endpoint && (
                  <p className="font-mono text-[11px] text-dim mb-2">{s.connection.endpoint}</p>
                )}
                <p className="text-[12px] text-dim">
                  <span className="text-ink font-semibold">{s.fields_mapped}</span> fields mapped ·{' '}
                  <span className="text-ink font-semibold">{s.fields_watched}</span> watched · v{s.version}
                </p>
                <div className="mt-3 pt-3 border-t border-line">
                  <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-1.5">Feeds these monitors</p>
                  {s.feeds?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {s.feeds.map((f: any) => (
                        <span key={f.id} className="font-mono text-[11px] bg-surface-ok text-pine-2 border border-moss px-2 py-0.5 rounded">
                          {f.name} <span className="text-moss">· {f.via_signals.join(', ')}</span>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[12px] text-dim">No monitor watches these signals yet — create one on Monitors.</p>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
