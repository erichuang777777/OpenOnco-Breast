import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PatientResponse } from '../api/types'

const TABS = [
  { key: 'all', label: '全部' },
  { key: 'followup', label: '待追蹤' },
  { key: 'consulted', label: '被諮詢' },
  { key: 'mtd', label: '待MTD' },
  { key: 'alerts', label: '警示' },
]

interface PatientStats {
  total: number
  urgent: number
  followup: number
  mtd: number
}

function ReminderDot({ urgency }: { urgency: 'urgent' | 'warn' | 'none' }) {
  if (urgency === 'urgent')
    return <span data-testid="reminder-dot-urgent" style={{ color: 'red' }}>●</span>
  if (urgency === 'warn')
    return <span data-testid="reminder-dot-warn" style={{ color: '#f59e0b' }}>●</span>
  return null
}

function HisBadge({ status }: { status?: string }) {
  if (!status || status === 'unknown') return null
  const cfg = {
    ok:    { color: '#16a34a', label: 'HIS ✓' },
    stale: { color: '#d97706', label: 'HIS ⚠' },
    never: { color: '#9ca3af', label: 'HIS —' },
  }[status] ?? null
  if (!cfg) return null
  return (
    <span data-testid={`his-badge-${status}`} style={{ fontSize: '0.75rem', color: cfg.color, marginLeft: '0.25rem', fontWeight: 500 }}>
      {cfg.label}
    </span>
  )
}

function dotUrgency(p: PatientResponse): 'urgent' | 'warn' | 'none' {
  if (!p.urgent_reminder_count) return 'none'
  return p.urgent_reminder_count > 0 ? 'urgent' : 'warn'
}

// ── FHIR import modal ─────────────────────────────────────────────────────────

