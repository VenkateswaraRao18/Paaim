'use client';

import { useEffect, useState } from 'react';
import { Eyebrow, Card, KpiTile, SignalPill } from '@/components/ui';

// PAAIM backend only. This page used to open an SSE connection straight to the
// feed on :9100 and render the feed's own `status` field — so it showed a
// hardcoded plant's signals even with nothing connected, and reported the
// source's opinion rather than PAAIM's. Both are things a real plant would have
// discovered the hard way. What follows is what the watchers actually judged.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Point = { t: string; v: number; s: string };
type Watcher = {
  key: string; machine_id: string; signal: string; source_id: string; label: string;
  connected: boolean; last_value: number | null; last_status: string; last_reason: string;
  judged_by: string; unit: string; events_raised: number; error: string | null;
  series?: Point[];
};

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';
const STATUS: Record<string, { tone: Tone; stroke: string; label: string }> = {
  normal:   { tone: 'ok',      stroke: '#1B5443', label: 'Normal' },
  warning:  { tone: 'warn',    stroke: '#E8A13D', label: 'Warning' },
  critical: { tone: 'bad',     stroke: '#D8492B', label: 'Critical' },
  // A watcher with no learned baseline and no limits from its source cannot
  // honestly call a reading good or bad. Saying so beats reporting "normal".
  unknown:  { tone: 'neutral', stroke: '#9AA0A6', label: 'Not yet judgeable' },
};
const valueColor: Record<Tone, string> = {
  ok: 'text-pine-2', warn: 'text-[#9A6B15]', bad: 'text-coral', neutral: 'text-dim',
};

