import { useState, useEffect } from 'react'
import type { MtdSessionResponse, MtdCaseResponse } from '../api/types'

export function BoardPage() {
  const [sessions, setSessions] = useState<MtdSessionResponse[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/v1/mtd/sessions', { credentials: 'include' })
      .then((r) => r.ok ? r.json() : [])
      .then(setSessions)
      .catch(() => {})
  }, [])

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
    }).catch(() => {})
  }

  return (
    <div data-testid="board-page">
      <h1>腫瘤委員會</h1>
      <button data-testid="new-session-btn" onClick={createSession}>新建會議</button>
      <button data-testid="export-agenda-btn">匯出議程</button>

      <table data-testid="case-table" style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
        <thead>
          <tr>
            <th>病歷號</th>
            <th>狀態</th>
            <th>會議</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {sessions.flatMap((session) =>
            session.cases.map((c: MtdCaseResponse) => (
              <tr
                key={`${session.id}-${c.patient_mrn}`}
                data-testid={`case-row-${c.patient_mrn}`}
                onClick={() => setExpanded(expanded === c.patient_mrn ? null : c.patient_mrn)}
              >
                <td data-testid={`case-mrn-${c.patient_mrn}`}>{c.patient_mrn}</td>
                <td>
                  <span data-testid={`case-status-chip-${c.patient_mrn}`}>{c.status}</span>
                </td>
                <td>{new Date(session.meeting_date).toLocaleDateString('zh-TW')}</td>
                <td>
                  <button
                    data-testid={`conclude-btn-${c.patient_mrn}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      conclude(session.id, c.patient_mrn, '委員會結論')
                    }}
                  >
                    記錄結論
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {expanded && (
        <div data-testid={`case-expanded-${expanded}`}>
          <div data-testid="recommendation-panel">建議治療方案</div>
          <div data-testid="annotation-timeline">討論記錄</div>
          <div>
            <input data-testid="annotation-input" placeholder="新增記錄" />
            <button data-testid="annotation-submit-btn">新增</button>
          </div>
        </div>
      )}
    </div>
  )
}
