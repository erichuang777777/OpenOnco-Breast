import { http, HttpResponse } from 'msw'
import { MOCK_PATIENTS, MOCK_STATS, MOCK_MTD_SESSIONS, MOCK_ME } from '../fixtures'

export const patientHandlers = [
  http.get('/api/v1/patients', ({ request }) => {
    const url = new URL(request.url)
    const q = url.searchParams.get('q')?.toLowerCase() ?? ''
    const tab = url.searchParams.get('tab') ?? 'all'
    const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)
    const offset = parseInt(url.searchParams.get('offset') ?? '0', 10)

    let patients = [...MOCK_PATIENTS]

    if (tab === 'alerts') patients = patients.filter(p => (p.urgent_reminder_count ?? 0) > 0)
    if (tab === 'mtd') patients = patients.filter(p =>
      MOCK_MTD_SESSIONS.some(s => s.cases.some(c => c.patient_mrn === p.mrn))
    )
    if (q) patients = patients.filter(p =>
      p.mrn.toLowerCase().includes(q) ||
      p.masked_name.toLowerCase().includes(q) ||
      (p.disease_summary ?? '').toLowerCase().includes(q)
    )

    const total = patients.length
    const page = patients.slice(offset, offset + limit)
    return HttpResponse.json(page, {
      headers: { 'X-Total-Count': String(total) },
    })
  }),

  http.get('/api/v1/patients/stats', () => HttpResponse.json(MOCK_STATS)),

  http.get('/api/v1/patients/:mrn', ({ params }) => {
    const patient = MOCK_PATIENTS.find(p => p.mrn === params.mrn)
    if (!patient) return HttpResponse.json({ error: 'PATIENT_NOT_FOUND' }, { status: 404 })
    return HttpResponse.json(patient)
  }),

  http.patch('/api/v1/patients/:mrn', async ({ params, request }) => {
    const patient = MOCK_PATIENTS.find(p => p.mrn === params.mrn)
    if (!patient) return HttpResponse.json({ error: 'PATIENT_NOT_FOUND' }, { status: 404 })
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ ...patient, ...body, updated_at: new Date().toISOString() })
  }),

  http.get('/api/v1/clinic/today', () =>
    HttpResponse.json([
      { patient_mrn: 'MRN-001', scheduled_time: '09:00', reason: '化療回診', checked_in: true },
      { patient_mrn: 'MRN-002', scheduled_time: '09:30', reason: '術後追蹤', checked_in: true },
      { patient_mrn: 'MRN-004', scheduled_time: '10:00', reason: 'BRCA 諮詢', checked_in: false },
    ])
  ),
]
