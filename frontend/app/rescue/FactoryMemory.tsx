'use client';

import { useEffect, useState } from 'react';
import { Eyebrow, SectionHeader, Card, SignalPill, AlertBar } from '@/components/ui';
import { getMemory, type Memory } from '@/lib/twin';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';
const statusTone = (s: string): Tone => /pending|progress/i.test(s) ? 'warn' : /draft/i.test(s) ? 'neutral' : 'ok';

export default function FactoryMemory({ context, decisionId }: {
  context?: { machine?: string; order?: string };
  /** Build the memory from this real incident rather than the scripted scenario. */
  decisionId?: string;
} = {}) {
  const [m, setM] = useState<Memory | null>(null);
  const [accepted, setAccepted] = useState(false);
  useEffect(() => { if (decisionId) getMemory(decisionId).then(setM).catch(() => {}); }, [decisionId]);

  if (!decisionId) return <div className="text-center py-16 text-dim text-sm">Factory Memory is built from a specific incident — open one from Operations.</div>;
  if (!m) return <div className="text-center py-16 text-dim text-sm">Loading Factory Memory…</div>;

  const rr = m.recurrence_risk;
  const bars = [
    { label: 'Now', v: rr.before_action, tone: 'bad' as Tone },
    { label: 'After corrective action', v: rr.after_corrective_action, tone: 'warn' as Tone },
    { label: 'After verified rule', v: rr.after_verified_rule, tone: 'ok' as Tone },
  ];

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Factory Memory · 8D recurrence loop"
        title="Turn this incident into"
        accent="recurrence prevention"
        sub="The incident becomes an 8D/CAPA plan, a pending learned rule, and a verification watch — so it does not come back."
      />

      <AlertBar tone="ok" title="Incident converted into a recurrence-prevention plan.">
        Learned rules remain pending until reviewed by the responsible owner.
      </AlertBar>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* 8D draft */}
        <Card className="p-5 lg:col-span-2">
          <Eyebrow>8D / CAPA draft</Eyebrow>
          <div className="mt-3 divide-y divide-line">
            {m.eight_d.map((d) => (
              <div key={d.id} className="py-2.5 flex items-start gap-3">
                <span className="font-mono text-[11px] font-bold text-pine-2 shrink-0 w-6">{d.id}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-ink">{d.discipline}</p>
                  <p className="text-[12px] text-dim mt-0.5 leading-snug">{d.content}</p>
                </div>
                <SignalPill tone={statusTone(d.status)}>{d.status}</SignalPill>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-4">
          {/* Recurrence risk */}
          <Card className="p-5">
            <Eyebrow>Recurrence risk</Eyebrow>
            <div className="mt-3 space-y-2.5">
              {bars.map((b) => (
                <div key={b.label}>
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-ink">{b.label}</span>
                    <span className={`font-mono font-bold ${b.tone === 'bad' ? 'text-coral' : b.tone === 'warn' ? 'text-[#9A6B15]' : 'text-pine-2'}`}>{Math.round(b.v * 100)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-paper overflow-hidden">
                    <div className={`h-full rounded-full ${b.tone === 'bad' ? 'bg-coral' : b.tone === 'warn' ? 'bg-amber' : 'bg-pine-2'}`} style={{ width: `${b.v * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Learned rule */}
          <Card className="p-5">
            <div className="flex items-center justify-between mb-2">
              <Eyebrow>Learned rule</Eyebrow>
              <SignalPill tone="warn">Pending approval</SignalPill>
            </div>
            <p className="text-[13px] text-ink leading-relaxed">{m.learned_rule.rule_text}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {m.learned_rule.applies_to.map((a) => <span key={a} className="font-mono text-[10px] text-dim bg-paper border border-line px-1.5 py-0.5 rounded">{a}</span>)}
            </div>
            <button onClick={() => setAccepted(true)} className="btn-primary w-full mt-3 py-2 text-[13px]">
              {accepted ? 'Accepted as pending ✓' : 'Accept as pending rule'}
            </button>
          </Card>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Similar incidents */}
        <Card className="p-5">
          <Eyebrow>Similar prior incidents ({m.similar_incidents_found})</Eyebrow>
          <div className="mt-3 space-y-2">
            {m.similar_incidents.map((s: any) => (
              <div key={s.incident_id} className="border border-line rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[12px] font-semibold text-ink">{s.incident_id} · {s.asset}</span>
                  <SignalPill tone={s.recurrence === 'yes' ? 'warn' : 'ok'}>{s.recurrence === 'yes' ? 'recurred' : 'no recur'}</SignalPill>
                </div>
                <p className="text-[12px] text-dim mt-1">{s.symptoms}</p>
                <p className="text-[12px] text-pine-2 mt-0.5">→ {s.action_taken} <span className="text-dim">({s.outcome})</span></p>
              </div>
            ))}
          </div>
        </Card>

        {/* Verification plan */}
        <Card className="p-5">
          <Eyebrow>Verification plan</Eyebrow>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead><tr className="border-b border-line text-left">
                {['Metric', 'Threshold', 'Owner', 'Window'].map((h) => <th key={h} className="pb-2 font-mono text-[10px] text-dim uppercase tracking-wide">{h}</th>)}
              </tr></thead>
              <tbody>
                {m.verification_plan.map((v: any, i: number) => (
                  <tr key={i} className="border-b border-line last:border-0">
                    <td className="py-2 text-ink font-medium">{v.metric}</td>
                    <td className="py-2 font-mono text-dim">{v.threshold}</td>
                    <td className="py-2 text-dim">{v.owner}</td>
                    <td className="py-2 font-mono text-dim">{v.window}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