function FhirImportModal({ onClose, onImported }: { onClose: () => void; onImported: (mrn: string) => void }) {
  const [json, setJson] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setError(null)
    let resource: unknown
    try { resource = JSON.parse(json) } catch { setError('JSON 格式錯誤'); return }
    setLoading(true)
    try {
      const res = await fetch('/api/v1/fhir/Patient/$import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ resource }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: { message?: string } }
        setError(body?.detail?.message ?? `HTTP ${res.status}`)
      } else {
        const result = await res.json() as { mrn: string; action: string }
        onImported(result.mrn)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '匯入失敗')
    } finally {
      setLoading(false)
    }
  }

  const placeholder = JSON.stringify({
    resourceType: 'Patient',
    id: 'twcore-001',
    identifier: [{ type: { coding: [{ system: 'http://terminology.hl7.org/CodeSystem/v2-0203', code: 'MR' }] }, value: 'MRN-FHIR-001' }],
    name: [{ use: 'official', text: '王大明' }],
    gender: 'male',
    birthDate: '1971',
  }, null, 2)

  return (
    <div data-testid="fhir-import-modal" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div style={{ background: '#fff', borderRadius: 8, padding: '1.5rem', maxWidth: 560, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.18)' }}>
        <h2 style={{ margin: '0 0 0.75rem', color: '#1e3a8a', fontSize: '1.1rem' }}>匯入 FHIR TW Core 病患資料</h2>
        <p style={{ fontSize: '0.82rem', color: '#6b7280', marginBottom: '0.75rem' }}>
          貼上符合 TW Core 規範的 FHIR R4 Patient 資源（或含有 Patient 的 Bundle）。
          姓名將自動遮蔽，僅保留第一字。
        </p>
        <textarea
          data-testid="fhir-json-input"
          value={json}
          onChange={e => setJson(e.target.value)}
          placeholder={placeholder}
          rows={10}
          style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.78rem', border: '1px solid #d1d5db', borderRadius: 4, padding: '0.5rem', boxSizing: 'border-box' }}
        />
        {error && <p data-testid="fhir-error" style={{ color: '#dc2626', fontSize: '0.85rem', margin: '0.5rem 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '0.4rem 0.9rem', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 6, cursor: 'pointer' }}>取消</button>
          <button
            data-testid="fhir-submit-btn"
            onClick={submit}
            disabled={loading || !json.trim()}
            style={{ padding: '0.4rem 0.9rem', background: '#1e40af', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', opacity: loading || !json.trim() ? 0.6 : 1 }}
          >
            {loading ? '匯入中…' : '確認匯入'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function PatientListPage() {
  const [tab, setTab] = useState('all')
  const [patients, setPatients] = useState<PatientResponse[]>([])
  const [stats, setStats] = useState<PatientStats>({ total: 0, urgent: 0, followup: 0, mtd: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [showFhirImport, setShowFhirImport] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    setCurrentPage(0)
  }, [tab, debouncedQ])

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`/api/v1/patients?tab=${tab}&q=${debouncedQ}&limit=20&offset=${currentPage * 20}`, { credentials: 'include' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const totalCount = r.headers.get('X-Total-Count')
        if (totalCount !== null) setTotal(parseInt(totalCount, 10))
        return r.json()
      })
      .then((data: PatientResponse[]) => {
        setPatients(data)
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [tab, debouncedQ, currentPage])

  useEffect(() => {
    fetch('/api/v1/patients/stats', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setStats(data) })
      .catch(() => {})
  }, [])

  return (
    <div data-testid="patient-list-page">
      {/* Stat cards */}
      <div style={{ display: 'flex', gap: '1rem', padding: '1rem' }}>
        <div data-testid="stat-total">總患者: {stats.total}</div>
        <div data-testid="stat-urgent">緊急: {stats.urgent}</div>
        <div data-testid="stat-followup">追蹤: {stats.followup}</div>
        <div data-testid="stat-mtd">MTD: {stats.mtd}</div>
      </div>

      {/* Search + FHIR import */}
      <div style={{ padding: '0 1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input
          data-testid="search-input"
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(0) }}
          placeholder="搜尋病歷號、姓名、診斷…"
          style={{ padding: '0.5rem', flex: 1, marginBottom: '0.5rem', border: '1px solid #d1d5db', borderRadius: 4 }}
        />
        <button
          data-testid="fhir-import-btn"
          onClick={() => setShowFhirImport(true)}
          style={{ padding: '0.5rem 0.75rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem', whiteSpace: 'nowrap', marginBottom: '0.5rem' }}
        >
          FHIR 匯入
        </button>
      </div>
      {showFhirImport && (
        <FhirImportModal
          onClose={() => setShowFhirImport(false)}
          onImported={(mrn) => { setShowFhirImport(false); navigate(`/patients/${mrn}`) }}
        />
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', padding: '0 1rem' }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`tab-${t.key}`}
            onClick={() => setTab(t.key)}
            aria-selected={tab === t.key}
            style={{
              fontWeight: tab === t.key ? 'bold' : 'normal',
              borderBottom: tab === t.key ? '2px solid #1e40af' : 'none',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0.5rem',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading && <div data-testid="loading-state">載入中…</div>}
      {error && <div data-testid="error-state">錯誤: {error}</div>}
      {!loading && !error && patients.length === 0 && (
        <div data-testid="empty-state">目前沒有患者</div>
      )}
      {!loading && !error && patients.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th data-testid="col-mrn">病歷號</th>
              <th data-testid="col-name">姓名</th>
              <th data-testid="col-disease">診斷</th>
              <th data-testid="col-status">狀態</th>
              <th data-testid="col-care">照護</th>
              <th>提醒</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr
                key={p.mrn}
                data-testid={`row-${p.mrn}`}
                onClick={() => navigate(`/patients/${p.mrn}`)}
                style={{
                  cursor: 'pointer',
                  background: p.his_patient_id ? '#f0f9ff' : undefined,
                }}
              >
                <td data-testid={`mrn-${p.mrn}`}>
                  {p.mrn}
                  <HisBadge status={p.his_sync_status} />
                </td>
                <td data-testid={`name-${p.mrn}`}>{p.masked_name}</td>
                <td data-testid={`disease-${p.mrn}`}>{p.disease_summary}</td>
                <td>
                  <span data-testid={`status-chip-${p.mrn}`}>{p.status}</span>
                </td>
                <td data-testid={`care-${p.mrn}`}>
                  {p.care_team.length > 0 ? `${p.care_team.length} 位` : '—'}
                </td>
                <td>
                  <ReminderDot urgency={dotUrgency(p)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      <div data-testid="pagination" style={{ display: 'flex', gap: '1rem', padding: '1rem', alignItems: 'center' }}>
        <button
          data-testid="prev-page-btn"
          disabled={currentPage === 0}
          onClick={() => setCurrentPage((p) => p - 1)}
        >上一頁</button>
        <span data-testid="page-info">第 {currentPage + 1} 頁 · 共 {total} 位</span>
        <button
          data-testid="next-page-btn"
          disabled={(currentPage + 1) * 20 >= total}
          onClick={() => setCurrentPage((p) => p + 1)}
        >下一頁</button>
      </div>
    </div>
  )
}
