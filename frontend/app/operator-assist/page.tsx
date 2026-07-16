'use client';

import { useEffect, useRef, useState } from 'react';
import { plainMachine } from '@/lib/labels';
import { Eyebrow, SectionHeader, Card, SignalPill, AlertBar } from '@/components/ui';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

type CodeMeta = {
  code: string; machine_id: string; signal_name: string;
  plain_meaning: string; severity: string; raw_register: string;
};
type PastCase = {
  log_id: string; date: string; raw_note: string; resolution: string;
  downtime_min: string; technician: string;
};
type SOP = {
  summary: string; steps: string[]; do_not: string[];
  escalate_if: string; estimated_time_min: number; _source?: string;
};
type Result = { diagnosis: CodeMeta; past_cases: PastCase[]; sop: SOP };

// Gemini sometimes returns **markdown bold**; render it cleanly.
function clean(s: string): string {
  return (s || '').replace(/\*\*/g, '').trim();
}

// Severity → signal tone (critical = danger, high/medium = attention, else neutral)
const sevTone = (s: string): Tone =>
  s === 'critical' ? 'bad' : s === 'high' || s === 'medium' ? 'warn' : 'neutral';

export default function OperatorAssistPage() {
  const [codes, setCodes] = useState<CodeMeta[]>([]);
  const [input, setInput] = useState('');
  const [machine, setMachine] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Vision agent state
  const [vision, setVision] = useState<any>(null);
  const [visionLoading, setVisionLoading] = useState(false);
  const [imgPreview, setImgPreview] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/semantic/codes`).then((r) => r.json()).then((d) => setCodes(d.codes || [])).catch(() => {});
  }, []);

  const inspectImage = async (file: File) => {
    setVisionLoading(true); setVision(null);
    setImgPreview(URL.createObjectURL(file));
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('machine_id', machine || 'robot_arm_01');
      const r = await fetch(`${API_BASE}/semantic/vision-inspect`, { method: 'POST', body: fd });
      const d = await r.json();
      setVision(d.vision);
    } catch { setVision({ error: 'Inspection failed' }); }
    setVisionLoading(false);
  };

  const diagnose = async (code: string, machine_id: string) => {
    if (!code) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await fetch(`${API_BASE}/semantic/diagnose`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, machine_id }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || 'Diagnose failed');
      setResult(await r.json());
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div className="max-w-[960px] mx-auto space-y-6">
      {/* Header — one question */}
      <SectionHeader
        eyebrow="Semantic disconnect · operator assist"
        title="What does this machine code mean,"
        accent="and what do I do?"
        sub="Enter a cryptic error code and get it in plain language: what it means, a step-by-step action plan, and what fixed it before."
      />

      {/* Search input */}
      <Card className="p-5">
        <Eyebrow>Machine code</Eyebrow>
        <div className="flex gap-2 flex-wrap mt-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && diagnose(input, machine)}
            placeholder="Enter a machine code   e.g.  0x4F3"
            className="flex-1 min-w-[200px] border border-line rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss"
          />
          <button
            onClick={() => diagnose(input, machine)}
            disabled={loading || !input}
            className="px-5 py-2.5 rounded-lg text-sm font-semibold bg-pine-2 hover:bg-pine disabled:opacity-50 text-white transition-colors"
          >
            {loading ? 'Diagnosing…' : 'Explain & guide me'}
          </button>
        </div>
        {/* Quick picks */}
        <div className="flex flex-wrap gap-1.5 mt-3 items-center">
          <span className="font-mono text-[10.5px] uppercase tracking-wide text-dim mr-1">Try</span>
          {codes.map((c) => (
            <button
              key={c.code}
              onClick={() => { setInput(c.code); setMachine(c.machine_id); diagnose(c.code, c.machine_id); }}
              className="font-mono text-[12px] font-semibold text-dim bg-paper hover:bg-surface-ok hover:text-pine-2 border border-line px-2 py-1 rounded transition-colors"
            >
              {c.code}
            </button>
          ))}
        </div>
      </Card>

      {error && <AlertBar tone="bad" title="Could not diagnose that code">{error}</AlertBar>}

      {result && (
        <div className="space-y-6">
          {/* 1 — What this means (lead with the plain-language answer) */}
          <Card className="overflow-hidden">
            <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
              <Eyebrow>What this means</Eyebrow>
              <SignalPill tone={sevTone(result.diagnosis.severity)}>{result.diagnosis.severity}</SignalPill>
            </div>
            <div className="p-5">
              <div className="flex items-center gap-2 flex-wrap mb-2.5">
                <span className="font-mono text-[13px] font-semibold bg-pine-2 text-white px-2 py-0.5 rounded">{result.diagnosis.code}</span>
                <span className="text-dim">→</span>
                <span className="text-sm font-semibold text-ink">{plainMachine(result.diagnosis.machine_id)}</span>
              </div>
              <p className="text-[14px] text-ink leading-relaxed">{result.diagnosis.plain_meaning}</p>
              {result.diagnosis.raw_register && (
                <p className="font-mono text-[11px] text-dim mt-2.5">raw {result.diagnosis.raw_register}</p>
              )}
            </div>
          </Card>

          {/* 2 — Your action plan */}
          <Card className="overflow-hidden">
            <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
              <Eyebrow>Your action plan</Eyebrow>
              <span className="font-mono text-[11px] text-dim uppercase tracking-wide">~{result.sop.estimated_time_min} min</span>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-[14px] font-medium text-ink leading-relaxed">{clean(result.sop.summary)}</p>
              <ol className="space-y-2.5">
                {result.sop.steps.map((s, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="w-5 h-5 rounded-full bg-pine-2 text-white font-mono text-[11px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                    <span className="text-[14px] text-ink leading-snug">{clean(s)}</span>
                  </li>
                ))}
              </ol>
              {result.sop.do_not?.length > 0 && (
                <AlertBar tone="bad" title="Do not">
                  <ul className="space-y-1">
                    {result.sop.do_not.map((d, i) => (
                      <li key={i}>{clean(d)}</li>
                    ))}
                  </ul>
                </AlertBar>
              )}
              <AlertBar tone="warn" title="Stop and call a senior if…">
                {clean(result.sop.escalate_if)}
              </AlertBar>
            </div>
          </Card>

          {/* 3 — What fixed this before (tribal knowledge) */}
          <Card className="overflow-hidden">
            <div className="px-5 py-3.5 border-b border-line">
              <Eyebrow>What fixed this before</Eyebrow>
              <p className="text-[12px] text-dim mt-0.5">From past maintenance logs — tribal knowledge, grounded in real cases.</p>
            </div>
            <div className="p-5 space-y-3">
              {result.past_cases.length === 0 && <p className="text-[13px] text-dim">No similar past cases on record.</p>}
              {result.past_cases.map((c) => (
                <div key={c.log_id} className="border border-line rounded-lg p-3.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono text-[11px] font-semibold text-ink uppercase tracking-wide">{c.date}</span>
                    <span className="font-mono text-[10.5px] text-dim uppercase tracking-wide">{c.downtime_min} min · {c.technician}</span>
                  </div>
                  <p className="text-[12.5px] text-dim italic font-mono mb-1.5 leading-snug">&ldquo;{c.raw_note}&rdquo;</p>
                  <p className="text-[13px] text-pine-2 font-medium leading-snug">→ {c.resolution}</p>
                </div>
              ))}
              {result.sop._source && (
                <p className="font-mono text-[10.5px] text-dim uppercase tracking-wide pt-1">
                  Plan by {result.sop._source === 'gemini' ? 'AI (Gemini)' : 'rule engine'} · grounded in {result.past_cases.length} past cases
                </p>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Vision inspection — secondary tool */}
      <Card className="overflow-hidden">
        <div className="px-5 py-3.5 border-b border-line flex items-center justify-between flex-wrap gap-3">
          <div>
            <Eyebrow>Visual inspection</Eyebrow>
            <p className="text-[12px] text-dim mt-0.5">Upload a photo of a part — the Vision Agent checks it for defects.</p>
          </div>
          <input ref={fileRef} type="file" accept="image/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) inspectImage(f); }} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={visionLoading}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-card border border-line text-ink hover:bg-surface-ok hover:text-pine-2 disabled:opacity-50 transition-colors shrink-0"
          >
            {visionLoading ? 'Inspecting…' : 'Upload part photo'}
          </button>
        </div>

        {(imgPreview || vision) && (
          <div className="p-5 flex flex-col sm:flex-row gap-4 items-start">
            {imgPreview && (
              <img src={imgPreview} alt="part" className="w-40 h-32 object-cover rounded-lg border border-line shrink-0" />
            )}
            {visionLoading && <p className="text-[13px] text-dim">Analysing image with AI…</p>}
            {vision && !vision.error && (
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1.5">
                  {vision.defect_found ? (
                    <SignalPill tone={sevTone(vision.severity)}>Defect · {vision.defect_type}</SignalPill>
                  ) : (
                    <SignalPill tone="ok">No defect found</SignalPill>
                  )}
                  {vision.severity && vision.severity !== 'none' && (
                    <span className={`font-mono text-[11px] font-semibold uppercase tracking-wide ${sevTone(vision.severity) === 'bad' ? 'text-coral' : sevTone(vision.severity) === 'warn' ? 'text-[#9A6B15]' : 'text-dim'}`}>
                      {vision.severity}
                    </span>
                  )}
                </div>
                <p className="text-[14px] text-ink leading-relaxed">{vision.description}</p>
                <div className="flex items-center gap-2 flex-wrap mt-2 font-mono text-[10.5px] text-dim uppercase tracking-wide">
                  {vision.recommended_disposition && <span>Disposition · <span className="text-ink">{vision.recommended_disposition.replace(/_/g, ' ')}</span></span>}
                  {vision.confidence != null && <span>· {(vision.confidence * 100).toFixed(0)}% confident</span>}
                  <span>· AI vision (Gemini)</span>
                </div>
              </div>
            )}
            {vision?.error && <p className="text-[13px] text-[#9A6B15]">{vision.error}</p>}
          </div>
        )}
      </Card>
    </div>
  );
}
