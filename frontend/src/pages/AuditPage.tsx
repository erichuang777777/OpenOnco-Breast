import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'

/**
 * Guideline import & verification interface (audit).
 *
 * Three panels:
 *  1. Ingestion status — content counts, CIViC snapshot freshness, source
 *     citation staleness (the SOURCE_INGESTION_SPEC §9 6-month audit queue).
 *  2. Verification queue — KB reviews awaiting the CHARTER §6.1 two-reviewer
 *     sign-off, with approve / request-changes / reject.
 *  3. A link into the guideline flowchart browser for visual verification.
 */

interface IngestionStatus {
  generated_at: string
  content_counts: Record<string, number>
  total_entities: number
  civic: {
    snapshots: Array<{ date: string; iso_date: string | null; has_evidence: boolean }>
    latest: { date: string; iso_date: string | null } | null
    latest_age_days: number | null
    stale: boolean
  }
  source_freshness: {
    total: number
    stale: number
    undated: number
    stalest: Array<{ source_id: string; title?: string; last_verified: string; age_days: number }>
  }
  stale_after_days: number
  review_queue: {
    pending: number
    approved: number
    rejected: number
    awaiting_second_reviewer: number
  }
}

interface KbReview {
  review_id: string
  entity_type: string
  entity_id: string
  branch_name?: string | null
  pr_number?: number | null
  diff_summary: string
  submitted_by: string
  reviewer_1?: string | null
  reviewer_2?: string | null
  status: string
}

function StatCard({ label, value, tone }: { label: string; value: string | number; tone?: 'warn' | 'ok' }) {
  const border = tone === 'warn' ? '#f59e0b' : tone === 'ok' ? '#16a34a' : '#e5e7eb'
  return (
    <div
      data-testid={`stat-${label}`}
      style={{ border: `1px solid ${border}`, borderRadius: 6, padding: '0.6rem 0.85rem', minWidth: 120 }}
    >
      <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{label}</div>
    </div>
  )
}

