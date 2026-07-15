'use client';

import { useEffect, useRef, useState } from 'react';
import { Eyebrow, SectionHeader, Card, SignalPill, AlertBar } from '@/components/ui';
import {
  getTwinConfig, getGate, simulate, postAudit,
  type TwinConfig, type SimResult, type GateBoard, type Control,
} from '@/lib/twin';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';
const money = (n: number) => '$' + Math.round(n).toLocaleString();
const statusTone = (s: string): Tone => s === 'pass' ? 'ok' : s === 'review' ? 'warn' : 'bad';

export default function DecisionTwin({ onContinue, context, decisionId }: {
  onContinue?: () => void;
  context?: { machine?: string; order?: string };
  /** Simulate against this real incident rather than the scripted scenario. */
  decisionId?: string;
}) {
  const [cfg, setCfg] = useState<TwinConfig | null>(null);
  const [gate, setGate] = useState<GateBoard | null>(null);
  const [factors, setFactors] = useState<Record<string, any>>({});
  const [res, setRes] = useState<SimResult | null>(null);
  const timer = useRef<any>(null);

  useEffect(() => {
    if (!decisionId) return;
    getTwinConfig(decisionId).then((c) => {
      setCfg(c);
      const init: Record<string, any> = {};
      c.controls.factors.forEach((f) => { init[f.factor_id] = f.default; });
      setFactors(init);
    }).catch(() => {});
    getGate(decisionId).then(setGate).catch(() => {});
  }, [decisionId]);

  // Debounced deterministic simulation as factors change
  useEffect(() => {
    if (!cfg || !decisionId || Object.keys(factors).length === 0) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      simulate(factors, decisionId!).then((r) => {
        setRes(r);
        postAudit({
          scenario_id: r.scenario_id, changed_factors: r.changed_factors,
          recommended_option: r.recommended_option,
          blocked_actions: gate?.blocked_actions ?? [], generated_drafts: [],
        }).catch(() => {});
      }).catch(() => {});
    }, 200);
    return () => clearTimeout(timer.current);
  }, [factors, cfg]); // eslint-disable-line

  const set = (id: string, v: any) => setFactors((f) => ({ ...f, [id]: v }));
  const applyPreset = (overrides: Record<string, any>) => setFactors((f) => ({ ...f, ...overrides }));
  const reset = () => { if (cfg) { const i: Record<string, any> = {}; cfg.controls.factors.forEach((f) => i[f.factor_id] = f.default); setFactors(i); } };

  if (!decisionId) return <div className="text-center py-16 text-dim text-sm">The Recovery Twin models a specific incident — open one from Operations.</div>;
  if (!cfg) return <div className="text-center py-16 text-dim text-sm">Loading Decision Twin…</div>;

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="Interactive Recovery Decision Twin"
        title="Compare safe recovery paths"
        accent={`for ${cfg.controls.order.customer} ${cfg.controls.order.id}`}
        sub="Adjust the assumptions on the left; the options, recommendation, and explanation update instantly and deterministically."
      />


      {/* Top banner */}
      <div className="alert alert-warn bg-surface-warn border border-l-4 p-4 flex items-center justify-between gap-4 flex-wrap">
        <p className="text-[14px] text-ink">
          <span className="font-bold">Decision required before 8:45 AM.</span> {cfg.controls.order.customer} {cfg.controls.order.id} is at risk. Adjust assumptions to compare safe recovery paths.
        </p>
        <span className="font-mono text-[10px] text-pine-2 uppercase tracking-wide shrink-0">Read-only OT mode</span>
      </div>

      <div className="grid lg:grid-cols-[280px_1fr_300px] gap-4">
        {/* ── LEFT: Scenario controls ── */}
        <Card className="p-4 space-y-4">
          <Eyebrow>Scenario controls</Eyebrow>
          {cfg.controls.factors.map((f) => (
            <ControlInput key={f.factor_id} f={f} value={factors[f.factor_id]} onChange={(v) => set(f.factor_id, v)} />
          ))}
          <div className="pt-2 border-t border-line">
            <Eyebrow dim>Presets</Eyebrow>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {cfg.presets.map((p) => (
                <button key={p.preset_id} onClick={() => applyPreset(p.factor_overrides)} title={p.description}
                  className="text-[11px] font-semibold px-2 py-1 rounded-lg border border-line bg-card text-dim hover:border-moss hover:text-pine-2 transition-colors">
                  {p.label}
                </button>
              ))}
              <button onClick={reset} className="text-[11px] font-semibold px-2 py-1 rounded-lg text-dim hover:text-ink">Reset</button>
            </div>
          </div>
        </Card>

        {/* ── CENTER: Option cards ── */}
        <div className="space-y-3">
          <Eyebrow dim>Outcome comparison</Eyebrow>
          {res?.options.map((o) => {
            const tone: Tone = !o.allowed ? 'bad' : o.is_recommended ? 'ok' : 'warn';
            const surf = tone === 'ok' ? 'bg-surface-ok border-moss' : tone === 'bad' ? 'bg-surface-bad border-coral/40' : 'bg-surface-warn border-amber/40';
            return (
              <div key={o.option_id} className={`rounded-card border p-4 ${surf}`}>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[15px] font-bold text-ink">{o.label}</h3>
                    {o.is_recommended && <SignalPill tone="ok">Recommended</SignalPill>}
                    {!o.allowed && <SignalPill tone="bad">{o.option_id === 'restart_now' ? 'Blocked' : 'Unavailable'}</SignalPill>}
                  </div>
                  <span className="font-mono text-[10px] text-dim uppercase tracking-wide">Owner · {o.owner}</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <Metric label="Ship prob" value={`${Math.round(o.ship_probability * 100)}%`} tone={o.ship_probability >= 0.8 ? 'ok' : o.ship_probability >= 0.65 ? 'warn' : 'bad'} />
                  {/* Unpriced when the plant has no cost model. The twin still
                      ranks these options — on ship probability and QA escape —
                      so the column is empty rather than the comparison absent. */}
                  <Metric label="Expected loss"
                    value={o.expected_loss === null ? 'Not priced' : money(o.expected_loss)}
                    tone="neutral" />
                  <Metric label="QA escape risk" value={`${Math.round(o.qa_escape_risk * 100)}%`} tone={o.qa_escape_risk <= 0.1 ? 'ok' : o.qa_escape_risk <= 0.2 ? 'warn' : 'bad'} />
                </div>
                <div className="mt-2.5 flex items-center gap-2">
                  <span className="font-mono text-[10px] text-dim uppercase tracking-wide">Safety</span>
                  <SignalPill tone={statusTone(o.safety_status)}>{o.safety_status}</SignalPill>
                  {o.blocked_by.length > 0 && <span className="font-mono text-[10px] text-coral">blocked by {o.blocked_by.join(', ')}</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── RIGHT: Explanation + Gates ── */}
        <div className="space-y-3">
          <Card className="p-4">
            <Eyebrow>Why this recommendation?</Eyebrow>
            <p className="text-[13px] text-ink mt-2 leading-relaxed">{res?.explanation.summary}</p>
            {res && res.explanation.triggered_constraints.length > 0 && (
              <div className="mt-2.5">
                <Eyebrow dim>Triggered constraints</Eyebrow>
                <ul className="mt-1 space-y-1">
                  {res.explanation.triggered_constraints.map((t, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[12px] text-ink/80"><span className="mt-1.5 w-1 h-1 rounded-full bg-amber shrink-0" />{t}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-2.5 pt-2.5 border-t border-line">
              <Eyebrow dim>Next best action</Eyebrow>
              <p className="text-[13px] text-pine-2 font-medium mt-1">{res?.next_best_action}</p>
            </div>
          </Card>

          {/* Assumption ledger */}
          <Card className="p-4">
            <Eyebrow>Assumption ledger</Eyebrow>
            <div className="mt-2 space-y-1.5">
              {res?.assumptions.map((a) => (
                <div key={a.assumption_id} className="flex items-center justify-between text-[12px]">
                  <span className="text-dim">{a.assumption_id.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-ink">{String(a.value)}{a.unit && ` ${a.unit}`}<span className="text-moss ml-1 text-[10px]">{a.source_file.split('.')[0]}</span></span>
                </div>
              ))}
            </div>
          </Card>

          {/* Facility gate */}
          {gate && (
            <Card className="p-4">
              <div className="flex items-center justify-between mb-2">
                <Eyebrow>Facility gate</Eyebrow>
                <SignalPill tone={gate.restart_blocked ? 'bad' : 'ok'}>{gate.restart_blocked ? 'Restart blocked' : 'Clear'}</SignalPill>
              </div>
              <div className="space-y-1.5">
                {gate.gates.map((g) => (
                  <div key={g.gate_id} className="flex items-center justify-between gap-2" title={`${g.reason} — ${g.owner}`}>
                    <span className="text-[12px] text-ink truncate">{g.label}</span>
                    <SignalPill tone={statusTone(g.status)}>{g.status}</SignalPill>
                  </div>
                ))}
              </div>
              <p className="font-mono text-[9.5px] text-dim uppercase tracking-wide mt-2.5 leading-snug">{gate.trust_banner}</p>
            </Card>
          )}

          {/* Audit strip */}
          {res && (
            <div className="font-mono text-[10px] text-dim uppercase tracking-wide px-1">
              Audit · {res.changed_factors.length} factor{res.changed_factors.length === 1 ? '' : 's'} changed · rec: {res.recommended_option} · {gate?.blocked_actions.length ?? 0} actions blocked · draft-only
            </div>
          )}
        </div>
      </div>

      {/* Bottom CTAs */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button className="btn-primary px-4 py-2 text-sm">Prepare recommended path</button>
        <button className="btn-ghost px-4 py-2 text-sm">Prepare fallback</button>
        <button className="btn-ghost px-4 py-2 text-sm">Generate management explanation</button>
        {onContinue && <button onClick={onContinue} className="ml-auto btn-primary px-4 py-2 text-sm">Continue to drafts →</button>}
      </div>
    </div>
  );
}

// ── small pieces ──
function Metric({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const c = tone === 'ok' ? 'text-pine-2' : tone === 'warn' ? 'text-[#9A6B15]' : tone === 'bad' ? 'text-coral' : 'text-ink';
  return (
    <div>
      <p className="font-mono text-[9px] text-dim uppercase tracking-wide">{label}</p>
      <p className={`font-mono text-[16px] font-bold ${c}`}>{value}</p>
    </div>
  );
}

function ControlInput({ f, value, onChange }: { f: Control; value: any; onChange: (v: any) => void }) {
  if (f.type === 'slider') {
    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-[12px] text-ink font-medium">{f.label}</label>
          <span className="font-mono text-[12px] font-bold text-pine-2">{value}{f.unit && ` ${f.unit}`}</span>
        </div>
        <input type="range" min={f.min} max={f.max} step={f.step ?? 1} value={value}
          onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-pine-2" />
      </div>
    );
  }
  if (f.type === 'toggle') {
    return (
      <div className="flex items-center justify-between">
        <label className="text-[12px] text-ink font-medium">{f.label}</label>
        <div className="flex gap-1">
          {[true, false].map((v) => (
            <button key={String(v)} onClick={() => onChange(v)}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-lg border transition-colors ${value === v ? 'bg-pine-2 text-white border-pine-2' : 'bg-card text-dim border-line hover:border-moss'}`}>
              {v ? 'Yes' : 'No'}
            </button>
          ))}
        </div>
      </div>
    );
  }
  // select
  return (
    <div>
      <label className="text-[12px] text-ink font-medium">{f.label}</label>
      <div className="flex flex-wrap gap-1 mt-1">
        {(f.options ?? []).map((opt) => (
          <button key={String(opt)} onClick={() => onChange(opt)}
            className={`text-[11px] font-semibold px-2 py-1 rounded-lg border transition-colors ${value === opt ? 'bg-pine-2 text-white border-pine-2' : 'bg-card text-dim border-line hover:border-moss'}`}>
            {String(opt)}{f.unit && typeof opt === 'number' ? ` ${f.unit}` : ''}
          </button>
        ))}
      </div>
    </div>
  );
}
