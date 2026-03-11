import {
  createContext,
  useCallback,
  useContext,
  useEffect,
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
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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
        .catch(() => {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
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
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    setCompany(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        company,
        isLoading,
        isAuthenticated: !!user,
        login,
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
