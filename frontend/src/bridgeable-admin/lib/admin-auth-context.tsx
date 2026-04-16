import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { adminLogin, adminMe, clearAdminSession, getAdminToken } from "./admin-api"

type AdminUser = {
  id: string
  email: string
  first_name: string
  last_name: string
  role: string
} | null

interface AdminAuthContextValue {
  user: AdminUser
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = getAdminToken()
    if (!token) {
      setLoading(false)
      return
    }
    adminMe()
      .then((u) => setUser(u))
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const { user } = await adminLogin(email, password)
    setUser(user)
  }

  const logout = () => {
    clearAdminSession()
    setUser(null)
  }

  return (
    <AdminAuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  )
}

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error("useAdminAuth must be used inside AdminAuthProvider")
  return ctx
}
