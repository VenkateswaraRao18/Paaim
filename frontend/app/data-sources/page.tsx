'use client';

import { useEffect, useState } from 'react';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar } from '@/components/ui';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Vocab = { signal: string; unit: string; event_type: string };
type Row = { raw: string; signal: string; unit: string; transform: string; resolved_by: string; confidence: number };

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

export default function DataSourcesPage() {
  const [vocab, setVocab] = useState<Vocab[]>([]);
  const [saved, setSaved] = useState<any[]>([]);

  // onboarding form
  const [sourceId, setSourceId] = useState('line3_scada');
  const [machineField, setMachineField] = useState('device_id');
  const [sampleText, setSampleText] = useState(SAMPLE);
  const [useLlm, setUseLlm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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

  const loadSaved = () => fetch(`${API_BASE}/normalization/mappings`).then(r => r.json()).then(d => setSaved(d.mappings ?? [])).catch(() => {});
  useEffect(() => {
    fetch(`${API_BASE}/normalization/vocab`).then(r => r.json()).then(d => setVocab(d.signals ?? [])).catch(() => {});
    loadSaved();
  }, []);

  const propose = async () => {
    setErr(null); setConfirmed(false); setBusy(true); setRows(null);
    let payload: any;
    try { payload = JSON.parse(sampleText); } catch { setErr('Sample payload is not valid JSON'); setBusy(false); return; }
    try {
      const r = await fetch(`${API_BASE}/normalization/propose`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, sample_payload: payload, machine_id_field: machineField || null, use_llm: useLlm }),
      });
      const d = await r.json();
      setMachineStrategy(d.machine_id_strategy); setMachineValue(d.machine_id_value);
      const mapped: Row[] = Object.values(d.fields || {}).map((f: any) => ({ ...f }));
      const unmapped: Row[] = (d.unmapped || []).map((raw: string) => ({ raw, signal: '', unit: '', transform: 'identity', resolved_by: 'unmapped', confidence: 0 }));
      setRows([...mapped, ...unmapped].sort((a, b) => a.raw.localeCompare(b.raw)));
    } catch { setErr('Could not reach the backend — is it running on :8000?'); }
    setBusy(false);
  };

  const changeSignal = (raw: string, signal: string) => {
    setRows((rs) => rs!.map((r) => {
      if (r.raw !== raw) return r;
      const v = vocab.find((x) => x.signal === signal);
      return { ...r, signal, unit: v?.unit ?? '', resolved_by: signal ? 'manual' : 'unmapped', confidence: signal ? 1 : 0 };
    }));
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

  return (
    <div className="max-w-[1180px] space-y-6">
      <div>
        <Eyebrow>Ingestion · onboarding</Eyebrow>
        <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Data Sources</h1>
        <p className="text-[13px] text-dim mt-0.5">Map a source's fields to PAAIM's language <span className="text-pine-2 font-semibold">once</span> — then ingest forever with zero AI.</p>
      </div>

      {/* Step 1 — sample */}
      <Card className="p-5">
        <SectionHeader eyebrow="Step 1" title="Give a" accent="sample payload" sub="One example reading from the source. The resolver maps its fields to the canonical vocabulary." />
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

      {/* Step 2 — review mapping */}
      {rows && (
        <Card className="p-5">
          <SectionHeader eyebrow="Step 2" title="Review the" accent="proposed mapping"
            sub="Each field mapped to a canonical signal, and how it was resolved. Edit any row, then confirm."
            right={<div className="flex gap-2"><SignalPill tone="ok">{mappedCount} mapped</SignalPill>{unmappedCount > 0 && <SignalPill tone="warn">{unmappedCount} unmapped</SignalPill>}</div>} />
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
                    <td className="py-2.5 font-mono text-[12px] text-dim">{r.unit || '—'}</td>
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
        <SectionHeader eyebrow="Step 3" title="Test" accent="ingestion"
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

      {/* Saved sources */}
      {saved.length > 0 && (
        <div>
          <SectionHeader eyebrow="Onboarded" title="Saved" accent="sources" sub="Confirmed mappings — deterministic runtime, no AI." />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {saved.map((m) => (
              <KpiTile key={m.source_id} label={m.source_id} value={Object.keys(m.fields || {}).length} unit="fields" tone="ok" meaning={`v${m.version} · ${m.unmapped?.length || 0} unmapped`} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
