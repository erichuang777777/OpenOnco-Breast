import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import type { UnsignedEntity, ReviewBundle, ReviewCitation } from '../api/types'

/**
 * Clinical sign-off review (CHARTER §6.1 two-reviewer).
 *
 * Left: the queue of KB entities not yet two-reviewer signed.
 * Right: the selected entity's structured claim (YAML + claim fields) beside
 * each cited source's license-safe evidence (citation, study design, key
 * results, endpoints) with a DOI/PMID/URL deep link to the original — so a
 * Clinical Co-Lead can verify the paraphrase against the source before
 * recording a sign-off.
 *
 * Recording a decision writes to the hospital KbReview + audit trail; the
 * actual `reviewer_signoffs` YAML update remains a governed git change.
 */

const ENTITY_TYPES = ['indication', 'algorithm', 'regimen', 'redflag', 'biomarker_actionability']

function Badge({ text, tone }: { text: string; tone?: string }) {
  return (
    <span style={{
      background: tone ?? '#e2e8f0', color: '#0f172a', borderRadius: 3,
      padding: '0 6px', fontSize: '0.7rem', marginLeft: 6,
    }}>{text}</span>
  )
}

function EvidenceBlock({ label, value }: { label: string; value: unknown }) {
  if (value == null || value === '') return null
  const render = (v: unknown) => {
    if (v && typeof v === 'object') {
      return (
        <ul style={{ margin: '2px 0 0', paddingLeft: '1.1rem' }}>
          {Object.entries(v as Record<string, unknown>).map(([k, val]) => (
            <li key={k} style={{ fontSize: '0.78rem' }}>
              <span style={{ color: '#64748b' }}>{k}:</span> {String(val)}
            </li>
          ))}
        </ul>
      )
    }
    return <span style={{ fontSize: '0.8rem' }}> {String(v)}</span>
  }
  return (
    <div style={{ marginTop: 4 }} data-testid={`evidence-${label}`}>
      <span style={{ fontWeight: 600, fontSize: '0.78rem', color: '#334155' }}>{label}:</span>
      {render(value)}
    </div>
  )
}

function CitationCard({ c }: { c: ReviewCitation }) {
  const cit = c.citation ?? {}
  return (
    <div
      data-testid={`citation-${c.source_id}`}
      style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '0.6rem', marginBottom: '0.5rem' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: '0.85rem' }}>{c.source_id}</strong>
        {c.type && <Badge text={c.type} />}
        {c.hosting && <Badge text={c.hosting} tone={c.hosting === 'referenced' ? '#fef3c7' : '#dcfce7'} />}
        {!c.found && <Badge text="missing source!" tone="#fecaca" />}
      </div>
      {c.title && <div style={{ fontSize: '0.82rem', margin: '3px 0' }}>{c.title}</div>}
      {(cit.authors || cit.journal) && (
        <div style={{ fontSize: '0.76rem', color: '#64748b' }}>
          {cit.authors} {cit.journal && <em>· {cit.journal}</em>} {cit.year && `(${cit.year})`}
          {cit.pages && `, pp. ${cit.pages}`}
        </div>
      )}
      {c.url && (
        <a data-testid={`citation-link-${c.source_id}`} href={c.url} target="_blank" rel="noreferrer"
           style={{ fontSize: '0.78rem' }}>
          開啟原文 Open source ↗ {cit.doi ? `(doi:${cit.doi})` : cit.pmid ? `(PMID ${cit.pmid})` : ''}
        </a>
      )}
      <EvidenceBlock label="study_design" value={c.study_design} />
      <EvidenceBlock label="key_results" value={c.key_results} />
      <EvidenceBlock label="primary_endpoint" value={c.primary_endpoint} />
      {c.fulltext && (
        <details data-testid={`fulltext-${c.source_id}`} style={{ marginTop: 6 }}>
          <summary style={{ fontSize: '0.78rem', color: '#0f766e', cursor: 'pointer' }}>
            原文全文（機構內部使用）Source full text (institutional internal use)
          </summary>
          <pre style={{
            background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 4,
            padding: '0.5rem', fontSize: '0.74rem', whiteSpace: 'pre-wrap', maxHeight: 280, overflow: 'auto',
          }}>{c.fulltext}</pre>
        </details>
      )}
      {c.license && (
        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: 4 }}>license: {c.license}</div>
      )}
    </div>
  )
}

