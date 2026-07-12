'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode, useEffect } from 'react';
import { useAuthStore } from '@/lib/auth-store';
import ChatWidget from '@/components/ChatWidget';

// ─── Icons ────────────────────────────────────────────────────────
const icons = {
  rescue: <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />,
  operations: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
  ),
  feed: <path strokeLinecap="round" strokeLinejoin="round" d="M3 12h4l3 8 4-16 3 8h4" />,
  assist: <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />,
  analytics: <path strokeLinecap="round" strokeLinejoin="round" d="M16 8v8m-4-5v5m-4-2v2M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />,
  monitors: <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2h-2" />,
  tower: <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />,
  memory: <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />,
  history: <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />,
  sources: <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />,
  eval: <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />,
};

const Icon = ({ d }: { d: ReactNode }) => (
  <svg className="w-[18px] h-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>{d}</svg>
);

// ─── Grouped navigation ───────────────────────────────────────────
const NAV_GROUPS = [
  {
    section: 'Rescue',
    items: [
      { href: '/rescue', label: 'Line 3 Rescue', sub: 'Guided incident story', icon: icons.rescue },
    ],
  },
  {
    section: 'Operate',
    items: [
      { href: '/dashboard', label: 'Operations', sub: 'Incidents & decisions', icon: icons.operations },
      { href: '/live-feed', label: 'Live Feed', sub: 'Real-time sensor streams', icon: icons.feed },
      { href: '/operator-assist', label: 'Operator Assist', sub: 'Code → action plan', icon: icons.assist },
    ],
  },
  {
    section: 'Intelligence',
    items: [
      { href: '/analytics', label: 'Analytics', sub: 'Trends & performance', icon: icons.analytics },
      { href: '/knowledge', label: 'Control Tower', sub: 'Orders, machines, quality', icon: icons.tower },
      { href: '/factory-memory', label: 'Factory Memory', sub: 'Learned from history', icon: icons.memory },
    ],
  },
  {
    section: 'System',
    items: [
      { href: '/custom-agents', label: 'Monitors', sub: 'Machine watchdogs', icon: icons.monitors },
      { href: '/data-sources', label: 'Data Sources', sub: 'Map & ingest raw data', icon: icons.sources },
      { href: '/evaluation', label: 'Evaluation', sub: 'Ground-truth proof', icon: icons.eval },
      { href: '/audit', label: 'History', sub: 'Every decision, on record', icon: icons.history },
    ],
  },
];

const FLAT_NAV = NAV_GROUPS.flatMap((g) => g.items);

function getPageMeta(pathname: string): { title: string; sub: string } {
  if (pathname.startsWith('/dashboard') && pathname !== '/dashboard') {
    return { title: 'Decision Detail', sub: 'What happened and what to do' };
  }
  const match = FLAT_NAV.find((n) => pathname.startsWith(n.href));
  if (match) return { title: match.label, sub: match.sub };
  return { title: 'PAAIM', sub: 'Manufacturing decision intelligence' };
}

