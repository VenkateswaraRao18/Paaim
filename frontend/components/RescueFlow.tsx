'use client';

import { useState } from 'react';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar, OTBanner } from '@/components/ui';
import DecisionTwin from '@/app/rescue/DecisionTwin';
import FactoryMemory from '@/app/rescue/FactoryMemory';
import type { RescueScenario } from '@/lib/rescue-scenario';

const money = (n: number) => '$' + Math.round(n).toLocaleString();

const PRIORITY_CLS: Record<'L1' | 'L2' | 'L3', string> = {
  L1: 'bg-surface-bad text-coral border-coral/40',
  L2: 'bg-surface-warn text-[#9A6B15] border-amber/40',
  L3: 'bg-paper text-dim border-line',
};
const PRIORITY_LABEL: Record<'L1' | 'L2' | 'L3', string> = {
  L1: 'L1 · Critical', L2: 'L2 · Elevated', L3: 'L3 · Routine',
};

function PriorityChip({ p }: { p: NonNullable<RescueScenario['priority']> }) {
  return (
    <span className={`inline-flex items-center font-mono text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded border ${PRIORITY_CLS[p.level]}`}
      title={p.rationale}>
      {PRIORITY_LABEL[p.level]}
    </span>
  );
}

const STEPS = [
  'Live Fault Console', 'Agent Coordination', 'Evidence Timeline', 'Evidence & Proof',
  'Decision', 'Recovery Twin', 'Action Drafts', 'Factory Memory',
];

/**
 * The 8-step guided incident timeline. Driven entirely by a `scenario` object, so
 * the SAME flow renders for the scripted Line 3 demo and for any real decision
 * (mapped from the API). `backHref` shows a back link when opened from an incident.
 */
export default function RescueFlow({ scenario: s, backHref }: { scenario: RescueScenario; backHref?: string }) {
  const [step, setStep] = useState(0);
  const [ran, setRan] = useState(false);

  return (
    <div className="max-w-[1080px] mx-auto pb-16">
      {/* Incident rail */}
      <div className="flex items-center justify-between gap-4 mb-5">
        <div className="flex items-center gap-3">
          {backHref && (
            <a href={backHref} className="text-dim hover:text-ink transition-colors" title="Back">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
            </a>
          )}
          {s.priority && <PriorityChip p={s.priority} />}
          <SignalPill tone="bad">{s.incident.line}{s.incident.station ? ` · ${s.incident.station}` : ''} · FAULTED</SignalPill>
          <span className="font-mono text-[11px] text-dim uppercase tracking-wide">Run {s.incident.runId}</span>
        </div>
        <OTBanner />
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-1.5 mb-6 overflow-x-auto">
        {STEPS.map((label, i) => {
          const active = i === step, done = i < step;
          return (
            <button key={label} onClick={() => setStep(i)}
              className={`flex items-center gap-2 shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors ${active ? 'bg-pine-2 text-white' : done ? 'bg-surface-ok text-pine-2' : 'bg-card border border-line text-dim hover:text-ink'}`}>
              <span className={`font-mono text-[10px] w-4 h-4 rounded-full flex items-center justify-center ${active ? 'bg-amber text-pine' : done ? 'bg-pine-2 text-white' : 'bg-paper text-dim'}`}>{i + 1}</span>
              <span className="hidden md:inline">{label}</span>
            </button>
          );
        })}
      </div>

      {step === 0 && <FaultConsole s={s} />}
      {step === 1 && <AgentBoard s={s} ran={ran} onRun={() => setRan(true)} />}
      {step === 2 && <Timeline s={s} />}
      {step === 3 && <Scoreboard s={s} />}
      {step === 4 && <DecisionPack s={s} />}
      {step === 5 && <DecisionTwin onContinue={() => setStep(6)} context={s.context} decisionId={s.decisionId} />}
      {step === 6 && <ActionDrafts s={s} />}
      {step === 7 && <FactoryMemory context={s.context} decisionId={s.decisionId} />}

      <div className="flex items-center justify-between mt-8 pt-5 border-t border-line">
        <button onClick={() => setStep((x) => Math.max(0, x - 1))} disabled={step === 0} className="btn-ghost px-4 py-2 text-sm disabled:opacity-40">← Back</button>
        <span className="font-mono text-[11px] text-dim uppercase tracking-wide">Step {step + 1} of {STEPS.length}</span>
        <button onClick={() => { if (step === 1) setRan(true); setStep((x) => Math.min(STEPS.length - 1, x + 1)); }} disabled={step === STEPS.length - 1} className="btn-primary px-4 py-2 text-sm disabled:opacity-40">Continue →</button>
      </div>
    </div>
  );
}

