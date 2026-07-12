'use client';

import { useState } from 'react';
import { GLOSSARY } from '@/lib/labels';

/**
 * A small "?" next to a technical term that explains it in one plain sentence
 * on hover/tap — so an operator never hits a word they can't decode.
 */
export function HelpTip({ term, text }: { term?: string; text?: string }) {
  const [open, setOpen] = useState(false);
  const body = text ?? (term ? GLOSSARY[term] : undefined);
  if (!body) return null;
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="ml-1 w-3.5 h-3.5 inline-flex items-center justify-center rounded-full bg-line text-dim text-[9px] font-bold hover:bg-moss hover:text-white transition-colors"
        aria-label="What does this mean?"
      >
        ?
      </button>
      {open && (
        <span className="absolute z-20 left-1/2 -translate-x-1/2 top-5 w-56 bg-pine text-white text-xs rounded-lg px-3 py-2 shadow-xl leading-snug">
          {body}
        </span>
      )}
    </span>
  );
}

/**
 * Turns a decision into one plain sentence an operator can act on:
 * what happened → why it matters → what to do.
 */
export function PlainImpactBanner({
  signal, machine, action, riskLevel, downtimePerHour, penalty, customer, deadline,
}: {
  signal: string;
  machine: string;
  action: string;
  riskLevel?: string;
  downtimePerHour?: number;
  penalty?: number;
  customer?: string;
  deadline?: string;
}) {
  const money = (n?: number) =>
    n && n > 0 ? `$${n >= 1000 ? `${(n / 1000).toFixed(0)}K` : n}` : null;

  const consequences: string[] = [];
  if (downtimePerHour) consequences.push(`about ${money(downtimePerHour)}/hr in downtime`);
  if (penalty) consequences.push(`a ${money(penalty)} late penalty`);
  if (customer && deadline) consequences.push(`the ${customer} order (due ${deadline}) at risk`);

  // signal discipline: critical/high = danger (coral), else attention (amber)
  const danger = riskLevel === 'critical' || riskLevel === 'high';
  const tone = danger
    ? 'alert-bad bg-surface-bad'
    : 'alert-warn bg-surface-warn';

  return (
    <div className={`alert border border-l-4 p-4 ${tone}`}>
      <p className="text-[14px] text-ink leading-relaxed">
        <span className="font-bold">{machine}:</span> {signal.toLowerCase()}.
        {consequences.length > 0 && (
          <> If ignored, this risks {consequences.join(', ')}.</>
        )}{' '}
        <span className="font-bold text-pine-2">Recommended: {action.toLowerCase()}.</span>
      </p>
    </div>
  );
}
