'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/auth-store';

/**
 * The landing page.
 *
 * This route used to be a spinner that redirected to /login, so PAAIM had no
 * front door at all.
 *
 * Every claim here is one the product actually makes good on, and the numbers
 * shown in the mockups are the real ones from a real run — 7.29 mm/s on
 * robot_arm_01, °F converted to °C, "cost impact unknown" where no cost model
 * exists. There is no "99.9% uptime" or "40% OEE lift": a plant manager asks how
 * a number was measured, and "marketing wrote it" ends the meeting. The one
 * uncomfortable number (44s to a governed decision) is on the page too, because
 * they will find it in the first demo anyway.
 */

const NAV = [
  ['Product', '#product'],
  ['How it works', '#how'],
  ['Multi-plant', '#tenancy'],
  ['Governance', '#governance'],
  ['Specs', '#specs'],
];

const PIPELINE = [
  ['Normalize', 'PSTR1_PROD_TEMP_F → product_temperature, °F → °C'],
  ['Judge', "Against this machine's own learned normal"],
  ['Deduplicate', 'One physical fault = one incident, across every feed'],
  ['Reason', 'Your monitors, on Gemini, inside your rules'],
  ['Estimate', 'Downtime, scrap, OEE per candidate action'],
  ['Govern', 'Policy engine, red-team challenge, approval route'],
  ['Triage', 'L1/L2/L3 from your orders, deadlines and costs'],
  ['Record', 'Every step, on the audit trail'],
];

const PILLARS = [
  {
    n: '01',
    k: "Speaks your plant's language",
    d: 'Your SCADA calls it PSTR1_PROD_TEMP_F. PAAIM reads your tag list once, proposes the mapping, and reconciles the units — a °F tag pointed at a °C signal is converted, and a kW tag pointed at a temperature signal is refused and handed to you.',
    proof: 'No one types 500 tags. Discovery reads them from the source.',
  },
  {
    n: '02',
    k: 'Judges the machine, not the manual',
    d: "Every watcher scores a reading against that machine's own history. 4.0 mm/s is unremarkable on a ten-year-old agitator and an 8σ event on last year's. A single fleet threshold cannot say both, so PAAIM learns each one.",
    proof: 'Learned from your historian export. Per machine, per signal.',
  },
  {
    n: '03',
    k: 'Reasons, then submits to governance',
    d: 'A breach wakes only the monitors that watch that signal. They reason with Gemini inside the rules you wrote, and the recommendation then passes impact estimation, a red-team challenge and an approval route before an operator ever sees it.',
    proof: 'The rules are guardrails. The reasoning is the model. Both are shown.',
  },
  {
    n: '04',
    k: 'Ranks by what it costs you',
    d: 'L1/L2/L3 from your real orders, real deadlines and your own cost model — safety first, loss-minimising tiebreak. Where you have not told PAAIM the money, it says "cost impact unknown" instead of inventing a figure to justify stopping your line.',
    proof: 'Unknown reads as unknown. Never as zero, never as a guess.',
  },
];

const FAQ: [string, string][] = [
  [
    'Do we have to change our tag names?',
    'No. PAAIM learns them. You connect the source, it reads the tag list, proposes a mapping to your vocabulary, and you confirm it once. Runtime after that is a dictionary lookup — no AI, microseconds.',
  ],
  [
    'What if our vocabulary is nothing like a machine shop’s?',
    'That is the normal case. The signal vocabulary is yours: pick the closest starter pack (CNC, injection moulding, food, press) and edit it, or define your own signals. No release, no code.',
  ],
  [
    'Does it need the cloud / can the LLM see our data?',
    'The reasoning layer calls Gemini with the incident context. The detection, normalization, judging and governance layers are deterministic and run locally — no model is involved in deciding whether a reading is a breach.',
  ],
  [
    'What happens on day one, before it has learned anything?',
    'It says so. A fresh plant has no baseline, so watchers fall back to whatever limits your source declares and report "judged by declared limits". Upload your history and they switch to learned baselines. The difference is visible on screen.',
  ],
  [
    'How fast is a decision?',
    'A breach is detected in milliseconds. A fully governed decision — multi-agent reasoning, impact, red-team, approval route, triage — currently takes around 44 seconds end to end, dominated by the LLM calls. That is the honest number, and the number we are working on.',
  ],
];