/* ── 1 · Live Fault Console ── */
function FaultConsole({ s }: { s: RescueScenario }) {
  const [query, setQuery] = useState<string>(s.incident.errorCode);
  const result = s.lookupSemantic(query);
  const { incident: inc } = s;
  return (
    <div className="space-y-5">
      <SectionHeader eyebrow={`${inc.timestamp} · Fault detected`} title={inc.headline} accent={inc.question}
        sub={`${inc.errorCode ? `Error ${inc.errorCode}: ${inc.errorMeaning}. ` : ''}${inc.order.id ? `${inc.order.customer} ${inc.order.id} is at risk — ` : ''}decision needed${inc.decisionDeadline ? ` before ${inc.decisionDeadline}` : ''}.`} />
      {s.priority && (
        <div className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 ${PRIORITY_CLS[s.priority.level]}`}>
          <PriorityChip p={s.priority} />
          <span className="text-[13px] font-medium">Triaged {PRIORITY_LABEL[s.priority.level]} — {s.priority.rationale}</span>
        </div>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiTile label="Downtime" value={inc.downtimeMinutes ?? '—'} unit={inc.downtimeMinutes === null ? '' : 'min'}
          tone="warn" meaning={inc.downtimeMinutes === null ? 'Not estimated' : `Since ${inc.timestamp}`} />
        {/* An unpriced incident says so. Showing a figure here that no one
            configured is worse than showing none: the operator reads it as the
            plant's own number and acts on it. */}
        <KpiTile
          label="Estimated loss"
          value={s.estimatedLoss === null ? 'Not priced' : money(s.estimatedLoss)}
          tone={s.estimatedLoss === null ? 'neutral' : 'bad'}
          meaning={inc.costPerMinute === null
            ? 'No cost model configured for this factory'
            : `${money(inc.costPerMinute)}/min`} />
        <KpiTile label="Units at risk" value={inc.unitsAtRisk} tone="warn" meaning="Produced before fault" />
        <KpiTile label="Affected order" value={inc.order.id || '—'} meaning={inc.order.id ? `${inc.order.customer} · due ${inc.order.dueTime}` : 'No linked order'} />
      </div>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <Eyebrow>What does {inc.errorCode || 'this signal'} mean?</Eyebrow>
          <div className="flex gap-2 mt-3">
            <input value={query} onChange={(e) => setQuery(e.target.value)} className="flex-1 font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss" placeholder="Error 0x4F3, DB12.DBX4.3, MTR03_TORQUE…" />
          </div>
          {result ? (
            <div className="mt-4 space-y-3">
              <AlertBar tone="warn" title={result.tagDict} />
              <div><Eyebrow dim>Tribal knowledge</Eyebrow><p className="text-[13px] text-ink mt-1 leading-relaxed">{result.tribalKnowledge}</p></div>
              <div><Eyebrow dim>Safe action</Eyebrow><p className="text-[13px] text-pine-2 font-medium mt-1 leading-relaxed">{result.humanAction}</p></div>
            </div>
          ) : <p className="text-[13px] text-dim mt-4">No match — try a code, tag, or symptom.</p>}
        </Card>
        <Card className="p-5">
          <Eyebrow>Raw machine tags</Eyebrow>
          <div className="mt-3 divide-y divide-line">
            {s.tags.map((t) => (
              <div key={t.tag} className="flex items-center justify-between py-2.5 gap-3" title={`${t.meaning}. Likely: ${t.likelyCauses}`}>
                <div className="min-w-0"><div className="font-mono text-[11px] text-dim">{t.tag}</div><div className="text-[13px] text-ink font-medium leading-tight">{t.displayName}</div></div>
                <div className="text-right shrink-0">
                  <div className={`font-mono text-[15px] font-semibold ${t.tone === 'bad' ? 'text-coral' : t.tone === 'warn' ? 'text-[#9A6B15]' : 'text-pine-2'}`}>{t.value}<span className="text-[11px] text-dim ml-0.5">{t.unit}</span></div>
                  <div className="font-mono text-[10px] text-dim">normal {t.normal}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <AlertBar tone="ok" title="Read-only OT mode">No PLC write-back, no autonomous restart. Every action below is a draft requiring human approval.</AlertBar>
    </div>
  );
}

/* ── 2 · Agent Coordination ── */
function AgentBoard({ s, ran, onRun }: { s: RescueScenario; ran: boolean; onRun: () => void }) {
  return (
    <div className="space-y-5">
      <SectionHeader eyebrow="Multi-agent diagnosis" title={`${s.agents.length} specialists`} accent="inspect the evidence in parallel."
        sub="This is not a chatbot. Each agent reads a different evidence layer and reports what it found."
        right={!ran ? <button onClick={onRun} className="btn-primary px-4 py-2 text-sm">Run Multi-Agent Diagnosis</button> : <SignalPill tone="ok">{s.agents.length} evidence layers captured</SignalPill>} />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {s.agents.map((a) => (
          <Card key={a.id} className="p-4 flex flex-col" focal={a.id === 'orchestrator'}>
            <div className="flex items-center justify-between">
              <Eyebrow dim>{a.role}</Eyebrow>
              {ran ? <SignalPill tone={a.tone}>Complete</SignalPill> : <span className="font-mono text-[10px] text-dim uppercase tracking-wide">Queued</span>}
            </div>
            <h3 className="text-[14px] font-bold text-ink mt-2">{a.name}</h3>
            <p className="text-[13px] text-ink/80 mt-1.5 leading-snug flex-1">{ran ? a.finding : 'Waiting to run…'}</p>
            {ran && (<>
              <div className="mt-3">
                <div className="flex items-center justify-between font-mono text-[10px] text-dim uppercase tracking-wide mb-1">
                  <span>Confidence</span>
                  <span>{a.confidence === null ? 'not stated' : `${Math.round(a.confidence * 100)}%`} · {a.sources} sources</span>
                </div>
                <div className="h-1.5 rounded-full bg-paper overflow-hidden">
                  {a.confidence !== null && (
                    <div className="h-full rounded-full bg-pine-2" style={{ width: `${a.confidence * 100}%` }} />
                  )}
                </div>
              </div>
              <p className="text-[12px] text-pine-2 mt-2.5 font-medium leading-snug">→ {a.actionImplication}</p>
            </>)}
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ── 3 · Evidence Timeline ── */
function Timeline({ s }: { s: RescueScenario }) {
  const t = s.timeline;
  const W = 640, H = 260, pad = 36;
  const xs = t.minutes;
  const maxX = Math.max(...xs, 1);
  // Generic series (real signal history) take precedence over the scripted trio.
  const series = t.series ?? [
    { name: 'Torque', data: t.torque, color: '#1B5443' },
    { name: 'Temperature Δ', data: t.tempDelta, color: '#E8A13D' },
    { name: 'Camera anomaly', data: t.cameraAnomaly, color: '#D8492B' },
  ];

  // Auto-scale Y to the data so small-amplitude signals (e.g. vibration ~4.5–4.9)
  // are legible instead of flattened against a fixed axis.
  const all = series.flatMap((se) => se.data).filter((v) => Number.isFinite(v));
  const lo = all.length ? Math.min(...all) : 0;
  const hi = all.length ? Math.max(...all) : 1;
  const span = hi - lo || Math.abs(hi) || 1;
  const yMin = Math.max(0, lo - span * 0.15);
  const yMax = hi + span * 0.15;
  const ticks = [0, 1, 2, 3].map((i) => yMin + ((yMax - yMin) * i) / 3);
  const fmt = (v: number) => (yMax - yMin < 10 ? v.toFixed(2) : Math.round(v).toString());

  const px = (x: number) => pad + (x / maxX) * (W - pad * 2);
  const py = (v: number) => H - pad - ((v - yMin) / (yMax - yMin || 1)) * (H - pad * 2);
  const line = (arr: number[]) => arr.map((v, i) => `${i ? 'L' : 'M'}${px(xs[i])},${py(v)}`).join(' ');
  const faultX = px(t.faultAt);
  // Thin out x labels so dense real series don't collide.
  const step = Math.max(1, Math.ceil(xs.length / 8));
  const dot = xs.length > 24 ? 0 : 3;

  return (
    <div className="space-y-5">
      <SectionHeader eyebrow="Incident evidence timeline" title="What changed" accent="before the fault."
        sub="How the machine's signals moved in the readings leading up to the fault." />
      <div className="grid lg:grid-cols-3 gap-5">
        <Card className="p-5 lg:col-span-2">
          {t.hasSeries ? (<>
            <div className="flex gap-4 mb-3">{series.map((se) => <span key={se.name} className="flex items-center gap-1.5 text-[12px] text-dim"><span className="w-3 h-0.5 rounded" style={{ background: se.color }} /> {se.name}</span>)}</div>
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
              {ticks.map((g, i) => (<g key={i}><line x1={pad} x2={W - pad} y1={py(g)} y2={py(g)} stroke="#DDE4DF" strokeWidth={1} /><text x={pad - 8} y={py(g) + 3} textAnchor="end" fontSize={9} fill="#5E6B64" fontFamily="monospace">{fmt(g)}</text></g>))}
              <line x1={faultX} x2={faultX} y1={pad} y2={H - pad} stroke="#D8492B" strokeWidth={1} strokeDasharray="4 3" />
              {/* flip the label to the left of the marker when the fault sits near the right edge */}
              <text x={faultX > W / 2 ? faultX - 5 : faultX + 5} y={pad + 10} textAnchor={faultX > W / 2 ? 'end' : 'start'}
                fontSize={9} fill="#D8492B" fontFamily="monospace">{t.faultLabel}</text>
              {series.map((se) => <g key={se.name}><path d={line(se.data)} fill="none" stroke={se.color} strokeWidth={2} />{dot > 0 && se.data.map((v, i) => <circle key={i} cx={px(xs[i])} cy={py(v)} r={dot} fill={se.color} />)}</g>)}
              {xs.filter((_, i) => i % step === 0).map((x, i) => (
                <text key={x} x={px(x)} y={H - pad + 14} textAnchor="middle" fontSize={9} fill="#5E6B64" fontFamily="monospace">
                  {t.xTickLabels ? t.xTickLabels[i * step] : x}
                </text>
              ))}
            </svg>
            <p className="text-center font-mono text-[10px] text-dim uppercase tracking-wide mt-1">{t.xUnitLabel ?? 'Minutes before / after incident'}</p>
          </>) : (
            <div className="text-center py-12"><p className="text-[13px] font-semibold text-ink">Single-reading event</p><p className="text-[12px] text-dim mt-1">This incident was raised from a live threshold breach — no prior readings for this signal. Evidence snippets are shown alongside.</p></div>
          )}
        </Card>
        <Card className="p-5">
          <Eyebrow>Evidence snippets</Eyebrow>
          <div className="mt-3 space-y-3">
            {t.snippets.map((sn, i) => (<div key={i}><div className="font-mono text-[10px] text-moss uppercase">{sn.source}</div><p className="text-[13px] text-ink mt-0.5 leading-snug">{sn.text}</p></div>))}
          </div>
        </Card>
      </div>
      {t.readout && <AlertBar tone="warn" title="Plain-English read">{t.readout}</AlertBar>}
    </div>
  );
}

/* ── 4 · Evidence & Proof ── */
function Scoreboard({ s }: { s: RescueScenario }) {
  const passed = s.evidenceRows.filter((r) => r.captured === 'PASS').length;
  return (
    <div className="space-y-5">
      <SectionHeader eyebrow="Evidence & proof" title="Every recommendation is backed by real data —" accent="here's the proof."
        sub={`Ground-truth check: ${passed} of ${s.evidenceRows.length} critical signals captured and surfaced for action.`}
        right={<SignalPill tone="ok">Evidence-backed · not guessed</SignalPill>} />
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="bg-paper border-b border-line text-left">{['Evidence', 'Source', 'Known truth', 'Captured', 'Action surfaced'].map((h) => <th key={h} className="font-mono text-[10px] text-dim uppercase tracking-wide font-semibold px-4 py-2.5">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {s.evidenceRows.map((r) => (
                <tr key={r.type} className="hover:bg-surface-ok transition-colors">
                  <td className="px-4 py-3 font-semibold text-ink">{r.type}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-dim">{r.source}</td>
                  <td className="px-4 py-3 text-ink/80">{r.groundTruth}</td>
                  <td className="px-4 py-3"><SignalPill tone={r.captured === 'PASS' ? 'ok' : 'warn'}>{r.captured}</SignalPill></td>
                  <td className="px-4 py-3 text-pine-2 font-medium">{r.actionSurfaced}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

/* ── 5 · Decision ── */
function DecisionPack({ s }: { s: RescueScenario }) {
  const d = s.decision;
  const maxPct = Math.max(...d.rootCause.map((r) => r.pct ?? 0), 1);
  return (
    <div className="space-y-5">
      <Card focal className="overflow-hidden">
        <div className="bg-surface-bad border-l-4 border-coral p-5">
          <Eyebrow dim>{d.title}</Eyebrow>
          <h2 className="text-[26px] font-bold text-coral tracking-[-0.02em] mt-1">{d.verdict}</h2>
          <p className="text-[14px] text-ink/80 mt-1.5 leading-relaxed">{d.reason}</p>
        </div>
      </Card>
      <div className="grid lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <Eyebrow>{d.rootCauseTitle ?? 'Root-cause contribution'}</Eyebrow>
          <div className="mt-4 space-y-3">
            {d.rootCause.map((r) => (
              <div key={r.cause}>
                {/* An agent that stated no confidence gets no bar. Drawing one
                    at an assumed 80% would invent the very number this panel
                    claims to be reporting. */}
                <div className="flex justify-between gap-3 text-[13px] mb-1">
                  <span className="text-ink">{r.cause}</span>
                  <span className="font-mono text-dim shrink-0">{r.pct === null ? 'not stated' : `${r.pct}%`}</span>
                </div>
                <div className="h-2 rounded-full bg-paper overflow-hidden">
                  {r.pct !== null && (
                    <div className="h-full rounded-full bg-pine-2" style={{ width: `${(r.pct / maxPct) * 100}%` }} />
                  )}
                </div>
              </div>
            ))}
          </div>
          {d.rootCauseNote && <p className="text-[11px] text-dim mt-3 leading-snug">{d.rootCauseNote}</p>}
        </Card>
        <Card className="p-5">
          <Eyebrow>Required before restart</Eyebrow>
          <ul className="mt-3 space-y-2">{d.requiredBeforeRestart.map((r) => <li key={r} className="flex items-start gap-2 text-[13px] text-ink"><span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-coral shrink-0" />{r}</li>)}</ul>
          <div className="mt-4"><Eyebrow dim>Fallback</Eyebrow><p className="text-[13px] text-ink mt-1 leading-relaxed">{d.fallback}</p></div>
        </Card>
      </div>
      <div className="grid sm:grid-cols-3 gap-3">
        {d.actions.map((a) => (
          <Card key={a.id} className="p-4"><div className="text-[14px] font-bold text-ink">{a.title}</div><div className="font-mono text-[11px] text-dim mt-2">OWNER · {a.owner}</div><div className="mt-1"><SignalPill tone={a.urgency === 'Immediate' ? 'bad' : 'warn'}>{a.urgency}</SignalPill></div></Card>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2"><Eyebrow dim>Approvals</Eyebrow>{d.approvals.map((a) => <SignalPill key={a} tone="neutral">{a}</SignalPill>)}</div>
        {d.avoidableLoss ? (
          <div className="font-mono text-[13px] text-pine-2 font-semibold">
            Avoidable loss {money(d.avoidableLoss.min)}–{money(d.avoidableLoss.max)}
          </div>
        ) : (
          <div className="font-mono text-[13px] text-dim">Avoidable loss — not priced</div>
        )}
      </div>
    </div>
  );
}

/* ── 7 · Action Drafts ── */
function ActionDrafts({ s }: { s: RescueScenario }) {
  const [active, setActive] = useState(s.drafts[0]?.id);
  const [approved, setApproved] = useState<Record<string, boolean>>({});
  const draft = s.drafts.find((d) => d.id === active) ?? s.drafts[0];
  if (!draft) return <p className="text-dim text-sm">No drafts.</p>;
  return (
    <div className="space-y-5">
      <SectionHeader eyebrow="Generated action drafts" title="Diagnosis becomes" accent="reviewable artifacts." sub="Draft only — review required before sending or writing back to any system." />
      <div className="grid lg:grid-cols-3 gap-5">
        <div className="space-y-2">
          {s.drafts.map((d) => (
            <button key={d.id} onClick={() => setActive(d.id)} className={`w-full text-left p-3 rounded-lg border transition-colors ${active === d.id ? 'border-pine-2 bg-surface-ok' : 'border-line bg-card hover:border-moss'}`}>
              <div className="flex items-center justify-between"><span className="text-[13px] font-semibold text-ink">{d.label}</span>{approved[d.id] && <SignalPill tone="ok">Approved</SignalPill>}</div>
              <div className="font-mono text-[10px] text-dim mt-1 uppercase tracking-wide">{d.owner} · {d.urgency}</div>
            </button>
          ))}
        </div>
        <Card className="p-5 lg:col-span-2 flex flex-col">
          <div className="flex items-center justify-between"><Eyebrow>{draft.label}</Eyebrow><span className="font-mono text-[10px] text-moss uppercase tracking-wide">SOP {draft.sop}</span></div>
          <pre className="mt-3 flex-1 whitespace-pre-wrap font-mono text-[12.5px] text-ink/90 leading-relaxed bg-paper rounded-lg p-4 border border-line">{draft.body}</pre>
          <div className="flex items-center gap-2 mt-4">
            <button onClick={() => setApproved((a) => ({ ...a, [draft.id]: !a[draft.id] }))} className="btn-primary px-4 py-2 text-sm">{approved[draft.id] ? 'Approved ✓' : 'Approve Draft'}</button>
            <button onClick={() => navigator.clipboard?.writeText(draft.body)} className="btn-ghost px-4 py-2 text-sm">Copy</button>
            <span className="font-mono text-[10px] text-dim uppercase tracking-wide ml-auto">Demo state only · no CMMS write-back</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
