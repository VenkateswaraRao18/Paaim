'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuditLog } from '@/lib/api-client';
import { Eyebrow, Card, KpiTile, SignalPill } from '@/components/ui';

type StatusFilter = 'all' | 'approved' | 'rejected' | 'recommended' | 'pending';
type AgentFilter = 'all' | 'safety' | 'quality' | 'maintenance' | 'production' | 'energy';
type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

const PAGE_SIZE = 20;

const statusTone = (s: string): Tone => s.includes('approved') ? 'ok' : s.includes('rejected') ? 'bad' : 'warn';
const eventTone = (t: string): Tone => t === 'safety' ? 'bad' : t === 'quality' || t === 'energy' ? 'warn' : 'neutral';

export default function HistoryPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [agentFilter, setAgentFilter] = useState<AgentFilter>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const { data, isLoading, error, refetch } = useAuditLog('factory_001', {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const logs = data?.logs ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const filtered = logs.filter((e) => {
    if (statusFilter !== 'all' && e.action !== statusFilter && !e.details?.status?.toString().includes(statusFilter)) return false;
    if (agentFilter !== 'all' && !e.actor.toLowerCase().includes(agentFilter)) return false;
    if (search && !e.action.toLowerCase().includes(search.toLowerCase()) && !e.decision_id?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const handleExport = () => {
    const csv = [
      ['Time', 'Decision ID', 'Action', 'Actor', 'Event Type', 'Status'].join(','),
      ...logs.map((e) => [
        new Date(e.timestamp).toISOString(),
        e.decision_id ?? '',
        e.action, e.actor, e.event_type,
        JSON.stringify(e.details?.status ?? ''),
      ].join(',')),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `paaim_history_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const th = 'text-left px-5 py-3 font-mono text-[10px] font-semibold text-dim uppercase tracking-wide';

  return (
    <div className="max-w-[1180px] space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>On the record</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">History</h1>
          <p className="text-[13px] text-dim mt-0.5">Every decision and who acted on it. Open any entry to see its full reasoning.</p>
        </div>
        <button onClick={handleExport} className="btn-ghost flex items-center gap-2 px-3 py-1.5 text-[13px]">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export CSV
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiTile label="Total entries" value={total} meaning="On record" />
        <KpiTile label="Showing" value={filtered.length} meaning="After filters" />
        <KpiTile label="Page" value={`${page + 1} / ${totalPages}`} meaning={`${PAGE_SIZE} per page`} />
        <KpiTile label="Source" value={total > 0 ? 'Live DB' : 'No data'} tone={total > 0 ? 'ok' : 'warn'} meaning="Audit log" />
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input
            type="text"
            placeholder="Search action or decision ID…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            className="border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss"
          />
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); setPage(0); }}
            className="border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss">
            <option value="all">All statuses</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="recommended">Recommended</option>
            <option value="pending">Pending</option>
          </select>
          <select value={agentFilter} onChange={(e) => { setAgentFilter(e.target.value as AgentFilter); setPage(0); }}
            className="border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss">
            <option value="all">All actors</option>
            <option value="safety">Safety Agent</option>
            <option value="quality">Quality Agent</option>
            <option value="maintenance">Maintenance Agent</option>
            <option value="production">Production Agent</option>
            <option value="energy">Energy Agent</option>
          </select>
        </div>
        {(statusFilter !== 'all' || agentFilter !== 'all' || search) && (
          <button onClick={() => { setStatusFilter('all'); setAgentFilter('all'); setSearch(''); setPage(0); }} className="mt-2 text-[12px] text-pine-2 hover:underline">
            Clear filters
          </button>
        )}
      </Card>

      {/* Table */}
      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-12 bg-paper rounded-lg animate-pulse" />)}</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-[13px] text-coral font-medium">Failed to load history</p>
            <p className="text-[12px] text-dim mt-1">Backend may not be running or no data yet</p>
            <button onClick={() => refetch()} className="mt-3 text-[12px] text-pine-2 hover:underline">Retry</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-line bg-paper">
                  {['Time', 'Decision', 'Action', 'Done by', 'Type', 'Status', ''].map((h, i) => <th key={i} className={th}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={7} className="text-center py-12 text-dim text-[13px]">
                    {total === 0 ? 'No history yet — decisions will appear here as incidents are handled' : 'No entries match the current filters'}
                  </td></tr>
                ) : (
                  filtered.map((entry, i) => {
                    const ts = new Date(entry.timestamp);
                    const statusVal = String(entry.details?.status ?? entry.action ?? '');
                    const openable = !!entry.decision_id;
                    return (
                      <tr
                        key={i}
                        onClick={() => openable && router.push(`/dashboard/${entry.decision_id}`)}
                        className={`border-b border-line last:border-0 transition-colors ${openable ? 'hover:bg-surface-ok cursor-pointer' : ''}`}
                      >
                        <td className="px-5 py-3 text-dim whitespace-nowrap">
                          <span className="font-mono">{ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          <p className="font-mono text-[11px] text-dim/70">{ts.toLocaleDateString([], { month: 'short', day: 'numeric' })}</p>
                        </td>
                        <td className="px-5 py-3 font-mono text-[11px] text-dim max-w-[140px] truncate">{entry.decision_id ?? '—'}</td>
                        <td className="px-5 py-3"><p className="font-medium text-ink capitalize">{entry.action.replace(/_/g, ' ')}</p></td>
                        <td className="px-5 py-3"><span className="font-mono text-[11px] text-dim">{entry.actor}</span></td>
                        <td className="px-5 py-3">{entry.event_type ? <SignalPill tone={eventTone(entry.event_type)}>{entry.event_type}</SignalPill> : '—'}</td>
                        <td className="px-5 py-3"><SignalPill tone={statusTone(statusVal)}>{statusVal.replace(/_/g, ' ') || 'recommended'}</SignalPill></td>
                        <td className="px-5 py-3 text-right">
                          {openable && <span className="text-[12px] font-semibold text-pine-2">Open →</span>}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-line bg-paper">
          <span className="font-mono text-[11px] text-dim">
            {total > 0 ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} of ${total}` : '0 entries'}
          </span>
          <div className="flex items-center gap-1">
            <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 text-[12px] rounded-lg border bg-card text-dim border-line hover:bg-surface-ok disabled:opacity-40 disabled:cursor-not-allowed transition-colors">Prev</button>
            {Array.from({ length: Math.min(totalPages, 5) }).map((_, i) => (
              <button key={i} onClick={() => setPage(i)}
                className={`px-3 py-1 text-[12px] rounded-lg border transition-colors ${i === page ? 'bg-pine-2 text-white border-pine-2' : 'bg-card text-dim border-line hover:bg-surface-ok'}`}>{i + 1}</button>
            ))}
            <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 text-[12px] rounded-lg border bg-card text-dim border-line hover:bg-surface-ok disabled:opacity-40 disabled:cursor-not-allowed transition-colors">Next</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