// ─── Layout ───────────────────────────────────────────────────────
export default function MainLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isLoggedIn, user, logout } = useAuthStore();

  const PUBLIC_PATHS = ['/', '/login'];
  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (!isPublic && !isLoggedIn) router.replace('/login');
  }, [isLoggedIn, isPublic, pathname, router]);

  if (pathname === '/' || pathname === '/login') return <>{children}</>;
  if (!isLoggedIn) return null;

  const { title, sub } = getPageMeta(pathname);

  return (
    <div className="flex h-screen overflow-hidden bg-paper">

      {/* ── Sidebar — deep pine ── */}
      <aside className="w-64 shrink-0 relative flex flex-col bg-pine overflow-hidden">
        {/* subtle ambient depth */}
        <div className="pointer-events-none absolute -top-24 -left-10 w-72 h-72 rounded-full bg-[#1B5443]/40 blur-[90px]" />
        <div className="pointer-events-none absolute bottom-10 -right-16 w-64 h-64 rounded-full bg-[#7FA893]/10 blur-[90px]" />

        <div className="relative flex flex-col h-full">
          {/* Logo */}
          <div className="h-16 flex items-center px-5 shrink-0">
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#7FA893] to-[#1B5443] flex items-center justify-center ring-1 ring-white/10">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <div className="text-white font-bold text-base leading-none tracking-tight">PAAIM</div>
                <div className="text-sage-dim text-[10px] leading-none mt-1 tracking-[0.14em] font-mono uppercase">Field&nbsp;Ops</div>
              </div>
            </Link>
          </div>

          {/* Factory badge */}
          <div className="px-4 shrink-0">
            <div className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 bg-white/[0.05] border border-white/[0.08]">
              <span className="relative flex w-2 h-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber" />
              </span>
              <div className="min-w-0">
                <p className="text-white text-xs font-semibold leading-none truncate">Factory 001</p>
                <p className="text-sage-dim text-[10px] mt-1 leading-none font-mono">AUSTIN, TX · LIVE</p>
              </div>
            </div>
          </div>

          {/* Navigation — grouped */}
          <nav className="flex-1 py-4 px-3 overflow-y-auto space-y-5">
            {NAV_GROUPS.map((group) => (
              <div key={group.section}>
                <p className="px-3 mb-2 font-mono text-[10px] font-semibold text-sage-dim uppercase tracking-[0.16em]">
                  {group.section}
                </p>
                <div className="space-y-1">
                  {group.items.map(({ href, label, sub, icon }) => {
                    const active = pathname.startsWith(href);
                    return (
                      <Link
                        key={href}
                        href={href}
                        className={`group relative flex items-center gap-3 pl-3.5 pr-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${
                          active
                            ? 'bg-pine-active text-white ring-1 ring-inset ring-white/10'
                            : 'text-sage hover:bg-pine-2/70'
                        }`}
                      >
                        {active && (
                          <span className="absolute -left-0 top-1/2 -translate-y-1/2 h-6 w-1 rounded-r-full bg-amber" />
                        )}
                        <span className={active ? 'text-amber' : 'text-sage-dim group-hover:text-amber transition-colors'}>
                          <Icon d={icon} />
                        </span>
                        <div className="min-w-0">
                          <div className={`font-semibold leading-none ${active ? 'text-white' : 'text-sage group-hover:text-white'}`}>{label}</div>
                          <div className={`text-[10px] mt-1 leading-none truncate ${active ? 'text-sage' : 'text-sage-dim group-hover:text-sage'}`}>
                            {sub}
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          {/* Bottom status */}
          <div className="px-4 pb-4 pt-3 shrink-0 border-t border-white/[0.08]">
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse shrink-0" />
              <span className="text-xs text-sage font-medium">All systems operational</span>
            </div>
            <div className="text-[10px] text-sage-dim font-mono">PAAIM v1.0 · SMART FACTORY DECISIONS</div>
          </div>
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Top bar */}
        <header className="h-16 shrink-0 flex items-center px-7 gap-4 bg-card border-b border-line">
          <div className="flex-1 min-w-0">
            <h1 className="text-base font-bold text-ink leading-none tracking-tight">{title}</h1>
            <p className="text-xs text-dim mt-1 leading-none">{sub}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className="hidden sm:flex items-center gap-1.5 font-mono text-[11px] font-semibold text-pine-2 bg-surface-ok border border-line px-3 py-1.5 rounded-full uppercase tracking-wide">
              <span className="relative flex w-1.5 h-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber opacity-60" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber" />
              </span>
              System Live
            </div>
            <div className="w-px h-6 bg-line hidden sm:block" />
            <div className="flex items-center gap-2.5">
              <div className="text-right hidden sm:block">
                <p className="text-xs font-semibold text-ink leading-none">{user?.name ?? 'Operator'}</p>
                <p className="text-[10px] text-dim mt-1 leading-none">{user?.role ?? 'Operator'}</p>
              </div>
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-[#7FA893] to-[#1B5443] flex items-center justify-center text-white text-[11px] font-bold">
                {(user?.name ?? 'OP').split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()}
              </div>
              <button
                onClick={() => { logout(); router.replace('/login'); }}
                className="hidden sm:flex items-center justify-center w-8 h-8 rounded-lg text-dim hover:text-ink hover:bg-paper transition-colors"
                title="Sign out"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
        </header>

        {/* Page content — paper canvas */}
        <main className="flex-1 overflow-y-auto p-7 bg-paper">
          {children}
        </main>
      </div>

      {/* Global AI assistant */}
      <ChatWidget />
    </div>
  );
}
