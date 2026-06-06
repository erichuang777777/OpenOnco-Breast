import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

interface NavItem {
  path: string
  label: string
  icon: string
  roles?: string[]
  testId: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/patients', label: '患者列表', icon: '👥', roles: ['clinic_hcp', 'tumor_board_hcp', 'kb_admin', 'auditor'], testId: 'nav-patients' },
  { path: '/board',    label: '腫瘤委員會', icon: '🏥', roles: ['tumor_board_hcp', 'kb_admin'], testId: 'nav-board' },
  { path: '/admin',    label: '管理後台', icon: '⚙️', roles: ['kb_admin', 'auditor'], testId: 'nav-admin' },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  if (!user) return <>{children}</>

  const visibleItems = NAV_ITEMS.filter(item =>
    !item.roles || item.roles.includes(user.role)
  )

  const handleNav = (path: string) => {
    navigate(path)
    setMobileOpen(false)
  }

  return (
    <div className="app-shell">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 199 }}
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`sidebar${mobileOpen ? ' open' : ''}`} data-testid="sidebar">
        <div className="sidebar-logo">
          Open<span>Onco</span>
        </div>

        <nav className="sidebar-nav">
          {visibleItems.map(item => {
            const active = location.pathname.startsWith(item.path)
            return (
              <button
                key={item.path}
                className={`sidebar-link${active ? ' active' : ''}`}
                onClick={() => handleNav(item.path)}
                data-testid={item.testId}
              >
                <span className="sidebar-link-icon">{item.icon}</span>
                {item.label}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">{user.name || user.email}</div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={logout}
            data-testid="logout-btn"
            style={{ color: 'rgba(255,255,255,0.7)', width: '100%', justifyContent: 'center' }}
          >
            登出
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="main-content">
        {/* Mobile top bar */}
        <header style={{
          display: 'none',
          padding: '0.75rem 1rem',
          background: 'var(--c-primary-900)',
          color: '#fff',
          alignItems: 'center',
          gap: '0.75rem',
          flexShrink: 0,
        }} className="mobile-topbar" data-testid="navbar">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="開啟選單"
            aria-expanded={mobileOpen}
            style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.25rem', cursor: 'pointer', padding: 0 }}
          >
            ☰
          </button>
          <span style={{ fontWeight: 700 }}>OpenOnco</span>
        </header>

        {children}
      </div>
    </div>
  )
}
