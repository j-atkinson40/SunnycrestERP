import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authService } from "@/services/auth-service";
import type { RegisterRequest, User } from "@/types/auth";
import type { Company } from "@/types/company";

interface AuthContextType {
  user: User | null;
  company: Company | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  permissions: Set<string>;
  hasPermission: (key: string) => boolean;
  enabledModules: Set<string>;
  hasModule: (key: string) => boolean;
  functionalAreas: Set<string>;
  hasFunctionalArea: (key: string) => boolean;
  track: string;
  consoleAccess: Set<string>;
  isAdmin: boolean;
  refreshUser: () => Promise<void>;
  refreshCompany: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  loginPin: (username: string, pin: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const permissions = useMemo(
    () => new Set(user?.permissions ?? []),
    [user?.permissions]
  );

  const hasPermission = useCallback(
    (key: string) => permissions.has(key),
    [permissions]
  );

  const enabledModules = useMemo(
    () => new Set(user?.enabled_modules ?? []),
    [user?.enabled_modules]
  );

  const hasModule = useCallback(
    (key: string) => enabledModules.has(key),
    [enabledModules]
  );

  const functionalAreas = useMemo(
    () => new Set(user?.functional_areas ?? []),
    [user?.functional_areas]
  );

  const hasFunctionalArea = useCallback(
    (key: string) => functionalAreas.has(key),
    [functionalAreas]
  );

  const track = useMemo(
    () => user?.track ?? "office_management",
    [user?.track]
  );

  const consoleAccess = useMemo(
    () => new Set(user?.console_access ?? []),
    [user?.console_access]
  );

  const isAdmin = useMemo(
    () => user?.role_slug === "admin",
    [user?.role_slug]
  );

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      authService
        .getMe()
        .then((data) => {
          setUser(data);
          if (data.company) {
            setCompany(data.company);
          }
        })
        // R-1.6.2: Discriminate by status. Only 401 ("token genuinely
        // invalid") destroys the access + refresh tokens. Every other
        // error (404 from wrong backend, 5xx server error, network
        // failure) leaves the token in place — better to surface an
        // unauthenticated UI state than to silently log the user out
        // on a transient or routing issue. The next request that
        // returns 401 will trigger the destroy path correctly.
        // See /tmp/shell_empty_state_bug.md for the originating
        // investigation: a wrong-backend 404 was sweeping valid
        // staging-realm impersonation tokens before R-1.6.2.
        .catch((err) => {
          const status = err?.response?.status;
          if (status === 401) {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
          }
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await authService.getMe();
    setUser(me);
    if (me.company) {
      setCompany(me.company);
    }
  }, []);

  const refreshCompany = useCallback(async () => {
    const me = await authService.getMe();
    if (me.company) {
      setCompany(me.company);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authService.login({ email, password });
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const me = await authService.getMe();
    setUser(me);
    if (me.company) {
      setCompany(me.company);
    }
  }, []);

  const loginPin = useCallback(async (username: string, pin: string) => {
    const tokens = await authService.loginPin(username, pin);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const me = await authService.getMe();
    setUser(me);
    if (me.company) {
      setCompany(me.company);
    }
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    await authService.register(data);
    const tokens = await authService.login({
      email: data.email,
      password: data.password,
    });
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const me = await authService.getMe();
    setUser(me);
    if (me.company) {
      setCompany(me.company);
    }
  }, []);

  const logout = useCallback(() => {
    // Store last username for shared tablet convenience
    if (user?.track === "production_delivery" && user.username) {
      localStorage.setItem("last_username", user.username);
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    setCompany(null);
  }, [user?.track, user?.username]);

  return (
    <AuthContext.Provider
      value={{
        user,
        company,
        isLoading,
        isAuthenticated: !!user,
        permissions,
        hasPermission,
        enabledModules,
        hasModule,
        functionalAreas,
        hasFunctionalArea,
        track,
        consoleAccess,
        isAdmin,
        refreshUser,
        refreshCompany,
        login,
        loginPin,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