function Sparkline({ points, stroke }: { points: number[]; stroke: string }) {
  if (points.length < 2) return <div className="h-10" />;
  const min = Math.min(...points), max = Math.max(...points);
  const span = max - min || 1;
  const w = 100, h = 40;
  const d = points.map((p, i) => `${(i / (points.length - 1)) * w},${h - ((p - min) / span) * h}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-10" preserveAspectRatio="none">
      <polyline points={d} fill="none" stroke={stroke} strokeWidth={2} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function LiveFeedPage() {
  const [watchers, setWatchers] = useState<Watcher[]>([]);
  // Three states, not two. `false` as the initial value means the page opens by
  // announcing a failure it has not observed — the backend is fine and the UI
  // says it is down, which is the same class of lie as a watcher reporting
  // "normal" because nothing told it otherwise. null = we have not asked yet.
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [injecting, setInjecting] = useState<string | null>(null);
  const [injectErr, setInjectErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let misses = 0;
    const poll = async () => {
      try {
        const r = await fetch(`${API_BASE}/stream-agents?include_series=true`);
        if (!r.ok) throw new Error(String(r.status));
        const d = await r.json();
        if (!alive) return;
        setWatchers(d.agents ?? []);
        misses = 0;
        setReachable(true);
      } catch {
        // One dropped poll is a restart or a hiccup, not an outage. Declaring
        // the backend down on the first miss makes the banner flap and trains
        // the operator to ignore it.
        if (!alive) return;
        misses += 1;
        if (misses >= 2) setReachable(false);
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const injectAnomaly = async (w: Watcher) => {
    setInjecting(w.key);
    setInjectErr(null);
    try {
      const r = await fetch(
        `${API_BASE}/stream-agents/simulate-fault?source_id=${encodeURIComponent(w.source_id)}` +
        `&machine_id=${encodeURIComponent(w.machine_id)}&signal=${encodeURIComponent(w.signal)}&duration=15`,
        { method: 'POST' },
      );
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setInjectErr(body.detail ?? `Injection failed (HTTP ${r.status})`);
      }
    } catch {
      setInjectErr('Could not reach PAAIM.');
    }
    setTimeout(() => setInjecting(null), 1500);
  };

  const items = [...watchers].sort((a, b) =>
    a.machine_id.localeCompare(b.machine_id) || a.signal.localeCompare(b.signal));
  const counts = items.reduce((acc, w) => {
    acc[w.last_status] = (acc[w.last_status] || 0) + 1; return acc;
  }, {} as Record<string, number>);
  const live = items.filter((w) => w.connected).length;

  return (
    <div className="max-w-[1180px] space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>Watchers · judged by PAAIM</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Live Feed</h1>
          <p className="text-[13px] text-dim mt-0.5">
            Every signal your connected sources put under watch, and what PAAIM makes of it.
            Read-only — watchers come from Data Sources, monitors from Monitors.
          </p>
        </div>
        <SignalPill tone={reachable === null ? 'neutral' : reachable === false ? 'bad' : live ? 'ok' : 'neutral'}>
          {reachable === null ? 'Checking…'
            : reachable === false ? 'Backend unreachable'
            : live ? `${live} watching` : 'Nothing watched'}
        </SignalPill>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiTile label="Watchers" value={items.length} meaning="From your sources" />
        <KpiTile label="Normal" value={counts.normal || 0} tone="ok" meaning="Within learned range" />
        <KpiTile label="Warning" value={counts.warning || 0} tone="warn" meaning="Approaching limit" />
        <KpiTile label="Critical" value={counts.critical || 0} tone="bad" meaning="Breach — raises an incident" />
      </div>

      {injectErr && (
        <Card className="p-4 border-coral/40">
          <p className="text-[13px] text-coral font-semibold">Fault injection unavailable</p>
          <p className="text-[12px] text-dim mt-1">{injectErr}</p>
        </Card>
      )}

      {reachable === null ? null : items.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-[14px] font-semibold text-ink">
            {reachable ? 'Nothing is being watched yet' : 'Cannot reach PAAIM'}
          </p>
          <p className="text-[13px] text-dim mt-1 max-w-md mx-auto">
            {reachable
              ? 'PAAIM watches a signal once you connect a data source and map its fields. Until then it has nothing to look at.'
              : 'The backend stopped answering on port 8000. Watchers are in-memory, so they rebuild from your confirmed sources when it comes back.'}
          </p>
          {reachable && (
            <a href="/data-sources" className="btn-primary inline-flex px-4 py-2 text-[13px] mt-4">
              Connect a data source
            </a>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((w) => {
            const st = STATUS[w.last_status] ?? STATUS.unknown;
            const pts = (w.series ?? []).map((p) => p.v);
            return (
              <Card key={w.key} className={`p-4 ${
                w.last_status === 'critical' ? 'border-coral/40'
                : w.last_status === 'warning' ? 'border-amber/40' : ''}`}>
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0">
                    <p className="text-[14px] font-bold text-ink truncate">{w.label}</p>
                    <p className="font-mono text-[11px] text-dim truncate">{w.machine_id} · {w.signal}</p>
                  </div>
                  <SignalPill tone={w.connected ? st.tone : 'neutral'}>
                    {w.connected ? st.label : 'Offline'}
                  </SignalPill>
                </div>

                <div className="flex items-end justify-between">
                  <div>
                    <span className={`font-mono text-[28px] font-semibold ${valueColor[st.tone]}`}>
                      {w.last_value ?? '—'}
                    </span>
                    <span className="text-[13px] text-dim ml-1">{w.unit}</span>
                  </div>
                  <p className="text-[10px] text-dim text-right leading-tight">
                    {w.events_raised} raised
                  </p>
                </div>

                <div className="mt-2"><Sparkline points={pts} stroke={st.stroke} /></div>

                {/* The verdict in PAAIM's words, and the yardstick behind it. */}
                <p className="text-[10px] text-dim font-mono truncate" title={w.last_reason}>
                  {w.last_reason || `judged by ${w.judged_by}`}
                </p>
                {w.error && <p className="text-[10px] text-coral mt-1 line-clamp-2">{w.error}</p>}

                <button
                  onClick={() => injectAnomaly(w)}
                  disabled={injecting === w.key}
                  className="mt-2 w-full text-[12px] font-semibold py-1.5 rounded-lg border border-line text-dim hover:bg-surface-bad hover:text-coral hover:border-coral/30 transition-colors disabled:opacity-50"
                >
                  {injecting === w.key ? 'Fault injected ✓' : 'Simulate fault'}
                </button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
