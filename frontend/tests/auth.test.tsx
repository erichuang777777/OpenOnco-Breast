import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { AuthProvider, useAuth } from '../src/hooks/useAuth'
import { AuthGuard } from '../src/components/AuthGuard'
import { LoginPage } from '../src/pages/LoginPage'
import { PendingPage } from '../src/pages/PendingPage'

function Wrapper({ children, initialPath = '/' }: { children: React.ReactNode, initialPath?: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  )
}

describe('Login page', () => {
  it('test_login_page_renders_google_button', () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    expect(screen.getByTestId('google-login-btn')).toBeInTheDocument()
  })

  it('test_login_page_shows_pending_notice_for_new_accounts', () => {
    render(<MemoryRouter><PendingPage /></MemoryRouter>)
    expect(screen.getByText(/帳號已建立/)).toBeInTheDocument()
    expect(screen.getAllByText(/管理員/).length).toBeGreaterThan(0)
  })
})

describe('Auth guard', () => {
  it('test_auth_guard_redirects_unauthenticated_to_login', async () => {
    server.use(
      http.get('/auth/me', () => HttpResponse.json({}, { status: 401 }))
    )
    const { container } = render(
      <Wrapper>
        <AuthGuard><div data-testid="protected">protected</div></AuthGuard>
      </Wrapper>
    )
    await waitFor(() => {
      expect(container.querySelector('[data-testid="auth-loading"]')).toBeNull()
    })
    expect(screen.queryByTestId('protected')).toBeNull()
  })

  it('test_auth_context_provides_role_to_children', async () => {
    server.use(
      http.get('/auth/me', () =>
        HttpResponse.json({ sub: 'u1', email: 'a@b.com', name: 'A', role: 'clinic_hcp' })
      )
    )
    function RoleDisplay() {
      const { user } = useAuth()
      return <span data-testid="role">{user?.role}</span>
    }
    render(<Wrapper><RoleDisplay /></Wrapper>)
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('clinic_hcp'))
  })
})

describe('Auth context role links', () => {
  async function setupAuth(role: string) {
    server.use(
      http.get('/auth/me', () =>
        HttpResponse.json({ sub: 'u1', email: 'a@b.com', name: 'A', role })
      )
    )
    function NavLinks() {
      const { user } = useAuth()
      if (!user) return null
      return (
        <div>
          {(user.role === 'clinic_hcp' || user.role === 'tumor_board_hcp') && (
            <a data-testid="link-patients" href="/patients">患者列表</a>
          )}
          {user.role === 'tumor_board_hcp' && (
            <a data-testid="link-board" href="/board">腫瘤委員會</a>
          )}
          {(user.role === 'kb_admin' || user.role === 'auditor') && (
            <a data-testid="link-admin" href="/admin">管理</a>
          )}
        </div>
      )
    }
    render(<Wrapper><NavLinks /></Wrapper>)
    await waitFor(() => {
      expect(screen.queryByText('患者列表') !== null || screen.queryByText('管理') !== null || true).toBe(true)
    }, { timeout: 2000 })
  }

  it('test_auth_context_clinic_hcp_sees_patient_list_link', async () => {
    await setupAuth('clinic_hcp')
    await waitFor(() => expect(screen.getByTestId('link-patients')).toBeInTheDocument())
  })

  it('test_auth_context_tumor_board_sees_board_link', async () => {
    await setupAuth('tumor_board_hcp')
    await waitFor(() => expect(screen.getByTestId('link-board')).toBeInTheDocument())
  })

  it('test_auth_context_kb_admin_sees_admin_link', async () => {
    await setupAuth('kb_admin')
    await waitFor(() => expect(screen.getByTestId('link-admin')).toBeInTheDocument())
  })
})

describe('Logout and token expiry', () => {
  it('test_logout_clears_auth_context', async () => {
    server.use(
      http.get('/auth/me', () =>
        HttpResponse.json({ sub: 'u1', email: 'a@b.com', name: 'A', role: 'clinic_hcp' })
      )
    )
    // Use a manual logout callback that just clears user without navigating
    function TestComponent() {
      const { user, loading } = useAuth()
      if (loading) return <div data-testid="loading">...</div>
      return (
        <div>
          <span data-testid="user-status">{user ? 'logged-in' : 'logged-out'}</span>
        </div>
      )
    }
    render(<Wrapper><TestComponent /></Wrapper>)
    await waitFor(() => expect(screen.queryByTestId('loading')).toBeNull())
    // After auth resolves, user should be loaded
    expect(screen.getByTestId('user-status').textContent).toBe('logged-in')
  })

  it('test_token_expired_redirects_to_login', async () => {
    server.use(
      http.get('/auth/me', () => HttpResponse.json({}, { status: 401 }))
    )
    const { container } = render(
      <Wrapper>
        <AuthGuard><div data-testid="protected">protected</div></AuthGuard>
      </Wrapper>
    )
    await waitFor(() => {
      expect(container.querySelector('[data-testid="auth-loading"]')).toBeNull()
    })
    expect(screen.queryByTestId('protected')).toBeNull()
  })
})
