'use client';

import { useState } from 'react';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar } from '@/components/ui';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Row = { category: string; name: string; expected: string; got: string; status: 'PASS' | 'REVIEW' };
type Scoreboard = { passed: number; total: number; pass_rate: number; rag_enabled: boolean; results: Row[] };

export default function EvaluationPage() {
  const [data, setData] = useState<Scoreboard | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${API_BASE}/eval/run`);
      setData(await r.json());
    } catch { setErr('Could not reach the backend — is it running on :8000?'); }
    setBusy(false);
  };

  return (
    <div className="max-w-[1000px] space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>Ground truth · proof</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Evaluation</h1>
          <p className="text-[13px] text-dim mt-0.5">Runs known inputs through PAAIM and checks the output against known facts — evidence-backed, not guessed.</p>
        </div>
        <button onClick={run} disabled={busy} className="btn-primary px-4 py-2 text-sm disabled:opacity-50">{busy ? 'Running…' : 'Run system check'}</button>
      </div>

      {err && <AlertBar tone="bad" title={err} />}

      {!data && !err && (
        <Card className="p-12 text-center">
          <p className="text-[14px] font-semibold text-ink">No run yet</p>
          <p className="text-[13px] text-dim mt-1">Run the check to verify normalization, agent firing, learned baselines, semantic decode, and tribal-knowledge retrieval.</p>
        </Card>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <KpiTile label="Checks passed" value={`${data.passed}/${data.total}`} tone={data.passed === data.total ? 'ok' : 'warn'} meaning="Known facts captured" />
            <KpiTile label="Pass rate" value={`${data.pass_rate}%`} tone={data.pass_rate === 100 ? 'ok' : data.pass_rate >= 80 ? 'warn' : 'bad'} meaning="This run" />
            <KpiTile label="Retrieval" value={data.rag_enabled ? 'Semantic' : 'Keyword'} meaning={data.rag_enabled ? 'Embeddings on' : 'Deterministic fallback'} />
          </div>

          <Card className="overflow-hidden">
            <div className="px-5 py-3 border-b border-line flex items-center justify-between">
              <Eyebrow>Ground-truth scoreboard</Eyebrow>
              <SignalPill tone={data.passed === data.total ? 'ok' : 'warn'}>{data.passed}/{data.total} pass</SignalPill>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-paper border-b border-line text-left">
                    {['Capability', 'Check', 'Expected', 'Got', 'Status'].map((h) => (
                      <th key={h} className="font-mono text-[10px] text-dim uppercase tracking-wide font-semibold px-4 py-2.5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.results.map((r, i) => (
                    <tr key={i} className="hover:bg-surface-ok transition-colors">
                      <td className="px-4 py-3 font-semibold text-ink">{r.category}</td>
                      <td className="px-4 py-3 text-ink/80">{r.name}</td>
                      <td className="px-4 py-3 font-mono text-[11px] text-dim">{r.expected}</td>
                      <td className="px-4 py-3 font-mono text-[11px] text-dim truncate max-w-[220px]">{r.got}</td>
                      <td className="px-4 py-3"><SignalPill tone={r.status === 'PASS' ? 'ok' : 'warn'}>{r.status}</SignalPill></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <AlertBar tone="ok" title="Why this matters">
            Every row is a real run against a known fact — proof the system captures ground truth, not free-form guesses.
          </AlertBar>
        </>
      )}
    </div>
  );
}
