'use client';

import { useEffect, useRef, useState } from 'react';
import { plainMachine, plainSignal } from '@/lib/labels';
import { Eyebrow, SectionHeader, Card, KpiTile, SignalPill, AlertBar } from '@/components/ui';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type SignalBaseline = {
  mean: number; std: number; min: number; max: number; p95: number;
  samples: number; normal_range: [number, number];
};
type MachineProfile = {
  records: number; failure_count: number; mtbf_hours: number | null;
  signals: Record<string, SignalBaseline>;
  recurring_issues: { issue: string; count: number }[];
};
type Profile = {
  computed_at: string; records_analyzed: number; machines_learned: number;
  total_failures: number; machines: Record<string, MachineProfile>;
};

export default function FactoryMemoryPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [meta, setMeta] = useState<{ records: number; filename: string; computed: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // The factory is derived from the signed-in token, so these endpoints take no
  // factory in the path any more. This page used to hardcode `factory_001` and
  // call `/history/profile/{factory}` — a tenant that no longer exists, on a
  // route that now 404s.
  const load = async () => {
    try {
      const r = await fetch(`${API_BASE}/knowledge/history/profile`);
      const d = await r.json();
      if (d.learned) {
        setProfile(d.profile);
        setMeta({ records: d.records_analyzed, filename: d.source_filename, computed: d.computed_at });
      }
    } catch {}
  };
  useEffect(() => { load(); }, []);

  const upload = async (file: File) => {
    setUploading(true); setError(null);
    try {
      // The history CSV holds the plant's raw tags in the plant's own units, so
      // the learner must translate it through a connected source's mapping. Pick
      // the tenant's first confirmed source automatically — the operator should
      // not have to know a source_id to upload their own history.
      const mr = await fetch(`${API_BASE}/normalization/mappings`);
      const mj = await mr.json();
      const src = (mj.mappings || []).find((m: any) => m.confirmed) || (mj.mappings || [])[0];
      if (!src) throw new Error('Connect a data source first — history is learned through its mapping.');

      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch(
        `${API_BASE}/knowledge/history/upload?source_id=${encodeURIComponent(src.source_id)}`,
        { method: 'POST', body: fd },
      );
      if (!r.ok) throw new Error((await r.json()).detail || 'Upload failed');
      await load();
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    }
    setUploading(false);
  };

  const machines = profile ? Object.entries(profile.machines) : [];

  return (
    <div className="max-w-[1180px] space-y-6">
      {/* Header — one question */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <Eyebrow>Learned from history</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">
            What has the factory learned from its history?
          </h1>
          <p className="text-[13px] text-dim mt-0.5 max-w-2xl">
            Upload past readings and events. The system learns each machine&apos;s normal range,
            failure rate and recurring problems — so monitors judge new readings against real history,
            not a generic threshold.
          </p>
        </div>
        <input
          ref={fileRef} type="file" accept=".csv" className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }}
        />
      </div>

      {/* Upload action */}
      <Card className="p-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <Eyebrow>Teach the factory</Eyebrow>
            <p className="text-[14px] font-semibold text-ink mt-1">Upload historical machine data (CSV)</p>
            <p className="font-mono text-[11px] text-dim mt-1">
              machine_id · signal_name · signal_value · event_type · is_failure · timestamp
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {uploading && <SignalPill tone="warn">Learning…</SignalPill>}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 rounded-lg text-[13px] font-semibold bg-pine-2 hover:bg-pine disabled:opacity-50 text-white transition-colors"
            >
              {uploading ? 'Learning…' : profile ? 'Upload more history' : 'Upload history'}
            </button>
          </div>
        </div>
      </Card>

      {error && <AlertBar tone="bad" title="Upload failed">{error}</AlertBar>}

      {/* Empty state */}
      {!profile && !uploading && (
        <Card className="p-12 text-center">
          <div className="w-12 h-12 bg-surface-ok rounded-xl flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-pine-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <p className="text-[15px] font-bold text-ink mb-1">Nothing learned yet</p>
          <p className="text-[13px] text-dim mb-4 max-w-md mx-auto leading-snug">
            Upload a CSV of past readings and events. The system will learn each machine&apos;s normal range,
            failure rate and recurring problems.
          </p>
          <button
            onClick={() => fileRef.current?.click()}
            className="bg-pine-2 hover:bg-pine text-white font-semibold py-2 px-5 rounded-lg text-[13px] transition-colors"
          >
            Upload history
          </button>
        </Card>
      )}

      {/* Learned profile — summary */}
      {profile && meta && (
        <div>
          <SectionHeader
            eyebrow="What was learned"
            title="Learned profile"
            sub="The scope of history the factory has absorbed."
          />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <KpiTile label="Records learned" value={meta.records.toLocaleString()} meaning="Historical readings analyzed" />
            <KpiTile label="Machines profiled" value={profile.machines_learned} tone="ok" meaning="Have their own baselines" />
            <KpiTile label="Failures seen" value={profile.total_failures} tone={profile.total_failures > 0 ? 'warn' : 'neutral'} meaning="Across all history" />
            <Card className="p-4">
              <Eyebrow dim>Source</Eyebrow>
              <div className="font-mono text-[13px] font-semibold text-ink mt-2 truncate">{meta.filename}</div>
              <p className="text-[12px] text-dim mt-1.5">Learned {new Date(meta.computed).toLocaleDateString()}</p>
            </Card>
          </div>
        </div>
      )}

      {/* Learned machine profiles */}
      {machines.length > 0 && (
        <div>
          <SectionHeader
            eyebrow="Per machine"
            title="Baselines, reliability & recurring issues"
            sub="What normal looks like for each machine, and where it tends to fail."
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {machines.map(([mid, m]) => (
              <Card key={mid} className="overflow-hidden">
                {/* Machine header */}
                <div className="px-5 py-3.5 border-b border-line flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-[14px] font-bold text-ink truncate">{plainMachine(mid)}</h3>
                    <p className="font-mono text-[11px] text-dim">{mid}</p>
                  </div>
                  <div className="flex gap-4 text-right shrink-0">
                    <div>
                      <p className="font-mono text-[10px] text-dim uppercase tracking-wide">Records</p>
                      <p className="font-mono text-[14px] font-semibold text-ink">{m.records.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="font-mono text-[10px] text-dim uppercase tracking-wide">Failures</p>
                      <p className={`font-mono text-[14px] font-semibold ${m.failure_count > 0 ? 'text-[#9A6B15]' : 'text-ink'}`}>{m.failure_count}</p>
                    </div>
                    <div>
                      <p className="font-mono text-[10px] text-dim uppercase tracking-wide">MTBF</p>
                      <p className="font-mono text-[14px] font-semibold text-ink">{m.mtbf_hours ? `${m.mtbf_hours}h` : '—'}</p>
                    </div>
                  </div>
                </div>

                <div className="p-5 space-y-4">
                  {/* Learned baselines */}
                  <div>
                    <Eyebrow dim>Learned normal ranges</Eyebrow>
                    <div className="space-y-2.5 mt-2.5">
                      {Object.entries(m.signals).map(([sig, s]) => (
                        <div key={sig} className="flex items-center gap-3">
                          <span className="text-[12px] font-medium text-ink w-28 shrink-0 truncate">{plainSignal(sig)}</span>
                          <div className="flex-1 bg-paper rounded-full h-2 relative overflow-hidden">
                            <div className="absolute inset-y-0 bg-moss/50" style={{ left: '15%', right: '15%' }} />
                            <div className="absolute inset-y-0 w-0.5 bg-pine-2" style={{ left: '50%' }} />
                          </div>
                          <span className="font-mono text-[11px] text-dim w-28 text-right shrink-0">
                            {s.normal_range[0]}–{s.normal_range[1]}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Recurring issues */}
                  {m.recurring_issues.length > 0 && (
                    <div>
                      <Eyebrow dim>Recurring problems</Eyebrow>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {m.recurring_issues.map((r) => (
                          <span
                            key={r.issue}
                            className="font-mono text-[11px] font-semibold text-[#9A6B15] bg-surface-warn border border-amber px-2 py-0.5 rounded-full"
                          >
                            {plainSignal(r.issue)} ×{r.count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {profile && (
        <p className="text-[12px] text-dim">
          This learned profile lets monitors judge a new reading against each machine&apos;s own history — not a generic threshold.
        </p>
      )}
    </div>
  );
}
