import { useParams } from 'react-router-dom'
import { useState } from 'react'

export function DrugReqPage() {
  const { mrn } = useParams<{ mrn: string }>()
  const [trackId, setTrackId] = useState('')
  const [status, setStatus] = useState('draft')

  const submit = () => {
    if (!trackId) return
    fetch(`/api/v1/patients/${mrn}/drug-req`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track_id: trackId, mrn }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setStatus('submitted') })
      .catch(() => {})
  }

  return (
    <div data-testid="drug-req-page">
      <h1>藥物申請</h1>
      <div data-testid="patient-info">病歷號: {mrn}</div>
      <div data-testid="track-name">治療方案: {trackId || '未選擇'}</div>

      <select
        data-testid="track-select"
        value={trackId}
        onChange={(e) => setTrackId(e.target.value)}
      >
        <option value="">選擇治療方案</option>
        <option value="T1">THP 1L</option>
        <option value="T2">EC-THP 1L</option>
      </select>

      <div data-testid={`status-${status}`} style={{ marginTop: '0.5rem', padding: '0.25rem 0.5rem', display: 'inline-block', background: status === 'submitted' ? '#d1fae5' : '#f3f4f6' }}>
        {status === 'draft' ? '草稿' : '已提交'}
      </div>

      <button data-testid="submit-drug-req-btn" onClick={submit}>
        提交申請
      </button>
    </div>
  )
}
