/**
 * AuthoringRequestContext — the bar→editor draft hand-off carrier (Shell-2).
 *
 * The omnipresent AuthoringAssistantBar (above the Routes) and the workflow
 * editor (inside the Routes) both consume this. The bar calls `submit(nl)`; the
 * editor reads `request` and hands it to WorkflowAssistantRail, then `consume()`s
 * it. A SHARED CONTEXT, not route state: route state carried the navigate-then-
 * deliver case fine, but React Router does not reliably re-fire useLocation on a
 * SAME-PATH (in-place) navigation, so an already-open editor never saw the new
 * state. The context handles both cases identically — for MoC the bar navigates
 * into the editor (which then reads the context); in-place it just sets the
 * context (the editor re-renders + delivers). Provider mounts above the Routes
 * so it survives navigation alongside the bar.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

export interface AuthoringRequest {
  nl: string
  /** Monotonic — the rail delivers once per nonce (guards double-run). */
  nonce: number
}

interface AuthoringRequestValue {
  request: AuthoringRequest | null
  /** Set a fresh draft request (assigns a new nonce). */
  submit: (nl: string) => void
  /** Clear the request once the editor has handed it to the rail. */
  consume: () => void
}

const AuthoringRequestContext = createContext<AuthoringRequestValue>({
  request: null,
  submit: () => {},
  consume: () => {},
})

export function AuthoringRequestProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<AuthoringRequest | null>(null)
  const nonceRef = useRef(0)
  const submit = useCallback((nl: string) => {
    const text = nl.trim()
    if (!text) return
    nonceRef.current += 1
    setRequest({ nl: text, nonce: nonceRef.current })
  }, [])
  const consume = useCallback(() => setRequest(null), [])
  const value = useMemo(
    () => ({ request, submit, consume }),
    [request, submit, consume],
  )
  return (
    <AuthoringRequestContext.Provider value={value}>
      {children}
    </AuthoringRequestContext.Provider>
  )
}

export function useAuthoringRequest(): AuthoringRequestValue {
  return useContext(AuthoringRequestContext)
}
