'use client';

import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  useAnalyticsSummary,
  useAnalyticsTimeline,
  useAnalyticsDistribution,
  useAnalyticsActions,
  useAnalyticsAgents,
  useAnalyticsLatency,
  useSystemHealth,
} from '@/lib/api-client';
import { Eyebrow, Card, KpiTile, SignalPill } from '@/components/ui';

// ─── Chart palette — pine / amber / coral / moss only ───────────────
const PINE = '#1B5443';
const AMBER = '#E8A13D';
const CORAL = '#D8492B';
const MOSS = '#7FA893';
const GRID = '#DDE4DF';
const TICK = '#5E6B64';

// safety = danger (coral), quality = attention (amber), rest = neutral greens
const EVENT_COLORS: Record<string, string> = {
  safety: CORAL,
  quality: AMBER,
  maintenance: PINE,
  production: MOSS,
  energy: '#123A2E',
};

// decision outcomes: auto (pine), human (moss), rejected (coral)
const OUTCOME_COLORS = [PINE, MOSS, CORAL];

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

const axisTick = { fontSize: 11, fontFamily: 'var(--mono, monospace)', fill: TICK };

// ─── Helpers ─────────────────────────────────────────────────────
function fmt(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

// ─── Demo agent data ─────────────────────────────────────────────
const DEMO_AGENTS = [
  { agent: 'Safety Agent',      recommendations: 38, accuracy_score: 0.94, auto_approved_rate: 0.63 },
  { agent: 'Quality Agent',     recommendations: 45, accuracy_score: 0.91, auto_approved_rate: 0.71 },
  { agent: 'Maintenance Agent', recommendations: 52, accuracy_score: 0.88, auto_approved_rate: 0.79 },
  { agent: 'Production Agent',  recommendations: 29, accuracy_score: 0.86, auto_approved_rate: 0.69 },
  { agent: 'Energy Agent',      recommendations: 21, accuracy_score: 0.90, auto_approved_rate: 0.86 },
];

// ─── Panel (eyebrow + card) ─────────────────────────────────────
function Panel({
  title,
  sub,
  isDemo,
  right,
  children,
}: {
  title: string;
  sub?: string;
  isDemo?: boolean;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div>
            <Eyebrow>{title}</Eyebrow>
            {sub && <p className="text-[12px] text-dim mt-0.5">{sub}</p>}
          </div>
          {isDemo && <SignalPill tone="warn">Demo data</SignalPill>}
        </div>
        {right}
      </div>
      <div className="p-5">{children}</div>
    </Card>
  );
}

const thCls = 'pb-2.5 font-mono text-[10px] font-semibold text-dim uppercase tracking-wide';

// ─── Chart tooltip (palette-tinted) ─────────────────────────────
const tooltipStyle = {
  background: '#FFFFFF',
  border: `1px solid ${GRID}`,
  borderRadius: 8,
  fontSize: 12,
  fontFamily: 'var(--mono, monospace)',
  color: '#17211C',
};

// ─── Page ────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const summary = useAnalyticsSummary();
  const timeline = useAnalyticsTimeline('factory_001', 14);
  const distribution = useAnalyticsDistribution();
  const actions = useAnalyticsActions();
  const agents = useAnalyticsAgents();
  const latency = useAnalyticsLatency();
  const health = useSystemHealth();

  const s = summary.data;
  const isLoading = summary.isLoading;

  const decisionPie = s
    ? [
        { name: 'Auto-approved', value: s.auto_approved },
        { name: 'Human-approved', value: s.human_approved },
        { name: 'Rejected', value: s.rejected },
      ]
    : [];

  const approvalTone: Tone = s ? (s.approval_rate >= 85 ? 'ok' : 'warn') : 'neutral';
  const latencyTone: Tone = s ? (s.avg_latency_ms < 2000 ? 'ok' : 'bad') : 'neutral';

  return (
    <div className="max-w-[1180px] space-y-6">
      {/* Header — the one question this screen answers */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow>Factory performance · last {s?.days ?? 30} days · Factory 001</Eyebrow>
          <h1 className="text-[22px] font-bold text-ink tracking-[-0.02em] mt-1">
            How is the factory performing?
          </h1>
          <p className="text-[13px] text-dim mt-0.5">
            Throughput, decision quality, and pipeline health across the orchestration stack.
          </p>
        </div>
        {s?.is_demo === false ? (
          <SignalPill tone="ok">Live data</SignalPill>
        ) : s?.is_demo ? (
          <SignalPill tone="warn">Demo data</SignalPill>
        ) : null}
      </div>

      {/* Headline KPIs */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-paper rounded-card h-24 animate-pulse" />
          ))}
        </div>
      ) : s ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KpiTile
            label="Events processed"
            value={s.total_events.toLocaleString()}
            meaning={`Last ${s.days} days`}
          />
          <KpiTile
            label="Decisions made"
            value={s.total_decisions.toLocaleString()}
            meaning={`${s.approval_rate}% approved`}
          />
          <KpiTile
            label="Approval rate"
            value={`${s.approval_rate}%`}
            tone={approvalTone}
            meaning={s.approval_rate >= 85 ? 'Above 85% target' : 'Below 85% target'}
          />
          <KpiTile
            label="Response time"
            value={s.avg_latency_ms}
            unit="ms"
            tone={latencyTone}
            meaning={s.avg_latency_ms < 2000 ? 'Within budget' : 'Over 2s budget'}
          />
          <KpiTile
            label="Cost savings"
            value={fmt(s.estimated_cost_savings_usd)}
            tone="ok"
            meaning="Estimated value"
          />
        </div>
      ) : null}

      {/* Timeline + Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Panel
            title="Event activity"
            sub="Daily events by type — last 14 days"
            isDemo={timeline.data?.is_demo}
          >
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={timeline.data?.timeline ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="date" tick={axisTick} tickFormatter={(v) => v.slice(5)} stroke={GRID} />
                <YAxis tick={axisTick} stroke={GRID} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'var(--mono, monospace)', color: TICK }} />
                {(['safety', 'quality', 'maintenance', 'production', 'energy'] as const).map((k) => (
                  <Area
                    key={k}
                    type="monotone"
                    dataKey={k}
                    stackId="1"
                    stroke={EVENT_COLORS[k]}
                    fill={EVENT_COLORS[k]}
                    fillOpacity={0.55}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        <Panel title="Event types" sub="Share by category" isDemo={distribution.data?.is_demo}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={distribution.data?.distribution ?? []} layout="vertical" margin={{ left: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={axisTick} stroke={GRID} />
              <YAxis dataKey="event_type" type="category" tick={axisTick} stroke={GRID} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v, 'Count']} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {(distribution.data?.distribution ?? []).map((entry) => (
                  <Cell key={entry.event_type} fill={EVENT_COLORS[entry.event_type] ?? MOSS} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* Decision outcomes + Monitor performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Decision outcomes" sub="How recommendations were resolved" isDemo={s?.is_demo}>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={180} height={180}>
              <PieChart>
                <Pie data={decisionPie} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                  {decisionPie.map((_, i) => (
                    <Cell key={i} fill={OUTCOME_COLORS[i]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-3 flex-1">
              {decisionPie.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: OUTCOME_COLORS[i] }} />
                    <span className="text-[13px] text-ink">{d.name}</span>
                  </div>
                  <span className="font-mono text-[14px] font-semibold text-pine">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel title="Monitor performance" sub="Recommendation quality by agent" isDemo>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left border-b border-line">
                  <th className={thCls}>Agent</th>
                  <th className={`${thCls} text-right`}>Recs</th>
                  <th className={`${thCls} text-right`}>Accuracy</th>
                  <th className={`${thCls} text-right`}>Auto %</th>
                </tr>
              </thead>
              <tbody>
                {(agents.data?.agents?.length ? agents.data.agents : DEMO_AGENTS).map((a) => {
                  const accTone =
                    a.accuracy_score >= 0.9 ? 'text-pine-2' : a.accuracy_score >= 0.8 ? 'text-[#9A6B15]' : 'text-coral';
                  return (
                    <tr key={a.agent} className="border-b border-line last:border-0 hover:bg-surface-ok">
                      <td className="py-2.5 font-semibold text-ink">{a.agent}</td>
                      <td className="py-2.5 text-right font-mono text-dim">{a.recommendations}</td>
                      <td className="py-2.5 text-right">
                        <span className={`font-mono font-semibold ${accTone}`}>
                          {(a.accuracy_score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 bg-paper rounded-full h-1.5 overflow-hidden">
                            <div className="h-full bg-pine-2 rounded-full" style={{ width: `${a.auto_approved_rate * 100}%` }} />
                          </div>
                          <span className="font-mono text-dim text-[11px] w-8 text-right">
                            {(a.auto_approved_rate * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      {/* Top actions + Pipeline latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Top recommended actions" sub="Most frequent recommendations" isDemo={actions.data?.is_demo}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={actions.data?.actions.slice(0, 7) ?? []} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={axisTick} stroke={GRID} />
              <YAxis dataKey="action" type="category" tick={axisTick} stroke={GRID} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill={PINE} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Pipeline latency" sub="Average time per orchestration step (ms)" isDemo={latency.data?.is_demo}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={latency.data?.latency ?? []}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="layer" tick={axisTick} angle={-15} textAnchor="end" interval={0} height={50} stroke={GRID} />
              <YAxis tick={axisTick} unit="ms" stroke={GRID} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v}ms`, 'Avg latency']} />
              <Bar dataKey="avg_ms" fill={AMBER} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* System health */}
      <Panel title="System health" sub="Orchestration layer uptime">
        {health.isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-20 bg-paper rounded-lg animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {(health.data?.layers ?? []).map(
              (layer: { name: string; status: string; uptime: number }) => {
                const ok = layer.status === 'healthy' || layer.status === 'ok' || layer.uptime >= 99;
                const tone: Tone = ok ? 'ok' : layer.uptime >= 95 ? 'warn' : 'bad';
                const surface = tone === 'ok' ? 'bg-surface-ok border-line' : tone === 'warn' ? 'bg-surface-warn border-amber/30' : 'bg-surface-bad border-coral/30';
                const dot = tone === 'ok' ? 'bg-pine-2' : tone === 'warn' ? 'bg-amber' : 'bg-coral';
                const upText = tone === 'ok' ? 'text-pine-2' : tone === 'warn' ? 'text-[#9A6B15]' : 'text-coral';
                return (
                  <div key={layer.name} className={`border rounded-lg p-3 text-center ${surface}`}>
                    <div className={`w-2 h-2 rounded-full mx-auto mb-2 ${dot}`} />
                    <p className="text-[11px] font-medium text-ink leading-tight">{layer.name}</p>
                    <p className={`font-mono text-[11px] mt-1 ${upText}`}>{layer.uptime}%</p>
                  </div>
                );
              }
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
