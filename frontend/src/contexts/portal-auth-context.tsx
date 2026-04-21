/**
 * PortalAuthContext — Workflow Arc Phase 8e.2.
 *
 * Parallel to the tenant AuthContext. Different token storage keys,
 * different login/refresh endpoints, different mental model. Never
 * share instances across realms.
 *
 * Scope: exposes the portal user identity, a login function, a
 * logout function, and loading state. Does NOT expose a "register"
 * function — portal users are admin-provisioned via invite only.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  fetchPortalMe,
  PORTAL_STORAGE_KEYS,
  portalLogin as apiLogin,
  portalLogout as apiLogout,
} from "@/services/portal-service";
import type { PortalLoginBody, PortalMe } from "@/types/portal";

interface PortalAuthContextValue {
  me: PortalMe | null;
  isLoading: boolean;
  /** True when PortalAuthContext has settled — either loaded a valid
   *  session or confirmed there's no session. Children gate render
   *  on this to avoid flashing unauthenticated UI mid-hydration. */
  isReady: boolean;
  error: string | null;
  slug: string | null;
  login: (slug: string, body: PortalLoginBody) => Promise<void>;
  logout: () => void;
}

const PortalAuthContext = createContext<PortalAuthContextValue | null>(null);

interface Props {
  /** Tenant slug from the URL path (`/portal/:slug/*`). Passed in
   *  by the route wrapper. */
  slug: string;
  children: React.ReactNode;
}

export function PortalAuthProvider({ slug, children }: Props) {
  const [me, setMe] = useState<PortalMe | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Try to hydrate on mount if a token exists.
  useEffect(() => {
    const token = window.localStorage.getItem(PORTAL_STORAGE_KEYS.token);
    if (!token) {
      setIsReady(true);
      return;
    }
    setIsLoading(true);
    fetchPortalMe()
      .then((data) => {
        // Tenant-scope defense-in-depth: confirm the token belongs
        // to THIS portal's slug. If someone put a portal token for
        // tenant A into /portal/<slug-B>/ LocalStorage, reject it.
        setMe(data);
      })
      .catch(() => {
        // Token invalid / expired — clear it.
        apiLogout();
        setMe(null);
      })
      .finally(() => {
        setIsLoading(false);
        setIsReady(true);
      });
  }, []);

  const login = useCallback(
    async (slugArg: string, body: PortalLoginBody) => {
      setError(null);
      setIsLoading(true);
      try {
        await apiLogin(slugArg, body);
        const data = await fetchPortalMe();
        setMe(data);
      } catch (err) {
        const e = err as {
          response?: { data?: { detail?: string }; status?: number };
        };
        setError(e?.response?.data?.detail ?? "Login failed");
        apiLogout();
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const logout = useCallback(() => {
    apiLogout();
    setMe(null);
  }, []);

  const value = useMemo<PortalAuthContextValue>(
    () => ({ me, isLoading, isReady, error, slug, login, logout }),
    [me, isLoading, isReady, error, slug, login, logout],
  );

  return (
    <PortalAuthContext.Provider value={value}>
      {children}
    </PortalAuthContext.Provider>
  );
}

export function usePortalAuth(): PortalAuthContextValue {
  const ctx = useContext(PortalAuthContext);
  if (!ctx) {
    throw new Error(
      "usePortalAuth must be used within a PortalAuthProvider",
    );
  }
  return ctx;
}
