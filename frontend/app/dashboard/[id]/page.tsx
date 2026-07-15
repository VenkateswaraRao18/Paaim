'use client';

import { useActiveDecision } from '@/lib/store';
import { useDecision } from '@/lib/api-client';
import { plainSignal, plainAction, plainMachine, plainEventType } from '@/lib/labels';
import RescueFlow from '@/components/RescueFlow';
import { lookupSemantic, type RescueScenario } from '@/lib/rescue-scenario';

const money = (n: number) => '$' + Math.round(n).toLocaleString();
const timeStr = (iso?: string) => { try { return new Date(iso!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch { return '—'; } };
const risky = (r?: string): 'bad' | 'warn' | 'ok' => r === 'critical' || r === 'high' ? 'bad' : r === 'medium' ? 'warn' : 'ok';

/**
 * Turn the decision's real pre-fault readings into a plottable series.
 * Needs >= 3 points to be worth a chart; otherwise the timeline shows the
 * honest "single-reading event" state.
 */
function buildSeries(history: any, signalLabel: string) {
  const pts: { t: string; v: number }[] = history?.points ?? [];
  const empty = { minutes: [] as number[], torque: [], tempDelta: [], cameraAnomaly: [], faultAt: 0, hasSeries: false };
  if (pts.length < 3) return empty;

  const data = pts.map((p) => p.v);
  // Readings inside ~2 days are better labelled by clock time than by date.
  const ms = (s: string) => new Date(s).getTime();
  const spanH = (ms(pts[pts.length - 1].t) - ms(pts[0].t)) / 3.6e6;
  const shortSpan = Number.isFinite(spanH) && spanH <= 48;
  const tick = (iso: string) => {
    try {
      const d = new Date(iso);
      return shortSpan
        ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch { return ''; }
  };
  const range = pts.length ? `${tick(pts[0].t)} → ${tick(pts[pts.length - 1].t)}` : '';

  return {
    ...empty,
    minutes: pts.map((_, i) => i),          // x = reading index (readings are irregularly spaced)
    faultAt: pts.length - 1,                 // the fault is the final reading
    hasSeries: true,
    series: [{ name: signalLabel, color: '#D8492B', data }],
    xUnitLabel: `Last ${pts.length} readings · ${range} · ends at the fault`,
    xTickLabels: pts.map((p) => tick(p.t)),
  };
}

/** Map a real decision (API/store) into the RescueScenario the 8-step flow renders. */
function mapDecision(src: any, api: any): RescueScenario {
  const ra = api?.recommended_action ?? src?.recommended_action ?? src?.orchestration_result ?? {};
  const event = api?.event ?? src?.event ?? {};
  const layers = api?.analysis_layers ?? src?.analysis_layers ?? {};
  // `api.factory_context` first — that is where the endpoint actually puts it.
  // This looked in three plausible places and not the real one: `ra` is the
  // recommended_action, and `evidence_pack` is not a key on this response at
  // all. So it always fell through to `{}`, costs came back undefined, and the
  // tile reported "No cost model configured for this factory" on a plant with a
  // $3,800/hour cost model — while the triage line beside it priced the same
  // incident at $27.5K. The fallbacks are kept for older stored shapes.
  const fctx = api?.factory_context ?? ra?.factory_context
    ?? api?.evidence_pack?.factory_context ?? src?.factory_context ?? {};
  const mo = api?.manager_options ?? {};

  const machineId = event.machine_id ?? fctx?.machine?.id ?? 'machine';
  const machineName = plainMachine(machineId);
  const signal = plainSignal(event.signal_name ?? 'signal');
  const action = plainAction(ra.selected_action ?? 'inspect_root_cause');
  const riskLevel = ra.risk_level ?? '';
  const co = fctx?.customer_order;
  const costs = fctx?.costs;
  // null, not a stand-in. The old fallbacks — $1,300/min and 14 minutes — were
  // invented here in the UI, and multiplied into a confident "Estimated loss
  // $39,000" on a factory that had never told PAAIM what a minute of downtime
  // costs. The backend now returns no cost model rather than a default; the UI
  // must not quietly restore one.
  const costPerMin = costs?.downtime_cost_per_hour_usd
    ? Math.round(costs.downtime_cost_per_hour_usd / 60) : null;
  const impact = (layers.impact_estimates ?? {})[ra.selected_action] ?? {};
  const downtimeMin = impact.downtime_hours ? Math.round(impact.downtime_hours * 60) : null;
  const estimatedLoss = costPerMin !== null && downtimeMin !== null
    ? downtimeMin * costPerMin : null;
  const decisionId: string = api?.decision_id ?? src?.decision_id ?? '';

  const agentAnalyses: any[] = layers.agent_analyses ?? [];
  const agents = (agentAnalyses.length ? agentAnalyses : [{ agent: 'orchestrator', confidence: ra.confidence ?? 0.9, reasoning: `Recommended: ${action}.`, recommendations: [] }])
    .map((a: any, i: number) => {
      const rec = (a.recommendations ?? [])[0];
      return {
        id: a.agent ?? `agent_${i}`,
        role: (a.agent ?? 'agent').replace(/_/g, ' '),
        name: (a.agent ?? 'Agent').replace(/_agent/, ' agent').replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
        finding: a.error ? 'Did not complete.' : (a.reasoning ?? 'Reviewed the evidence.'),
        // null when the agent did not state one. This panel's own note promises
        // "each agent's own stated confidence" — filling a silent agent in at
        // 80% makes that note a lie, and an unusually confident one.
        confidence: typeof a.confidence === 'number' ? a.confidence : null,
        sources: (a.recommendations ?? []).length || 1,
        actionImplication: rec ? plainAction(rec.action_name) : action,
        tone: (a.error ? 'bad' : risky(rec?.risk_level)) as 'ok' | 'warn' | 'bad',
      };
    });

  const evidenceRows = agents.slice(0, 6).map((a) => ({
    type: a.role.replace(/\b\w/g, (c: string) => c.toUpperCase()),
    source: a.id, groundTruth: a.finding.slice(0, 80), captured: 'PASS' as const, actionSurfaced: a.actionImplication,
  }));

  const rt = (layers.red_team_reviews ?? {})[ra.selected_action] ?? {};
  const options = (mo.options ?? []).map((o: any, i: number) => ({
    id: o.action ?? `opt_${i}`, title: plainAction(o.action), owner: (o.proposed_by ?? ra.approval_route ?? 'operator').replace(/_/g, ' '),
    urgency: o.risk_level === 'critical' || o.risk_level === 'high' ? 'Immediate' : 'Review',
  }));

  return {
    incident: {
      line: machineName, station: event.context?.station ?? '', errorCode: event.context?.plc_code ?? '',
      errorMeaning: signal, runId: (decisionId || event.event_id || 'RUN').slice(0, 12),
      timestamp: timeStr(api?.created_at ?? src?.timestamp), decisionDeadline: co?.promised_delivery ? new Date(co.promised_delivery).toLocaleDateString() : '',
      downtimeMinutes: downtimeMin, costPerMinute: costPerMin, costModelConfigured: costPerMin !== null,
      unitsAtRisk: co?.quantity_remaining ?? fctx?.active_work_order?.quantity_planned ?? 0,
      order: { id: co?.order_id ?? '', customer: co?.customer_name ?? '', dueTime: co?.promised_delivery ? new Date(co.promised_delivery).toLocaleDateString() : '' },
      headline: `${machineName} flagged.`, question: 'Can we act safely?',
    },
    estimatedLoss,
    tags: [{
      tag: event.signal_name ?? 'signal', displayName: signal, value: String(event.signal_value ?? '—'), unit: '',
      normal: '—', tone: (risky(riskLevel) === 'ok' ? 'ok' : risky(riskLevel)) as 'ok' | 'warn' | 'bad',
      meaning: `${signal} on ${machineName}`, likelyCauses: rt.risk_factors?.[0] ?? 'Under review',
    }],
    agents,
    timeline: {
      ...buildSeries(api?.signal_history, signal),
      faultLabel: `${timeStr(api?.created_at ?? src?.timestamp)} · ${event.signal_name ?? ''}`,
      snippets: agents.slice(0, 3).map((a) => ({ source: a.role, text: a.finding.slice(0, 90) })),
      readout: rt.overall_risk_assessment ? `Automated risk review: ${rt.overall_risk_assessment}.` : '',
    },
    evidenceRows,
    decision: {
      title: 'Governed decision', verdict: action.toUpperCase(),
      reason: rt.risk_factors?.[0] ?? agents[0]?.finding ?? `Recommended action: ${action}.`,
      requiredBeforeRestart: rt.risk_factors ?? (rt.assumptions_challenged ?? []),
      fallback: mo.if_no_action?.consequence ?? 'Escalate if the condition persists or worsens.',
      // Only where there is a cost model to derive it from. The ±40% band is a
      // presentational spread around a single computed figure, not a modelled
      // confidence interval — so with no cost model it has nothing to spread.
      avoidableLoss: estimatedLoss === null ? null
        : { min: Math.round(estimatedLoss * 0.6), max: Math.round(estimatedLoss * 1.4) },
      approvals: [(ra.approval_route ?? 'operator').replace(/_/g, ' ')],
      // Report what the agents actually concluded and how sure each one was.
      // A cause-attribution breakdown (62/24/14) was hardcoded here: identical on
      // every incident, derived from nothing, and indefensible the moment anyone
      // asked how it was computed. Confidence is a real number the agents report.
      rootCauseTitle: 'Evidence weighed',
      rootCauseNote: 'Each agent\'s own stated confidence in its finding — not a cause attribution.',
      rootCause: agents.slice(0, 4).map((a) => ({
        cause: `${a.name}: ${a.finding.slice(0, 64)}${a.finding.length > 64 ? '…' : ''}`,
        pct: a.confidence === null ? null : Math.round(a.confidence * 100),
      })),
      actions: options.length ? options : [{ id: 'a1', title: action, owner: (ra.approval_route ?? 'operator').replace(/_/g, ' '), urgency: risky(riskLevel) === 'bad' ? 'Immediate' : 'Review' }],
    },
    drafts: [
      { id: 'wo', label: 'Maintenance Work Order', owner: 'Maintenance Lead', sop: 'SOP-MNT-007', urgency: 'Immediate',
        body: `WORK ORDER — ${machineName}\nInvestigate ${signal.toLowerCase()} and perform ${action.toLowerCase()}.\nEvidence: ${event.signal_name}=${event.signal_value}. Do not restart until sign-off.` },
      { id: 'qa', label: 'QA Hold Notice', owner: 'QA Lead', sop: 'SOP-QA-014', urgency: 'Review',
        body: `QA HOLD — ${machineName}\nHold recent output pending inspection linked to ${signal.toLowerCase()}.` },
      { id: 'handoff', label: 'Shift Handoff', owner: 'Production Supervisor', sop: '—', urgency: 'This shift',
        body: `SHIFT HANDOFF — ${machineName}\n${signal} detected. Recommended: ${action}. Owner: ${(ra.approval_route ?? 'operator').replace(/_/g, ' ')}.` },
      { id: 'brief', label: '9 AM Brief', owner: 'Plant Manager', sop: '—', urgency: '09:00 AM',
        body: `9 AM BRIEF\n${machineName}: ${signal}. Recommended action ${action}${co?.order_id ? `; ${co.customer_name} ${co.order_id} watched` : ''}.` },
    ],
    lookupSemantic,
    decisionId,
    context: { machine: machineId, order: co?.order_id },
    priority: (api?.priority ?? src?.priority) ? {
      level: (api?.priority ?? src?.priority).level,
      score: (api?.priority ?? src?.priority).score,
      rationale: (api?.priority ?? src?.priority).rationale,
      drivers: (api?.priority ?? src?.priority).drivers ?? [],
    } : undefined,
  };
}

export default function DecisionDetailPage({ params }: { params: { id: string } }) {
  const activeDecision = useActiveDecision();
  const { data: apiDecision, isLoading } = useDecision(activeDecision ? null : params.id);

  if (!activeDecision && isLoading) {
    return <div className="flex items-center justify-center h-64"><div className="text-sm text-dim">Loading incident…</div></div>;
  }

  // No scripted fallback: substituting a canned scenario when mapping fails is
  // how a hand-authored incident ends up presented as this machine's analysis.
  // If we cannot build it from the record, say so.
  let scenario: RescueScenario;
  try {
    scenario = mapDecision(activeDecision, apiDecision);
  } catch (e) {
    return (
      <div className="max-w-[560px] mx-auto py-16 text-center">
        <p className="text-[15px] font-semibold text-ink">This incident could not be read</p>
        <p className="text-[13px] text-dim mt-2">
          Its record is incomplete, so there is nothing real to show. Nothing has been substituted.
        </p>
        <a href="/dashboard" className="btn-ghost inline-block mt-5 px-4 py-2 text-[13px]">← Back to Operations</a>
      </div>
    );
  }

  return <RescueFlow scenario={scenario} backHref="/dashboard" />;
}
