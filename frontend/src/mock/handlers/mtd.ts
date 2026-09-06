import { http, HttpResponse } from 'msw'
import { MOCK_MTD_SESSIONS, MOCK_ME } from '../fixtures'

export const mtdHandlers = [
  http.get('/api/v1/mtd/sessions', () =>
    HttpResponse.json(MOCK_MTD_SESSIONS)
  ),

  http.post('/api/v1/mtd/sessions', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: `mtd-new-${Date.now()}`,
      meeting_date: body.meeting_date ?? new Date().toISOString(),
      location: body.location ?? '',
      created_by: MOCK_ME.sub,
      status: 'scheduled',
      created_at: new Date().toISOString(),
      cases: [],
    }, { status: 201 })
  }),

  http.post('/api/v1/mtd/sessions/:sessionId/cases', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: `mtdcase-new-${Date.now()}`,
      mtd_session_id: params.sessionId,
      patient_mrn: body.patient_mrn ?? '',
      added_by: MOCK_ME.sub,
      reason: body.reason ?? '',
      status: 'pending',
      conclusion_text: null,
      conclusion_by: null,
      conclusion_at: null,
      created_at: new Date().toISOString(),
    }, { status: 201 })
  }),

  http.patch('/api/v1/mtd/sessions/:sessionId/cases/:mrn/conclude', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    const session = MOCK_MTD_SESSIONS.find(s => s.id === params.sessionId)
    const cas = session?.cases.find(c => c.patient_mrn === params.mrn)
    if (!cas) return HttpResponse.json({ error: 'NOT_FOUND' }, { status: 404 })
    return HttpResponse.json({
      ...cas,
      status: body.case_status ?? 'discussed',
      conclusion_text: body.conclusion_text ?? '',
      conclusion_by: MOCK_ME.sub,
      conclusion_at: new Date().toISOString(),
    })
  }),
]
