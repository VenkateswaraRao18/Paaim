'use client';

import { useEffect, useRef, useState } from 'react';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill } from '@/components/ui';

// factory-stream service (the external sensor feed)
const STREAM_BASE = process.env.NEXT_PUBLIC_STREAM_URL || 'http://localhost:9100';
const HISTORY = 40; // points kept per signal for the sparkline

type Reading = {
  machine_id: string; signal: string; label: string; value: number; unit: string;
  status: 'normal' | 'warning' | 'critical'; timestamp: string;
};
type SignalMeta = {
  machine_id: string; signal: string; label: string; unit: string;
  warn: number; critical: number; higher_is_worse: boolean;
};

type Tone = 'ok' | 'warn' | 'bad';
const STATUS: Record<string, { tone: Tone; stroke: string; label: string }> = {
  normal:   { tone: 'ok',   stroke: '#1B5443', label: 'Normal' },
  warning:  { tone: 'warn', stroke: '#E8A13D', label: 'Warning' },
  critical: { tone: 'bad',  stroke: '#D8492B', label: 'Critical' },
};
const valueColor: Record<Tone, string> = { ok: 'text-pine-2', warn: 'text-[#9A6B15]', bad: 'text-coral' };

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
  const [meta, setMeta] = useState<Record<string, SignalMeta>>({});
  const [readings, setReadings] = useState<Record<string, Reading>>({});
  const [connected, setConnected] = useState(false);
  const [injecting, setInjecting] = useState<string | null>(null);
  const histRef = useRef<Record<string, number[]>>({});

  const key = (m: string, s: string) => `${m}::${s}`;

  // Load signal catalogue once
  useEffect(() => {
    fetch(`${STREAM_BASE}/signals`)
      .then((r) => r.json())
      .then((d) => {
        const m: Record<string, SignalMeta> = {};
        for (const s of d.signals) m[key(s.machine_id, s.signal)] = s;
        setMeta(m);
      })
      .catch(() => {});
  }, []);

  // Subscribe to the live SSE stream
  useEffect(() => {
    const es = new EventSource(`${STREAM_BASE}/stream`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const r: Reading = JSON.parse(e.data);
        const k = key(r.machine_id, r.signal);
        const h = histRef.current[k] ?? [];
        h.push(r.value);
        if (h.length > HISTORY) h.shift();
        histRef.current[k] = h;
        setReadings((prev) => ({ ...prev, [k]: r }));
      } catch {}
    };
    return () => es.close();
  }, []);

  const injectAnomaly = async (machine_id: string, signal: string) => {
    setInjecting(key(machine_id, signal));
    try {
      await fetch(`${STREAM_BASE}/anomaly?machine_id=${machine_id}&signal=${signal}&duration=15`, { method: 'POST' });
    } catch {}
    setTimeout(() => setInjecting(null), 1500);
  };

  const items = Object.values(readings).sort((a, b) =>
    a.machine_id.localeCompare(b.machine_id) || a.signal.localeCompare(b.signal));
  const counts = items.reduce((acc, r) => { acc[r.status] = (acc[r.status] || 0) + 1; return acc; }, {} as Record<string, number>);

  return (
    <div className="max-w-[1180px] space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>factory-stream · {STREAM_BASE.replace(/^https?:\/\//, '')}</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">Live Feed</h1>
          <p className="text-[13px] text-dim mt-0.5">Raw sensor signals streaming from the floor. Read-only — monitoring is set up under Monitors.</p>
        </div>
        <SignalPill tone={connected ? 'ok' : 'neutral'}>{connected ? 'Streaming live' : 'Connecting…'}</SignalPill>
      </div>

      {/* Status strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiTile label="Signals" value={items.length} meaning="Live from the feed" />
        <KpiTile label="Normal" value={counts.normal || 0} tone="ok" meaning="Within range" />
        <KpiTile label="Warning" value={counts.warning || 0} tone="warn" meaning="Approaching limit" />
        <KpiTile label="Critical" value={counts.critical || 0} tone="bad" meaning="Over threshold" />
      </div>

      {/* Signal cards */}
      {items.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-[14px] font-semibold text-ink">Waiting for the factory feed…</p>
          <p className="text-[13px] text-dim mt-1">
            Make sure <span className="font-mono">factory-stream</span> is running on {STREAM_BASE.replace(/^https?:\/\//, '')}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((r) => {
            const k = key(r.machine_id, r.signal);
            const st = STATUS[r.status] ?? STATUS.normal;
            const m = meta[k];
            return (
              <Card key={k} className={`p-4 ${r.status !== 'normal' ? (r.status === 'critical' ? 'border-coral/40' : 'border-amber/40') : ''}`}>
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0">
                    <p className="text-[14px] font-bold text-ink truncate">{r.label}</p>
                    <p className="font-mono text-[11px] text-dim">{r.machine_id}</p>
                  </div>
                  <SignalPill tone={st.tone}>{st.label}</SignalPill>
                </div>

                <div className="flex items-end justify-between">
                  <div>
                    <span className={`font-mono text-[28px] font-semibold ${valueColor[st.tone]}`}>{r.value}</span>
                    <span className="text-[13px] text-dim ml-1">{r.unit}</span>
                  </div>
                  {m && (
                    <p className="font-mono text-[10px] text-dim text-right leading-tight">
                      warn {m.warn}<br />crit {m.critical}
                    </p>
                  )}
                </div>

                <div className="mt-2"><Sparkline points={histRef.current[k] ?? []} stroke={st.stroke} /></div>

                <button
                  onClick={() => injectAnomaly(r.machine_id, r.signal)}
                  disabled={injecting === k}
                  className="mt-2 w-full text-[12px] font-semibold py-1.5 rounded-lg border border-line text-dim hover:bg-surface-bad hover:text-coral hover:border-coral/30 transition-colors disabled:opacity-50"
                >
                  {injecting === k ? 'Fault injected ✓' : 'Simulate fault'}
                </button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
