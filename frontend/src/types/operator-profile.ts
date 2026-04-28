/**
 * Phase W-4a operator profile types — mirrors backend
 * `app/services/operator_profile_service.py` + the
 * `_OperatorProfileResponse` Pydantic model.
 *
 * Per BRIDGEABLE_MASTER §3.26.3 — work_areas + responsibilities feed
 * Pulse composition (Tier 1 rule-based + Tier 2+ intelligence).
 */

export interface OperatorProfile {
  /** Multi-select work areas the user covers in their daily work. */
  work_areas: string[]
  /** Free-text natural-language responsibilities description. */
  responsibilities_description: string | null
  /**
   * True when the user has explicitly completed the onboarding flow
   * OR has at least one work area set. Drives the first-login prompt
   * on PulseSurface — banner shows when `false`.
   */
  onboarding_completed: boolean
  /**
   * Canonical work-area vocabulary surfaced by the backend so the
   * multi-select UI doesn't hardcode the list. Backend is the source
   * of truth; this list extends without a frontend deploy.
   */
  available_work_areas: string[]
}


export interface OperatorProfileUpdateRequest {
  work_areas?: string[]
  responsibilities_description?: string | null
  /**
   * Set true when the user explicitly clicks "Save and continue" to
   * stamp the `preferences.onboarding_touches.operator_profile` flag.
   * Auto-save fires with `false` on each debounced flush.
   */
  mark_onboarding_complete?: boolean
}
