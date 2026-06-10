import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

interface TrackResponse {
  track_id: string
  label: string
  label_en?: string | null
  is_default: boolean
  indication_id: string
  regimen_id?: string | null
  regimen_name?: string | null
  evidence_level?: string | null
  nccn_category?: string | null
  median_os_months?: number | null
  selection_reason?: string | null
}

interface GapItem {
  field: string
  tier: number
  rationale: string
  if_positive_changes_to?: string | null
  recommended_test?: string | null
}

interface PlanResponse {
  plan_id: string
  disease_id: string
  algorithm_id?: string | null
  tracks: TrackResponse[]
  gaps: GapItem[]
  warnings: string[]
}

function trackBorderColor(trackId: string, label_en?: string | null): string {
  const id = trackId.toLowerCase()
  const en = (label_en ?? '').toLowerCase()
  if (id.includes('standard') || en.includes('standard')) return '#1e40af'
  if (id.includes('aggressive') || en.includes('aggressive')) return '#c2410c'
  return '#6b7280'
}

export function PatientOncologyPage() {
  const { mrn } = useParams<{ mrn: string }>()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [warningsOpen, setWarningsOpen] = useState(false)

  useEffect(() => {
    if (!mrn) return
    const planId = `PLAN-${mrn.toUpperCase()}-V1`
    const ctrl = new AbortController()
    setLoading(true)
    fetch(`/api/v1/plan/${planId}`, { credentials: 'include', signal: ctrl.signal })
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null }
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => { if (data) setPlan(data as PlanResponse) })
      .catch((e: unknown) => {
        if (e instanceof Error && e.name === 'AbortError') return
        setNotFound(true)
      })
      .finally(() => setLoading(false))
    return () => ctrl.abort()
  }, [mrn])

  if (loading) {
    return <div data-testid="onco-loading" style={{ padding: '2rem', color: '#6b7280' }}>載入中…</div>
  }

  if (notFound || !plan) {
    return (
      <div style={{ padding: '2rem' }}>
        <p style={{ color: '#6b7280', marginBottom: '1rem' }}>尚未產生計畫</p>
        <button onClick={() => navigate(`/patients/${mrn}`)} style={{ fontSize: '0.9rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6, padding: '0.4rem 0.75rem', cursor: 'pointer' }}>
          ← 返回
        </button>
      </div>
    )
  }

  const planId = `PLAN-${mrn!.toUpperCase()}-V1`
  const sortedTracks = [...plan.tracks].sort((a, b) => (b.is_default ? 1 : 0) - (a.is_default ? 1 : 0))

  return (
    <div data-testid="onco-page" style={{ padding: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', paddingBottom: '1rem', borderBottom: '1px solid #e5e7eb' }}>
        <button
          data-testid="onco-back-btn"
          onClick={() => navigate(`/patients/${mrn}`)}
          style={{ fontSize: '0.875rem', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 6, padding: '0.35rem 0.75rem', cursor: 'pointer' }}
        >
          ← 返回
        </button>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e3a8a', margin: 0 }}>
          {mrn} — OpenOnco 分析報告
        </h1>
      </div>

      {/* Meta */}
      <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1.5rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        <span>疾病：<strong style={{ color: '#111827' }}>{plan.disease_id}</strong></span>
        {plan.algorithm_id && (
          <span>演算法：<strong style={{ color: '#111827' }}>{plan.algorithm_id}</strong></span>
        )}
        <span>計畫 ID：<code style={{ fontFamily: 'monospace', background: '#f3f4f6', padding: '0 0.3rem', borderRadius: 3 }}>{plan.plan_id}</code></span>
      </div>

      {/* Track cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
        {sortedTracks.map((track) => {
          const borderColor = trackBorderColor(track.track_id, track.label_en)
          return (
            <div
              key={track.track_id}
              data-testid="track-card"
              style={{
                border: `2px solid ${borderColor}`,
                borderRadius: 8,
                padding: '1rem 1.25rem',
                background: '#fff',
                boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                <strong style={{ fontSize: '1rem', color: '#111827' }}>
                  {track.label_en ?? track.label}
                </strong>
                {track.is_default && (
                  <span style={{ fontSize: '0.75rem', background: '#fef9c3', color: '#854d0e', border: '1px solid #fde68a', borderRadius: 4, padding: '1px 6px', fontWeight: 600 }}>
                    ★ 建議
                  </span>
                )}
              </div>
              {track.label_en && track.label !== track.label_en && (
                <div style={{ fontSize: '0.82rem', color: '#6b7280', marginBottom: '0.35rem' }}>{track.label}</div>
              )}
              {track.regimen_name && (
                <div style={{ fontSize: '0.875rem', color: '#374151', marginBottom: '0.35rem' }}>
                  方案：<strong>{track.regimen_name}</strong>
                </div>
              )}
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.8rem', color: '#6b7280' }}>
                {track.evidence_level && (
                  <span>證據等級：<strong style={{ color: '#111827' }}>{track.evidence_level}</strong></span>
                )}
                {track.nccn_category && (
                  <span>NCCN：<strong style={{ color: '#111827' }}>{track.nccn_category}</strong></span>
                )}
                {track.median_os_months != null && (
                  <span>中位 OS：<strong style={{ color: '#111827' }}>{track.median_os_months} 個月</strong></span>
                )}
              </div>
              {track.selection_reason && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#374151', background: '#f9fafb', padding: '0.4rem 0.6rem', borderRadius: 4 }}>
                  {track.selection_reason}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Gaps section */}
      {plan.gaps.length > 0 && (
        <div data-testid="gaps-section" style={{ marginBottom: '1.5rem', border: '1px solid #fde68a', borderRadius: 8, padding: '1rem 1.25rem', background: '#fffbeb' }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#92400e', marginBottom: '0.75rem' }}>
            決策缺口 — 建議補充檢查
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {plan.gaps.map((gap) => (
              <div key={gap.field} style={{ fontSize: '0.85rem', color: '#374151', padding: '0.4rem 0.6rem', background: '#fff', borderRadius: 4, border: '1px solid #fde68a' }}>
                <strong style={{ color: '#111827' }}>{gap.field}</strong>
                <span style={{ marginLeft: '0.5rem', color: '#6b7280' }}>({gap.rationale})</span>
                {gap.recommended_test && (
                  <span style={{ marginLeft: '0.5rem', color: '#1e40af', fontStyle: 'italic' }}>→ {gap.recommended_test}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings section */}
      {plan.warnings.length > 0 && (
        <div style={{ marginBottom: '1.5rem', border: '1px solid #fca5a5', borderRadius: 8, background: '#fef2f2' }}>
          <button
            onClick={() => setWarningsOpen((v) => !v)}
            style={{ width: '100%', textAlign: 'left', padding: '0.75rem 1.25rem', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.875rem', fontWeight: 600, color: '#991b1b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          >
            <span>警告 ({plan.warnings.length})</span>
            <span style={{ fontSize: '0.75rem' }}>{warningsOpen ? '▲ 收起' : '▼ 展開'}</span>
          </button>
          {warningsOpen && (
            <div style={{ padding: '0 1.25rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {plan.warnings.map((w, i) => (
                <div key={i} style={{ fontSize: '0.82rem', color: '#7f1d1d', background: '#fff', borderRadius: 4, padding: '0.3rem 0.5rem', border: '1px solid #fca5a5' }}>
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* PDF button */}
      <div>
        <a
          data-testid="plan-pdf-btn"
          href={`/api/v1/plan/${planId}/pdf`}
          download={`${planId}.pdf`}
          style={{ display: 'inline-block', fontSize: '0.82rem', background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '0.35rem 0.75rem', color: '#166534', textDecoration: 'none', cursor: 'pointer' }}
        >
          下載 PDF
        </a>
      </div>
    </div>
  )
}
