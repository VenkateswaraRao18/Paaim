'use client';

import { useState } from 'react';
import {
  useFactoryModel, useKpiSnapshot,
  useContextSummary, useMachineAssets, useWorkOrders,
  useCustomerOrders, useNCRRecords,
  type WorkOrder, type CustomerOrder, type NCRRecord, type MachineAsset,
} from '@/lib/api-client';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill } from '@/components/ui';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

// ─── tone maps (signal discipline) ─────────────────────────────────
const priorityTone = (p: string): Tone => p === 'urgent' ? 'bad' : p === 'high' ? 'warn' : 'neutral';
const severityTone = (s: string): Tone => s === 'critical' ? 'bad' : s === 'major' ? 'warn' : 'neutral';
const machineTone = (s: string): Tone => s === 'running' ? 'ok' : s === 'fault' ? 'bad' : s === 'maintenance' ? 'warn' : 'neutral';
const kpiTone = (s: string): Tone => s === 'on_target' ? 'ok' : s === 'critical' ? 'bad' : 'warn';
const critText: Record<string, string> = { critical: 'text-coral', high: 'text-[#9A6B15]', medium: 'text-[#9A6B15]', low: 'text-dim' };

function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`bg-paper rounded-lg animate-pulse ${className}`} />;
}

function hoursLabel(h: number) {
  if (h < 0) return <span className="text-coral font-semibold">Overdue</span>;
  if (h < 24) return <span className="text-coral font-semibold">{h.toFixed(0)}h</span>;
  const d = Math.floor(h / 24);
  return <span className={d <= 3 ? 'text-[#9A6B15] font-semibold' : 'text-dim'}>{d}d</span>;
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 bg-paper rounded-full overflow-hidden">
        <div className="h-full bg-pine-2 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="font-mono text-[11px] text-dim shrink-0">{pct.toFixed(0)}%</span>
    </div>
  );
}

// ─── Panel (eyebrow + card) ────────────────────────────────────────
function Panel({ title, sub, right, children }: { title: string; sub?: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
        <div>
          <Eyebrow>{title}</Eyebrow>
          {sub && <p className="text-[12px] text-dim mt-0.5">{sub}</p>}
        </div>
        {right}
      </div>
      <div className="p-5">{children}</div>
    </Card>
  );
}

const thCls = 'pb-2 font-mono text-[10px] font-semibold text-dim uppercase tracking-wide';

// ─── Summary strip ────────────────────────────────────────────────
function SummaryStrip() {
  const { data: summary, isLoading } = useContextSummary();
  if (isLoading) {
    return <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}</div>;
  }
  if (!summary) return null;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <KpiTile label="Machines running" value={`${summary.machines.running}/${summary.machines.total}`} tone={summary.machines.fault > 0 ? 'bad' : 'ok'} meaning={summary.machines.fault > 0 ? `${summary.machines.fault} in fault` : 'All healthy'} />
      <KpiTile label="Active work orders" value={summary.work_orders.active} tone={summary.work_orders.urgent > 0 ? 'warn' : 'neutral'} meaning={`${summary.work_orders.urgent} urgent`} />
      <KpiTile label="Orders at risk" value={summary.customer_orders.at_risk} tone={summary.customer_orders.at_risk > 0 ? 'bad' : 'ok'} meaning={summary.customer_orders.at_risk > 0 ? `$${(summary.customer_orders.total_penalty_exposure_usd / 1000).toFixed(0)}K exposure` : 'No delivery risk'} />
      <KpiTile label="Open quality issues" value={summary.quality.open_ncrs} tone={summary.quality.critical_ncrs > 0 ? 'bad' : summary.quality.open_ncrs > 0 ? 'warn' : 'ok'} meaning={summary.quality.critical_ncrs > 0 ? `${summary.quality.critical_ncrs} critical` : 'No critical NCRs'} />
    </div>
  );
}

