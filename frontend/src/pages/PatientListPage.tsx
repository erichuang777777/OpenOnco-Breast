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

      {/* Search input */}
      <div style={{ padding: '0 1rem' }}>
        <input
          data-testid="search-input"
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(0) }}
          placeholder="搜尋病歷號、姓名、診斷…"
          style={{ padding: '0.5rem', width: '100%', marginBottom: '0.5rem', border: '1px solid #d1d5db', borderRadius: 4 }}
        />
      </div>

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
