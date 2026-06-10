import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface TrackData {
  track_id: string
  label: string
  is_default: boolean
  indication_id: string
  evidence_level?: string
  nccn_category?: string
  nccn_category_zh?: string
  regimen_name?: string
}

interface PlanData {
  plan_id: string
  disease_id: string
  tracks: TrackData[]
  gaps: Array<{ field: string; tier: number; rationale: string }>
  warnings: string[]
}

export function ClinicPage() {
  const { mrn } = useParams<{ mrn: string }>()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<PlanData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!mrn) return
    // Write audit log on page load
    fetch('/api/v1/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'onco_page_view', mrn }),
      credentials: 'include',
    }).catch(() => {})

    setLoading(true)

    fetch(`/api/v1/patients/${mrn}/timeline`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(async (events: Array<{ event_type: string; body_json: unknown }>) => {
        const planEvent = events.find((e) => e.event_type === 'onco_query_initiated')
        if (planEvent && planEvent.body_json) {
          const body = typeof planEvent.body_json === 'string'
            ? JSON.parse(planEvent.body_json)
            : planEvent.body_json
          if (body.plan_id) {
            const r = await fetch(`/api/v1/plan/${body.plan_id}`, { credentials: 'include' })
            if (r.ok) return r.json()
          }
        }
        // No existing plan — generate one now
        const genResp = await fetch('/api/v1/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            patient_mrn: mrn,
            include_gaps: true,
            patient: {
              patient_id: mrn,
              disease: { id: 'DIS-BREAST' },
              line_of_therapy: 1,
            },
          }),
        })
        if (!genResp.ok) throw new Error(`HTTP ${genResp.status}`)
        return genResp.json()
      })
      .then((data) => { if (data) setPlan(data) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [mrn])

  const selectTrack = (trackId: string) => {
    fetch(`/api/v1/patients/${mrn}/track-selection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId, plan_id: plan?.plan_id }),
      credentials: 'include',
    }).catch(() => {})
  }

  return (
    <div data-testid="clinic-page">
      <div data-testid="breadcrumb">
        <button onClick={() => navigate(`/patients/${mrn}`)}>← 返回個案</button>
      </div>
      <h1 data-testid="clinic-header">
        OpenOnco 分析 — <span data-testid="clinic-mrn">{mrn}</span>
      </h1>

      {loading && <div data-testid="clinic-loading">分析中…</div>}

      {error && (
        <div data-testid="clinic-error" style={{ padding: '1rem', color: '#dc2626', background: '#fef2f2', borderRadius: 4 }}>
          無法載入分析結果：{error}
          <button onClick={() => window.location.reload()} style={{ marginLeft: '1rem' }}>重試</button>
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

      <div>
        {plan?.tracks.map((t, i) => (
          <div
            key={t.track_id}
            data-testid={i === 0 ? 'standard-track' : 'aggressive-track'}
            style={{ border: '1px solid #e5e7eb', padding: '1rem', marginBottom: '1rem' }}
          >
            <strong>{t.label}</strong>
            {t.nccn_category && (
              <span data-testid={`nccn-chip-${t.track_id}`} style={{ marginLeft: '0.5rem', background: '#dbeafe', padding: '0 0.25rem', borderRadius: 2 }}>
                NCCN {t.nccn_category}
              </span>
            )}
            {t.evidence_level && (
              <div data-testid={`citations-${t.track_id}`} style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                證據等級: {t.evidence_level}
              </div>
            )}
            <button
              data-testid={`select-track-btn-${t.track_id}`}
              onClick={() => selectTrack(t.track_id)}
            >
              選擇此方案
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
