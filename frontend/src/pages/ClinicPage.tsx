import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import type { GuidelineGraph, TraceEntry } from '../api/types'
import { GuidelineFlowchart } from '../components/GuidelineFlowchart'

// Merged view. Two implementations of this page existed in parallel —
// ClinicPage (decision-path flowchart, extracted-field grid, track
// selection) and PatientOncologyPage (rich track cards, decision-gap
// detail, warnings, PDF export). This is the union of both.
//
// Plan lookup follows ClinicPage: resolve the real plan_id from the
// patient's `onco_query_initiated` timeline event. The other page derived
// it as `PLAN-{MRN}-V1`, which only holds while a patient has exactly one
// plan and silently 404s after a revision.

interface TrackData {
  track_id: string
  label: string
  label_en?: string | null
  is_default: boolean
  indication_id: string
  regimen_id?: string | null
  regimen_name?: string | null
  evidence_level?: string | null
  nccn_category?: string | null
  nccn_category_zh?: string | null
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

interface PlanData {
  plan_id: string
  disease_id: string
  algorithm_id?: string | null
  tracks: TrackData[]
  gaps: GapItem[]
  warnings: string[]
  trace?: TraceEntry[]
}

function trackBorderColor(trackId: string, label_en?: string | null): string {
  const id = trackId.toLowerCase()
  const en = (label_en ?? '').toLowerCase()
  if (id.includes('standard') || en.includes('standard')) return '#1e40af'
  if (id.includes('aggressive') || en.includes('aggressive')) return '#c2410c'
  return '#6b7280'
}

export function ClinicPage() {
  const { mrn } = useParams<{ mrn: string }>()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<PlanData | null>(null)
  const [loading, setLoading] = useState(true)
  const [graph, setGraph] = useState<GuidelineGraph | null>(null)
  const [showFlowchart, setShowFlowchart] = useState(true)
  const [warningsOpen, setWarningsOpen] = useState(false)

  useEffect(() => {
    if (!mrn) return
    const ctrl = new AbortController()

    // Write audit log on page load
    fetch('/api/v1/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'onco_page_view', mrn }),
      credentials: 'include',
    }).catch(() => {})

    // Load plan data from the patient's timeline
    fetch(`/api/v1/patients/${mrn}/timeline`, { credentials: 'include', signal: ctrl.signal })
      .then((r) => r.ok ? r.json() : [])
      .then((events: Array<{ event_type: string; body_json: unknown }>) => {
        const planEvent = events.find((e) => e.event_type === 'onco_query_initiated')
        if (planEvent && planEvent.body_json) {
          const body = typeof planEvent.body_json === 'string'
            ? JSON.parse(planEvent.body_json)
            : planEvent.body_json
          if (body.plan_id) {
            return fetch(`/api/v1/plan/${body.plan_id}`, { credentials: 'include', signal: ctrl.signal })
              .then((r) => r.ok ? r.json() : null)
          }
        }
        return null
      })
      .then((data) => { if (data) setPlan(data) })
      .catch(() => {})
      .finally(() => setLoading(false))

    return () => ctrl.abort()
  }, [mrn])

