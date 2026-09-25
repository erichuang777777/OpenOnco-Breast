import { Fragment, useState, useEffect } from 'react'
import type { MtdSessionResponse, MtdCaseResponse } from '../api/types'

interface PlanTrack {
  track_id: string
  label: string
  regimen_name?: string
  nccn_category?: string
  evidence_level?: string
  is_default: boolean
}

export function BoardPage() {
  const [sessions, setSessions] = useState<MtdSessionResponse[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [planCache, setPlanCache] = useState<Record<string, PlanTrack[]>>({})
  const [annotationText, setAnnotationText] = useState<Record<string, string>>({})
  const [annotationSaving, setAnnotationSaving] = useState<Record<string, boolean>>({})

  useEffect(() => {
    fetch('/api/v1/mtd/sessions', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(setSessions)
      .catch(() => {})
  }, [])

  const loadPlan = (mrn: string) => {
    if (planCache[mrn]) return
    fetch(`/api/v1/patients/${mrn}/timeline`, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(async (events: Array<{ event_type: string; body_json: unknown }>) => {
        const planEvent = events.find((e) => e.event_type === 'onco_query_initiated')
        if (!planEvent?.body_json) return
        const body = typeof planEvent.body_json === 'string'
          ? JSON.parse(planEvent.body_json as string) : planEvent.body_json as Record<string, unknown>
        if (!body.plan_id) return
        const r = await fetch(`/api/v1/plan/${body.plan_id}`, { credentials: 'include' })
        if (!r.ok) return
        const plan = await r.json()
        setPlanCache((prev) => ({ ...prev, [mrn]: plan.tracks ?? [] }))
      })
      .catch(() => {})
  }

  const toggleExpand = (mrn: string) => {
    const next = expanded === mrn ? null : mrn
    setExpanded(next)
    if (next) loadPlan(mrn)
  }

  const createSession = () => {
    const date = new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString()
    fetch('/api/v1/mtd/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meeting_date: date }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((s) => { if (s) setSessions((prev) => [s, ...prev]) })
      .catch(() => {})
  }

  const conclude = (sessionId: string, mrn: string, text: string) => {
    fetch(`/api/v1/mtd/sessions/${sessionId}/cases/${mrn}/conclude`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conclusion_text: text, case_status: 'discussed' }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((updated) => {
        if (!updated) return
        setSessions((prev) => prev.map((s) =>
          s.id === sessionId
            ? { ...s, cases: s.cases.map((c) => c.patient_mrn === mrn ? updated : c) }
            : s
        ))
      })
      .catch(() => {})
  }

  const submitAnnotation = (mrn: string) => {
    const text = annotationText[mrn]?.trim()
    if (!text) return
    setAnnotationSaving((prev) => ({ ...prev, [mrn]: true }))
    fetch(`/api/v1/patients/${mrn}/timeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'doctor_note', title: text }),
      credentials: 'include',
    }).then((r) => r.ok ? r.json() : null)
      .then((evt) => { if (evt) setAnnotationText((prev) => ({ ...prev, [mrn]: '' })) })
      .catch(() => {})
      .finally(() => setAnnotationSaving((prev) => ({ ...prev, [mrn]: false })))
  }

  const exportAgenda = () => {
    const lines: string[] = ['腫瘤委員會議程', '='.repeat(40)]
    sessions.filter((s) => s.status === 'open' || s.status === 'scheduled').forEach((s) => {
      lines.push(`\n日期：${new Date(s.meeting_date).toLocaleDateString('zh-TW')}`)
      s.cases.forEach((c, i) => {
        const tracks = planCache[c.patient_mrn]
        const rec = tracks?.find((t) => t.is_default)?.label ?? '待分析'
        lines.push(`  ${i + 1}. ${c.patient_mrn}  [${c.status}]  建議方案: ${rec}`)
      })
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'mtd-agenda.txt'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div data-testid="board-page">
      <h1>腫瘤委員會</h1>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button data-testid="new-session-btn" onClick={createSession}>新建會議</button>
        <button data-testid="export-agenda-btn" onClick={exportAgenda}>匯出議程</button>
      </div>

      <div className="table-scroll">
        <table data-testid="case-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={{ padding: '0.5rem', textAlign: 'left' }}>病歷號</th>
              <th style={{ padding: '0.5rem', textAlign: 'left' }}>狀態</th>
              <th style={{ padding: '0.5rem', textAlign: 'left' }}>會議日期</th>
              <th style={{ padding: '0.5rem', textAlign: 'left' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {sessions.flatMap((session) =>
              session.cases.map((c: MtdCaseResponse) => (
                <Fragment key={`${session.id}-${c.patient_mrn}`}>
                  <tr
                    key={`${session.id}-${c.patient_mrn}`}
                    data-testid={`case-row-${c.patient_mrn}`}
                    onClick={() => toggleExpand(c.patient_mrn)}
                    style={{ cursor: 'pointer', borderBottom: '1px solid #e5e7eb', background: expanded === c.patient_mrn ? '#eff6ff' : undefined }}
                  >
                    <td style={{ padding: '0.5rem' }} data-testid={`case-mrn-${c.patient_mrn}`}>{c.patient_mrn}</td>
                    <td style={{ padding: '0.5rem' }}>
                      <span data-testid={`case-status-chip-${c.patient_mrn}`}
                        style={{ background: c.status === 'discussed' ? '#d1fae5' : '#fef9c3', padding: '0.1rem 0.4rem', borderRadius: 4, fontSize: '0.85rem' }}>
                        {c.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.5rem' }}>{new Date(session.meeting_date).toLocaleDateString('zh-TW')}</td>
                    <td style={{ padding: '0.5rem' }}>
                      <button
                        data-testid={`conclude-btn-${c.patient_mrn}`}
                        onClick={(e) => { e.stopPropagation(); conclude(session.id, c.patient_mrn, '委員會結論') }}
                        disabled={c.status === 'discussed'}
                        style={{ fontSize: '0.85rem' }}
                      >
                        記錄結論
                      </button>
                    </td>
                  </tr>
                  {expanded === c.patient_mrn && (
                    <tr key={`${session.id}-${c.patient_mrn}-expanded`}>
                      <td colSpan={4} style={{ padding: '0.75rem 1rem', background: '#f0f9ff', borderBottom: '2px solid #bfdbfe' }}>
                        <div data-testid={`case-expanded-${c.patient_mrn}`}>
                          <div data-testid="recommendation-panel" style={{ marginBottom: '0.75rem' }}>
                            <strong>建議治療方案</strong>
                            {!planCache[c.patient_mrn] && <span style={{ color: '#6b7280', marginLeft: '0.5rem', fontSize: '0.85rem' }}>載入中…</span>}
                            {planCache[c.patient_mrn]?.length === 0 && <span style={{ color: '#6b7280', marginLeft: '0.5rem', fontSize: '0.85rem' }}>尚無計畫</span>}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
                              {planCache[c.patient_mrn]?.map((t) => (
                                <div key={t.track_id} style={{ border: `2px solid ${t.is_default ? '#3b82f6' : '#e5e7eb'}`, borderRadius: 6, padding: '0.4rem 0.75rem', background: t.is_default ? '#eff6ff' : '#f9fafb', fontSize: '0.9rem' }}>
                                  <strong>{t.label}</strong>
                                  {t.nccn_category && <span style={{ marginLeft: '0.4rem', color: '#2563eb', fontSize: '0.8rem' }}>NCCN {t.nccn_category}</span>}
                                  {t.is_default && <span style={{ marginLeft: '0.4rem', color: '#16a34a', fontSize: '0.75rem' }}>★ 預設</span>}
                                </div>
                              ))}
                            </div>
                          </div>
                          <div data-testid="annotation-timeline" style={{ marginBottom: '0.5rem', fontSize: '0.9rem', color: '#374151' }}>
                            {c.conclusion_text
                              ? <span><strong>結論：</strong>{c.conclusion_text}</span>
                              : <span style={{ color: '#9ca3af' }}>尚無討論記錄</span>}
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <input
                              data-testid="annotation-input"
                              value={annotationText[c.patient_mrn] ?? ''}
                              onChange={(e) => setAnnotationText((prev) => ({ ...prev, [c.patient_mrn]: e.target.value }))}
                              placeholder="新增討論記錄…"
                              style={{ flex: 1, padding: '0.35rem 0.5rem', border: '1px solid #d1d5db', borderRadius: 4, fontSize: '0.9rem' }}
                            />
                            <button
                              data-testid="annotation-submit-btn"
                              onClick={() => submitAnnotation(c.patient_mrn)}
                              disabled={annotationSaving[c.patient_mrn] || !annotationText[c.patient_mrn]?.trim()}
                              style={{ fontSize: '0.85rem' }}
                            >
                              {annotationSaving[c.patient_mrn] ? '…' : '新增'}
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>

      {sessions.flatMap((s) => s.cases).length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', color: '#9ca3af' }}>目前沒有待討論案例</div>
      )}
    </div>
  )
}
