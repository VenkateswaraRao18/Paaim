'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * Real authentication against the backend.
 *
 * This store used to hold a `DEMO_USERS` array and check the password in the
 * browser: `login()` was a synchronous array lookup that set isLoggedIn and
 * produced no token at all. Every API call then went out unauthenticated —
 * which worked, because no route checked. The login screen was a routing
 * decision, not a security boundary.
 *
 * Now the backend issues a JWT carrying the tenant, and that token is what every
 * request is scoped by. The browser cannot choose its own factory.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export type AuthUser = {
  id: string; email: string; full_name: string; role: string; factory_id: string | null;
};
export type AuthFactory = {
  id: string; name: string; location?: string | null;
  industry?: string | null; vocabulary_pack?: string | null;
};

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  factory: AuthFactory | null;
  isLoggedIn: boolean;
  login: (email: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  logout: () => void;
  hydrate: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      factory: null,
      isLoggedIn: false,

      login: async (email, password) => {
        try {
          const r = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
          });
          const d = await r.json().catch(() => ({}));
          if (!r.ok) return { ok: false, error: d.detail ?? 'Sign-in failed.' };

          set({ token: d.access_token, refreshToken: d.refresh_token, isLoggedIn: true });
          // Who am I, and which plant am I? The token carries the tenant; this is
          // what the UI renders, so an operator can always see which factory they
          // are looking at.
          const me = await fetch(`${API_BASE}/auth/me`, {
            headers: { Authorization: `Bearer ${d.access_token}` },
          });
          if (me.ok) {
            const j = await me.json();
            set({ user: j.user, factory: j.factory });
          }
          return { ok: true };
        } catch {
          return { ok: false, error: 'Cannot reach PAAIM. Is the backend running on :8000?' };
        }
      },

      logout: () => set({ token: null, refreshToken: null, user: null, factory: null, isLoggedIn: false }),

      /** Is the persisted token still good? Called on load, before trusting it. */
      hydrate: async () => {
        const t = get().token;
        if (!t) return false;
        try {
          const r = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${t}` } });
          if (!r.ok) { get().logout(); return false; }
          const j = await r.json();
          set({ user: j.user, factory: j.factory, isLoggedIn: true });
          return true;
        } catch {
          // The backend being down is not the same as being signed out — keep the
          // session and let each page report its own connection error.
          return get().isLoggedIn;
        }
      },
    }),
    { name: 'paaim-auth' },
  ),
);

/** The bearer token, for callers that build their own requests. */
export const authHeader = (): Record<string, string> => {
  const t = useAuthStore.getState().token;
  return t ? { Authorization: `Bearer ${t}` } : {};
};
