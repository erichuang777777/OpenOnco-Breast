import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface TrackOption {
  track_id: string
  label: string
  regimen_name?: string
  nccn_category?: string
}

type SubmitState = 'idle' | 'submitting' | 'done' | 'error'

export function DrugReqPage() {
  const { mrn } = useParams<{ mrn: string }>()
  const navigate = useNavigate()
  const [tracks, setTracks] = useState<TrackOption[]>([])
  const [planId, setPlanId] = useState<string | null>(null)
  const [trackId, setTrackId] = useState('')
  const [submitState, setSubmitState] = useState<SubmitState>('idle')
  const [reqId, setReqId] = useState<string | null>(null)  // DB id for preview URL
  const [reqCode, setReqCode] = useState<string | null>(null) // human-readable code
  const [loadError, setLoadError] = useState<string | null>(null)
  const [patientInfo, setPatientInfo] = useState<{ nameInitials: string; birthYear: string; sex: string }>({ nameInitials: '', birthYear: '', sex: '' })

  useEffect(() => {
    if (!mrn) return
    fetch(`/api/v1/patients/${mrn}`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : null)
      .then((p) => {
        if (p) setPatientInfo({
          nameInitials: p.masked_name ?? '',
          birthYear: p.dob_year ? String(p.dob_year) : '',
          sex: p.sex ?? '',
        })
      })
      .catch(() => {})
  }, [mrn])

  // Load plan tracks from the patient's most recent onco_query_initiated timeline event
  useEffect(() => {
    if (!mrn) return
    fetch(`/api/v1/patients/${mrn}/timeline`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(async (events: Array<{ event_type: string; body_json: unknown }>) => {
        const planEvent = events.find((e) => e.event_type === 'onco_query_initiated')
        if (!planEvent?.body_json) throw new Error('尚未生成治療計畫')
        const body = typeof planEvent.body_json === 'string'
          ? JSON.parse(planEvent.body_json) : planEvent.body_json
        if (!body.plan_id) throw new Error('找不到 plan_id')
        const r = await fetch(`/api/v1/plan/${body.plan_id}`, { credentials: 'include' })
        if (!r.ok) throw new Error(`無法載入計畫 (HTTP ${r.status})`)
        const plan = await r.json()
        setPlanId(plan.plan_id)
        setTracks((plan.tracks ?? []).map((t: TrackOption) => t))
        if (plan.tracks?.length > 0) setTrackId(plan.tracks[0].track_id)
      })
      .catch((e: Error) => setLoadError(e.message))
  }, [mrn])

  const submit = () => {
    if (!trackId || !planId) return
    setSubmitState('submitting')
    fetch('/api/v1/drug-requisition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plan_id: planId,
        track_id: trackId,
        patient_mrn: mrn,
        patient_name_initials: patientInfo.nameInitials,
        patient_birth_year: patientInfo.birthYear,
        patient_sex: patientInfo.sex,
      }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((data) => { setReqId(data.id); setReqCode(data.requisition_id); setSubmitState('done') })
      .catch(() => setSubmitState('error'))
  }

  const selectedTrack = tracks.find((t) => t.track_id === trackId)

  return (
    <div data-testid="drug-req-page">
      <button onClick={() => navigate(`/patients/${mrn}`)} style={{ marginBottom: '1rem' }}>← 返回個案</button>
      <h1>藥物申請</h1>
      <div data-testid="patient-info" style={{ marginBottom: '1rem', color: '#6b7280' }}>病歷號: {mrn}</div>

      {loadError && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 6, padding: '0.75rem', marginBottom: '1rem', color: '#dc2626' }}>
          {loadError} —{' '}
          <button onClick={() => navigate(`/patients/${mrn}/onco`)} style={{ textDecoration: 'underline', background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer' }}>
            先執行 OpenOnco 分析
          </button>
        </div>
      )}

      {!loadError && tracks.length === 0 && !loadError && (
        <div style={{ color: '#6b7280' }}>載入治療方案中…</div>
      )}

      {tracks.length > 0 && submitState !== 'done' && (
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>選擇治療方案</label>
          <select
            data-testid="track-select"
            value={trackId}
            onChange={(e) => setTrackId(e.target.value)}
            style={{ width: '100%', padding: '0.5rem', marginBottom: '1rem', border: '1px solid #d1d5db', borderRadius: 4 }}
          >
            {tracks.map((t) => (
              <option key={t.track_id} value={t.track_id}>
                {t.label}{t.regimen_name ? ` — ${t.regimen_name}` : ''}{t.nccn_category ? ` [NCCN ${t.nccn_category}]` : ''}
              </option>
            ))}
          </select>

          {selectedTrack && (
            <div data-testid="track-name" style={{ background: '#eff6ff', borderRadius: 6, padding: '0.75rem', marginBottom: '1rem' }}>
              <strong>{selectedTrack.label}</strong>
              {selectedTrack.regimen_name && <div style={{ fontSize: '0.9rem', color: '#4b5563' }}>{selectedTrack.regimen_name}</div>}
              {selectedTrack.nccn_category && <div style={{ fontSize: '0.85rem', color: '#2563eb' }}>NCCN 類別 {selectedTrack.nccn_category}</div>}
            </div>
          )}

          <button
            data-testid="submit-drug-req-btn"
            onClick={submit}
            disabled={submitState === 'submitting' || !trackId}
            style={{ padding: '0.5rem 1.5rem' }}
          >
            {submitState === 'submitting' ? '提交中…' : '提交申請'}
          </button>

          {submitState === 'error' && (
            <div style={{ color: '#dc2626', marginTop: '0.5rem' }}>提交失敗，請重試</div>
          )}
        </div>
      )}

      {submitState === 'done' && (
        <div data-testid="status-submitted" style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>✓</div>
          <strong>申請已提交</strong>
          {reqCode && <div style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem' }}>申請編號：{reqCode}</div>}
          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
            <button onClick={() => navigate(`/patients/${mrn}`)}>返回個案</button>
            {reqId && (
              <button onClick={() => window.open(`/api/v1/drug-requisition/${reqId}/preview`, '_blank')}>
                列印申請單
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
