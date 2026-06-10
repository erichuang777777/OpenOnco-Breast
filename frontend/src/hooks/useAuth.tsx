import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'
import { DEMO_MODE } from '../config'

export interface AuthUser {
  sub: string
  email: string
  name: string
  role: string
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  logout: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/auth/me', { credentials: 'include', signal: controller.signal })
      .then(async (r) => {
        if (r.status === 401) {
          if (DEMO_MODE) {
            // Auto-login in demo mode — skip the login page entirely
            await fetch('/auth/dev/login', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({ email: 'demo@openonco.local', role: 'clinic_hcp' }),
            })
            window.location.href = '/'
          }
          return null
        }
        return r.json()
      })
      .then((data) => {
        if (data && data.sub) setUser(data as AuthUser)
      })
      .catch((e: unknown) => {
        if (e instanceof Error && e.name === 'AbortError') return
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const logout = () => {
    setUser(null)
    window.location.href = '/auth/logout'
  }

  return (
    <AuthContext.Provider value={{ user, loading, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function roleHomeUrl(role: string): string {
  const map: Record<string, string> = {
    tumor_board_hcp: '/board',
    clinic_hcp: '/patients',
    kb_admin: '/admin',
    auditor: '/admin/audit',
  }
  return map[role] ?? '/patients'
}