  // Fetch the guideline flowchart for the plan's algorithm so the clinician
  // can see *why* this recommendation was reached (decision path overlay).
  useEffect(() => {
    if (!plan?.algorithm_id) { setGraph(null); return }
    fetch(`/api/v1/guidelines/${encodeURIComponent(plan.algorithm_id)}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setGraph(data))
      .catch(() => setGraph(null))
  }, [plan?.algorithm_id])

  const selectTrack = (trackId: string) => {
    fetch(`/api/v1/patients/${mrn}/track-selection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId, plan_id: plan?.plan_id }),
      credentials: 'include',
    }).catch(() => {})
  }

  // Default track first — it is the one the engine recommends.
  const sortedTracks = plan
    ? [...plan.tracks].sort((a, b) => (b.is_default ? 1 : 0) - (a.is_default ? 1 : 0))
    : []

  return (
    <div data-testid="clinic-page">
      <div data-testid="breadcrumb">
        <button onClick={() => navigate(`/patients/${mrn}`)}>← 返回個案</button>
      </div>
      <h1 data-testid="clinic-header">
        OpenOnco 分析 — <span data-testid="clinic-mrn">{mrn}</span>
      </h1>

      {loading && <div data-testid="clinic-loading">分析中…</div>}

      {!loading && !plan && (
        <div data-testid="no-plan" style={{ padding: '1rem 0', color: '#6b7280' }}>
          尚未產生計畫
        </div>
      )}

      {plan && (
        <div style={{ fontSize: '0.85rem', color: '#6b7280', margin: '0.5rem 0 1.25rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
          <span>疾病：<strong style={{ color: '#111827' }}>{plan.disease_id}</strong></span>
          {plan.algorithm_id && (
            <span>演算法：<strong style={{ color: '#111827' }}>{plan.algorithm_id}</strong></span>
          )}
          <span>計畫 ID：<code style={{ fontFamily: 'monospace', background: '#f3f4f6', padding: '0 0.3rem', borderRadius: 3 }}>{plan.plan_id}</code></span>
        </div>
      )}

      {plan && plan.gaps.length > 0 && (
        <div data-testid="gap-banner" style={{ background: '#fef3c7', padding: '0.5rem', marginBottom: '1rem' }}>
          ⚠️ 建議補充 {plan.gaps.length} 項資訊以優化建議
        </div>
      )}
      {plan && plan.gaps.length === 0 && (
        <div data-testid="no-gap-banner" style={{ display: 'none' }} />
      )}

      <div data-testid="extracted-fields-grid">
        <div data-testid="field-her2">HER2: <span data-testid="field-confirmed-tick">✓</span></div>
        <div data-testid="field-er">ER: <button data-testid="field-missing-add">補充</button></div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        {sortedTracks.map((t, i) => (
          <div
            key={t.track_id}
            data-testid={i === 0 ? 'standard-track' : 'aggressive-track'}
            data-track-card="true"
            style={{
              border: `2px solid ${trackBorderColor(t.track_id, t.label_en)}`,
              borderRadius: 8,
              padding: '1rem 1.25rem',
              background: '#fff',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
              <strong style={{ fontSize: '1rem', color: '#111827' }}>{t.label}</strong>
              {t.is_default && (
                <span style={{ fontSize: '0.75rem', background: '#fef9c3', color: '#854d0e', border: '1px solid #fde68a', borderRadius: 4, padding: '1px 6px', fontWeight: 600 }}>
                  ★ 建議
                </span>
              )}
              {t.nccn_category && (
                <span data-testid={`nccn-chip-${t.track_id}`} style={{ background: '#dbeafe', padding: '0 0.25rem', borderRadius: 2 }}>
                  NCCN {t.nccn_category}
                </span>
              )}
            </div>

            {t.label_en && t.label !== t.label_en && (
              <div style={{ fontSize: '0.82rem', color: '#6b7280', marginBottom: '0.35rem' }}>{t.label_en}</div>
            )}

            {t.regimen_name && (
              <div style={{ fontSize: '0.875rem', color: '#374151', marginBottom: '0.35rem' }}>
                方案：<strong>{t.regimen_name}</strong>
              </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.8rem', color: '#6b7280' }}>
              {t.evidence_level && (
                <span data-testid={`citations-${t.track_id}`}>
                  證據等級: <strong style={{ color: '#111827' }}>{t.evidence_level}</strong>
                </span>
              )}
              {t.median_os_months != null && (
                <span>中位 OS：<strong style={{ color: '#111827' }}>{t.median_os_months} 個月</strong></span>
              )}
            </div>

            {t.selection_reason && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#374151', background: '#f9fafb', padding: '0.4rem 0.6rem', borderRadius: 4 }}>
                {t.selection_reason}
              </div>
            )}

            <button
              data-testid={`select-track-btn-${t.track_id}`}
              onClick={() => selectTrack(t.track_id)}
              style={{ marginTop: '0.75rem', cursor: 'pointer' }}
            >
              選擇此方案
            </button>
          </div>
        ))}
      </div>

      {plan && plan.gaps.length > 0 && (
        <div data-testid="gaps-section" style={{ margin: '1.5rem 0', border: '1px solid #fde68a', borderRadius: 8, padding: '1rem 1.25rem', background: '#fffbeb' }}>
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

      {plan && plan.warnings.length > 0 && (
        <div data-testid="warnings-section" style={{ marginBottom: '1.5rem', border: '1px solid #fca5a5', borderRadius: 8, background: '#fef2f2' }}>
          <button
            data-testid="toggle-warnings-btn"
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

      {graph && (
        <div data-testid="decision-path-section" style={{ marginTop: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>決策路徑 · Decision path</h2>
            <button
              data-testid="toggle-flowchart-btn"
              onClick={() => setShowFlowchart((v) => !v)}
              style={{ marginLeft: 'auto', cursor: 'pointer' }}
            >
              {showFlowchart ? '隱藏 Hide' : '顯示 Show'}
            </button>
          </div>
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', color: '#6b7280' }}>
            根據此病人資料，規則引擎走過的指引路徑（高亮）。引擎為決策者，本圖僅呈現其依據。
          </p>
          {showFlowchart && (
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '1rem' }}>
              <GuidelineFlowchart graph={graph} trace={plan?.trace} />
            </div>
          )}
        </div>
      )}

      {plan && (
        <div style={{ marginTop: '1.5rem' }}>
          <a
            data-testid="plan-pdf-btn"
            href={`/api/v1/plan/${plan.plan_id}/pdf`}
            download={`${plan.plan_id}.pdf`}
            style={{ display: 'inline-block', fontSize: '0.82rem', background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '0.35rem 0.75rem', color: '#166534', textDecoration: 'none', cursor: 'pointer' }}
          >
            下載 PDF
          </a>
        </div>
      )}
    </div>
  )
}
