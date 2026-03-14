import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/contexts/auth-context";
import { featureFlagService } from "@/services/feature-flag-service";

interface FeatureFlagContextType {
  flags: Record<string, boolean>;
  isLoaded: boolean;
  isEnabled: (flagKey: string) => boolean;
  refresh: () => Promise<void>;
}

const FeatureFlagContext = createContext<FeatureFlagContextType | undefined>(
  undefined,
);

export function FeatureFlagProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [isLoaded, setIsLoaded] = useState(false);

  const loadFlags = useCallback(async () => {
    try {
      const data = await featureFlagService.getMyFlags();
      setFlags(data.flags);
    } catch {
      // If the endpoint fails, keep existing flags
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      loadFlags();
    } else {
      setFlags({});
      setIsLoaded(false);
    }
  }, [isAuthenticated, loadFlags]);

  const isEnabled = useCallback(
    (flagKey: string) => flags[flagKey] ?? false,
    [flags],
  );

  const value = useMemo(
    () => ({ flags, isLoaded, isEnabled, refresh: loadFlags }),
    [flags, isLoaded, isEnabled, loadFlags],
  );

  return (
    <FeatureFlagContext.Provider value={value}>
      {children}
    </FeatureFlagContext.Provider>
  );
}

export function useFeatureFlags() {
  const context = useContext(FeatureFlagContext);
  if (!context)
    throw new Error(
      "useFeatureFlags must be used within FeatureFlagProvider",
    );
  return context;
}

export function useFeatureFlag(flagKey: string): boolean {
  const { isEnabled } = useFeatureFlags();
  return isEnabled(flagKey);
}

/**
 * Renders children only if the specified feature flag is enabled.
 * Optional fallback rendered when disabled.
 */
export function FeatureGate({
  flag,
  children,
  fallback = null,
}: {
  flag: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const enabled = useFeatureFlag(flag);
  return <>{enabled ? children : fallback}</>;
}

/**
 * Renders children only if the user is admin AND the flag is enabled.
 */
export function AdminFeatureGate({
  flag,
  children,
  fallback = null,
}: {
  flag: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const enabled = useFeatureFlag(flag);
  const { isAdmin } = useAuth();
  return <>{isAdmin && enabled ? children : fallback}</>;
}
