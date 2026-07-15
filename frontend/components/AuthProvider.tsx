'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth-store';

/**
 * Attaches the bearer token to every PAAIM API call, and gates the app.
 *
 * The interceptor exists because ~40 raw `fetch()` calls are spread across the
 * pages, and a token that only some of them send is worse than none: the pages
 * that forgot would 401 at random and look like backend outages. Patching fetch
 * once means a request cannot be made without its tenant — the same reasoning
 * behind an axios interceptor, and the same reason the backend now derives the
 * factory from the token instead of a query parameter.
 *
 * Only PAAIM's own API is touched. Anything else the page fetches is left alone;
 * sending a customer's token to a third-party host would be a real leak.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// Reachable without signing in.
const PUBLIC_PATHS = ['/', '/login'];

let installed = false;

function installInterceptor() {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  const original = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    const isPaaim = url.startsWith(API_BASE) || url.startsWith('/api/');
    const token = useAuthStore.getState().token;

    if (isPaaim && token) {
      const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
      if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
      init = { ...init, headers };
    }

    const res = await original(input as any, init);

    // An expired token must end the session rather than leave every screen
    // silently empty — "no incidents" and "you are signed out" look identical.
    if (isPaaim && res.status === 401 && useAuthStore.getState().isLoggedIn) {
      useAuthStore.getState().logout();
      if (!PUBLIC_PATHS.includes(window.location.pathname)) window.location.href = '/login';
    }
    return res;
  };
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isLoggedIn, hydrate } = useAuthStore();
  const [checked, setChecked] = useState(false);

  installInterceptor();

  useEffect(() => {
    let alive = true;
    (async () => {
      await hydrate();          // a persisted token is a claim, not proof — verify it
      if (alive) setChecked(true);
    })();
    return () => { alive = false; };
  }, [hydrate]);

  useEffect(() => {
    if (!checked) return;
    if (!isLoggedIn && !PUBLIC_PATHS.includes(pathname)) router.replace('/login');
  }, [checked, isLoggedIn, pathname, router]);

  // Don't render a protected page before the token has been checked: a flash of
  // one tenant's shell while another's data loads is exactly the confusion this
  // whole change exists to remove.
  if (!checked && !PUBLIC_PATHS.includes(pathname)) return null;
  return <>{children}</>;
}
