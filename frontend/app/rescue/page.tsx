'use client';

import { useState } from 'react';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar, OTBanner } from '@/components/ui';
import {
  incident, estimatedLoss, tags, agents, timeline, evidenceRows, decision, drafts, lookupSemantic,
} from '@/lib/rescue-scenario';

const money = (n: number) => '$' + n.toLocaleString();

const STEPS = [
  'Live Fault Console',
  'Agent Coordination',
  'Evidence Timeline',
  'Evidence & Proof',
  'Restart Decision',
  'Action Drafts',
];

export default function RescuePage() {
  const [step, setStep] = useState(0);
  const [ran, setRan] = useState(false); // agents run state on step 2

  return (
      <div className="max-w-[1040px] mx-auto pb-16">
        {/* Persistent incident rail */}
        <div className="flex items-center justify-between gap-4 mb-5">
          <div className="flex items-center gap-3">
            <SignalPill tone="bad">{incident.line} · {incident.station} · FAULTED</SignalPill>
            <span className="font-mono text-[11px] text-dim uppercase tracking-wide">Run {incident.runId}</span>
          </div>
          <OTBanner />
        </div>

        {/* Stepper */}
        <div className="flex items-center gap-1.5 mb-6 overflow-x-auto">
          {STEPS.map((label, i) => {
            const active = i === step;
            const done = i < step;
            return (
              <button
                key={label}
                onClick={() => setStep(i)}
                className={`flex items-center gap-2 shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors ${
                  active ? 'bg-pine-2 text-white' : done ? 'bg-surface-ok text-pine-2' : 'bg-card border border-line text-dim hover:text-ink'
                }`}
              >
                <span className={`font-mono text-[10px] w-4 h-4 rounded-full flex items-center justify-center ${
                  active ? 'bg-amber text-pine' : done ? 'bg-pine-2 text-white' : 'bg-paper text-dim'
                }`}>{i + 1}</span>
                <span className="hidden md:inline">{label}</span>
              </button>
            );
          })}
        </div>

        {/* Screens */}
        {step === 0 && <FaultConsole />}
        {step === 1 && <AgentBoard ran={ran} onRun={() => setRan(true)} />}
        {step === 2 && <Timeline />}
        {step === 3 && <Scoreboard />}
        {step === 4 && <DecisionPack />}
        {step === 5 && <ActionDrafts />}

        {/* Nav footer */}
        <div className="flex items-center justify-between mt-8 pt-5 border-t border-line">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="btn-ghost px-4 py-2 text-sm disabled:opacity-40"
          >← Back</button>
          <span className="font-mono text-[11px] text-dim uppercase tracking-wide">Step {step + 1} of {STEPS.length}</span>
          <button
            onClick={() => {
              if (step === 1) setRan(true);
              setStep((s) => Math.min(STEPS.length - 1, s + 1));
            }}
            disabled={step === STEPS.length - 1}
            className="btn-primary px-4 py-2 text-sm disabled:opacity-40"
          >Continue →</button>
        </div>
      </div>
  );
}

/* ══════════════════ PAGE 1 — LIVE FAULT CONSOLE ══════════════════ */
function FaultConsole() {
  const [query, setQuery] = useState<string>(incident.errorCode);
  const result = lookupSemantic(query);

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow={`${incident.timestamp} · Fault detected`}
        title="Line 3 is down."
        accent="Can we safely restart?"
        sub={`Error ${incident.errorCode}: ${incident.errorMeaning}. ${incident.order.customer} ${incident.order.id} is at risk — decision needed before ${incident.decisionDeadline}.`}
      />

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiTile label="Downtime" value={incident.downtimeMinutes} unit="min" tone="warn" meaning="Since 08:17 AM" />
        <KpiTile label="Estimated loss" value={money(estimatedLoss)} tone="bad" meaning={`${money(incident.costPerMinute)}/min`} />
        <KpiTile label="Units at risk" value={incident.unitsAtRisk} tone="warn" meaning="Produced before fault" />
        <KpiTile label="Affected order" value={incident.order.id} meaning={`${incident.order.customer} · due ${incident.order.dueTime}`} />
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Semantic decode — promoted to the front */}
        <Card className="p-5">
          <Eyebrow>What does {incident.errorCode} mean?</Eyebrow>
          <div className="flex gap-2 mt-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 font-mono text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss"
              placeholder="Error 0x4F3, DB12.DBX4.3, MTR03_TORQUE…"
            />
          </div>
          {result ? (
            <div className="mt-4 space-y-3">
              <AlertBar tone="warn" title={result.tagDict} />
              <div>
                <Eyebrow dim>Tribal knowledge</Eyebrow>
                <p className="text-[13px] text-ink mt-1 leading-relaxed">{result.tribalKnowledge}</p>
              </div>
              <div>
                <Eyebrow dim>Safe action</Eyebrow>
                <p className="text-[13px] text-pine-2 font-medium mt-1 leading-relaxed">{result.humanAction}</p>
              </div>
            </div>
          ) : (
            <p className="text-[13px] text-dim mt-4">No match — try a code, tag, or symptom.</p>
          )}
        </Card>

        {/* Raw machine tags */}
        <Card className="p-5">
          <Eyebrow>Raw machine tags</Eyebrow>
          <div className="mt-3 divide-y divide-line">
            {tags.map((t) => (
              <div key={t.tag} className="flex items-center justify-between py-2.5 gap-3 group" title={`${t.meaning}. Likely: ${t.likelyCauses}`}>
                <div className="min-w-0">
                  <div className="font-mono text-[11px] text-dim">{t.tag}</div>
                  <div className="text-[13px] text-ink font-medium leading-tight">{t.displayName}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`font-mono text-[15px] font-semibold ${t.tone === 'bad' ? 'text-coral' : t.tone === 'warn' ? 'text-[#9A6B15]' : 'text-pine-2'}`}>
                    {t.value}<span className="text-[11px] text-dim ml-0.5">{t.unit}</span>
                  </div>
                  <div className="font-mono text-[10px] text-dim">normal {t.normal}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <AlertBar tone="ok" title="Read-only OT mode">
        No PLC write-back, no autonomous restart. Every action below is a draft requiring human approval.
      </AlertBar>
    </div>
  );
}

