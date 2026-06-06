import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'

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
      .then((r) => {
        if (r.status === 401) return null
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
