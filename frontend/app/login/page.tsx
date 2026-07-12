'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth-store';

const LIVE_FEED = [
  { time: 'Just now', event: 'Vibration anomaly detected', machine: 'Robot Arm 01', type: 'maintenance', status: 'auto-resolved' },
  { time: '2m ago',  event: 'Zone intrusion alert',      machine: 'Press Line A',   type: 'safety',      status: 'escalated' },
  { time: '5m ago',  event: 'Defect rate spike',         machine: 'Vision Station', type: 'quality',     status: 'approved' },
  { time: '8m ago',  event: 'Energy overconsumption',    machine: 'CNC Cluster 3',  type: 'energy',      status: 'auto-resolved' },
  { time: '11m ago', event: 'Bearing temperature trend', machine: 'Robot Arm 02',   type: 'maintenance', status: 'pending' },
];

const TYPE_DOT: Record<string, string> = {
  safety:      'bg-coral',
  quality:     'bg-amber',
  maintenance: 'bg-moss',
  energy:      'bg-sage-dim',
  production:  'bg-moss',
};

const STATUS_PILL: Record<string, string> = {
  'auto-resolved': 'text-moss',
  'approved':      'text-sage',
  'escalated':     'text-amber',
  'pending':       'text-sage-dim',
};

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoggedIn } = useAuthStore();
  const [email, setEmail]       = useState('demo@paaim.io');
  const [password, setPassword] = useState('demo123');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [tick, setTick]         = useState(0);

  useEffect(() => { if (isLoggedIn) router.replace('/dashboard'); }, [isLoggedIn, router]);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 3000);
    return () => clearInterval(id);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    await new Promise((r) => setTimeout(r, 700));
    const ok = login(email, password);
    setLoading(false);
    if (ok) router.replace('/dashboard');
    else setError('Invalid credentials');
  };

  return (
    <div className="min-h-screen flex">

      {/* ── Left: Brand Panel — deep pine ── */}
      <div className="hidden lg:flex lg:w-[55%] bg-pine flex-col relative overflow-hidden">

        {/* Grid overlay */}
        <div className="absolute inset-0 opacity-[0.05]"
          style={{ backgroundImage: 'linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)', backgroundSize: '48px 48px' }}
        />

        {/* Ambient glow */}
        <div className="pointer-events-none absolute -top-24 left-1/3 w-[600px] h-[420px] rounded-full bg-pine-2/50 blur-[90px]" />
        <div className="pointer-events-none absolute bottom-0 right-0 w-[400px] h-[300px] rounded-full bg-moss/10 blur-[90px]" />

        <div className="relative z-10 flex flex-col h-full p-10">

          {/* Logo */}
          <div className="flex items-center gap-3 mb-auto">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#7FA893] to-[#1B5443] flex items-center justify-center ring-1 ring-white/10">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <span className="text-white font-bold text-lg tracking-tight leading-none">PAAIM</span>
              <p className="text-sage-dim text-[10px] leading-none mt-1 tracking-[0.14em] font-mono uppercase">Field&nbsp;Ops</p>
            </div>
          </div>

          {/* Hero text */}
          <div className="py-12">
            <p className="font-mono text-[11px] font-semibold text-amber uppercase tracking-[0.16em] mb-4">
              Smart Factory Decisions
            </p>
            <h1 className="text-3xl font-bold text-white leading-tight tracking-[-0.02em] mb-4">
              Too many alerts.<br />Not enough action.<br />
              <span className="text-amber">We fix that.</span>
            </h1>
            <p className="text-sage-dim text-sm leading-relaxed max-w-sm">
              Smart monitors watch every machine, work out what each problem will cost in downtime and scrap, check it against your safety rules, and tell the right person exactly what to do — in seconds.
            </p>

            {/* Feature pills */}
            <div className="flex flex-wrap gap-2 mt-6">
              {['5 Smart Monitors', 'Safety Rules Built-in', 'Cost & Downtime Forecast', 'Safety Double-check', 'You Approve', 'Full Audit Trail'].map((f) => (
                <span key={f} className="font-mono text-[10.5px] font-semibold text-sage bg-pine-2/40 border border-moss/20 px-3 py-1 rounded-full">
                  {f}
                </span>
              ))}
            </div>
          </div>

          {/* Live activity feed */}
          <div className="mt-auto">
            <div className="flex items-center gap-2 mb-3">
              <span className="relative flex w-2 h-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber" />
              </span>
              <span className="font-mono text-[10.5px] font-semibold text-sage-dim uppercase tracking-[0.16em]">Live activity — Factory 001</span>
            </div>
            <div className="space-y-2">
              {LIVE_FEED.map((item, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all duration-500 ${
                    i === tick % LIVE_FEED.length ? 'border-moss/30 bg-pine-2/50' : 'border-moss/15 bg-pine-2/25'
                  }`}
                >
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${TYPE_DOT[item.type]}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-sage truncate">{item.event}</p>
                    <p className="text-[10px] text-sage-dim truncate">{item.machine}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`font-mono text-[10px] font-semibold ${STATUS_PILL[item.status]}`}>{item.status}</span>
                    <span className="font-mono text-[10px] text-sage-dim">{item.time}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3 mt-4">
              {[
                { label: 'Decisions today', value: '247' },
                { label: 'Auto-resolved',   value: '91%'  },
                { label: 'Avg latency',     value: '1.3s' },
              ].map((s) => (
                <div key={s.label} className="bg-pine-2/30 border border-moss/20 rounded-lg p-3 text-center">
                  <p className="font-mono text-lg font-semibold text-white leading-none">{s.value}</p>
                  <p className="text-[10px] text-sage-dim mt-1.5 leading-none">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* ── Right: Form Panel ── */}
      <div className="flex-1 flex items-center justify-center bg-paper p-6 lg:p-12">
        <div className="w-full max-w-sm">

          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#7FA893] to-[#1B5443] flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="text-ink font-bold">PAAIM</span>
          </div>

          <p className="font-mono text-[10.5px] font-semibold text-pine-2 uppercase tracking-[0.16em] mb-2">Sign in</p>
          <h2 className="text-2xl font-bold text-ink tracking-[-0.02em] mb-1">Welcome back</h2>
          <p className="text-sm text-dim mb-8">Factory 001 · Austin, TX</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block font-mono text-[10.5px] font-semibold text-dim uppercase tracking-[0.12em] mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full bg-white border border-line rounded-xl px-4 py-3 text-sm text-ink placeholder-dim focus:outline-none focus:border-moss focus:ring-2 focus:ring-pine-2/20 transition-all"
                placeholder="you@factory.com"
              />
            </div>

            <div>
              <label className="block font-mono text-[10.5px] font-semibold text-dim uppercase tracking-[0.12em] mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full bg-white border border-line rounded-xl px-4 py-3 text-sm text-ink placeholder-dim focus:outline-none focus:border-moss focus:ring-2 focus:ring-pine-2/20 transition-all"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-surface-bad border border-coral text-coral text-xs rounded-xl px-4 py-3">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-pine-2 hover:bg-pine disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold text-sm py-3 rounded-xl transition-colors mt-1"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating…
                </span>
              ) : 'Sign in to PAAIM'}
            </button>
          </form>

          {/* Demo credentials */}
          <div className="mt-6 pt-6 border-t border-line">
            <p className="font-mono text-[10.5px] font-semibold text-dim uppercase tracking-[0.16em] mb-3">Demo credentials</p>
            <div className="space-y-2">
              {[
                { role: 'Operator', email: 'demo@paaim.io', pwd: 'demo123',  color: 'text-pine-2 bg-surface-ok border-moss' },
                { role: 'Admin',    email: 'admin@paaim.io', pwd: 'admin123', color: 'text-amber bg-surface-warn border-amber' },
              ].map(({ role, email: e, pwd, color }) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => { setEmail(e); setPassword(pwd); setError(''); }}
                  className="w-full flex items-center justify-between px-4 py-2.5 rounded-xl border border-line bg-white hover:bg-paper transition-colors text-xs"
                >
                  <span className={`font-mono font-bold px-2 py-0.5 rounded-md border text-[11px] uppercase tracking-wide ${color}`}>{role}</span>
                  <span className="text-dim font-mono">{e}</span>
                </button>
              ))}
            </div>
          </div>

          <p className="text-center font-mono text-[10px] text-dim uppercase tracking-[0.12em] mt-8">
            PAAIM v1.0 · 7-Layer Decision Pipeline · IATF 16949 Ready
          </p>
        </div>
      </div>

    </div>
  );
}
