/**
 * Authentication context for platform admin users.
 *
 * Completely separate from the tenant AuthContext — uses platform_access_token
 * and hits /api/platform/auth/ endpoints.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { platformGetMe, platformLogin } from "@/services/platform-service";
import type { PlatformUser } from "@/types/platform";

interface PlatformAuthContextType {
  user: PlatformUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isSuperAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const PlatformAuthContext = createContext<PlatformAuthContextType | undefined>(
  undefined
);

export function PlatformAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<PlatformUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isSuperAdmin = useMemo(
    () => user?.role === "super_admin",
    [user?.role]
  );

  useEffect(() => {
    const token = localStorage.getItem("platform_access_token");
    if (token) {
      platformGetMe()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem("platform_access_token");
          localStorage.removeItem("platform_refresh_token");
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await platformGetMe();
    setUser(me);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await platformLogin(email, password);
    localStorage.setItem("platform_access_token", tokens.access_token);
    localStorage.setItem("platform_refresh_token", tokens.refresh_token);
    const me = await platformGetMe();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("platform_access_token");
    localStorage.removeItem("platform_refresh_token");
    setUser(null);
  }, []);

  return (
    <PlatformAuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isSuperAdmin,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </PlatformAuthContext.Provider>
  );
}

export function usePlatformAuth() {
  const context = useContext(PlatformAuthContext);
  if (!context) {
    throw new Error(
      "usePlatformAuth must be used within PlatformAuthProvider"
    );
  }
  return context;
}