const SPECS: [string, string][] = [
  ['Ingestion', 'SSE stream · REST poll · REST push. Long and wide payloads, enveloped or flat.'],
  ['Not yet supported', 'OPC-UA, Modbus, MQTT — refused explicitly, not faked.'],
  ['Detection', 'SPC against learned per-machine baselines (2σ warn / 3σ critical), direction-aware.'],
  ['Units', '°C ↔ K ↔ °F, psi ↔ bar ↔ kPa, W ↔ kW. Unconvertible pairs are escalated, never guessed.'],
  ['Reasoning', 'Gemini 2.5 Flash, with deterministic rule fallback if unavailable.'],
  ['Governance', 'Policy engine, red-team challenge, risk-based approval routing, full audit trail.'],
  ['Event backbone', 'Durable local log or Kafka.'],
  ['Tenancy', 'Per-factory vocabulary, mappings, monitors, watchers, context and incidents.'],
];

export default function Landing() {
  const { isLoggedIn } = useAuthStore();
  // Decided after mount: the session is restored from storage, so rendering the
  // CTA on the server would flash the wrong one.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);

  const cta = ready && isLoggedIn ? '/dashboard' : '/login';
  const ctaLabel = ready && isLoggedIn ? 'Open dashboard' : 'Sign in';

  return (
    <div className="min-h-screen bg-paper">
      {/* ── Nav ───────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-paper/85 backdrop-blur-md border-b border-line">
        <div className="max-w-[1180px] mx-auto px-6 h-16 flex items-center justify-between gap-6">
          <Link href="/" className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#7FA893] to-[#1B5443] flex items-center justify-center ring-1 ring-black/5">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="leading-none">
              <div className="font-bold text-ink tracking-[-0.02em] text-[15px]">PAAIM</div>
              <div className="font-mono text-[9px] text-dim tracking-[0.14em] uppercase mt-0.5">Field Ops</div>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-7">
            {NAV.map(([label, href]) => (
              <a key={href} href={href} className="text-[13px] font-medium text-dim hover:text-ink transition-colors">
                {label}
              </a>
            ))}
          </nav>

          <Link href={cta} className="btn-primary px-4 py-1.5 text-[13px] shrink-0">{ctaLabel}</Link>
        </div>
      </header>

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-40 right-0 w-[560px] h-[420px] rounded-full bg-moss/20 blur-[120px]" />
        <div className="relative max-w-[1180px] mx-auto px-6 pt-20 pb-16 grid lg:grid-cols-[1.05fr_0.95fr] gap-14 items-center">
          <div>
            <p className="eyebrow">Policy-Aware Agentic Intelligence Manager</p>
            <h1 className="text-[46px] leading-[1.06] font-bold text-ink h-tight mt-4">
              Your factory already told you<br />what was wrong.
              <span className="text-dim"> Nobody had time to read it.</span>
            </h1>
            <p className="text-[16px] text-dim mt-5 leading-relaxed max-w-xl">
              Hundreds of signals breach every shift. A handful matter. PAAIM judges each one against
              that machine&apos;s own history, reasons about it with your rules in force, ranks it by
              what it actually costs you — and shows its work.
            </p>
            <div className="flex flex-wrap gap-3 mt-8">
              <Link href={cta} className="btn-primary px-5 py-2.5 text-[14px]">{ctaLabel}</Link>
              <a href="#how" className="btn-ghost px-5 py-2.5 text-[14px]">See the pipeline</a>
            </div>
            <p className="font-mono text-[11px] text-dim mt-6">
              Two live plants on one deployment · sign in as either
            </p>
          </div>

          {/* A real incident, as it actually renders. The numbers are from a
              real run rather than a designer's placeholder. */}
          <div className="card p-0 overflow-hidden shadow-[0_18px_50px_-24px_rgba(18,58,46,0.45)]">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-line bg-surface-ok/60">
              <span className="font-mono text-[10px] text-pine-2 uppercase tracking-[0.14em] font-semibold">Live incident</span>
              <span className="font-mono text-[10px] text-dim">dec_20260715_163630</span>
            </div>
            <div className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 signal-bad font-mono text-[10px] font-bold uppercase tracking-wide">
                    L1 · Critical
                  </span>
                  <h3 className="text-[17px] font-bold text-ink mt-2.5">Robot Arm 1 — Vibration</h3>
                  <p className="font-mono text-[11px] text-dim mt-1">robot_arm_01 · VE_102 → vibration</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="mono text-[26px] font-semibold text-coral leading-none">7.29</div>
                  <div className="text-[11px] text-dim mt-1">mm/s</div>
                </div>
              </div>

              <div className="mt-4 rounded-lg bg-paper border border-line p-3">
                <p className="font-mono text-[9.5px] text-dim uppercase tracking-[0.14em] mb-2">Judged by learned baseline</p>
                <div className="flex items-end gap-[3px] h-12">
                  {[18, 21, 19, 24, 22, 26, 23, 29, 34, 41, 55, 72, 88, 100].map((h, i) => (
                    <div
                      key={i}
                      className={`flex-1 rounded-sm ${h > 70 ? 'bg-coral' : h > 40 ? 'bg-amber' : 'bg-moss'}`}
                      style={{ height: `${h}%` }}
                    />
                  ))}
                </div>
                <p className="font-mono text-[10px] text-dim mt-2">3σ threshold 4.84 mm/s · 60 pre-fault points</p>
              </div>

              <div className="mt-4 space-y-2">
                {[
                  ['maintenance_agent', '0.97', 'gemini-2.5-flash'],
                  ['Spindle Health', '0.98', 'gemini-2.5-flash'],
                ].map(([n, c, m]) => (
                  <div key={n} className="flex items-center justify-between text-[12px]">
                    <span className="text-ink font-medium truncate">{n}</span>
                    <span className="font-mono text-[10px] text-dim shrink-0 ml-3">{m} · {c}</span>
                  </div>
                ))}
              </div>

              <div className="mt-4 alert alert-bad p-3">
                <p className="text-[12.5px] font-semibold text-coral">stop_line · safety_officer approval required</p>
                <p className="text-[11.5px] text-ink/75 mt-1 leading-snug">
                  restart is safety-critical · cost impact unknown — no cost model configured
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── The problem ───────────────────────────────────────── */}
      <section className="border-y border-line bg-white">
        <div className="max-w-[1180px] mx-auto px-6 py-14 grid md:grid-cols-3 gap-8">
          {[
            ['Alarm floods', 'A threshold set once, years ago, for a machine that has since been rebuilt. It fires all shift. Everyone mutes it.'],
            ['Tribal knowledge', 'The one fitter who knows that this mixer always runs rough after a CIP is on nights, or has retired.'],
            ['No defensible ranking', 'Two faults, one crew. Which one costs more to leave? Nobody can show their working, so the loudest wins.'],
          ].map(([t, d]) => (
            <div key={t}>
              <div className="w-9 h-9 rounded-lg signal-warn flex items-center justify-center mb-3">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M5 19h14a2 2 0 001.84-2.75L13.74 4a2 2 0 00-3.5 0l-7.1 12.25A2 2 0 004.99 19z" />
                </svg>
              </div>
              <h3 className="text-[15px] font-bold text-ink">{t}</h3>
              <p className="text-[13.5px] text-dim mt-1.5 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pillars ───────────────────────────────────────────── */}
      <section id="product" className="max-w-[1180px] mx-auto px-6 py-20">
        <p className="eyebrow">The product</p>
        <h2 className="text-[30px] font-bold text-ink h-tight mt-2 max-w-2xl">
          Four things it does that a rules engine cannot
        </h2>
        <div className="grid md:grid-cols-2 gap-x-12 gap-y-10 mt-12">
          {PILLARS.map((p) => (
            <div key={p.n} className="relative pl-14">
              <span className="absolute left-0 top-0 mono text-[13px] font-bold text-moss">{p.n}</span>
              <h3 className="text-[16px] font-bold text-ink">{p.k}</h3>
              <p className="text-[13.5px] text-dim mt-2 leading-relaxed">{p.d}</p>
              <p className="text-[12px] text-pine-2 mt-2.5 font-medium">{p.proof}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pipeline ──────────────────────────────────────────── */}
      <section id="how" className="relative bg-pine overflow-hidden">
        <div className="pointer-events-none absolute -top-24 left-1/4 w-[520px] h-[380px] rounded-full bg-[#1B5443]/60 blur-[110px]" />
        <div className="relative max-w-[1180px] mx-auto px-6 py-20">
          <p className="font-mono text-[10.5px] text-moss uppercase tracking-[0.14em] font-semibold">
            One reading, eight layers
          </p>
          <h2 className="text-[30px] font-bold text-white h-tight mt-2 max-w-2xl">
            From a number on a wire to a decision someone will sign
          </h2>
          <p className="text-[14px] text-white/60 mt-3 max-w-2xl leading-relaxed">
            Only a breach reaches the expensive layers. That is what keeps the LLM bill sane and the
            queue readable — the eyes are cheap and constant, the brain is rare.
          </p>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-10">
            {PIPELINE.map(([t, d], i) => (
              <div key={t} className="rounded-xl bg-white/[0.05] border border-white/[0.09] p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="mono text-[10px] text-moss font-bold">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-white text-[13.5px] font-semibold">{t}</span>
                </div>
                <p className="text-[11.5px] text-white/55 leading-snug">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── The learned-baseline argument ─────────────────────── */}
      <section className="max-w-[1180px] mx-auto px-6 py-20 grid lg:grid-cols-2 gap-14 items-center">
        <div>
          <p className="eyebrow">Why one threshold cannot work</p>
          <h2 className="text-[28px] font-bold text-ink h-tight mt-2">
            Two mixers. Same reading. One is fine, one is failing.
          </h2>
          <p className="text-[14px] text-dim mt-4 leading-relaxed">
            Both agitators read <span className="mono font-semibold text-ink">4.0 mm/s</span>. A fleet-wide
            limit either alarms on both — and gets muted — or on neither, and you lose the bearing.
          </p>
          <p className="text-[14px] text-dim mt-3 leading-relaxed">
            PAAIM learned each machine from your own history. On the older mixer that reading is
            ordinary. On the newer one it is eight standard deviations from everything it has ever
            done. Same number, opposite meaning, and only the machine&apos;s own past can tell you which.
          </p>
        </div>

        <div className="space-y-3">
          {[
            { m: 'mixer_01', age: 'Installed 2019 · runs rough', mean: '2.9', sd: '0.42', sigma: '2.6σ', tone: 'warn' as const, w: 62 },
            { m: 'mixer_02', age: 'Installed 2021 · smooth', mean: '1.9', sd: '0.24', sigma: '8.0σ', tone: 'bad' as const, w: 100 },
          ].map((r) => (
            <div key={r.m} className="card p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="mono text-[13px] font-semibold text-ink">{r.m}</p>
                  <p className="text-[11.5px] text-dim mt-0.5">{r.age}</p>
                </div>
                <span className={`font-mono text-[11px] font-bold px-2 py-1 rounded-md ${r.tone === 'bad' ? 'signal-bad' : 'signal-warn'}`}>
                  {r.sigma}
                </span>
              </div>
              <div className="mt-3 h-1.5 rounded-full bg-paper overflow-hidden">
                <div className={`h-full rounded-full ${r.tone === 'bad' ? 'bg-coral' : 'bg-amber'}`} style={{ width: `${r.w}%` }} />
              </div>
              <p className="font-mono text-[10.5px] text-dim mt-2">
                learned normal {r.mean} ± {r.sd} mm/s · reading 4.0
              </p>
            </div>
          ))}
          <p className="text-[11.5px] text-dim leading-snug pt-1">
            Learned from a 30-day historian export, per machine, per signal — in your units.
          </p>
        </div>
      </section>

      {/* ── Multi-tenancy ─────────────────────────────────────── */}
      <section id="tenancy" className="border-y border-line bg-white">
        <div className="max-w-[1180px] mx-auto px-6 py-20">
          <p className="eyebrow">Multi-plant</p>
          <h2 className="text-[30px] font-bold text-ink h-tight mt-2 max-w-2xl">
            One deployment, many plants — that share nothing
          </h2>
          <p className="text-[14px] text-dim mt-3 max-w-2xl leading-relaxed">
            A dairy and a machine shop have no signals in common, no units in common, and no business
            seeing each other. Each gets its own vocabulary, mappings, monitors, watchers, cost model
            and incidents. Neither can read or change the other&apos;s.
          </p>

          <div className="grid md:grid-cols-2 gap-4 mt-10">
            {[
              {
                name: 'Northfield Foods', kind: 'Dairy · HTST', vocab: 'food_processing · 12 signals',
                tags: [['PSTR1_PROD_TEMP_F', '°F → C'], ['PSTR1_HOLD_PRESS_PSI', 'psi → bar'], ['FILR1_NET_WT_G', 'g']],
                note: 'Hold pressure fails LOW. Routes to quality.',
              },
              {
                name: 'Precision Parts Co', kind: 'CNC machining', vocab: 'cnc_machining · 11 signals',
                tags: [['TT_101', '°C'], ['VE_102', 'mm/s'], ['PT_HYD_01', 'bar']],
                note: 'Hydraulic pressure fails LOW. Routes to maintenance.',
              },
            ].map((t) => (
              <div key={t.name} className="card p-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-[15px] font-bold text-ink">{t.name}</h3>
                  <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-md signal-ok uppercase tracking-wide">{t.kind}</span>
                </div>
                <p className="font-mono text-[11px] text-dim mt-1">{t.vocab}</p>
                <div className="mt-4 space-y-1.5">
                  {t.tags.map(([tag, unit]) => (
                    <div key={tag} className="flex items-center justify-between font-mono text-[11.5px]">
                      <span className="text-ink">{tag}</span>
                      <span className="text-pine-2">{unit}</span>
                    </div>
                  ))}
                </div>
                <p className="text-[12px] text-dim mt-4 leading-snug">{t.note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Governance ────────────────────────────────────────── */}
      <section id="governance" className="max-w-[1180px] mx-auto px-6 py-20">
        <p className="eyebrow">Governance</p>
        <h2 className="text-[30px] font-bold text-ink h-tight mt-2 max-w-2xl">
          The agent never gets the last word
        </h2>
        <div className="grid md:grid-cols-3 gap-5 mt-10">
          {[
            ['Policy engine', 'Deterministic rules you own. An action outside them is blocked before it is offered, not after.'],
            ['Red-team challenge', 'A second pass attacks the recommendation: what is assumed, what breaks it, what was not considered.'],
            ['Approval routing', 'Risk decides who signs — operator, manager, safety officer. Critical actions cannot self-approve.'],
            ['Evidence, attached', 'The pre-fault series, each agent\'s stated confidence, the model that answered. An agent that stated no confidence shows "not stated".'],
            ['Honest unknowns', 'No cost model means "cost impact unknown", not $0 and not an estimate. The same for units a source never declared.'],
            ['Full audit trail', 'Every layer, its latency, its output, on the record — for the incident review that happens three weeks later.'],
          ].map(([t, d]) => (
            <div key={t} className="card p-5">
              <h3 className="text-[14px] font-bold text-ink">{t}</h3>
              <p className="text-[12.5px] text-dim mt-1.5 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Commissioning ─────────────────────────────────────── */}
      <section className="border-y border-line bg-surface-ok/40">
        <div className="max-w-[1180px] mx-auto px-6 py-20">
          <p className="eyebrow">Commissioning</p>
          <h2 className="text-[30px] font-bold text-ink h-tight mt-2">Five steps, then it runs</h2>
          <div className="mt-10 grid md:grid-cols-5 gap-4">
            {[
              ['Tell it what your plant is', 'Machines, cost model, open orders — from your ERP, or one document.'],
              ['Connect a source', 'Stream, REST or historian. It reads your tag list.'],
              ['Confirm the mapping', 'The one screen worth your time. Units reconciled here.'],
              ['Upload your history', "It learns each machine's normal from your own past."],
              ['Build a monitor', 'Name the signals it watches. Any source feeding them wakes it.'],
            ].map(([t, d], i) => (
              <div key={t} className="relative">
                <div className="w-7 h-7 rounded-lg bg-pine-2 text-white font-mono text-[11px] font-bold flex items-center justify-center">
                  {i + 1}
                </div>
                <p className="text-[13.5px] font-semibold text-ink mt-3">{t}</p>
                <p className="text-[12px] text-dim mt-1 leading-snug">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Specs ─────────────────────────────────────────────── */}
      <section id="specs" className="max-w-[1180px] mx-auto px-6 py-20">
        <p className="eyebrow">Technical</p>
        <h2 className="text-[30px] font-bold text-ink h-tight mt-2">What it actually supports</h2>
        <div className="card mt-8 overflow-hidden">
          {SPECS.map(([k, v], i) => (
            <div key={k} className={`grid sm:grid-cols-[220px_1fr] gap-x-6 gap-y-1 px-5 py-4 ${i ? 'border-t border-line' : ''}`}>
              <span className="font-mono text-[11px] text-pine-2 uppercase tracking-[0.1em] font-semibold pt-0.5">{k}</span>
              <span className="text-[13.5px] text-ink/85 leading-relaxed">{v}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────── */}
      <section className="border-t border-line bg-white">
        <div className="max-w-[820px] mx-auto px-6 py-20">
          <p className="eyebrow">Questions we actually get</p>
          <h2 className="text-[30px] font-bold text-ink h-tight mt-2">Straight answers</h2>
          <div className="mt-8">
            {FAQ.map(([q, a]) => (
              <details key={q} className="group border-b border-line py-4">
                <summary className="flex items-center justify-between cursor-pointer list-none gap-4">
                  <span className="text-[14.5px] font-semibold text-ink">{q}</span>
                  <span className="text-dim text-lg leading-none shrink-0 transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="text-[13.5px] text-dim mt-2.5 leading-relaxed pr-8">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────── */}
      <section className="relative bg-pine overflow-hidden">
        <div className="pointer-events-none absolute -bottom-32 left-1/2 -translate-x-1/2 w-[640px] h-[380px] rounded-full bg-[#7FA893]/15 blur-[110px]" />
        <div className="relative max-w-[1180px] mx-auto px-6 py-20 text-center">
          <h2 className="text-[32px] font-bold text-white h-tight">See it on two real plants</h2>
          <p className="text-[14.5px] text-white/60 mt-3 max-w-xl mx-auto leading-relaxed">
            Sign in as a dairy or a machine shop. Different tags, different units, different
            vocabulary, different incidents — the same PAAIM, and neither can see the other.
          </p>
          <div className="flex justify-center gap-3 mt-8">
            <Link href={cta} className="btn-primary bg-white text-pine hover:bg-white/90 px-6 py-2.5 text-[14px]">
              {ctaLabel}
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="border-t border-line bg-paper">
        <div className="max-w-[1180px] mx-auto px-6 py-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-pine-2 flex items-center justify-center">
              <span className="text-white font-bold text-[11px]">P</span>
            </div>
            <span className="text-[12.5px] text-dim">
              PAAIM — Policy-Aware Agentic Intelligence Manager
            </span>
          </div>
          <div className="flex items-center gap-6">
            {NAV.slice(0, 3).map(([label, href]) => (
              <a key={href} href={href} className="text-[12px] text-dim hover:text-ink transition-colors">{label}</a>
            ))}
            <Link href={cta} className="text-[12px] text-pine-2 font-semibold">{ctaLabel} →</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
