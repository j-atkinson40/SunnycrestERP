/**
 * StudioRailContext — exposes Studio rail state to descendant editor pages.
 *
 * Studio 1a-i.B (editor adaptation pass). The Studio rail and an editor's
 * own left pane are mutually exclusive in their expanded states per the
 * rail-collapses-not-replaces canon (investigation 2026-05-13-studio-1a-i
 * §3). When the rail is expanded AND the editor is mounted inside the
 * Studio shell, the editor hides its own left pane; when the rail
 * collapses to an icon strip, the editor's left pane reappears.
 *
 * Default context value (outside any provider) is
 * `{ railExpanded: false, inStudioContext: false }` so that editors
 * mounted standalone — e.g. via the legacy `/visual-editor/*` redirects
 * during the migration window, or rendered directly in unit tests —
 * always keep their left pane visible. Editors should treat the
 * "hide left pane" condition as `railExpanded && inStudioContext` so
 * the standalone path is never accidentally hidden.
 */
import * as React from "react"


export interface StudioRailContextValue {
  /** Whether the Studio rail is currently in its expanded (full-width) state. */
  railExpanded: boolean
  /** True when the consumer is rendered inside a StudioShell provider. */
  inStudioContext: boolean
}


const DEFAULT: StudioRailContextValue = {
  railExpanded: false,
  inStudioContext: false,
}


export const StudioRailContext = React.createContext<StudioRailContextValue>(DEFAULT)


/**
 * Hook for editors + descendants to read Studio rail state.
 *
 * Returns the default `{ railExpanded: false, inStudioContext: false }`
 * when called outside a StudioRailContext.Provider so that editors
 * rendered standalone behave identically to pre-Studio shipped state.
 */
export function useStudioRail(): StudioRailContextValue {
  return React.useContext(StudioRailContext)
}
