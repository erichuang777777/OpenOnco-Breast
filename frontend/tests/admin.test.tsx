import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { AdminPage } from '../src/pages/AdminPage'
import { AuthProvider } from '../src/hooks/useAuth'

const USERS = [
  { user_id: 'u1', google_email: 'alice@hospital.tw', role: 'clinic_hcp', active: true },
  { user_id: 'u2', google_email: 'bob@hospital.tw', role: 'pending', active: true },
]

const REVIEWS = [
  { id: 'rev-1', entity_type: 'biomarker', status: 'pending', reviewer_1: undefined },
  { id: 'rev-2', entity_type: 'regimen', status: 'pending', reviewer_1: 'admin-user' },
]

const AUDIT_LOG = [
  { id: 'aud-1', ts: '2026-06-01T10:00:00Z', user_id: 'u1', action: 'login' },
  { id: 'aud-2', ts: '2026-06-01T11:00:00Z', user_id: 'u2', action: 'onco_query' },
]

function renderAdmin(role = 'kb_admin', sub = 'admin-user') {
  server.use(
    http.get('/auth/me', () => HttpResponse.json({ sub, email: 'admin@hospital.tw', role }))
  )
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <AuthProvider>
        <Routes>
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('AdminPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/admin/users', () => HttpResponse.json(USERS)),
      http.get('/api/v1/admin/kb/reviews', () => HttpResponse.json(REVIEWS)),
      http.get('/api/v1/admin/audit', () => HttpResponse.json(AUDIT_LOG)),
      http.patch('/api/v1/admin/users/:userId/role', () => HttpResponse.json({ ok: true })),
      http.post('/api/v1/admin/kb/reviews/:id/approve', () => HttpResponse.json({ ok: true })),
      http.post('/api/v1/admin/kb/reviews/:id/reject', () => HttpResponse.json({ ok: true }))
    )
  })

  it('test_admin_page_renders', async () => {
    renderAdmin()
    expect(await screen.findByTestId('admin-page')).toBeInTheDocument()
  })

  it('test_admin_access_denied_for_non_admin', async () => {
    renderAdmin('clinic_hcp')
    expect(await screen.findByTestId('access-denied')).toBeInTheDocument()
  })

  it('test_admin_auditor_can_access', async () => {
    renderAdmin('auditor')
    expect(await screen.findByTestId('admin-page')).toBeInTheDocument()
  })

  it('test_admin_user_management_section', async () => {
    renderAdmin()
    expect(await screen.findByTestId('user-management')).toBeInTheDocument()
  })

  it('test_admin_users_listed', async () => {
    renderAdmin()
    expect(await screen.findByTestId('user-row-u1')).toBeInTheDocument()
    expect(screen.getByTestId('user-row-u2')).toBeInTheDocument()
  })

  it('test_admin_user_email_displayed', async () => {
    renderAdmin()
    expect(await screen.findByTestId('user-email-u1')).toHaveTextContent('alice@hospital.tw')
  })

  it('test_admin_pending_user_highlighted', async () => {
    renderAdmin()
    const pendingRow = await screen.findByTestId('user-row-u2')
    expect(pendingRow.style.background).toBeTruthy()
  })

  it('test_admin_role_select_present', async () => {
    renderAdmin()
    expect(await screen.findByTestId('role-select-u1')).toBeInTheDocument()
  })

  it('test_admin_role_patch_called_on_change', async () => {
    let patchedRole: string | null = null
    server.use(
      http.patch('/api/v1/admin/users/:userId/role', async ({ request }) => {
        const body = await request.json() as { role: string }
        patchedRole = body.role
        return HttpResponse.json({ ok: true })
      })
    )
    renderAdmin()
    const select = await screen.findByTestId('role-select-u1')
    fireEvent.change(select, { target: { value: 'tumor_board_hcp' } })
    await waitFor(() => expect(patchedRole).toBe('tumor_board_hcp'))
  })

  it('test_admin_kb_review_section', async () => {
    renderAdmin()
    expect(await screen.findByTestId('kb-review-section')).toBeInTheDocument()
  })

  it('test_admin_reviews_listed', async () => {
    renderAdmin()
    expect(await screen.findByTestId('review-row-rev-1')).toBeInTheDocument()
    expect(screen.getByTestId('review-row-rev-2')).toBeInTheDocument()
  })

  it('test_admin_review_entity_type_displayed', async () => {
    renderAdmin()
    expect(await screen.findByTestId('review-entity-type-rev-1')).toHaveTextContent('biomarker')
  })

  it('test_admin_approve_btn_disabled_for_same_reviewer', async () => {
    renderAdmin('kb_admin', 'admin-user')
    const approveBtn = await screen.findByTestId('approve-btn-rev-2')
    expect(approveBtn).toBeDisabled()
  })

  it('test_admin_approve_btn_enabled_for_different_reviewer', async () => {
    renderAdmin('kb_admin', 'admin-user')
    const approveBtn = await screen.findByTestId('approve-btn-rev-1')
    expect(approveBtn).not.toBeDisabled()
  })

  it('test_admin_approve_calls_api', async () => {
    let approveCalled = false
    server.use(
      http.post('/api/v1/admin/kb/reviews/:id/approve', () => {
        approveCalled = true
        return HttpResponse.json({ ok: true })
      })
    )
    renderAdmin()
    const btn = await screen.findByTestId('approve-btn-rev-1')
    fireEvent.click(btn)
    await waitFor(() => expect(approveCalled).toBe(true))
  })

  it('test_admin_reject_calls_api', async () => {
    let rejectCalled = false
    server.use(
      http.post('/api/v1/admin/kb/reviews/:id/reject', () => {
        rejectCalled = true
        return HttpResponse.json({ ok: true })
      })
    )
    renderAdmin()
    const btn = await screen.findByTestId('reject-btn-rev-1')
    fireEvent.click(btn)
    await waitFor(() => expect(rejectCalled).toBe(true))
  })

  it('test_admin_audit_log_section', async () => {
    renderAdmin()
    expect(await screen.findByTestId('audit-log-section')).toBeInTheDocument()
  })

  it('test_admin_audit_entries_displayed', async () => {
    renderAdmin()
    expect(await screen.findByTestId('audit-row-aud-1')).toBeInTheDocument()
    expect(screen.getByTestId('audit-row-aud-2')).toBeInTheDocument()
  })

  it('test_admin_audit_filter_input', async () => {
    renderAdmin()
    expect(await screen.findByTestId('audit-filter-input')).toBeInTheDocument()
  })

  it('test_admin_audit_filter_by_user', async () => {
    renderAdmin()
    await screen.findByTestId('audit-row-aud-1')
    fireEvent.change(screen.getByTestId('audit-filter-input'), { target: { value: 'u1' } })
    await waitFor(() => {
      expect(screen.getByTestId('audit-row-aud-1')).toBeInTheDocument()
      expect(screen.queryByTestId('audit-row-aud-2')).not.toBeInTheDocument()
    })
  })
})
