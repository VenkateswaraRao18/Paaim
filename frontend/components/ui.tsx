'use client';

/**
 * PAAIM shared UI primitives — "Field Ops / Pine & Amber".
 * See DESIGN.md. Compose screens from these; never re-style from scratch.
 */

import { ReactNode } from 'react';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

const toneText: Record<Tone, string> = {
  ok: 'text-pine-2',
  warn: 'text-[#9A6B15]',
  bad: 'text-coral',
  neutral: 'text-dim',
};
const toneSurface: Record<Tone, string> = {
  ok: 'bg-surface-ok',
  warn: 'bg-surface-warn',
  bad: 'bg-surface-bad',
  neutral: 'bg-paper',
};
const toneBorder: Record<Tone, string> = {
  ok: 'border-pine-2',
  warn: 'border-amber',
  bad: 'border-coral',
  neutral: 'border-line',
};

// ── Eyebrow — mono uppercase label ─────────────────────────────
export function Eyebrow({ children, dim = false, className = '' }: { children: ReactNode; dim?: boolean; className?: string }) {
  return (
    <span
      className={`font-mono text-[10.5px] uppercase tracking-eyebrow font-semibold ${dim ? 'text-dim' : 'text-pine-2'} ${className}`}
    >
      {children}
    </span>
  );
}

// ── Section header — the eyebrow → title → sub stack ───────────
export function SectionHeader({
  eyebrow,
  title,
  sub,
  right,
  accent,
}: {
  eyebrow?: string;
  title: ReactNode;
  sub?: string;
  right?: ReactNode;
  accent?: string; // a word inside title to tint
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5"><Eyebrow>{eyebrow}</Eyebrow></div>}
        <h2 className="text-[19px] font-bold text-ink tracking-[-0.02em] leading-tight">
          {title}{accent && <span className="text-pine-2"> {accent}</span>}
        </h2>
        {sub && <p className="text-[13px] text-dim mt-1 leading-snug">{sub}</p>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

// ── Card-on-paper ──────────────────────────────────────────────
export function Card({ children, className = '', focal = false, onClick }: { children: ReactNode; className?: string; focal?: boolean; onClick?: () => void }) {
  return (
    <div onClick={onClick} className={`bg-card border border-line rounded-card ${focal ? 'shadow-[0_1px_3px_rgba(18,58,46,0.08)]' : ''} ${className}`}>
      {children}
    </div>
  );
}

// ── KPI tile — mono value, eyebrow label, meaning below ────────
export function KpiTile({
  label,
  value,
  meaning,
  tone = 'neutral',
  unit,
}: {
  label: string;
  value: ReactNode;
  meaning?: string;
  tone?: Tone;
  unit?: string;
}) {
  return (
    <Card className="p-4">
      <Eyebrow dim>{label}</Eyebrow>
      <div className={`font-mono text-[26px] font-semibold leading-none mt-2 ${tone === 'neutral' ? 'text-pine' : toneText[tone]}`}>
        {value}
        {unit && <span className="text-[14px] text-dim ml-1 font-normal">{unit}</span>}
      </div>
      {meaning && <p className="text-[12px] text-dim mt-1.5 leading-snug">{meaning}</p>}
    </Card>
  );
}

// ── Signal pill — status chip that means something ─────────────
export function SignalPill({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded-full ${toneSurface[tone]} ${toneText[tone]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${tone === 'ok' ? 'bg-pine-2' : tone === 'warn' ? 'bg-amber' : tone === 'bad' ? 'bg-coral' : 'bg-moss'}`} />
      {children}
    </span>
  );
}

// ── Alert bar — left-border pattern ────────────────────────────
export function AlertBar({ tone = 'ok', title, children }: { tone?: Tone; title?: string; children?: ReactNode }) {
  return (
    <div className={`alert ${toneSurface[tone]} ${toneBorder[tone]} border border-l-4 p-4`}>
      {title && <p className={`font-semibold text-[14px] ${toneText[tone]}`}>{title}</p>}
      {children && <div className="text-[13px] text-ink/80 mt-1 leading-relaxed">{children}</div>}
    </div>
  );
}

// ── Evidence row — fact → source → interpretation ──────────────
export function EvidenceRow({
  fact,
  source,
  interpretation,
  onClick,
}: {
  fact: ReactNode;
  source: string;
  interpretation?: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-start gap-3 py-2.5 px-3 rounded-lg hover:bg-surface-ok transition-colors group"
    >
      <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-pine-2 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="text-[13px] text-ink font-medium leading-snug">{fact}</div>
        {interpretation && <div className="text-[12px] text-dim mt-0.5 leading-snug">{interpretation}</div>}
      </div>
      <span className="font-mono text-[10.5px] text-moss uppercase tracking-wide shrink-0 mt-1 group-hover:text-pine-2 transition-colors">
        {source}
      </span>
    </button>
  );
}

// ── Read-only OT banner — calm, persistent, never alarming ─────
export function OTBanner() {
  return (
    <div className="flex items-center gap-2 text-[11.5px] text-pine-2 bg-surface-ok border border-line rounded-lg px-3 py-1.5">
      <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
      <span className="font-mono uppercase tracking-wide">Read-only OT mode — no PLC write-back, no autonomous restart</span>
    </div>
  );
}