export function AuditPage() {
  const { user } = useAuth()
  const [status, setStatus] = useState<IngestionStatus | null>(null)
  const [reviews, setReviews] = useState<KbReview[]>([])
  const [message, setMessage] = useState<string | null>(null)

  const loadReviews = useCallback(() => {
    fetch('/api/v1/admin/kb/reviews', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { pending: [] }))
      .then((data) => setReviews(data.pending ?? []))
      .catch(() => setReviews([]))
  }, [])

  useEffect(() => {
    fetch('/api/v1/admin/kb/ingestion-status', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then(setStatus)
      .catch(() => setStatus(null))
    loadReviews()
  }, [loadReviews])

  if (!user || (user.role !== 'kb_admin' && user.role !== 'auditor')) {
    return <div data-testid="audit-access-denied">存取被拒絕 Access denied</div>
  }
  const canApprove = user.role === 'kb_admin'

  const actOnReview = (reviewId: string, action: 'approve' | 'reject' | 'request_changes') => {
    fetch(`/api/v1/admin/kb/reviews/${reviewId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, comment: '' }),
      credentials: 'include',
    })
      .then((r) => {
        if (r.ok) {
          setMessage(`已${action} ${reviewId}`)
          loadReviews()
        } else {
          return r.json().then((e) => setMessage(e?.detail?.message ?? '操作失敗'))
        }
      })
      .catch(() => setMessage('網路錯誤'))
  }

  return (
    <div data-testid="audit-page" style={{ padding: '1rem', maxWidth: 1100, margin: '0 auto' }}>
      <h1>指引匯入與驗證 · Guideline import &amp; verification</h1>
      <p style={{ fontSize: '0.85rem', color: '#6b7280' }}>
        <a href="/guidelines" data-testid="audit-guidelines-link">→ 指引流程圖檢視 Guideline flowcharts</a>
      </p>

      {message && (
        <div data-testid="audit-message" style={{ background: '#eff6ff', padding: '0.5rem', borderRadius: 4, marginBottom: '0.75rem' }}>
          {message}
        </div>
      )}

      {/* ── Panel 1: ingestion status ─────────────────────────────────────── */}
      <section data-testid="ingestion-status-section" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem' }}>匯入狀態 · Ingestion status</h2>
        {!status && <div data-testid="ingestion-loading">載入中…</div>}
        {status && (
          <>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
              <StatCard label="entities" value={status.total_entities} />
              <StatCard label="algorithms" value={status.content_counts.algorithms ?? 0} />
              <StatCard label="indications" value={status.content_counts.indications ?? 0} />
              <StatCard label="sources" value={status.content_counts.sources ?? 0} />
              <StatCard
                label="stale-sources"
                value={status.source_freshness.stale}
                tone={status.source_freshness.stale > 0 ? 'warn' : 'ok'}
              />
              <StatCard
                label="pending-reviews"
                value={status.review_queue.pending}
                tone={status.review_queue.pending > 0 ? 'warn' : 'ok'}
              />
            </div>

            <div data-testid="civic-status" style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <strong>CIViC snapshot:</strong>{' '}
              {status.civic.latest ? (
                <span>
                  {status.civic.latest.date}
                  {status.civic.latest_age_days != null && ` (${status.civic.latest_age_days}d old)`}
                  {status.civic.stale && (
                    <span data-testid="civic-stale-badge" style={{ color: '#b45309', marginLeft: 6 }}>
                      ⚠ stale (&gt; {status.stale_after_days}d)
                    </span>
                  )}
                </span>
              ) : (
                <span data-testid="civic-none" style={{ color: '#6b7280' }}>none ingested</span>
              )}
            </div>

            {status.source_freshness.stalest.length > 0 && (
              <details data-testid="stale-sources-detail">
                <summary>
                  {status.source_freshness.stale} sources past {status.stale_after_days}d audit window
                </summary>
                <ul style={{ fontSize: '0.8rem' }}>
                  {status.source_freshness.stalest.map((s) => (
                    <li key={s.source_id} data-testid={`stale-source-${s.source_id}`}>
                      {s.source_id} — {s.age_days}d (verified {s.last_verified})
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </section>

      {/* ── Panel 2: verification queue ───────────────────────────────────── */}
      <section data-testid="verification-queue-section">
        <h2 style={{ fontSize: '1.1rem' }}>驗證佇列 · Verification queue (two-reviewer)</h2>
        {reviews.length === 0 && (
          <div data-testid="verification-empty" style={{ color: '#6b7280' }}>佇列為空 Queue is empty.</div>
        )}
        {reviews.map((r) => {
          const alreadyMine = r.reviewer_1 === user.sub
          return (
            <div
              key={r.review_id}
              data-testid={`review-row-${r.review_id}`}
              style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '0.75rem', marginBottom: '0.5rem' }}
            >
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600 }}>{r.entity_type}</span>
                <span data-testid={`review-entity-${r.review_id}`} style={{ color: '#374151' }}>{r.entity_id}</span>
                {r.pr_number != null && (
                  <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>PR #{r.pr_number}</span>
                )}
                <span
                  data-testid={`review-signoff-${r.review_id}`}
                  style={{ marginLeft: 'auto', fontSize: '0.78rem', color: r.reviewer_1 ? '#16a34a' : '#6b7280' }}
                >
                  {r.reviewer_1 ? '1/2 signed' : '0/2 signed'}
                </span>
              </div>
              <p style={{ margin: '0.4rem 0', fontSize: '0.82rem', color: '#374151' }}>{r.diff_summary}</p>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {canApprove && (
                  <button
                    data-testid={`approve-btn-${r.review_id}`}
                    onClick={() => actOnReview(r.review_id, 'approve')}
                    disabled={alreadyMine}
                    title={alreadyMine ? '需要第二位審核者 (CHARTER §6.1)' : ''}
                  >
                    批准 Approve
                  </button>
                )}
                {canApprove && (
                  <button
                    data-testid={`request-changes-btn-${r.review_id}`}
                    onClick={() => actOnReview(r.review_id, 'request_changes')}
                  >
                    要求修改 Request changes
                  </button>
                )}
                {canApprove && (
                  <button
                    data-testid={`reject-btn-${r.review_id}`}
                    onClick={() => actOnReview(r.review_id, 'reject')}
                  >
                    拒絕 Reject
                  </button>
                )}
                {!canApprove && (
                  <span data-testid={`review-readonly-${r.review_id}`} style={{ fontSize: '0.78rem', color: '#6b7280' }}>
                    審核者唯讀 auditor (read-only)
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </section>
    </div>
  )
}