/* ══════════════════ PAGE 2 — AGENT COORDINATION ══════════════════ */
function AgentBoard({ ran, onRun }: { ran: boolean; onRun: () => void }) {
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Multi-agent diagnosis"
        title="Six specialists"
        accent="inspect the evidence in parallel."
        sub="This is not a chatbot. Each agent reads a different evidence layer and reports what it found."
        right={
          !ran ? (
            <button onClick={onRun} className="btn-primary px-4 py-2 text-sm">Run Multi-Agent Diagnosis</button>
          ) : (
            <SignalPill tone="ok">5 of 5 evidence layers captured</SignalPill>
          )
        }
      />

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {agents.map((a, i) => (
          <Card key={a.id} className="p-4 flex flex-col" focal={a.id === 'orchestrator'}>
            <div className="flex items-center justify-between">
              <Eyebrow dim>{a.role}</Eyebrow>
              {ran ? <SignalPill tone={a.tone}>Complete</SignalPill>
                   : <span className="font-mono text-[10px] text-dim uppercase tracking-wide">Queued</span>}
            </div>
            <h3 className="text-[14px] font-bold text-ink mt-2">{a.name}</h3>
            <p className="text-[13px] text-ink/80 mt-1.5 leading-snug flex-1">
              {ran ? a.finding : 'Waiting to run…'}
            </p>
            {ran && (
              <>
                <div className="mt-3">
                  <div className="flex items-center justify-between font-mono text-[10px] text-dim uppercase tracking-wide mb-1">
                    <span>Confidence</span><span>{Math.round(a.confidence * 100)}% · {a.sources} sources</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-paper overflow-hidden">
                    <div className="h-full rounded-full bg-pine-2" style={{ width: `${a.confidence * 100}%` }} />
                  </div>
                </div>
                <p className="text-[12px] text-pine-2 mt-2.5 font-medium leading-snug">→ {a.actionImplication}</p>
              </>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ══════════════════ PAGE 3 — EVIDENCE TIMELINE ══════════════════ */
function Timeline() {
  const W = 640, H = 260, pad = 36;
  const xs = timeline.minutes;
  const maxX = Math.max(...xs);
  const px = (x: number) => pad + (x / maxX) * (W - pad * 2);
  const py = (v: number) => H - pad - (v / 75) * (H - pad * 2);
  const line = (arr: number[]) => arr.map((v, i) => `${i ? 'L' : 'M'}${px(xs[i])},${py(v)}`).join(' ');
  const faultX = px(timeline.faultAt);

  const series = [
    { name: 'Torque', data: timeline.torque, color: '#1B5443' },
    { name: 'Temperature Δ', data: timeline.tempDelta, color: '#E8A13D' },
    { name: 'Camera anomaly', data: timeline.cameraAnomaly, color: '#D8492B' },
  ];

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Incident evidence timeline"
        title="What changed"
        accent="before the fault."
        sub="Torque and temperature began rising 8–11 minutes before Line 3 stopped; the camera anomaly crossed its high-risk threshold just before the fault."
      />
      <div className="grid lg:grid-cols-3 gap-5">
        <Card className="p-5 lg:col-span-2">
          <div className="flex gap-4 mb-3">
            {series.map((s) => (
              <span key={s.name} className="flex items-center gap-1.5 text-[12px] text-dim">
                <span className="w-3 h-0.5 rounded" style={{ background: s.color }} /> {s.name}
              </span>
            ))}
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
            {[0, 25, 50, 75].map((g) => (
              <g key={g}>
                <line x1={pad} x2={W - pad} y1={py(g)} y2={py(g)} stroke="#DDE4DF" strokeWidth={1} />
                <text x={pad - 8} y={py(g) + 3} textAnchor="end" fontSize={9} fill="#5E6B64" fontFamily="monospace">{g}</text>
              </g>
            ))}
            {/* fault marker */}
            <line x1={faultX} x2={faultX} y1={pad} y2={H - pad} stroke="#D8492B" strokeWidth={1} strokeDasharray="4 3" />
            <text x={faultX + 4} y={pad + 10} fontSize={9} fill="#D8492B" fontFamily="monospace">08:17 · 0x4F3</text>
            {series.map((s) => (
              <g key={s.name}>
                <path d={line(s.data)} fill="none" stroke={s.color} strokeWidth={2} />
                {s.data.map((v, i) => <circle key={i} cx={px(xs[i])} cy={py(v)} r={3} fill={s.color} />)}
              </g>
            ))}
            {xs.map((x) => (
              <text key={x} x={px(x)} y={H - pad + 14} textAnchor="middle" fontSize={9} fill="#5E6B64" fontFamily="monospace">{x}</text>
            ))}
          </svg>
          <p className="text-center font-mono text-[10px] text-dim uppercase tracking-wide mt-1">Minutes before / after incident</p>
        </Card>
        <Card className="p-5">
          <Eyebrow>Evidence snippets</Eyebrow>
          <div className="mt-3 space-y-3">
            <div>
              <div className="font-mono text-[10px] text-moss uppercase">AI4I telemetry</div>
              <p className="text-[13px] text-ink mt-0.5 leading-snug">Tool wear 226 min + torque 68.9 Nm → overstrain failure mode.</p>
            </div>
            <div>
              <div className="font-mono text-[10px] text-moss uppercase">Future Factories image</div>
              <p className="text-[13px] text-ink mt-0.5 leading-snug">Camera anomaly 0.91 (threshold 0.70) at the fault window.</p>
            </div>
            <div>
              <div className="font-mono text-[10px] text-moss uppercase">CMMS prior note</div>
              <p className="text-[13px] text-ink mt-0.5 leading-snug">"clamp binding, air line — reset didn't hold" (WO-3391).</p>
            </div>
          </div>
        </Card>
      </div>
      <AlertBar tone="warn" title="Plain-English read">
        The pattern is consistent with tool-wear / overstrain plus a potential assembly-quality risk — not a random trip.
      </AlertBar>
    </div>
  );
}

/* ══════════════════ PAGE 4 — EVIDENCE & PROOF ══════════════════ */
function Scoreboard() {
  const passed = evidenceRows.filter((r) => r.captured === 'PASS').length;
  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Evidence & proof"
        title="Every recommendation is backed by real data —"
        accent="here's the proof."
        sub={`Ground-truth check: ${passed} of ${evidenceRows.length} critical signals captured and surfaced for action.`}
        right={<SignalPill tone="ok">Evidence-backed · not guessed</SignalPill>}
      />
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="bg-paper border-b border-line text-left">
                {['Evidence', 'Source', 'Known truth', 'Captured', 'Action surfaced'].map((h) => (
                  <th key={h} className="font-mono text-[10px] text-dim uppercase tracking-wide font-semibold px-4 py-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {evidenceRows.map((r) => (
                <tr key={r.type} className="hover:bg-surface-ok transition-colors">
                  <td className="px-4 py-3 font-semibold text-ink">{r.type}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-dim">{r.source}</td>
                  <td className="px-4 py-3 text-ink/80">{r.groundTruth}</td>
                  <td className="px-4 py-3"><SignalPill tone="ok">{r.captured}</SignalPill></td>
                  <td className="px-4 py-3 text-pine-2 font-medium">{r.actionSurfaced}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <AlertBar tone="ok" title="Why this matters">
        Known truth → agent capture → surfaced action. Every decision on the next screen links back to a source here.
      </AlertBar>
    </div>
  );
}

/* ══════════════════ PAGE 5 — RESTART DECISION ══════════════════ */
function DecisionPack() {
  const maxPct = Math.max(...decision.rootCause.map((r) => r.pct));
  return (
    <div className="space-y-5">
      {/* Decision banner */}
      <Card focal className="overflow-hidden">
        <div className="bg-surface-bad border-l-4 border-coral p-5">
          <Eyebrow dim>Safe restart decision</Eyebrow>
          <h2 className="text-[26px] font-bold text-coral tracking-[-0.02em] mt-1">{decision.verdict}</h2>
          <p className="text-[14px] text-ink/80 mt-1.5 leading-relaxed">{decision.reason}</p>
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Root cause */}
        <Card className="p-5">
          <Eyebrow>Root-cause contribution</Eyebrow>
          <div className="mt-4 space-y-3">
            {decision.rootCause.map((r) => (
              <div key={r.cause}>
                <div className="flex justify-between text-[13px] mb-1">
                  <span className="text-ink">{r.cause}</span>
                  <span className="font-mono text-dim">{r.pct}%</span>
                </div>
                <div className="h-2 rounded-full bg-paper overflow-hidden">
                  <div className="h-full rounded-full bg-pine-2" style={{ width: `${(r.pct / maxPct) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Rationale */}
        <Card className="p-5">
          <Eyebrow>Required before restart</Eyebrow>
          <ul className="mt-3 space-y-2">
            {decision.requiredBeforeRestart.map((r) => (
              <li key={r} className="flex items-start gap-2 text-[13px] text-ink">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-coral shrink-0" />{r}
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <Eyebrow dim>Fallback</Eyebrow>
            <p className="text-[13px] text-ink mt-1 leading-relaxed">{decision.fallback}</p>
          </div>
        </Card>
      </div>

      {/* Action cards */}
      <div className="grid sm:grid-cols-3 gap-3">
        {decision.actions.map((a) => (
          <Card key={a.id} className="p-4">
            <div className="text-[14px] font-bold text-ink">{a.title}</div>
            <div className="font-mono text-[11px] text-dim mt-2">OWNER · {a.owner}</div>
            <div className="mt-1"><SignalPill tone={a.urgency === 'Immediate' ? 'bad' : 'warn'}>{a.urgency}</SignalPill></div>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Eyebrow dim>Approvals</Eyebrow>
          {decision.approvals.map((a) => <SignalPill key={a} tone="neutral">{a}</SignalPill>)}
        </div>
        <div className="font-mono text-[13px] text-pine-2 font-semibold">
          Avoidable loss {money(decision.avoidableLoss.min)}–{money(decision.avoidableLoss.max)}
        </div>
      </div>
    </div>
  );
}

/* ══════════════════ PAGE 6 — ACTION DRAFTS ══════════════════ */
function ActionDrafts() {
  const [active, setActive] = useState(drafts[0].id);
  const [approved, setApproved] = useState<Record<string, boolean>>({});
  const draft = drafts.find((d) => d.id === active)!;

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Generated action drafts"
        title="Diagnosis becomes"
        accent="reviewable artifacts."
        sub="Draft only — review required before sending or writing back to any system."
      />
      <div className="grid lg:grid-cols-3 gap-5">
        {/* Tabs */}
        <div className="space-y-2">
          {drafts.map((d) => (
            <button
              key={d.id}
              onClick={() => setActive(d.id)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                active === d.id ? 'border-pine-2 bg-surface-ok' : 'border-line bg-card hover:border-moss'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-ink">{d.label}</span>
                {approved[d.id] && <SignalPill tone="ok">Approved</SignalPill>}
              </div>
              <div className="font-mono text-[10px] text-dim mt-1 uppercase tracking-wide">{d.owner} · {d.urgency}</div>
            </button>
          ))}
        </div>

        {/* Draft body */}
        <Card className="p-5 lg:col-span-2 flex flex-col">
          <div className="flex items-center justify-between">
            <Eyebrow>{draft.label}</Eyebrow>
            <span className="font-mono text-[10px] text-moss uppercase tracking-wide">SOP {draft.sop}</span>
          </div>
          <pre className="mt-3 flex-1 whitespace-pre-wrap font-mono text-[12.5px] text-ink/90 leading-relaxed bg-paper rounded-lg p-4 border border-line">
{draft.body}
          </pre>
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={() => setApproved((a) => ({ ...a, [draft.id]: !a[draft.id] }))}
              className="btn-primary px-4 py-2 text-sm"
            >{approved[draft.id] ? 'Approved ✓' : 'Approve Draft'}</button>
            <button
              onClick={() => navigator.clipboard?.writeText(draft.body)}
              className="btn-ghost px-4 py-2 text-sm"
            >Copy</button>
            <span className="font-mono text-[10px] text-dim uppercase tracking-wide ml-auto">Demo state only · no CMMS write-back</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
