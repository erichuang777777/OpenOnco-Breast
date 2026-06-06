import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import type { PatientResponse } from '../api/types'
import { FEATURES } from '../config'

const TABS = [
  { key: 'all', label: '全部' },
  { key: 'followup', label: '待追蹤' },
  { key: 'consulted', label: '被諮詢' },
  { key: 'mtd', label: '待MTD' },
  { key: 'alerts', label: '⚠ 警示' },
]

interface PatientStats {
  total: number
  urgent: number
  followup: number
  mtd: number
}

function urgencyColor(p: PatientResponse): string | undefined {
  if (!p.urgent_reminder_count) return undefined
  return p.urgent_reminder_count > 0 ? 'var(--c-danger)' : 'var(--c-warn)'
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    active: 'badge-green',
    followup: 'badge-blue',
    discharged: 'badge-gray',
    critical: 'badge-red',
  }
  return map[status] ?? 'badge-gray'
}

function HisBadge({ status }: { status?: string }) {
  if (!status || status === 'unknown') return null
  const cfg = {
    ok:    { cls: 'badge-green', label: 'HIS ✓' },
    stale: { cls: 'badge-yellow', label: 'HIS ⚠' },
    never: { cls: 'badge-gray', label: 'HIS —' },
  }[status] ?? null
  if (!cfg) return null
  return (
    <span data-testid={`his-badge-${status}`} className={`badge ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
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
    <div data-testid="fhir-import-modal" className="modal-overlay">
      <div className="modal">
        <h2 className="modal-title">匯入 FHIR TW Core 病患資料</h2>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--c-gray-500)', marginBottom: 'var(--sp-4)' }}>
          貼上符合 TW Core 規範的 FHIR R4 Patient 資源（或含有 Patient 的 Bundle）。
          姓名將自動遮蔽，僅保留第一字。
        </p>
        <textarea
          data-testid="fhir-json-input"
          value={json}
          onChange={e => setJson(e.target.value)}
          placeholder={placeholder}
          rows={10}
          className="form-input"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', resize: 'vertical' }}
        />
        {error && <p data-testid="fhir-error" className="form-error" style={{ marginTop: 'var(--sp-2)' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-4)', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onClose}>取消</button>
          <button
            data-testid="fhir-submit-btn"
            className="btn btn-primary"
            onClick={submit}
            disabled={loading || !json.trim()}
          >
            {loading ? '匯入中…' : '確認匯入'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

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

  useEffect(() => { setCurrentPage(0) }, [tab, debouncedQ])

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
      .then((data: PatientResponse[]) => { setPatients(data); setLoading(false) })
      .catch((e: Error) => { setError(e.message); setLoading(false) })
  }, [tab, debouncedQ, currentPage])

  useEffect(() => {
    fetch('/api/v1/patients/stats', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setStats(data) })
      .catch(() => {})
  }, [])

  return (
    <div data-testid="patient-list-page" className="page">
      {/* Page header */}
      <div className="page-header">
        <h1 className="page-title">患者列表</h1>
        {FEATURES.fhirImport && (
          <button
            data-testid="fhir-import-btn"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowFhirImport(true)}
            style={{ marginLeft: 'auto' }}
          >
            ⬆ FHIR 匯入
          </button>
        )}
      </div>

      {/* Stat cards */}
      <div className="stat-cards">
        <div className="stat-card">
          <div data-testid="stat-total" className="stat-card-value">{stats.total}</div>
          <div className="stat-card-label">總患者</div>
        </div>
        <div className="stat-card">
          <div data-testid="stat-urgent" className="stat-card-value" style={{ color: 'var(--c-danger)' }}>{stats.urgent}</div>
          <div className="stat-card-label">緊急提醒</div>
        </div>
        <div className="stat-card">
          <div data-testid="stat-followup" className="stat-card-value">{stats.followup}</div>
          <div className="stat-card-label">待追蹤</div>
        </div>
        <div className="stat-card">
          <div data-testid="stat-mtd" className="stat-card-value">{stats.mtd}</div>
          <div className="stat-card-label">待MTD</div>
        </div>
      </div>

      {/* Search bar */}
      <div className="search-bar">
        <input
          data-testid="search-input"
          className="search-input"
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(0) }}
          placeholder="搜尋病歷號、姓名、診斷…"
        />
      </div>

      {/* Tabs */}
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            data-testid={`tab-${t.key}`}
            className={`tab-btn${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
            aria-selected={tab === t.key}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* States */}
      {loading && <div data-testid="loading-state" className="state-placeholder">載入中…</div>}
      {error && <div data-testid="error-state" className="state-placeholder" style={{ color: 'var(--c-danger)' }}>錯誤: {error}</div>}
      {!loading && !error && patients.length === 0 && (
        <div data-testid="empty-state" className="state-placeholder">目前沒有患者</div>
      )}

      {/* Patient cards */}
      {!loading && !error && patients.length > 0 && (
        <div className="patient-cards">
          {patients.map((p) => (
            <div
              key={p.mrn}
              data-testid={`row-${p.mrn}`}
              className={`patient-card${p.his_patient_id ? ' his-synced' : ''}`}
              onClick={() => navigate(`/patients/${p.mrn}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && navigate(`/patients/${p.mrn}`)}
            >
              <div className="patient-card-header">
                <div>
                  <div data-testid={`mrn-${p.mrn}`} className="patient-card-mrn">{p.mrn}</div>
                  <div data-testid={`name-${p.mrn}`} className="patient-card-name">{p.masked_name}</div>
                </div>
                {p.urgent_reminder_count ? (
                  <span
                    data-testid={p.urgent_reminder_count > 0 ? 'reminder-dot-urgent' : 'reminder-dot-warn'}
                    style={{ color: urgencyColor(p), fontSize: '1.1rem' }}
                  >●</span>
                ) : null}
              </div>

              <div data-testid={`disease-${p.mrn}`} className="patient-card-disease">
                {p.disease_summary ?? <span style={{ color: 'var(--c-gray-300)' }}>—</span>}
              </div>

              <div className="patient-card-footer">
                <span data-testid={`status-chip-${p.mrn}`} className={`badge ${statusBadgeClass(p.status ?? '')}`}>
                  {p.status}
                </span>
                <HisBadge status={p.his_sync_status} />
                {p.care_team.length > 0 && (
                  <span data-testid={`care-${p.mrn}`} className="badge badge-gray">
                    👤 {p.care_team.length}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      <div data-testid="pagination" className="pagination">
        <button
          className="btn btn-secondary btn-sm"
          data-testid="prev-page-btn"
          disabled={currentPage === 0}
          onClick={() => setCurrentPage((p) => p - 1)}
        >上一頁</button>
        <span data-testid="page-info" className="pagination-info">第 {currentPage + 1} 頁 · 共 {total} 位</span>
        <button
          className="btn btn-secondary btn-sm"
          data-testid="next-page-btn"
          disabled={(currentPage + 1) * 20 >= total}
          onClick={() => setCurrentPage((p) => p + 1)}
        >下一頁</button>
      </div>

      {/* FHIR import modal */}
      {showFhirImport && (
        <FhirImportModal
          onClose={() => setShowFhirImport(false)}
          onImported={(mrn) => { setShowFhirImport(false); navigate(`/patients/${mrn}`) }}
        />
      )}
    </div>
  )
}
