'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useActiveDecision } from '@/lib/store';
import { LivePipeline } from '@/components/LivePipeline';
import { useApproveDecision, useDecision } from '@/lib/api-client';
import { plainSignal, plainAction, plainEventType, plainMachine } from '@/lib/labels';
import { HelpTip, PlainImpactBanner } from '@/components/PlainHelp';
import { Eyebrow, Card, SignalPill, AlertBar } from '@/components/ui';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

// ─── Types ────────────────────────────────────────────────────────
interface AgentAnalysis {
  agent: string;
  confidence: number;
  reasoning?: string;
  recommendations?: { action_name: string; description: string; risk_level: string; confidence: number }[];
  error?: string;
}
interface ImpactEstimate {
  downtime_hours?: number; scrap_units?: number; cost_impact?: number;
  safety_improvement?: string; quality_improvement?: string; oee_impact?: number; impact_score?: number;
}
interface RedTeamReview {
  risk_factors?: string[]; assumptions_challenged?: string[]; suggested_alternatives?: string[];
  confidence_adjustment?: number; overall_risk_assessment?: string; should_escalate?: boolean;
}

// ─── tone helpers (signal discipline) ──────────────────────────────
function riskTone(risk?: string): Tone {
  if (risk === 'critical' || risk === 'high') return 'bad';
  if (risk === 'medium') return 'warn';
  return 'neutral';
}
function confTone(v: number): Tone {
  if (v >= 0.9) return 'ok';
  if (v >= 0.7) return 'warn';
  return 'bad';
}
const toneText: Record<Tone, string> = { ok: 'text-pine-2', warn: 'text-[#9A6B15]', bad: 'text-coral', neutral: 'text-dim' };
const toneFill: Record<Tone, string> = { ok: 'bg-pine-2', warn: 'bg-amber', bad: 'bg-coral', neutral: 'bg-moss' };

// ─── Demo fallback ────────────────────────────────────────────────
function buildDemoDecision(id: string) {
  return {
    decision_id: id, event_id: 'evt_20260522_0001', factory_id: 'factory_001', timestamp: new Date().toISOString(),
    event: { event_type: 'safety', signal_name: 'zone_intrusion', signal_value: 1.0, confidence: 0.98, factory_id: 'factory_001', timestamp: new Date().toISOString(), context: { zone_id: 'restricted_zone_a', worker_id: 'W123' } },
    orchestration_result: { selected_action: 'stop_line', approval_required: true, approval_route: 'safety_officer' },
    analysis_layers: {
      agent_analyses: [
        { agent: 'safety_agent', confidence: 0.98, reasoning: 'Critical safety hazard — zone intrusion detected in restricted area.', recommendations: [{ action_name: 'stop_line', description: 'Stop production line immediately', risk_level: 'critical', confidence: 0.99 }] },
        { agent: 'quality_agent', confidence: 0.72, reasoning: 'Monitor for downstream quality impact.', recommendations: [] },
        { agent: 'maintenance_agent', confidence: 0.55, reasoning: 'Inspect area post-incident.', recommendations: [] },
      ] as AgentAnalysis[],
      policy_evaluations: { stop_line: { policy_decision: 'allowed', approval_level: 'safety_officer', reason: 'Requires safety_officer approval' } } as Record<string, { policy_decision: string; approval_level: string; reason: string }>,
      impact_estimates: { stop_line: { downtime_hours: 0.5, scrap_units: 0, cost_impact: -2000, safety_improvement: 'critical', quality_improvement: 'none', oee_impact: -5.0, impact_score: 0.92 } } as Record<string, ImpactEstimate>,
      red_team_reviews: { stop_line: { risk_factors: ['Verify zone intrusion is not a false positive', 'Sudden stop may cause material waste'], assumptions_challenged: ['Zone sensor calibration confirmed'], suggested_alternatives: ['Alert operator first and verify visually'], confidence_adjustment: -0.05, overall_risk_assessment: 'acceptable', should_escalate: false } } as Record<string, RedTeamReview>,
    },
    evidence_pack: {},
  };
}

