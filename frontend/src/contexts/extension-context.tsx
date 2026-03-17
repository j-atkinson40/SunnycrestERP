/**
 * ExtensionContext — loaded at bootstrap from the /me endpoint.
 * Provides synchronous isExtensionEnabled() checks for FeatureGate.
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
import { useAuth } from "@/contexts/auth-context";

interface ExtensionContextType {
  /** Set of active extension keys for the current tenant. */
  extensions: Set<string>;
  /** Check if a specific extension is enabled. */
  isExtensionEnabled: (key: string) => boolean;
  /** Refresh from server — call after install/disable. */
  refresh: () => void;
}

const ExtensionContext = createContext<ExtensionContextType | undefined>(
  undefined,
);

export function ExtensionProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [extensionKeys, setExtensionKeys] = useState<Set<string>>(new Set());

  // Sync from user data (loaded via /me endpoint)
  useEffect(() => {
    if (isAuthenticated && user) {
      const keys = user.enabled_extensions;
      if (Array.isArray(keys)) {
        setExtensionKeys(new Set(keys as string[]));
      }
    } else {
      setExtensionKeys(new Set());
    }
  }, [isAuthenticated, user]);

  const isExtensionEnabled = useCallback(
    (key: string) => extensionKeys.has(key),
    [extensionKeys],
  );

  const refresh = useCallback(() => {
    // Re-read from user — triggers on refreshUser()
    if (user) {
      const keys = user.enabled_extensions;
      if (Array.isArray(keys)) {
        setExtensionKeys(new Set(keys as string[]));
      }
    }
  }, [user]);

  const value = useMemo(
    () => ({ extensions: extensionKeys, isExtensionEnabled, refresh }),
    [extensionKeys, isExtensionEnabled, refresh],
  );

  return (
    <ExtensionContext.Provider value={value}>
      {children}
    </ExtensionContext.Provider>
  );
}

export function useExtensions() {
  const context = useContext(ExtensionContext);
  if (!context)
    throw new Error("useExtensions must be used within ExtensionProvider");
  return context;
}

export function useExtensionEnabled(key: string): boolean {
  const { isExtensionEnabled } = useExtensions();
  return isExtensionEnabled(key);
}