export function ClinicalReviewPage() {
  const { user } = useAuth()
  const [type, setType] = useState('indication')
  const [items, setItems] = useState<UnsignedEntity[]>([])
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<UnsignedEntity | null>(null)
  const [bundle, setBundle] = useState<ReviewBundle | null>(null)
  const [showYaml, setShowYaml] = useState(false)
  const [comment, setComment] = useState('')
  const [passage, setPassage] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    fetch(`/api/v1/admin/kb/unsigned?entity_type=${type}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { total: 0, entities: [] }))
      .then((d) => { setItems(d.entities ?? []); setTotal(d.total ?? 0) })
      .catch(() => { setItems([]); setTotal(0) })
  }, [type])

  const loadBundle = useCallback((e: UnsignedEntity) => {
    setSelected(e)
    setMessage(null)
    fetch(`/api/v1/admin/kb/entity/${e.entity_type}/${e.entity_id}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then(setBundle)
      .catch(() => setBundle(null))
  }, [])

  if (!user || (user.role !== 'kb_admin' && user.role !== 'auditor')) {
    return <div data-testid="review-access-denied">存取被拒絕 Access denied</div>
  }
  const canSign = user.role === 'kb_admin'

  const signoff = (decision: 'approve' | 'reject' | 'request_changes') => {
    if (!bundle) return
    fetch(`/api/v1/admin/kb/entity/${bundle.entity_type}/${bundle.entity_id}/signoff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, comment, verified_passage: passage }),
      credentials: 'include',
    })
      .then((r) => r.json().then((d) => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        setMessage(ok ? (d.message ?? 'OK') : (d?.detail?.message ?? '操作失敗'))
        if (ok) { setComment(''); setPassage('') }
      })
      .catch(() => setMessage('網路錯誤'))
  }

  return (
    <div data-testid="clinical-review-page" style={{ padding: '1rem', maxWidth: 1200, margin: '0 auto' }}>
      <h1>臨床簽核 · Clinical sign-off review</h1>
      <p style={{ fontSize: '0.82rem', color: '#64748b' }}>
        兩位不同審核者核准後標記為 approved（CHARTER §6.1）。最終 YAML 簽核仍須經 git 流程。
        Referenced 來源依授權僅能連結原文，下方顯示來源實體中的結構化證據供核對。
      </p>

      {message && (
        <div data-testid="review-message" style={{ background: '#eff6ff', padding: '0.5rem', borderRadius: 4, margin: '0.5rem 0' }}>
          {message}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1rem', alignItems: 'start' }}>
        {/* Queue */}
        <div>
          <select
            data-testid="review-type-select"
            value={type}
            onChange={(e) => { setType(e.target.value); setSelected(null); setBundle(null) }}
            style={{ width: '100%', padding: '0.3rem', marginBottom: '0.5rem' }}
          >
            {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <div data-testid="review-queue-count" style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: 4 }}>
            {total} unsigned
          </div>
          <div data-testid="review-queue" style={{ border: '1px solid #e5e7eb', borderRadius: 6, maxHeight: 600, overflow: 'auto' }}>
            {items.map((e) => (
              <button
                key={e.entity_id}
                data-testid={`review-item-${e.entity_id}`}
                onClick={() => loadBundle(e)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left', border: 'none',
                  borderBottom: '1px solid #f1f5f9', padding: '0.5rem',
                  background: selected?.entity_id === e.entity_id ? '#eff6ff' : '#fff', cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: '0.78rem', fontWeight: 600 }}>{e.entity_id}</div>
                <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                  {e.signoff_count}/2 signed{e.draft ? ' · draft' : ''}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Bundle */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '1rem', minHeight: 240 }}>
          {!bundle && <div data-testid="review-placeholder" style={{ color: '#9ca3af' }}>← 選擇項目以審閱 Select an item to review.</div>}
          {bundle && (
            <>
              <div style={{ display: 'flex', alignItems: 'baseline', flexWrap: 'wrap', gap: 6 }}>
                <h2 data-testid="bundle-id" style={{ margin: 0, fontSize: '1.05rem' }}>{bundle.entity_id}</h2>
                {bundle.disease_id && <Badge text={bundle.disease_id} />}
                <Badge text={`${bundle.signoff_count}/2 signed`} tone={bundle.signoff_count >= 1 ? '#dcfce7' : '#e2e8f0'} />
                {bundle.draft && <Badge text="draft" tone="#fef3c7" />}
              </div>
              <p style={{ color: '#475569', fontSize: '0.85rem', margin: '0.3rem 0 0.75rem' }}>{bundle.label}</p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {/* Claims */}
                <div data-testid="bundle-claims">
                  <h3 style={{ fontSize: '0.9rem' }}>主張 Claims</h3>
                  {bundle.claims.map((cl) => (
                    <div key={cl.field} style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: '0.74rem', color: '#64748b', textTransform: 'uppercase' }}>{cl.field}</div>
                      <div style={{ fontSize: '0.82rem', whiteSpace: 'pre-wrap' }}>{String(cl.value)}</div>
                    </div>
                  ))}
                </div>

                {/* Citations */}
                <div data-testid="bundle-citations">
                  <h3 style={{ fontSize: '0.9rem' }}>引用來源 Cited sources ({bundle.citation_count})</h3>
                  {bundle.citations.length === 0 && (
                    <div data-testid="no-citations" style={{ color: '#b45309', fontSize: '0.82rem' }}>
                      ⚠ 無引用來源 — 臨床主張須有來源支持
                    </div>
                  )}
                  {bundle.citations.map((c) => <CitationCard key={c.source_id} c={c} />)}
                </div>
              </div>

              <button data-testid="toggle-yaml" onClick={() => setShowYaml((v) => !v)} style={{ marginTop: '0.75rem' }}>
                {showYaml ? '隱藏 YAML' : '顯示原始 YAML'}
              </button>
              {showYaml && (
                <pre data-testid="bundle-yaml" style={{ background: '#f8fafc', padding: '0.75rem', overflow: 'auto', fontSize: '0.74rem', maxHeight: 320 }}>
                  {bundle.raw_yaml}
                </pre>
              )}

              {/* Sign-off */}
              <div style={{ marginTop: '1rem', borderTop: '1px solid #e5e7eb', paddingTop: '0.75rem' }}>
                <h3 style={{ fontSize: '0.9rem' }}>簽核 Sign-off</h3>
                {!canSign && (
                  <div data-testid="review-readonly" style={{ color: '#64748b', fontSize: '0.8rem' }}>
                    審核者唯讀 auditor (read-only)
                  </div>
                )}
                {canSign && (
                  <>
                    <textarea
                      data-testid="signoff-passage"
                      value={passage}
                      onChange={(e) => setPassage(e.target.value)}
                      placeholder="已核對之原文段落 / 出處 (verified passage / locator)…"
                      rows={2}
                      style={{ width: '100%', marginBottom: 4 }}
                    />
                    <textarea
                      data-testid="signoff-comment"
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="審核意見 comment…"
                      rows={2}
                      style={{ width: '100%', marginBottom: 4 }}
                    />
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button data-testid="signoff-approve" onClick={() => signoff('approve')}>核准 Approve</button>
                      <button data-testid="signoff-request-changes" onClick={() => signoff('request_changes')}>要求修改</button>
                      <button data-testid="signoff-reject" onClick={() => signoff('reject')}>拒絕 Reject</button>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
