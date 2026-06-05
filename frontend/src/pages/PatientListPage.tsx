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
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`/api/v1/patients?tab=${tab}`, { credentials: 'include' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
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
  }, [tab])

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
                <td data-testid={`mrn-${p.mrn}`}>{p.mrn}</td>
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
    </div>
  )
}
