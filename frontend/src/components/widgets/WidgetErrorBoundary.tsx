// WidgetErrorBoundary — catches errors in individual widgets without crashing the grid

import { Component, type ReactNode } from "react"
import { AlertCircle } from "lucide-react"

interface Props {
  widgetId: string
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class WidgetErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error) {
    console.error(`[Widget ${this.props.widgetId}] Error:`, error)
  }

  render() {
    if (this.state.hasError) {
      // Aesthetic Arc Session 3 refresh — DESIGN_LANGUAGE status-error
      // family for the failure indicator; accent focus ring on retry.
      return (
        <div className="flex flex-col items-center justify-center gap-2 p-4 text-center font-sans text-body-sm text-content-muted">
          <AlertCircle className="h-5 w-5 text-status-error" />
          <p>Widget failed to load</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="rounded-sm text-caption text-accent transition-colors duration-quick ease-settle hover:text-accent-hover hover:underline focus-ring-accent"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
