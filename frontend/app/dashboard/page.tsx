'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import {
  useEventsList,
  useAnalyticsSummary,
  useDecisionsList,
  useApproveDecision,
  type DecisionListItem,
} from '@/lib/api-client';
import { useSelectedFactory } from '@/lib/store';
import { plainSignal, plainAction, plainMachine } from '@/lib/labels';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar } from '@/components/ui';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

// ─── mapping helpers (signal discipline — no rainbow) ──────────────
function eventTone(eventType: string): Tone {
  if (eventType === 'safety') return 'bad';
  if (eventType === 'quality' || eventType === 'energy') return 'warn';
  return 'neutral'; // maintenance, production
}
function riskTone(risk?: string): Tone {
  if (risk === 'critical' || risk === 'high') return 'bad';
  if (risk === 'medium') return 'warn';
  return 'neutral';
}
function statusTone(status: string): Tone {
  if (status === 'recommended') return 'warn';
  if (status === 'approved' || status === 'executed') return 'ok';
  if (status === 'rejected') return 'bad';
  return 'neutral';
}
const dotClass: Record<Tone, string> = {
  ok: 'bg-pine-2', warn: 'bg-amber', bad: 'bg-coral', neutral: 'bg-moss',
};

function timeAgo(ts?: string): string {
  if (!ts) return '—';
  const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ─── Monitors (right rail, slim, no emoji) ─────────────────────────
const MONITORS = ['Safety', 'Quality', 'Maintenance', 'Production', 'Energy'];

// ─── Decision card — the fused incident+decision object ────────────
function DecisionCard({
  d, incident, pending, busy, onApprove, onReject,
}: {
  d: DecisionListItem;
  incident?: { machine_id?: string; signal_name?: string; event_type?: string };
  pending: boolean;
  busy: boolean;
  onApprove: (e: React.MouseEvent) => void;
  onReject: (e: React.MouseEvent) => void;
}) {
  const action = plainAction(d.recommended_action?.selected_action ?? 'unknown');
  const risk = d.recommended_action?.risk_level;
  const conf = d.recommended_action?.confidence;
  const rTone = riskTone(risk);
  const machine = incident?.machine_id ? plainMachine(incident.machine_id) : null;
  const signal = incident?.signal_name ? plainSignal(incident.signal_name) : null;

  return (
    <Card focal={pending} className="p-4">
      {/* Incident line — what happened */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-2 h-2 rounded-full shrink-0 ${pending ? 'bg-amber animate-pulse' : dotClass[statusTone(d.status)]}`} />
        <span className="text-[13px] font-semibold text-ink truncate">
          {signal ?? 'Incident'}{machine && <span className="text-dim font-normal"> · {machine}</span>}
        </span>
        <span className="font-mono text-[10.5px] text-dim uppercase tracking-wide ml-auto shrink-0">{timeAgo(d.created_at)}</span>
      </div>

      {/* Agent verdict → recommendation (the chain) */}
      <div className="pl-4 border-l-2 border-line ml-1 space-y-1.5">
        {(risk || conf != null) && (
          <p className="font-mono text-[11px] text-dim uppercase tracking-wide">
            Agents: {risk ?? 'assessed'} risk{conf != null && ` · ${Math.round(conf * 100)}% confidence`}
          </p>
        )}
        <p className="text-[14px] text-ink">
          <span className="text-dim">→ Recommended: </span>
          <span className="font-semibold text-pine-2">{action}</span>
        </p>
      </div>

      {/* Action row */}
      <div className="flex items-center gap-2 mt-3.5">
        {pending ? (
          <>
            <button onClick={onApprove} disabled={busy} className="btn-primary px-3.5 py-1.5 text-[13px] disabled:opacity-50">
              {busy ? '…' : 'Approve'}
            </button>
            <button onClick={onReject} disabled={busy} className="px-3.5 py-1.5 text-[13px] font-semibold rounded-lg border border-coral/40 text-coral hover:bg-surface-bad disabled:opacity-50 transition-colors">
              Reject
            </button>
            <Link href={`/dashboard/${d.decision_id}`} className="ml-auto text-[13px] font-semibold text-pine-2 hover:text-pine">
              See full reasoning →
            </Link>
          </>
        ) : (
          <>
            <SignalPill tone={statusTone(d.status)}>{d.status}</SignalPill>
            {risk && <SignalPill tone={rTone}>{risk} risk</SignalPill>}
            {d.approved_by && <span className="text-[11px] text-dim">✓ {d.approved_by}</span>}
            <Link href={`/dashboard/${d.decision_id}`} className="ml-auto text-[13px] font-semibold text-pine-2 hover:text-pine">
              View →
            </Link>
          </>
        )}
      </div>
    </Card>
  );
}

// ─── Page ──────────────────────────────────────────────────────────
export default function DashboardPage() {
  const queryClient = useQueryClient();
  const selectedFactory = useSelectedFactory();

  const { data: eventsList, isLoading: eventsLoading } = useEventsList(selectedFactory);
  const { data: analyticsData } = useAnalyticsSummary(selectedFactory);
  const { data: decisionsData, isLoading: decisionsLoading } = useDecisionsList(selectedFactory, 100);
  const approveMutation = useApproveDecision();
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const incidents: any[] = eventsList?.events ?? [];
  const dbDecisions: DecisionListItem[] = decisionsData?.decisions ?? [];
  const pending = dbDecisions.filter((d) => d.status === 'recommended');
  const resolved = dbDecisions.filter((d) => d.status !== 'recommended');

  // Join decision → its triggering incident (best-effort on event_id)
  const eventById = new Map<string, any>();
  incidents.forEach((e) => { const id = e.id ?? e.event_id; if (id) eventById.set(String(id), e); });
  const incidentFor = (d: DecisionListItem) => eventById.get(String(d.event_id));

  const handleApproval = async (decisionId: string, action: 'approve' | 'reject', e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    setApprovingId(decisionId);
    try {
      await approveMutation.mutateAsync({ decisionId, action, approvedBy: 'operator' });
      queryClient.invalidateQueries({ queryKey: ['decisions', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['analytics'] });
    } finally {
      setApprovingId(null);
    }
  };

  return (
    <div className="max-w-[1180px] space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>Factory 001 · Live</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Operations</h1>
          <p className="text-[13px] text-dim mt-0.5">What needs your attention right now.</p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries()}
          className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-[13px]"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiTile label="Active incidents" value={incidents.length} tone={incidents.length ? 'warn' : 'ok'} meaning={incidents.length ? 'Streaming from the floor' : 'Floor is quiet'} />
        <KpiTile label="Needs approval" value={pending.length} tone={pending.length ? 'bad' : 'ok'} meaning={pending.length ? 'Waiting on you' : 'Nothing pending'} />
        <KpiTile label="Approval rate" value={analyticsData ? `${analyticsData.approval_rate}%` : '—'} meaning="Target ≥ 85%" />
        <KpiTile label="Avg response" value={analyticsData ? `${(analyticsData.avg_latency_ms / 1000).toFixed(1)}s` : '—'} meaning="Per decision" />
      </div>

      <div className="flex gap-6">
        <div className="flex-1 min-w-0 space-y-7">
          {/* HERO — Needs your approval */}
          <section>
            <SectionHeader
              eyebrow="Needs your approval"
              title="Decisions"
              accent="waiting on you"
              sub="Each is an incident the agents diagnosed and turned into a recommended action."
              right={pending.length > 0 ? <SignalPill tone="warn">{pending.length} pending</SignalPill> : undefined}
            />
            {decisionsLoading ? (
              <div className="space-y-2">{Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-28 bg-card border border-line rounded-card animate-pulse" />)}</div>
            ) : pending.length === 0 ? (
              <AlertBar tone="ok" title="All clear — nothing needs your approval">
                When an incident produces a recommended action, it will appear here for you to approve.
              </AlertBar>
            ) : (
              <div className="space-y-3">
                {pending.map((d) => (
                  <DecisionCard
                    key={d.decision_id} d={d} incident={incidentFor(d)} pending busy={approvingId === d.decision_id}
                    onApprove={(e) => handleApproval(d.decision_id, 'approve', e)}
                    onReject={(e) => handleApproval(d.decision_id, 'reject', e)}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Live incidents */}
          <section>
            <SectionHeader
              eyebrow="Live incidents"
              title="What's happening"
              accent="on the floor"
              sub="Signals streaming in from machine monitors."
            />
            {eventsLoading ? (
              <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 bg-card border border-line rounded-card animate-pulse" />)}</div>
            ) : incidents.length === 0 ? (
              <AlertBar tone="ok" title="All systems healthy — no active incidents" />
            ) : (
              <Card className="divide-y divide-line overflow-hidden">
                {incidents.slice(0, 12).map((e: any, i: number) => {
                  const tone = eventTone(e.event_type);
                  return (
                    <div key={i} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-ok transition-colors">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${dotClass[tone]}`} />
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-semibold text-ink truncate">{plainSignal(e.signal_name)}</p>
                        <p className="text-[11px] text-dim truncate">{e.machine_id ? plainMachine(e.machine_id) : '—'} · {timeAgo(e.created_at || e.timestamp)}</p>
                      </div>
                      <span className="font-mono text-[11px] text-dim shrink-0">{((e.confidence || 0) * 100).toFixed(0)}%</span>
                      <SignalPill tone={tone}>{e.event_type}</SignalPill>
                    </div>
                  );
                })}
              </Card>
            )}
          </section>

          {/* Recent decisions */}
          {resolved.length > 0 && (
            <section>
              <SectionHeader eyebrow="Resolved" title="Recent" accent="decisions" sub="Already approved, rejected, or executed." />
              <div className="space-y-2">
                {resolved.slice(0, 8).map((d) => (
                  <DecisionCard key={d.decision_id} d={d} incident={incidentFor(d)} pending={false} busy={false} onApprove={() => {}} onReject={() => {}} />
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right rail — slim live monitors */}
        <aside className="w-56 shrink-0 hidden lg:block">
          <div className="sticky top-0">
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <Eyebrow>Monitors</Eyebrow>
                <SignalPill tone="ok">All live</SignalPill>
              </div>
              <div className="space-y-2.5">
                {MONITORS.map((m) => (
                  <div key={m} className="flex items-center gap-2.5">
                    <span className="relative flex w-1.5 h-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pine-2 opacity-50" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-pine-2" />
                    </span>
                    <span className="text-[13px] text-ink">{m}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </aside>
      </div>
    </div>
  );
}
