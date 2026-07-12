'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth-store';

export default function Home() {
  const router = useRouter();
  const { isLoggedIn } = useAuthStore();

  useEffect(() => {
    router.replace(isLoggedIn ? '/dashboard' : '/login');
  }, [isLoggedIn, router]);

  return (
    <div className="min-h-screen bg-pine flex flex-col items-center justify-center relative overflow-hidden">
      {/* Grid overlay */}
      <div className="absolute inset-0 opacity-[0.05]"
        style={{ backgroundImage: 'linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)', backgroundSize: '48px 48px' }}
      />
      {/* Ambient glow */}
      <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 w-[600px] h-[420px] rounded-full bg-pine-2/50 blur-[90px]" />

      <div className="relative z-10 flex flex-col items-center">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#7FA893] to-[#1B5443] flex items-center justify-center ring-1 ring-white/10">
          <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <span className="text-white font-bold text-xl tracking-tight mt-4">PAAIM</span>
        <p className="font-mono text-[10.5px] font-semibold text-sage-dim uppercase tracking-[0.16em] mt-1.5">Field Ops</p>

        <div className="flex items-center gap-2 mt-8">
          <span className="w-4 h-4 border-2 border-moss/30 border-t-amber rounded-full animate-spin" />
          <span className="font-mono text-[11px] text-sage-dim uppercase tracking-[0.12em]">Loading workspace</span>
        </div>
      </div>
    </div>
  );
}