// ─── Orders & Delivery (risk-first) ───────────────────────────────
function CustomerOrders() {
  const { data, isLoading } = useCustomerOrders('factory_001', 'open');
  const orders = data?.customer_orders ?? [];
  const atRisk = orders.filter((o: CustomerOrder) => o.is_at_risk);
  const onTrack = orders.filter((o: CustomerOrder) => !o.is_at_risk);

  const row = (co: CustomerOrder) => (
    <div key={co.id} className={`rounded-lg border p-3.5 ${co.is_at_risk ? 'bg-surface-bad border-coral/30' : co.hours_until_delivery < 72 ? 'bg-surface-warn border-amber/30' : 'border-line'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-[14px] text-ink">{co.id}</span>
            <span className="text-dim text-[12px]">· {co.customer_name}</span>
            <SignalPill tone={priorityTone(co.priority)}>{co.priority}</SignalPill>
            {co.is_at_risk && <SignalPill tone="bad">At risk</SignalPill>}
          </div>
          <div className="flex items-center gap-4 mt-1.5 text-[12px] text-dim">
            <span>{co.quantity_delivered}/{co.quantity} delivered</span>
            <span>Delivery: {hoursLabel(co.hours_until_delivery)}</span>
            {co.late_delivery_penalty_usd > 0 && <span className="font-mono text-coral">Penalty ${co.late_delivery_penalty_usd.toLocaleString()}</span>}
            {co.contract_value_usd > 0 && <span className="font-mono">Contract ${(co.contract_value_usd / 1000).toFixed(0)}K</span>}
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="font-mono text-[10px] text-dim uppercase tracking-wide">Due</p>
          <p className="font-mono text-[12px] text-ink">{new Date(co.promised_delivery).toLocaleDateString()}</p>
        </div>
      </div>
    </div>
  );

  if (isLoading) return <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16" />)}</div>;
  if (orders.length === 0) return <p className="text-[13px] text-dim text-center py-8">No open customer orders</p>;

  return (
    <div className="space-y-5">
      {atRisk.length > 0 && (
        <Panel title="Needs attention" sub="Open orders at risk of missing their deadline" right={<SignalPill tone="bad">{atRisk.length} at risk</SignalPill>}>
          <div className="space-y-2">{atRisk.map(row)}</div>
        </Panel>
      )}
      <Panel title="On track" sub="Open orders meeting their schedule" right={<SignalPill tone="ok">{onTrack.length} on track</SignalPill>}>
        <div className="space-y-2">{onTrack.length ? onTrack.map(row) : <p className="text-[13px] text-dim text-center py-4">None</p>}</div>
      </Panel>
    </div>
  );
}

// ─── Production (work orders) ─────────────────────────────────────
function WorkOrders() {
  const { data, isLoading } = useWorkOrders('factory_001', 'in_progress');
  const orders = data?.work_orders ?? [];
  return (
    <Panel title="Active work orders" sub="Currently running on the floor" right={<SignalPill tone="neutral">{orders.length} active</SignalPill>}>
      {isLoading ? <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        : orders.length === 0 ? <p className="text-[13px] text-dim text-center py-8">No active work orders</p>
        : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="border-b border-line text-left">
                {['Order / Product', 'Machine', 'Customer', 'Deadline', 'Progress', 'Priority'].map((h) => <th key={h} className={thCls}>{h}</th>)}
              </tr></thead>
              <tbody>
                {orders.map((wo: WorkOrder) => {
                  const hoursLeft = wo.scheduled_end ? (new Date(wo.scheduled_end).getTime() - Date.now()) / 3600000 : null;
                  return (
                    <tr key={wo.id} className="border-b border-line last:border-0 hover:bg-surface-ok">
                      <td className="py-2.5"><p className="font-semibold text-ink">{wo.id}</p><p className="text-[12px] text-dim truncate max-w-[160px]">{wo.product_name}</p></td>
                      <td className="py-2.5 font-mono text-[12px] text-dim">{wo.machine_id}</td>
                      <td className="py-2.5 text-[12px] text-dim truncate max-w-[120px]">{wo.customer_name ?? '—'}</td>
                      <td className="py-2.5">{hoursLeft !== null ? hoursLabel(hoursLeft) : '—'}</td>
                      <td className="py-2.5">
                        <ProgressBar pct={wo.completion_pct} />
                        <p className="text-[11px] text-dim mt-0.5">{wo.quantity_completed}/{wo.quantity_planned}{wo.quantity_scrapped > 0 && <span className="text-coral ml-1">· {wo.quantity_scrapped} scrap</span>}</p>
                      </td>
                      <td className="py-2.5"><SignalPill tone={priorityTone(wo.priority)}>{wo.priority}</SignalPill></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </Panel>
  );
}

// ─── Quality (NCRs) ───────────────────────────────────────────────
function NCRs() {
  const { data, isLoading } = useNCRRecords('factory_001', 'open');
  const ncrs = data?.ncrs ?? [];
  return (
    <Panel title="Open quality issues (NCRs)" sub="Non-conformance reports awaiting resolution" right={<SignalPill tone={ncrs.length ? 'warn' : 'ok'}>{ncrs.length} open</SignalPill>}>
      {isLoading ? <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        : ncrs.length === 0 ? <p className="text-[13px] text-dim text-center py-8">No open NCRs</p>
        : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="border-b border-line text-left">
                {['NCR', 'Defect', 'Machine', 'Severity', 'Units', 'Disposition', 'Recurrences', 'Cost'].map((h) => <th key={h} className={thCls}>{h}</th>)}
              </tr></thead>
              <tbody>
                {ncrs.map((ncr: NCRRecord) => (
                  <tr key={ncr.id} className="border-b border-line last:border-0 hover:bg-surface-ok">
                    <td className="py-2.5 font-mono text-[12px] font-semibold text-ink">{ncr.id}</td>
                    <td className="py-2.5"><p className="text-ink text-[12px] capitalize">{ncr.defect_type.replace(/_/g, ' ')}</p>{ncr.root_cause && <p className="text-[11px] text-dim">→ {ncr.root_cause.replace(/_/g, ' ')}</p>}</td>
                    <td className="py-2.5 font-mono text-[12px] text-dim">{ncr.machine_id}</td>
                    <td className="py-2.5"><SignalPill tone={severityTone(ncr.severity)}>{ncr.severity}</SignalPill></td>
                    <td className="py-2.5 font-semibold text-ink">{ncr.quantity_affected}</td>
                    <td className="py-2.5 text-[12px] text-dim capitalize">{ncr.disposition?.replace(/_/g, ' ') ?? '—'}</td>
                    <td className="py-2.5">{ncr.recurrence_count > 0 ? <span className="font-mono text-[12px] font-bold text-coral">{ncr.recurrence_count}×</span> : <span className="text-[12px] text-dim">First</span>}</td>
                    <td className="py-2.5 font-mono text-[12px] text-coral font-semibold">${ncr.cost_impact_usd.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </Panel>
  );
}

// ─── Machines ─────────────────────────────────────────────────────
function Machines() {
  const { data, isLoading } = useMachineAssets('factory_001');
  const machines = data?.machines ?? [];
  return (
    <Panel title="Machine asset registry" sub="Live status, maintenance schedule, and production value">
      {isLoading ? <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
        : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead><tr className="border-b border-line text-left">
                {['Machine', 'Zone', 'Status', 'Criticality', 'Last maint.', 'Next maint.', 'Value/hr'].map((h) => <th key={h} className={thCls}>{h}</th>)}
              </tr></thead>
              <tbody>
                {machines.map((m: MachineAsset) => {
                  const lastMaint = m.last_maintenance_date ? Math.floor((Date.now() - new Date(m.last_maintenance_date).getTime()) / 86400000) : null;
                  const nextMaint = m.next_scheduled_maintenance ? Math.floor((new Date(m.next_scheduled_maintenance).getTime() - Date.now()) / 86400000) : null;
                  const nextOverdue = nextMaint !== null && nextMaint < 0;
                  const nextSoon = nextMaint !== null && nextMaint <= 7;
                  return (
                    <tr key={m.id} className="border-b border-line last:border-0 hover:bg-surface-ok">
                      <td className="py-2.5"><p className="font-semibold text-ink">{m.name}</p><p className="font-mono text-[11px] text-dim">{m.id}</p></td>
                      <td className="py-2.5 text-[12px] text-dim">{m.zone_id}</td>
                      <td className="py-2.5"><SignalPill tone={machineTone(m.status)}>{m.status}</SignalPill></td>
                      <td className={`py-2.5 text-[12px] font-semibold capitalize ${critText[m.criticality] ?? 'text-dim'}`}>{m.criticality}</td>
                      <td className="py-2.5 text-[12px] text-dim">{lastMaint !== null ? `${lastMaint}d ago` : '—'}</td>
                      <td className={`py-2.5 text-[12px] font-semibold ${nextOverdue ? 'text-coral' : nextSoon ? 'text-[#9A6B15]' : 'text-dim'}`}>{nextOverdue ? 'Overdue' : nextMaint !== null ? `in ${nextMaint}d` : '—'}</td>
                      <td className="py-2.5 font-mono text-[12px] text-dim">{m.hourly_production_value_usd > 0 ? `$${m.hourly_production_value_usd.toLocaleString()}` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </Panel>
  );
}

// ─── KPIs ─────────────────────────────────────────────────────────
function Kpis() {
  const { data, isLoading } = useKpiSnapshot('factory_001');
  const kpis = (data as any)?.kpis ?? (data as any)?.snapshot ?? [];
  if (isLoading) return <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24" />)}</div>;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
      {kpis.slice(0, 12).map((kpi: any) => (
        <KpiTile
          key={kpi.kpi_id ?? kpi.id}
          label={kpi.name}
          value={typeof kpi.value === 'number' ? kpi.value.toFixed(1) : kpi.value}
          unit={kpi.unit}
          tone={kpiTone(kpi.status)}
          meaning={`Target ${kpi.target}${kpi.unit}`}
        />
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────
const TABS = [
  { id: 'orders', label: 'Orders & Delivery' },
  { id: 'production', label: 'Production' },
  { id: 'quality', label: 'Quality' },
  { id: 'machines', label: 'Machines' },
  { id: 'kpis', label: 'KPIs' },
];

export default function ControlTowerPage() {
  const [tab, setTab] = useState('orders');
  const factory = useFactoryModel('factory_001');

  return (
    <div className="max-w-[1180px] space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>Business state · seeded context</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Control Tower</h1>
          <p className="text-[13px] text-dim mt-0.5">Orders, quality, machines and KPIs — the factory's business state and what's at risk.</p>
        </div>
        {factory.data && (
          <div className="text-right">
            <p className="text-[13px] font-semibold text-ink">{factory.data.name}</p>
            <p className="font-mono text-[11px] text-dim">{factory.data.location}</p>
          </div>
        )}
      </div>

      {/* Summary — always visible */}
      <SummaryStrip />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-line overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-[13px] font-semibold transition-colors border-b-2 -mb-px whitespace-nowrap ${
              tab === t.id ? 'border-pine-2 text-pine-2' : 'border-transparent text-dim hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'orders' && <CustomerOrders />}
      {tab === 'production' && <WorkOrders />}
      {tab === 'quality' && <NCRs />}
      {tab === 'machines' && <Machines />}
      {tab === 'kpis' && <Panel title="Live KPI snapshot" sub="Current performance vs. targets"><Kpis /></Panel>}
    </div>
  );
}
