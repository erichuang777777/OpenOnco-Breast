import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import type { PatientResponse, TimelineEventResponse, ReminderResponse, ConsultationResponse, MtdSessionResponse } from '../api/types'
import { useToast } from '../hooks/useToast'

function TimelineEvent({ event }: { event: TimelineEventResponse }) {
  const [expanded, setExpanded] = useState(false)
  const styleMap: Record<string, React.CSSProperties> = {
    coordinator_note: { background: '#eff6ff', padding: '0.5rem', borderLeft: '3px solid #3b82f6' },
    doctor_note: { padding: '0.5rem' },
    his_sync: { fontStyle: 'italic', color: '#6b7280', padding: '0.25rem' },
    alert: { background: '#fef3c7', padding: '0.5rem', borderLeft: '3px solid #f59e0b' },
    mtd_conclusion: { background: '#f0fdf4', padding: '0.5rem', borderLeft: '3px solid #16a34a' },
    consultation_reply: { background: '#f5f3ff', padding: '0.5rem', borderLeft: '3px solid #7c3aed' },
  }
  const style = styleMap[event.event_type] ?? { padding: '0.5rem' }
  const hasBody = event.body_json && Object.keys(event.body_json as object).length > 0

  return (
    <div
      data-testid={`timeline-event-${event.id}`}
      data-event-type={event.event_type}
      style={style}
    >
      <strong>{event.title}</strong>
      <span style={{ marginLeft: '0.5rem', color: '#9ca3af', fontSize: '0.8rem' }}>
        {new Date(event.event_time).toLocaleString('zh-TW')}
      </span>
      {hasBody && (
        <button
          data-testid={`expand-event-${event.id}`}
          onClick={() => setExpanded((v) => !v)}
          style={{ marginLeft: '0.5rem', fontSize: '0.75rem', background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer' }}
        >
          {expanded ? '▲' : '▼'}
        </button>
      )}
      {expanded && hasBody && (
        <pre
          data-testid={`event-body-${event.id}`}
          style={{ marginTop: '0.5rem', fontSize: '0.75rem', background: '#f9fafb', padding: '0.5rem', borderRadius: 4, overflow: 'auto' }}
        >
          {JSON.stringify(event.body_json, null, 2)}
        </pre>
      )}
    </div>
  )
}

function RemindersPanel({ mrn }: { mrn: string }) {
  const [reminders, setReminders] = useState<ReminderResponse[]>([])

  useEffect(() => {
    fetch(`/api/v1/patients/${mrn}/reminders?reminder_status=active`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(setReminders)
      .catch(() => {})
  }, [mrn])

  const urgent = reminders.filter((r) => r.urgency === 'high' || r.urgency === 'critical')

  const ack = (id: string) => {
    fetch(`/api/v1/patients/${mrn}/reminders/${id}/acknowledge`, {
      method: 'PATCH', credentials: 'include',
    }).then(() => setReminders((prev) => prev.filter((r) => r.id !== id)))
  }

  return (
    <div data-testid="reminders-panel">
      <h3>提醒 {urgent.length > 0 && <span data-testid="urgent-count-badge">{urgent.length}</span>}</h3>
      {reminders.length === 0 && (
        <div data-testid="reminders-empty" style={{ color: '#9ca3af', fontSize: '0.9rem', padding: '0.5rem 0' }}>目前沒有待處理提醒</div>
      )}
      {reminders.map((r) => (
        <div key={r.id} data-testid={`reminder-${r.reminder_type}`} style={{ padding: '0.5rem', marginBottom: '0.5rem', border: '1px solid #e5e7eb' }}>
          <div>{r.title}</div>
          <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{r.reminder_type}</div>
          <button data-testid={`ack-btn-${r.id}`} onClick={() => ack(r.id)}>確認</button>
        </div>
      ))}
    </div>
  )
}

function ConsultationsPanel({ mrn, openOnMount }: { mrn: string; openOnMount?: boolean }) {
  const [consultations, setConsultations] = useState<ConsultationResponse[]>([])
  const [showForm, setShowForm] = useState(openOnMount ?? false)
  const [toUser, setToUser] = useState('')
  const [subject, setSubject] = useState('')

  useEffect(() => {
    fetch(`/api/v1/patients/${mrn}/consultations`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(setConsultations)
      .catch(() => {})
  }, [mrn])

  useEffect(() => {
    if (openOnMount) setShowForm(true)
  }, [openOnMount])

  const submit = () => {
    if (!toUser || !subject) return
    fetch(`/api/v1/patients/${mrn}/consultations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to_user_id: toUser, subject }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((c) => { if (c) setConsultations((prev) => [c, ...prev]); setShowForm(false); setToUser(''); setSubject('') })
  }

  return (
    <div data-testid="consultations-panel">
      <h3>諮詢</h3>
      {consultations.filter((c) => c.status !== 'closed').map((c) => (
        <div key={c.id} data-testid={`consult-${c.status}`} style={{ padding: '0.5rem', border: '1px solid #e5e7eb', marginBottom: '0.5rem' }}>
          {c.subject} — {c.status}
        </div>
      ))}
      <button data-testid="new-consult-btn" onClick={() => setShowForm(true)}>新諮詢</button>
      {showForm && (
        <div data-testid="consult-form">
          <input data-testid="consult-to-input" value={toUser} onChange={(e) => setToUser(e.target.value)} placeholder="受諮詢醫師 ID" />
          <input data-testid="consult-subject-input" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="主題" />
          <button data-testid="consult-submit-btn" onClick={submit}>送出</button>
          <button onClick={() => setShowForm(false)} style={{ marginLeft: '0.5rem' }}>取消</button>
        </div>
      )}
    </div>
  )
}

// ── Trials panel ─────────────────────────────────────────────────────────────

interface TrialSummary {
  nct_id: string; title: string; status: string; phase: string;
  enrollment: number | null; start_date: string; completion_date: string;
  brief_summary: string; primary_outcomes: string[]; sponsor: string;
  countries: string[]; site_count: number; url: string;
}

function TrialsPanel({ condition }: { condition: string }) {
  const [trials, setTrials] = useState<TrialSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  const load = () => {
    if (loading) return
    setLoading(true)
    const q = new URLSearchParams({ condition, status: 'recruiting', max_results: '5' })
    fetch(`/api/v1/trials?${q}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : [])
      .then((data: TrialSummary[]) => { setTrials(data); setOpen(true) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const statusColor = (s: string) => s === 'RECRUITING' ? '#16a34a' : s === 'COMPLETED' ? '#6b7280' : '#d97706'

  return (
    <div data-testid="trials-panel" style={{ marginTop: '1rem' }}>
      <button
        data-testid="trials-toggle-btn"
        onClick={open ? () => setOpen(false) : load}
        style={{ fontSize: '0.9rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6, padding: '0.4rem 0.75rem', cursor: 'pointer' }}
      >
        {loading ? '搜尋中…' : open ? '▲ 收起試驗' : '🔬 相關臨床試驗'}
      </button>
      {open && (
        <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {trials.length === 0 && <p style={{ color: '#9ca3af', fontSize: '0.85rem' }}>無相關招募中試驗</p>}
          {trials.map(t => (
            <div key={t.nct_id} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '0.6rem 0.75rem', background: '#fff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                <div>
                  <a href={t.url} target="_blank" rel="noreferrer" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1d4ed8' }}>
                    {t.nct_id}
                  </a>
                  <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: statusColor(t.status), fontWeight: 500 }}>{t.status}</span>
                  <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', color: '#6b7280' }}>{t.phase}</span>
                </div>
                {t.site_count > 0 && <span style={{ fontSize: '0.75rem', color: '#6b7280', whiteSpace: 'nowrap' }}>{t.site_count} 個研究中心</span>}
              </div>
              <div style={{ fontSize: '0.82rem', marginTop: '0.25rem', color: '#374151' }}>{t.title}</div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: '0.2rem' }}>贊助：{t.sponsor}</div>
            </div>
          ))}
          <a
            href={`https://clinicaltrials.gov/search?cond=${encodeURIComponent(condition)}&recrs=a&recrs=b`}
            target="_blank" rel="noreferrer"
            style={{ fontSize: '0.78rem', color: '#6b7280', textAlign: 'right' }}
          >
            在 ClinicalTrials.gov 查看更多 →
          </a>
        </div>
      )}
    </div>
  )
}

// ── Plan PDF button ───────────────────────────────────────────────────────────

function PlanPdfButton({ planId }: { planId: string }) {
  const download = () => {
    const a = document.createElement('a')
    a.href = `/api/v1/plan/${planId}/pdf`
    a.download = `plan-${planId}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }
  return (
    <button
      data-testid="plan-pdf-btn"
      onClick={download}
      style={{ fontSize: '0.82rem', background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '0.3rem 0.65rem', cursor: 'pointer' }}
    >
      下載 PDF
    </button>
  )
}

export function PatientDetailPage() {
  const { mrn } = useParams<{ mrn: string }>()
  const navigate = useNavigate()
  const [patient, setPatient] = useState<PatientResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<TimelineEventResponse[]>([])
  const [page, setPage] = useState(0)
  const [note, setNote] = useState('')
  const [oncoLoading, setOncoLoading] = useState(false)
  const [showMtdPicker, setShowMtdPicker] = useState(false)
  const [mtdSessions, setMtdSessions] = useState<MtdSessionResponse[]>([])
  const [openConsult, setOpenConsult] = useState(false)
  const { show: showToast, ToastContainer } = useToast()
  const pageSize = 20

  useEffect(() => {
    if (!mrn) return
    fetch(`/api/v1/patients/${mrn}`, { credentials: 'include' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setPatient)
      .catch((e: Error) => setError(e.message))

    fetch(`/api/v1/patients/${mrn}/timeline?skip=0&limit=${pageSize}`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(setTimeline)
      .catch(() => {})
  }, [mrn])

  const loadMore = () => {
    const nextSkip = (page + 1) * pageSize
    fetch(`/api/v1/patients/${mrn}/timeline?skip=${nextSkip}&limit=${pageSize}`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then((more: TimelineEventResponse[]) => {
        setTimeline((prev) => [...prev, ...more])
        setPage((p) => p + 1)
      })
      .catch(() => {})
  }

  const saveNote = () => {
    if (!note.trim()) return
    fetch(`/api/v1/patients/${mrn}/timeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'doctor_note', title: note }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((evt) => { if (evt) { setTimeline((prev) => [evt, ...prev]); setNote(''); showToast('備注已儲存', 'success') } })
      .catch(() => {})
  }

  const openMtdPicker = () => {
    setShowMtdPicker(true)
    if (mtdSessions.length === 0) {
      fetch('/api/v1/mtd/sessions?status=open', { credentials: 'include' })
        .then((r) => r.ok ? r.json() : [])
        .then(setMtdSessions)
        .catch(() => {})
    }
  }

  const addToMtd = (sessionId: string) => {
    fetch(`/api/v1/mtd/sessions/${sessionId}/cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_mrn: mrn }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((s) => { if (s) showToast(`已加入 ${new Date(s.meeting_date).toLocaleDateString('zh-TW')} 委員會`, 'success') })
      .catch(() => showToast('加入失敗', 'error'))
      .finally(() => setShowMtdPicker(false))
  }

  const initOnco = async () => {
    if (!mrn || oncoLoading) return
    setOncoLoading(true)
    try {
      await fetch('/api/v1/plan', {
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
      navigate(`/patients/${mrn}/onco`)
    } catch {
      setOncoLoading(false)
    }
  }

  if (error) return (
    <div data-testid="patient-detail-error" style={{ padding: '2rem', color: '#dc2626' }}>
      <h2>無法載入患者資料</h2>
      <p>{error}</p>
      <button onClick={() => window.location.reload()}>重試</button>
    </div>
  )
  if (!patient) return <div data-testid="patient-detail-loading">載入中…</div>

  return (
    <div data-testid="patient-detail-page">
      <button data-testid="back-btn" onClick={() => navigate('/patients')}>← 返回列表</button>

      <h1 data-testid="patient-header">
        <span data-testid="header-mrn">{patient.mrn}</span>
        {' · '}
        <span data-testid="header-name">{patient.masked_name}</span>
      </h1>
      <div>
        <span data-testid="status-chip">{patient.status}</span>
        {patient.his_synced_at && (
          <span data-testid="his-sync-timestamp" style={{ marginLeft: '1rem', fontSize: '0.8rem', color: '#6b7280' }}>
            HIS 同步: {new Date(patient.his_synced_at).toLocaleString('zh-TW')}
          </span>
        )}
      </div>
      <div data-testid="team-avatars">
        {patient.care_team.map((m) => (
          <span key={m.id} data-testid={`avatar-${m.user_id}`} style={{ display: 'inline-block', background: '#dbeafe', borderRadius: '50%', width: 32, height: 32, textAlign: 'center', lineHeight: '32px', marginRight: 4 }}>
            {m.user_id.slice(0, 2)}
          </span>
        ))}
      </div>

      <div className="grid-2" style={{ marginTop: '1rem' }}>
        <div>
          {/* Timeline */}
          <div data-testid="timeline-section">
            {timeline.length === 0 && (
              <div data-testid="timeline-empty" style={{ color: '#9ca3af', fontSize: '0.9rem', padding: '1rem 0', textAlign: 'center' }}>
                目前沒有時間軸事件
              </div>
            )}
            {timeline.map((e) => <TimelineEvent key={e.id} event={e} />)}
            {timeline.length > 0 && (
              <button data-testid="load-more-btn" onClick={loadMore}>載入更多</button>
            )}
          </div>

          {/* Note input */}
          <div style={{ marginTop: '1rem' }}>
            <textarea
              data-testid="note-textarea"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="新增備注…"
              rows={3}
              style={{ width: '100%' }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button data-testid="save-note-btn" onClick={saveNote}>儲存</button>
              <button data-testid="mtd-btn" onClick={openMtdPicker}>MTD</button>
              <button data-testid="consult-btn" onClick={() => setOpenConsult(true)}>諮詢</button>
            </div>
            {showMtdPicker && (
              <div data-testid="mtd-picker" style={{ marginTop: '0.5rem', border: '1px solid #e5e7eb', borderRadius: 6, padding: '0.75rem', background: '#f9fafb' }}>
                <strong>選擇委員會場次</strong>
                {mtdSessions.length === 0 && <p style={{ color: '#6b7280', fontSize: '0.85rem' }}>目前沒有開放中的委員會場次</p>}
                {mtdSessions.map((s) => (
                  <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0' }}>
                    <span>{new Date(s.meeting_date).toLocaleDateString('zh-TW')} — {s.status}</span>
                    <button data-testid={`add-to-mtd-${s.id}`} onClick={() => addToMtd(s.id)} style={{ fontSize: '0.85rem' }}>加入</button>
                  </div>
                ))}
                <button onClick={() => setShowMtdPicker(false)} style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>關閉</button>
              </div>
            )}
          </div>
        </div>

        <div>
          <RemindersPanel mrn={mrn!} />
          <div style={{ marginTop: '1rem' }}>
            <button
              data-testid="onco-init-btn"
              onClick={initOnco}
              disabled={oncoLoading}
            >
              {oncoLoading ? '分析中…' : 'OpenOnco 分析'}
            </button>
            {patient.his_synced_at && (
              <div data-testid="last-query-timestamp" style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                上次查詢: {new Date(patient.his_synced_at).toLocaleString('zh-TW')}
              </div>
            )}
          </div>
          <ConsultationsPanel mrn={mrn!} openOnMount={openConsult} />
          {patient.disease_summary && (
            <TrialsPanel condition={patient.disease_summary.split('·')[0].trim()} />
          )}
        </div>
      </div>

      {/* Plan actions row */}
      {patient.his_synced_at && (
        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <PlanPdfButton planId={`plan-${mrn!.toLowerCase()}`} />
        </div>
      )}
      <ToastContainer />
    </div>
  )
}
