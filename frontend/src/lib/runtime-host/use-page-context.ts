/**
 * Phase R-1 — usePageContext hook.
 *
 * Derives the canonical page_context string from the current
 * react-router pathname using the PAGE_CONTEXT_MAP registry.
 * Updates whenever the route changes; consumers (EditModeToggle,
 * inspector tabs) react accordingly.
 */
import { useMemo } from "react"
import { useLocation } from "react-router-dom"

import { resolvePageContext } from "./page-contexts"


export function usePageContext() {
  const { pathname } = useLocation()
  return useMemo(() => resolvePageContext(pathname), [pathname])
}
