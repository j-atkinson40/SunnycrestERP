// Admin API client — separate from tenant api-client.ts
// Routes through /api/platform/admin/* with environment toggle support.

import axios from "axios"

export type AdminEnvironment = "production" | "staging"

const PRODUCTION_API = import.meta.env.VITE_API_URL || "https://api.getbridgeable.com"
const STAGING_API =
  import.meta.env.VITE_STAGING_API_URL ||
  "https://sunnycresterp-staging.up.railway.app"

const ENV_STORAGE_KEY = "bridgeable-admin-env"
const TOKEN_STORAGE_KEY = "bridgeable-admin-token"

export function getAdminEnvironment(): AdminEnvironment {
  const v = localStorage.getItem(ENV_STORAGE_KEY)
  return v === "staging" ? "staging" : "production"
}

export function setAdminEnvironment(env: AdminEnvironment) {
  localStorage.setItem(ENV_STORAGE_KEY, env)
  // Dispatch event so app-wide banner updates
  window.dispatchEvent(new CustomEvent("admin-environment-changed", { detail: env }))
}

export function getAdminBaseUrl(env?: AdminEnvironment): string {
  const e = env || getAdminEnvironment()
  return e === "staging" ? STAGING_API : PRODUCTION_API
}

export function getAdminToken(): string | null {
  const env = getAdminEnvironment()
  const key = `${TOKEN_STORAGE_KEY}-${env}`
  return localStorage.getItem(key)
}

export function setAdminToken(token: string | null) {
  const env = getAdminEnvironment()
  const key = `${TOKEN_STORAGE_KEY}-${env}`
  if (token) {
    localStorage.setItem(key, token)
  } else {
    localStorage.removeItem(key)
  }
}

export function clearAdminSession() {
  setAdminToken(null)
}

// Axios instance that always uses current environment
export function makeAdminClient() {
  const instance = axios.create()
  instance.interceptors.request.use((config) => {
    config.baseURL = getAdminBaseUrl()
    const token = getAdminToken()
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
  return instance
}

export const adminApi = makeAdminClient()

export async function adminLogin(email: string, password: string): Promise<{ token: string; user: any }> {
  const baseUrl = getAdminBaseUrl()
  const { data } = await axios.post(
    `${baseUrl}/api/platform/auth/login`,
    { email, password }
  )
  const token = data.access_token
  setAdminToken(token)
  return { token, user: data.user }
}

export async function adminMe(): Promise<any | null> {
  try {
    const { data } = await adminApi.get("/api/platform/auth/me")
    return data
  } catch {
    return null
  }
}
