/**
 * R-5.0 — EdgePanelProvider.
 *
 * Mounts at app root inside TenantProviders. Holds:
 *   - `isOpen` boolean (Edge handle / Cmd+Shift+E / swipe → open;
 *     Esc / click-outside / button-fire → close)
 *   - `currentPageIndex` (multi-page panels)
 *   - `composition` (resolved via /api/v1/edge-panel/resolve, lazily on first auth)
 *   - `tenantConfig` (width + enabled — read once on mount)
 *   - `closePanel()` callback used by R-4 buttons rendered inside
 *     the panel to auto-close on action fire.
 *
 * Uses `useAuth()` to gate fetches — only fires resolve/tenant-config
 * after the user is authenticated. The provider itself sits unconditionally
 * inside TenantProviders; consumers see `isReady=false` until auth resolves.
 *
 * Outside-provider stub: `useEdgePanelOptional()` returns null so
 * RegisteredButton can call it safely from any tree.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { useAuth } from "@/contexts/auth-context"
import {
  getEdgePanelTenantConfig,
  resolveEdgePanel,
} from "./edge-panel-service"
import type {
  EdgePanelTenantConfig,
  ResolvedEdgePanel,
} from "./types"


const DEFAULT_PANEL_KEY = "default"


export interface EdgePanelContextValue {
  isOpen: boolean
  currentPageIndex: number
  isReady: boolean
  composition: ResolvedEdgePanel | null
  tenantConfig: EdgePanelTenantConfig
  panelKey: string
  openPanel: () => void
  closePanel: () => void
  togglePanel: () => void
  setCurrentPageIndex: (idx: number) => void
}


const EdgePanelContext = createContext<EdgePanelContextValue | null>(null)


export interface EdgePanelProviderProps {
  children: ReactNode
  /** Override which composition slug to resolve. Defaults to "default". */
  panelKey?: string
}


export function EdgePanelProvider({
  children,
  panelKey = DEFAULT_PANEL_KEY,
}: EdgePanelProviderProps) {
  const { user, isLoading: authLoading } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [currentPageIndex, setCurrentPageIndex] = useState(0)
  const [composition, setComposition] = useState<ResolvedEdgePanel | null>(null)
  const [tenantConfig, setTenantConfig] = useState<EdgePanelTenantConfig>({
    enabled: true,
    width: 320,
  })
  const [isReady, setIsReady] = useState(false)

  // Fetch composition + tenant config on mount, scoped to authenticated.
  useEffect(() => {
    if (authLoading || !user) return
    let cancelled = false
    void (async () => {
      try {
        const [resolved, cfg] = await Promise.all([
          resolveEdgePanel(panelKey),
          getEdgePanelTenantConfig(),
        ])
        if (cancelled) return
        setComposition(resolved)
        setTenantConfig(cfg)
        setIsReady(true)
      } catch (err) {
        // Surfacing a console.warn keeps fetch failures observable
        // without blocking the rest of the app. The handle + panel
        // remain hidden if isReady stays false.
        // eslint-disable-next-line no-console
        console.warn("[edge-panel] resolve failed", err)
        if (!cancelled) {
          setIsReady(true)
          setComposition(null)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [authLoading, user, panelKey])

  const openPanel = useCallback(() => {
    setIsOpen(true)
  }, [])

  const closePanel = useCallback(() => {
    setIsOpen(false)
  }, [])

  const togglePanel = useCallback(() => {
    setIsOpen((prev) => !prev)
  }, [])

  // Reset to first page when reopening — feels more deliberate than
  // landing on the page the user last left at.
  useEffect(() => {
    if (isOpen) {
      const desired = composition?.canvas_config?.padding ? 0 : 0
      setCurrentPageIndex(desired)
    }
  }, [isOpen, composition])

  // Keep currentPageIndex in bounds when the composition changes.
  useEffect(() => {
    const pageCount = composition?.pages?.length ?? 0
    if (pageCount > 0 && currentPageIndex >= pageCount) {
      setCurrentPageIndex(0)
    }
  }, [composition, currentPageIndex])

  // Body data-attr so other layers (runtime editor) can mode-mutex.
  useEffect(() => {
    if (typeof document === "undefined") return
    if (isOpen) {
      document.body.setAttribute("data-edge-panel-open", "true")
    } else {
      document.body.removeAttribute("data-edge-panel-open")
    }
    return () => {
      document.body.removeAttribute("data-edge-panel-open")
    }
  }, [isOpen])

  const value: EdgePanelContextValue = useMemo(
    () => ({
      isOpen,
      currentPageIndex,
      isReady,
      composition,
      tenantConfig,
      panelKey,
      openPanel,
      closePanel,
      togglePanel,
      setCurrentPageIndex,
    }),
    [
      isOpen,
      currentPageIndex,
      isReady,
      composition,
      tenantConfig,
      panelKey,
      openPanel,
      closePanel,
      togglePanel,
    ],
  )

  return (
    <EdgePanelContext.Provider value={value}>
      {children}
    </EdgePanelContext.Provider>
  )
}


export function useEdgePanel(): EdgePanelContextValue {
  const ctx = useContext(EdgePanelContext)
  if (ctx === null) {
    throw new Error(
      "useEdgePanel must be called inside an EdgePanelProvider",
    )
  }
  return ctx
}


/** Null-safe variant for callers that may live outside the provider
 * (e.g. RegisteredButton — rendered in many trees). Returns null
 * outside the provider tree.
 */
export function useEdgePanelOptional(): EdgePanelContextValue | null {
  return useContext(EdgePanelContext)
}
