import { createContext, useContext, useEffect, useMemo } from "react";
import { useAuth } from "@/contexts/auth-context";
import { useExtensions } from "@/contexts/extension-context";
import { parseTenantSettings } from "@/types/company";
import {
  getNavigation,
  type NavigationConfig,
} from "@/services/navigation-service";
// R-2.5 — production tenant boot reads + applies committed theme
// overrides. Mirrors RuntimeEditorShell's R-1.6.14 resolve+apply
// chain but consumed by every authenticated tenant route, not just
// the editor preview. Closes the gap R-1.6.14 flagged: pre-R-2.5,
// runtime-editor commits never reached end users on /home, /dashboard,
// or any tenant route — they applied only inside the editor shell.
import { tenantThemesService } from "@/services/tenant-themes-service";
import { useThemeMode } from "@/lib/theme-mode";
import {
  applyThemeToElement,
  composeEffective,
  stackFromResolved,
} from "@/lib/visual-editor/themes/theme-resolver";

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
  const { extensions: enabledExtensions } = useExtensions();

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
      enabledExtensions,
    );
  }, [company?.vertical, enabledModules, permissions, tenantSettings, functionalAreas, isAdmin, enabledExtensions]);

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

  // R-2.5 — resolve + apply committed theme overrides on tenant boot.
  //
  // Mirrors RuntimeEditorShell's R-1.6.14 effect verbatim, just consumed
  // by every authenticated tenant route instead of only the editor
  // shell. Reuses the same `themes-resolver` helpers
  // (`stackFromResolved`, `composeEffective`, `applyThemeToElement`)
  // the editor uses, so DB-stored overrides apply identically inside
  // and outside the editor.
  //
  // Triggers:
  //   - on mount (after auth resolves company.id + company.vertical)
  //   - on theme mode change (light↔dark — mode is part of the
  //     resolve key)
  //   - on tenant switch (company.id change)
  //
  // Failure mode: console.warn + fall back to tokens.css static
  // defaults. Theme resolution is non-load-bearing for app
  // functionality; never block render on a failed fetch.
  //
  // Scope: this effect runs INSIDE ProtectedRoute, so unauthenticated
  // users never trigger it. RuntimeEditorShell's R-1.6.14 effect
  // continues running independently for the editor's preview render —
  // both apply to documentElement; the editor's effect re-runs on
  // every component-selection mount, the tenant boot effect runs once
  // per (company, mode) pair. Idempotent.
  const [themeMode] = useThemeMode();
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (!company?.id || !company?.vertical) return;

    let cancelled = false;
    tenantThemesService
      .resolve(themeMode)
      .then((resolved) => {
        if (cancelled) return;
        const stack = stackFromResolved(resolved, {});
        const effective = composeEffective(themeMode, stack);
        applyThemeToElement(effective, document.documentElement);
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn(
          "[PresetThemeProvider] tenant theme resolve failed; " +
            "falling back to tokens.css defaults.",
          err,
        );
      });
    return () => {
      cancelled = true;
    };
  }, [company?.id, company?.vertical, themeMode]);

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
