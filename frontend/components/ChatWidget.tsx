'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Msg = { role: 'user' | 'assistant'; content: string };

const STARTERS = [
  'Which orders are at risk?',
  'What does 0x4F3 mean?',
  'How many decisions need approval?',
  'What’s the vibration baseline for cnc_mill_01?',
];

// Shown when the user is looking at a specific decision (co-pilot mode)
const DECISION_STARTERS = [
  'Why this action?',
  'Why not an alternative?',
  'Has this happened before?',
  'Explain this simply',
];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Co-pilot context: if we're on a decision page, focus the bot on that decision
  const pathname = usePathname();
  const decisionMatch = pathname?.match(/^\/dashboard\/(.+)$/);
  const decisionId = decisionMatch ? decisionMatch[1] : null;
  const starters = decisionId ? DECISION_STARTERS : STARTERS;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || loading) return;
    const next = [...messages, { role: 'user' as const, content: q }];
    setMessages(next);
    setInput('');
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: next, decision_id: decisionId }),
      });
      const d = await r.json();
      setMessages((m) => [...m, { role: 'assistant', content: d.reply || '…' }]);
    } catch {
      setMessages((m) => [...m, { role: 'assistant', content: 'Sorry — I could not reach the assistant.' }]);
    }
    setLoading(false);
  };

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-50 h-14 w-14 rounded-2xl bg-gradient-to-br from-[#7FA893] to-[#1B5443] shadow-xl shadow-pine/20 flex items-center justify-center text-white hover:scale-105 active:scale-95 transition-transform"
        aria-label="Ask PAAIM"
      >
        {open ? (
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[380px] max-w-[calc(100vw-3rem)] h-[560px] max-h-[calc(100vh-8rem)] flex flex-col rounded-2xl bg-card border border-line shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 bg-pine-2 text-white flex items-center gap-3 shrink-0">
            <div className="w-8 h-8 rounded-xl bg-white/15 flex items-center justify-center">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold leading-none">Ask PAAIM</p>
              <p className="text-[11px] text-white/70 mt-1 leading-none">{decisionId ? 'Co-pilot for this decision' : 'Grounded in your live factory data'}</p>
            </div>
            <span className="flex items-center gap-1.5 text-[10px] font-semibold bg-white/15 px-2 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" /> Live
            </span>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-paper">
            {messages.length === 0 && (
              <div className="text-center pt-6">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#7FA893] to-[#1B5443] mx-auto flex items-center justify-center mb-3">
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-ink">{decisionId ? 'Ask me about this decision.' : 'Hi! Ask me about the factory.'}</p>
                <p className="text-xs text-dim mt-1 mb-4">{decisionId ? 'Why this action, alternatives, or past fixes.' : 'I know your machines, orders, codes & history.'}</p>
                <div className="space-y-1.5">
                  {starters.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="block w-full text-left text-xs text-dim bg-card border border-line rounded-lg px-3 py-2 hover:border-moss hover:text-pine-2 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] text-sm rounded-2xl px-3.5 py-2 leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-pine-2 text-white rounded-br-sm'
                    : 'bg-card border border-line text-ink rounded-bl-sm'
                }`}>
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-card border border-line rounded-2xl rounded-bl-sm px-3.5 py-2.5">
                  <span className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-moss animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-moss animate-bounce" style={{ animationDelay: '120ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-moss animate-bounce" style={{ animationDelay: '240ms' }} />
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-line bg-card shrink-0">
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send(input)}
                placeholder="Ask about machines, orders, codes…"
                className="flex-1 text-sm border border-line rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-pine-2/20 focus:border-moss"
              />
              <button
                onClick={() => send(input)}
                disabled={loading || !input.trim()}
                className="h-10 w-10 shrink-0 rounded-xl bg-pine-2 text-white flex items-center justify-center disabled:opacity-40 hover:bg-pine transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