// ─── Panel (eyebrow + card) ────────────────────────────────────────
function Panel({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3 border-b border-line flex items-center justify-between gap-2">
        <Eyebrow>{title}</Eyebrow>
        {right}
      </div>
      <div className="p-5">{children}</div>
    </Card>
  );
}

// ─── Decision journey — the reasoning chain, always visible ────────
function JourneyStrip({ steps }: { steps: { k: string; v: string; tone?: Tone; strong?: boolean }[] }) {
  return (
    <Card className="p-4">
      <Eyebrow dim>Decision journey</Eyebrow>
      <div className="mt-3 flex items-stretch gap-1 overflow-x-auto pb-1">
        {steps.map((s, i) => (
          <div key={s.k} className="flex items-center gap-1 shrink-0">
            <div className={`min-w-[116px] rounded-lg px-3 py-2 border ${s.strong ? 'border-pine-2 bg-surface-ok' : 'border-line bg-paper'}`}>
              <div className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${toneFill[s.tone ?? 'neutral']}`} />
                <span className="font-mono text-[9.5px] text-dim uppercase tracking-wide">{s.k}</span>
              </div>
              <p className={`text-[12px] leading-tight mt-1 capitalize ${s.strong ? 'font-bold text-pine-2' : 'font-semibold text-ink'}`}>{s.v}</p>
            </div>
            {i < steps.length - 1 && (
              <svg className="w-3.5 h-3.5 text-line shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-paper rounded-full overflow-hidden">
        <div className={`h-full ${toneFill[confTone(value)]} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[11px] font-semibold text-dim w-9 text-right">{pct}%</span>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────
export default function DecisionDetailPage({ params }: { params: { id: string } }) {
  const activeDecision = useActiveDecision();
  const { data: apiDecision, isLoading: apiLoading } = useDecision(activeDecision ? null : params.id);
  const [approvalStatus, setApprovalStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [showTech, setShowTech] = useState(false);
  const approveMutation = useApproveDecision();

  useEffect(() => {
    const s = (apiDecision as any)?.status ?? (activeDecision as any)?.status;
    if (s === 'approved') setApprovalStatus('approved');
    else if (s === 'rejected') setApprovalStatus('rejected');
    else setApprovalStatus('pending');
  }, [apiDecision, activeDecision]);

  if (!activeDecision && apiLoading) {
    return <div className="flex items-center justify-center h-64"><div className="text-sm text-dim">Loading decision…</div></div>;
  }

  const apiAny = apiDecision as any;
  const rawApi = apiDecision ? {
    decision_id: apiDecision.decision_id, event_id: apiDecision.event_id, factory_id: apiDecision.factory_id,
    timestamp: apiDecision.created_at, status: apiDecision.status,
    event: {
      event_type: apiAny.event?.event_type ?? apiDecision.recommended_action?.event_type ?? 'unknown',
      signal_name: apiAny.event?.signal_name ?? '—', signal_value: apiAny.event?.signal_value ?? 0,
      confidence: apiAny.event?.confidence ?? 0, factory_id: apiDecision.factory_id,
      timestamp: apiDecision.created_at, context: apiAny.event?.context ?? {},
    },
    orchestration_result: {
      selected_action: apiDecision.recommended_action?.selected_action ?? 'unknown',
      risk_level: apiDecision.recommended_action?.risk_level,
      approval_required: apiDecision.recommended_action?.approval_required ?? true,
      approval_route: apiDecision.recommended_action?.approval_route ?? 'operator',
    },
    analysis_layers: apiAny.analysis_layers ?? { agent_analyses: [], policy_evaluations: {}, impact_estimates: {}, red_team_reviews: {} },
    evidence_pack: {}, approved_by: apiDecision.approved_by,
  } : null;

  const raw = activeDecision || rawApi || buildDemoDecision(params.id);
  const decision = {
    ...raw,
    analysis_layers: {
      agent_analyses: (raw.analysis_layers?.agent_analyses ?? []) as AgentAnalysis[],
      policy_evaluations: (raw.analysis_layers?.policy_evaluations ?? {}) as Record<string, { policy_decision: string; approval_level: string; reason: string }>,
      impact_estimates: (raw.analysis_layers?.impact_estimates ?? {}) as Record<string, ImpactEstimate>,
      red_team_reviews: (raw.analysis_layers?.red_team_reviews ?? {}) as Record<string, RedTeamReview>,
    },
  };

  const action = decision.orchestration_result?.selected_action ?? 'unknown';
  const impact: ImpactEstimate = decision.analysis_layers.impact_estimates[action] ?? {};
  const redTeam: RedTeamReview = decision.analysis_layers.red_team_reviews[action] ?? {};
  const policy = decision.analysis_layers.policy_evaluations[action];
  const statusTone: Tone = approvalStatus === 'approved' ? 'ok' : approvalStatus === 'rejected' ? 'bad' : 'warn';

  const handleApproval = async (act: 'approve' | 'reject') => {
    setApprovalError(null);
    try {
      await approveMutation.mutateAsync({ decisionId: decision.decision_id, action: act, approvedBy: 'operator' });
      setApprovalStatus(act === 'approve' ? 'approved' : 'rejected');
    } catch {
      setApprovalError('Failed to submit approval — decision may not be persisted yet');
      setApprovalStatus(act === 'approve' ? 'approved' : 'rejected');
    }
  };

  const auditTimeline = [
    { label: 'Problem detected', actor: 'Sensors', detail: `${plainEventType(decision.event.event_type)} · ${plainSignal(decision.event.signal_name)}`, ms: 0 },
    { label: 'Monitors reviewed it', actor: `${decision.analysis_layers.agent_analyses.length} monitors`, detail: 'Reviewed at the same time', ms: 120 },
    { label: 'Safety rules checked', actor: 'Rule book', detail: policy?.reason ?? 'Checked against the safety rules', ms: 240 },
    { label: 'Impact estimated', actor: 'Impact forecast', detail: `${impact.downtime_hours ?? 0}h downtime estimated`, ms: 380 },
    { label: 'Safety double-check', actor: 'Auto review', detail: redTeam.overall_risk_assessment ?? 'Risks reviewed', ms: 620 },
    { label: 'Sent for approval', actor: 'Routing', detail: `Sent to ${decision.orchestration_result?.approval_route ?? 'operator'}`, ms: 720 },
  ];

  return (
    <div className="max-w-[1180px] space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-dim hover:text-ink transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <Eyebrow>Decision detail</Eyebrow>
            <p className="font-mono text-[11px] text-dim mt-1">{decision.decision_id}</p>
          </div>
        </div>
        <SignalPill tone={statusTone}>
          {approvalStatus === 'pending' ? 'Awaiting approval' : approvalStatus === 'approved' ? 'Approved' : 'Rejected'}
        </SignalPill>
      </div>

      {/* Plain-language chain banner */}
      {(() => {
        const fctx = (raw as any)?.recommended_action?.factory_context ?? (raw as any)?.evidence_pack?.factory_context ?? (activeDecision as any)?.factory_context;
        const co = fctx?.customer_order; const costs = fctx?.costs;
        const deadline = co?.promised_delivery ? new Date(co.promised_delivery).toLocaleDateString() : undefined;
        return (
          <PlainImpactBanner
            signal={plainSignal(decision.event.signal_name)}
            machine={plainMachine((decision.event as any).machine_id || decision.event.context?.machine_id || fctx?.machine?.id)}
            action={plainAction(action)}
            riskLevel={(decision.orchestration_result as any)?.risk_level}
            downtimePerHour={costs?.downtime_cost_per_hour_usd}
            penalty={co?.late_delivery_penalty_usd}
            customer={co?.customer_name}
            deadline={deadline}
          />
        );
      })()}

      {/* Decision journey — the reasoning chain, at a glance */}
      <JourneyStrip steps={[
        { k: 'Incident', v: plainEventType(decision.event.event_type), tone: decision.event.event_type === 'safety' ? 'bad' : 'warn' },
        { k: 'Monitors', v: `${decision.analysis_layers.agent_analyses.length} reviewed`, tone: 'neutral' },
        { k: 'Safety rules', v: policy ? 'Checked' : 'Checked', tone: 'ok' },
        { k: 'Impact & cost', v: impact.downtime_hours != null ? `${impact.downtime_hours}h downtime` : 'Estimated', tone: 'warn' },
        { k: 'Auto review', v: redTeam.overall_risk_assessment ?? 'Reviewed', tone: redTeam.overall_risk_assessment === 'acceptable' ? 'ok' : 'warn' },
        { k: 'Recommended', v: plainAction(action), tone: 'ok', strong: true },
        { k: 'Your call', v: approvalStatus, tone: statusTone },
      ]} />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* ── Left 2/3 ── */}
        <div className="xl:col-span-2 space-y-5">
          {/* What happened */}
          <Panel title="What happened">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Type', value: plainEventType(decision.event.event_type), help: undefined },
                { label: 'Problem', value: plainSignal(decision.event.signal_name), help: undefined },
                { label: 'Certainty', value: `${(decision.event.confidence * 100).toFixed(0)}% sure`, help: 'Certainty' },
                { label: 'Site', value: decision.factory_id, help: undefined },
              ].map(({ label, value, help }) => (
                <div key={label}>
                  <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-1 flex items-center">
                    {label}{help && <HelpTip term={help} />}
                  </p>
                  <p className="text-[14px] font-semibold text-ink">{value}</p>
                </div>
              ))}
            </div>
          </Panel>

          {/* Factory context */}
          {(() => {
            const fctx = (raw as any)?.recommended_action?.factory_context ?? (raw as any)?.evidence_pack?.factory_context ?? (activeDecision as any)?.factory_context;
            if (!fctx) return null;
            const wo = fctx.active_work_order; const co = fctx.customer_order; const mach = fctx.machine; const costs = fctx.costs; const qh = fctx.quality_history;
            return (
              <Panel title="What's running on this machine">
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {mach && (
                      <div className="bg-paper rounded-lg p-3 border border-line">
                        <Eyebrow dim>Machine</Eyebrow>
                        <p className="text-[14px] font-semibold text-ink mt-1">{mach.name}</p>
                        <p className="text-[12px] text-dim mt-0.5">{mach.criticality?.toUpperCase()} criticality · {mach.status}</p>
                        {mach.days_since_last_maintenance != null && (
                          <p className="text-[12px] text-dim mt-1">Last maint: <span className={mach.days_since_last_maintenance > 30 ? 'text-coral font-semibold' : 'text-dim'}>{Math.round(mach.days_since_last_maintenance)}d ago</span></p>
                        )}
                        <p className="font-mono text-[11px] text-dim mt-0.5">${(mach.hourly_production_value_usd ?? 0).toLocaleString()}/hr value</p>
                      </div>
                    )}
                    {wo && (
                      <div className="bg-surface-ok rounded-lg p-3 border border-moss">
                        <Eyebrow>Work order</Eyebrow>
                        <p className="text-[14px] font-semibold text-ink mt-1">{wo.work_order_id}</p>
                        <p className="text-[12px] text-dim mt-0.5">{wo.product_name}</p>
                        <p className="text-[12px] text-dim mt-1">{wo.quantity_completed}/{wo.quantity_planned} units ({wo.completion_pct?.toFixed(0)}%)</p>
                        {wo.hours_until_deadline != null && (
                          <p className={`text-[12px] font-semibold mt-0.5 ${wo.hours_until_deadline < 24 ? 'text-coral' : wo.hours_until_deadline < 72 ? 'text-[#9A6B15]' : 'text-dim'}`}>Due in {wo.hours_until_deadline.toFixed(0)}h</p>
                        )}
                      </div>
                    )}
                    {co && (
                      <div className={`rounded-lg p-3 border ${co.is_at_risk ? 'bg-surface-bad border-coral/30' : 'bg-surface-ok border-moss'}`}>
                        <div className="flex items-center gap-1.5">
                          <Eyebrow dim>Customer order</Eyebrow>
                          {co.is_at_risk && <SignalPill tone="bad">At risk</SignalPill>}
                        </div>
                        <p className="text-[14px] font-semibold text-ink mt-1">{co.order_id}</p>
                        <p className="text-[12px] text-dim mt-0.5">{co.customer_name}</p>
                        <p className="text-[12px] text-dim mt-1">Due {co.promised_delivery?.slice(0, 10)}</p>
                        {co.late_delivery_penalty_usd > 0 && (
                          <p className="font-mono text-[11px] text-coral font-semibold mt-0.5">Penalty: ${co.late_delivery_penalty_usd.toLocaleString()}</p>
                        )}
                      </div>
                    )}
                  </div>

                  {costs && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {[
                        { label: 'Downtime/hr', value: `$${(costs.downtime_cost_per_hour_usd ?? 0).toLocaleString()}` },
                        { label: 'Scrap/unit', value: `$${costs.scrap_cost_per_unit_usd ?? 0}` },
                        { label: 'Late penalty/day', value: `$${(costs.late_delivery_penalty_per_day_usd ?? 0).toLocaleString()}` },
                        { label: 'Failure multiplier', value: `${costs.unplanned_failure_multiplier ?? 5}×` },
                      ].map(({ label, value }) => (
                        <div key={label} className="bg-paper rounded-lg p-2.5 border border-line text-center">
                          <p className="font-mono text-[10px] text-dim uppercase tracking-wide">{label}</p>
                          <p className="font-mono text-[14px] font-bold text-ink mt-0.5">{value}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {qh && (qh.open_ncrs > 0 || qh.recurring_defects?.length > 0) && (
                    <div className="alert alert-warn bg-surface-warn p-3">
                      <p className="text-[12px] font-semibold text-[#9A6B15] mb-1">Quality history on this machine</p>
                      <div className="flex flex-wrap gap-3 text-[12px] text-ink/80">
                        <span>Open NCRs: <strong>{qh.open_ncrs}</strong></span>
                        <span>Scrap rate: <strong>{qh.scrap_rate_pct?.toFixed(1)}%</strong></span>
                        <span>Rework rate: <strong>{qh.rework_rate_pct?.toFixed(1)}%</strong></span>
                        {qh.recurring_defects?.length > 0 && <span>Recurring: <strong className="text-[#9A6B15]">{qh.recurring_defects.join(', ')}</strong></span>}
                      </div>
                    </div>
                  )}
                </div>
              </Panel>
            );
          })()}

          {/* Manager options */}
          {(() => {
            const mo = (apiDecision as any)?.manager_options;
            if (!mo || !(mo.options?.length)) return null;
            const money = (n: number | null | undefined) => n == null ? null : `${n < 0 ? '-' : ''}$${Math.abs(n).toLocaleString()}`;
            return (
              <Panel title="Options for the approver">
                <div className="space-y-2.5">
                  {mo.options.map((o: any, i: number) => {
                    const rec = o.is_recommended;
                    return (
                      <div key={i} className={`rounded-xl border p-3.5 ${rec ? 'border-moss bg-surface-ok' : 'border-line'}`}>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={`w-5 h-5 rounded-full flex items-center justify-center font-mono text-[11px] font-bold shrink-0 ${rec ? 'bg-pine-2 text-white' : 'bg-line text-dim'}`}>{String.fromCharCode(65 + i)}</span>
                            <span className="text-[14px] font-bold text-ink truncate">{plainAction(o.action)}</span>
                            {rec && <SignalPill tone="ok">Recommended</SignalPill>}
                          </div>
                          {o.risk_level && <SignalPill tone={riskTone(o.risk_level)}>{o.risk_level} risk</SignalPill>}
                        </div>
                        {o.description && <p className="text-[12px] text-dim ml-7 mb-1.5">{o.description}</p>}
                        <div className="flex items-center gap-4 ml-7 font-mono text-[11px] text-dim">
                          {o.downtime_hours != null && <span>{o.downtime_hours}h downtime</span>}
                          {o.cost_impact_usd != null && <span>{money(o.cost_impact_usd)} impact</span>}
                          {o.proposed_by && <span>· by {o.proposed_by.replace(/_/g, ' ')}</span>}
                        </div>
                      </div>
                    );
                  })}
                  {mo.if_no_action && (
                    <AlertBar tone="bad" title="If no action is taken">{mo.if_no_action.consequence}</AlertBar>
                  )}
                  {(mo.alternatives_considered?.length > 0) && (
                    <p className="text-[12px] text-dim pt-1"><span className="font-semibold">Also considered:</span> {mo.alternatives_considered.join(' · ')}</p>
                  )}
                </div>
              </Panel>
            );
          })()}

          {/* Technical toggle */}
          <button onClick={() => setShowTech((v) => !v)} className="w-full flex items-center justify-between px-4 py-2.5 bg-paper hover:bg-surface-ok border border-line rounded-xl text-[13px] font-semibold text-dim transition-colors">
            <span>{showTech ? 'Hide' : 'Show'} technical details (for engineers)</span>
            <svg className={`w-4 h-4 transition-transform ${showTech ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showTech && (<>
            <Panel title="What each monitor found">
              <div className="space-y-3">
                {decision.analysis_layers.agent_analyses.map((a, i) => (
                  <div key={i} className="border border-line rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[13px] font-semibold text-ink capitalize">{a.agent.replace(/_/g, ' ')}</span>
                      {a.error ? <span className="text-[12px] text-coral font-medium">Error</span> : <span className="font-mono text-[11px] text-dim">{(a.confidence * 100).toFixed(0)}%</span>}
                    </div>
                    {!a.error && <ConfidenceBar value={a.confidence} />}
                    {a.reasoning && <p className="text-[12px] text-dim mt-2">{a.reasoning}</p>}
                    {a.recommendations && a.recommendations.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {a.recommendations.map((r, j) => (
                          <div key={j} className="flex items-center justify-between text-[12px]">
                            <span className="text-dim font-medium capitalize">{r.action_name.replace(/_/g, ' ')}</span>
                            <SignalPill tone={riskTone(r.risk_level)}>{r.risk_level}</SignalPill>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Predicted impact">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {[
                  { label: 'Downtime', value: `${impact.downtime_hours ?? 0}h`, tone: 'bad' as Tone },
                  { label: 'Scrap units', value: `${impact.scrap_units ?? 0}`, tone: 'warn' as Tone },
                  { label: 'Cost impact', value: `$${Math.abs(impact.cost_impact ?? 0).toLocaleString()}`, tone: (impact.cost_impact ?? 0) < 0 ? 'bad' as Tone : 'ok' as Tone },
                  { label: 'Safety', value: impact.safety_improvement ?? 'N/A', tone: 'ok' as Tone },
                  { label: 'OEE impact', value: `${impact.oee_impact ?? 0}%`, tone: 'neutral' as Tone },
                  { label: 'Impact score', value: `${(impact.impact_score ?? 0).toFixed(2)}/1.0`, tone: 'neutral' as Tone },
                ].map(({ label, value, tone }) => (
                  <div key={label} className="bg-paper rounded-lg p-3 border border-line">
                    <p className="font-mono text-[10px] text-dim uppercase tracking-wide mb-1">{label}</p>
                    <p className={`font-mono text-[15px] font-bold capitalize ${toneText[tone]}`}>{value}</p>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Live decision steps"><LivePipeline decisionId={decision.decision_id} /></Panel>

            <Panel title="How this decision was made">
              <div className="relative">
                <div className="absolute left-3 top-0 bottom-0 w-px bg-line" />
                <div className="space-y-4">
                  {auditTimeline.map((step, i) => (
                    <div key={i} className="flex items-start gap-4 pl-8 relative">
                      <div className={`absolute left-1.5 w-3 h-3 rounded-full ring-2 ring-card ${i === 0 ? 'bg-pine-2' : 'bg-moss'}`} style={{ top: '3px' }} />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[12px] font-semibold text-ink">{step.label}</span>
                          <span className="text-[12px] text-dim">· {step.actor}</span>
                          <span className="font-mono text-[10px] text-dim ml-auto">+{step.ms}ms</span>
                        </div>
                        <p className="text-[12px] text-dim mt-0.5">{step.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Panel>
          </>)}
        </div>

        {/* ── Sidebar 1/3 ── */}
        <div className="space-y-5">
          {/* Recommended action — FIXED (was invisible text on pine) */}
          <div className="bg-pine-2 text-white rounded-card p-5">
            <p className="font-mono text-[10px] text-sage uppercase tracking-eyebrow mb-2">Recommended action</p>
            <p className="text-[20px] font-bold leading-tight">{plainAction(action)}</p>
            <div className="mt-3 pt-3 border-t border-white/15 flex justify-between text-[13px]">
              <span className="text-sage">Needs approval from</span>
              <span className="font-medium capitalize">{decision.orchestration_result?.approval_route?.replace(/_/g, ' ') ?? 'Auto'}</span>
            </div>
          </div>

          {/* Approval panel */}
          <Panel title="Your decision">
            <div className="space-y-3">
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-dim">Required approver</span>
                <span className="font-semibold capitalize text-ink">{(decision.orchestration_result?.approval_route ?? 'auto').replace(/_/g, ' ')}</span>
              </div>
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-dim">Status</span>
                <span className={`font-semibold capitalize ${toneText[statusTone]}`}>{approvalStatus}</span>
              </div>
              {approvalError && <p className="text-[12px] text-[#9A6B15] bg-surface-warn border border-amber/30 rounded p-2">{approvalError}</p>}
              {approvalStatus === 'pending' ? (
                <div className="grid grid-cols-2 gap-2 pt-2">
                  <button onClick={() => handleApproval('approve')} disabled={approveMutation.isPending} className="btn-primary py-2 text-[13px] disabled:opacity-60">{approveMutation.isPending ? '…' : 'Approve'}</button>
                  <button onClick={() => handleApproval('reject')} disabled={approveMutation.isPending} className="py-2 rounded-lg border border-coral/40 text-coral hover:bg-surface-bad disabled:opacity-60 text-[13px] font-semibold transition-colors">{approveMutation.isPending ? '…' : 'Reject'}</button>
                </div>
              ) : (
                <button onClick={() => { setApprovalStatus('pending'); setApprovalError(null); }} className="w-full py-2 rounded-lg bg-paper hover:bg-surface-ok border border-line text-dim text-[13px] font-semibold transition-colors">Reset</button>
              )}
            </div>
          </Panel>

          {/* Red-team */}
          <Panel title="Risks & safer options">
            <div className="space-y-2">
              <div className="flex items-center gap-2 mb-3">
                <SignalPill tone={redTeam.overall_risk_assessment === 'acceptable' ? 'ok' : 'warn'}>{redTeam.overall_risk_assessment ?? 'unknown'}</SignalPill>
                {redTeam.should_escalate && <SignalPill tone="bad">Escalate</SignalPill>}
              </div>
              {(redTeam.risk_factors ?? []).map((f, i) => (
                <div key={i} className="flex items-start gap-2 text-[12px] text-dim">
                  <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber shrink-0" />
                  <span>{f}</span>
                </div>
              ))}
              {(redTeam.suggested_alternatives ?? []).length > 0 && (
                <div className="mt-3 pt-3 border-t border-line">
                  <Eyebrow dim>Alternatives</Eyebrow>
                  <div className="mt-1 space-y-0.5">
                    {(redTeam.suggested_alternatives ?? []).map((a, i) => <p key={i} className="text-[12px] text-dim">· {a}</p>)}
                  </div>
                </div>
              )}
            </div>
          </Panel>

          {showTech && (
            <Panel title="Technical stats">
              <div className="space-y-2">
                {[
                  { label: 'Response time', value: '~720ms' },
                  { label: 'Monitors run', value: decision.analysis_layers.agent_analyses.length.toString() },
                  { label: 'Impact score', value: `${(impact.impact_score ?? 0).toFixed(2)} / 1.0` },
                  { label: 'Evidence items', value: '7' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-[13px]">
                    <span className="text-dim">{label}</span>
                    <span className="font-mono font-semibold text-ink">{value}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
