import { createContext, useContext, useEffect, useMemo } from "react";
import { useAuth } from "@/contexts/auth-context";
import { parseTenantSettings } from "@/types/company";
import {
  getNavigation,
  type NavigationConfig,
} from "@/services/navigation-service";

interface PresetThemeContextValue {
  navigation: NavigationConfig;
  presetAccent: string;
  presetLabel: string;
  tenantSettings: Record<string, unknown>;
}

const PresetThemeContext = createContext<PresetThemeContextValue | null>(null);

export function PresetThemeProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { company, enabledModules, permissions, functionalAreas, isAdmin } = useAuth();

  const tenantSettings = useMemo(
    () => parseTenantSettings(company),
    [company?.settings_json],
  );

  const navigation = useMemo(() => {
    return getNavigation(
      company?.vertical ?? null,
      enabledModules ?? new Set(),
      permissions ?? new Set(),
      tenantSettings,
      functionalAreas,
      isAdmin,
    );
  }, [company?.vertical, enabledModules, permissions, tenantSettings, functionalAreas, isAdmin]);

  // Set CSS custom property on root
  useEffect(() => {
    document.documentElement.style.setProperty(
      "--preset-accent",
      navigation.presetAccent,
    );
    document.documentElement.style.setProperty(
      "--preset-accent-light",
      navigation.presetAccent + "20",
    ); // with alpha
  }, [navigation.presetAccent]);

  return (
    <PresetThemeContext.Provider
      value={{
        navigation,
        presetAccent: navigation.presetAccent,
        presetLabel: navigation.presetLabel,
        tenantSettings,
      }}
    >
      {children}
    </PresetThemeContext.Provider>
  );
}

export function usePresetTheme() {
  const ctx = useContext(PresetThemeContext);
  if (!ctx)
    throw new Error("usePresetTheme must be used within PresetThemeProvider");
  return ctx;
}
