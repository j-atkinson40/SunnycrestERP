// use-device-preference.ts — User preference override for device layout
// Persisted per-user in localStorage. Null = auto-detect (no override).

import { useState, useCallback, useEffect } from "react"
import type { DeviceType } from "./use-device-type"

const STORAGE_KEY_PREFIX = "bridgeable_device_pref"

function storageKey(userId: string | null): string {
  return userId ? `${STORAGE_KEY_PREFIX}_${userId}` : STORAGE_KEY_PREFIX
}

function loadPreference(userId: string | null): DeviceType | null {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    if (raw === "mobile" || raw === "tablet" || raw === "desktop") return raw
    return null
  } catch {
    return null
  }
}

function savePreference(userId: string | null, pref: DeviceType | null): void {
  try {
    const key = storageKey(userId)
    if (pref === null) {
      localStorage.removeItem(key)
    } else {
      localStorage.setItem(key, pref)
    }
  } catch {
    // localStorage unavailable (private browsing, etc.)
  }
}

/**
 * Returns the user's device layout preference and a setter.
 * `null` means "auto-detect" (use physical device type).
 * Persisted in localStorage keyed by userId.
 */
export function useDevicePreference(userId: string | null): {
  preference: DeviceType | null
  setPreference: (pref: DeviceType | null) => void
} {
  const [preference, setPreferenceState] = useState<DeviceType | null>(() =>
    loadPreference(userId)
  )

  // Re-read from storage if userId changes
  useEffect(() => {
    setPreferenceState(loadPreference(userId))
  }, [userId])

  const setPreference = useCallback(
    (pref: DeviceType | null) => {
      setPreferenceState(pref)
      savePreference(userId, pref)
    },
    [userId]
  )

  return { preference, setPreference }
}
