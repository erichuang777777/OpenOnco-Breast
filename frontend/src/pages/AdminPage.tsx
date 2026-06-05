import { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'

interface UserRecord {
  user_id: string
  google_email: string
  role: string
  active: boolean
}

interface KbReview {
  id: string
  entity_type: string
  status: string
  reviewer_1?: string
}

interface AuditEntry {
  id: string
  ts: string
  user_id: string
  action: string
}

export function AdminPage() {
  const { user } = useAuth()
  const [users, setUsers] = useState<UserRecord[]>([])
  const [reviews, setReviews] = useState<KbReview[]>([])
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([])
  const [filterUser, setFilterUser] = useState('')

  useEffect(() => {
    fetch('/api/v1/admin/users', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : []).then(setUsers).catch(() => {})
    fetch('/api/v1/admin/kb/reviews', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : []).then(setReviews).catch(() => {})
    fetch('/api/v1/admin/audit', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : []).then(setAuditLog).catch(() => {})
  }, [])

  if (!user || (user.role !== 'kb_admin' && user.role !== 'auditor')) {
    return <div data-testid="access-denied">存取被拒絕</div>
  }

  const patchRole = (userId: string, role: string) => {
    fetch(`/api/v1/admin/users/${userId}/role`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
      credentials: 'include',
    }).catch(() => {})
  }

  const approveReview = (id: string) => {
    fetch(`/api/v1/admin/kb/reviews/${id}/approve`, { method: 'POST', credentials: 'include' }).catch(() => {})
  }
  const rejectReview = (id: string) => {
    fetch(`/api/v1/admin/kb/reviews/${id}/reject`, { method: 'POST', credentials: 'include' }).catch(() => {})
  }

  const filteredAudit = filterUser
    ? auditLog.filter((e) => e.user_id.includes(filterUser))
    : auditLog

  return (
    <div data-testid="admin-page">
      <h1>管理後台</h1>

      <section data-testid="user-management">
        <h2>使用者管理</h2>
        {users.map((u) => (
          <div key={u.user_id} data-testid={`user-row-${u.user_id}`}
            style={{ background: u.role === 'pending' ? '#fef9c3' : undefined, padding: '0.5rem', marginBottom: '0.25rem' }}>
            <span data-testid={`user-email-${u.user_id}`}>{u.google_email}</span>
            {' '}
            <span data-testid={`user-role-${u.user_id}`}>{u.role}</span>
            <select
              data-testid={`role-select-${u.user_id}`}
              value={u.role}
              onChange={(e) => patchRole(u.user_id, e.target.value)}
            >
              <option value="pending">pending</option>
              <option value="clinic_hcp">clinic_hcp</option>
              <option value="tumor_board_hcp">tumor_board_hcp</option>
              <option value="kb_admin">kb_admin</option>
              <option value="auditor">auditor</option>
            </select>
          </div>
        ))}
      </section>

      <section data-testid="kb-review-section">
        <h2>知識庫審核</h2>
        {reviews.map((r) => (
          <div key={r.id} data-testid={`review-row-${r.id}`} style={{ padding: '0.5rem', marginBottom: '0.25rem', border: '1px solid #e5e7eb' }}>
            <span data-testid={`review-entity-type-${r.id}`}>{r.entity_type}</span>
            <button
              data-testid={`approve-btn-${r.id}`}
              onClick={() => approveReview(r.id)}
              disabled={r.reviewer_1 === user.sub}
            >
              批准
            </button>
            <button data-testid={`reject-btn-${r.id}`} onClick={() => rejectReview(r.id)}>拒絕</button>
          </div>
        ))}
      </section>

      <section data-testid="audit-log-section">
        <h2>稽核記錄</h2>
        <input
          data-testid="audit-filter-input"
          value={filterUser}
          onChange={(e) => setFilterUser(e.target.value)}
          placeholder="篩選使用者…"
        />
        {filteredAudit.map((e) => (
          <div key={e.id} data-testid={`audit-row-${e.id}`} style={{ padding: '0.25rem' }}>
            <span data-testid={`audit-ts-${e.id}`}>{e.ts}</span>
            {' '}
            <span data-testid={`audit-action-${e.id}`}>{e.action}</span>
            {' '}
            <span data-testid={`audit-user-${e.id}`}>{e.user_id}</span>
          </div>
        ))}
      </section>
    </div>
  )
}
