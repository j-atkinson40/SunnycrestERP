/**
 * Phase R-0 — TenantProviders.
 *
 * The 9-deep tenant context chain extracted from App.tsx so it can be
 * mounted from anywhere (the tenant boot path AND the admin tree's
 * runtime-host-test surface). App.tsx's tenant boot path consumes
 * this exact provider; the admin tree's `/_runtime-host-test/*` route
 * mounts it the same way.
 *
 * Order (top-down — outermost first; matches App.tsx pre-R-0 order):
 *   AuthProvider
 *     FeatureFlagProvider
 *       ExtensionProvider
 *         LocationProvider
 *           LayoutProvider
 *             AuthDeviceProvider     (bridges useAuth().user.id → DeviceProvider)
 *               FocusProvider
 *                 CommandBarProvider
 *                   CallContextProvider
 *                     TooltipProvider
 *
 * Per-route stack (PresetThemeProvider / SpaceProvider / PeekProvider)
 * stays inside the route tree because it's gated by the protected-
 * route check and only applies after authentication. TenantRouteTree
 * mounts those itself.
 *
 * No props; the providers consume their own data. The router context
 * (BrowserRouter) MUST be provided externally because react-router
 * hooks need it; both the tenant App and the admin tree provide their
 * own router.
 *
 * Why this lives here instead of in App.tsx: the admin tree's
 * runtime-host-test surface needs to render tenant content, which
 * means it needs the same provider chain. Sharing a single source
 * of truth for the chain prevents drift. The provider boundary also
 * makes it explicit that "rendering tenant content" depends on this
 * specific chain — adding a provider in App.tsx without adding it
 * here would break the runtime host.
 */
import { type ReactNode } from "react"

import { AuthProvider, useAuth } from "@/contexts/auth-context"
import { CallContextProvider } from "@/contexts/call-context"
import { CommandBarProvider } from "@/core/CommandBarProvider"
import { DeviceProvider } from "@/contexts/device-context"
import { ExtensionProvider } from "@/contexts/extension-context"
import { FeatureFlagProvider } from "@/contexts/feature-flag-context"
import { FocusProvider } from "@/contexts/focus-context"
import { LayoutProvider } from "@/contexts/layout-context"
import { LocationProvider } from "@/contexts/location-context"
import { TooltipProvider } from "@/components/ui/tooltip"


/** Bridges auth context → DeviceProvider so userId is available. */
function AuthDeviceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return <DeviceProvider userId={user?.id ?? null}>{children}</DeviceProvider>
}


export function TenantProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <FeatureFlagProvider>
        <ExtensionProvider>
          <LocationProvider>
            <LayoutProvider>
              <AuthDeviceProvider>
                <FocusProvider>
                  <CommandBarProvider>
                    <CallContextProvider>
                      {/* Aesthetic Arc Session 3 — TooltipProvider
                          mounted once at the tenant-route root. Sets
                          the 150 ms delay from DESIGN_LANGUAGE §6
                          (prevents drive-by tooltips on cursor
                          transit). Phase B Session 4 Phase 4.2.5 —
                          `timeout={0}` disables base-ui's
                          FloatingDelayGroup grouping (per App.tsx
                          comment: pre-4.2.5 the default 400ms timeout
                          let adjacent tooltips open instantly within
                          400ms of a prior close, causing a sticky-
                          state race; disabling grouping makes each
                          Tooltip root fully independent). */}
                      <TooltipProvider timeout={0}>{children}</TooltipProvider>
                    </CallContextProvider>
                  </CommandBarProvider>
                </FocusProvider>
              </AuthDeviceProvider>
            </LayoutProvider>
          </LocationProvider>
        </ExtensionProvider>
      </FeatureFlagProvider>
    </AuthProvider>
  )
}
