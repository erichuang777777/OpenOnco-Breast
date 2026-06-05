/**
 * MSW request handlers — used in:
 *   • dev mode  (via browser.ts + main.tsx when VITE_MOCK=true)
 *   • Vitest    (via tests/setup.ts)
 */
import { http, HttpResponse } from 'msw'
import {
  MOCK_PATIENTS, MOCK_STATS, MOCK_TIMELINES, MOCK_REMINDERS,
  MOCK_CONSULTATIONS, MOCK_MTD_SESSIONS, MOCK_PLANS,
  MOCK_DRUG_REQS, MOCK_KB_STATUS, MOCK_ME,
} from './fixtures'

export const handlers = [

  // ── Auth ─────────────────────────────────────────────────────────────────
  http.get('/auth/me', () =>
    HttpResponse.json({ ...MOCK_ME, name: MOCK_ME.display_name, email: MOCK_ME.email })
  ),

  // ── Patient list ──────────────────────────────────────────────────────────
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

  // ── Single patient ────────────────────────────────────────────────────────
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

  // ── Timeline ──────────────────────────────────────────────────────────────
  http.get('/api/v1/patients/:mrn/timeline', ({ params }) => {
    const events = MOCK_TIMELINES[params.mrn as string] ?? []
    return HttpResponse.json(events)
  }),

  http.post('/api/v1/patients/:mrn/timeline', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: `tl-new-${Date.now()}`,
      patient_mrn: params.mrn,
      event_type: body.event_type ?? 'doctor_note',
      event_time: new Date().toISOString(),
      source: 'manual',
      title: body.title ?? '',
      body_json: {},
      created_by: MOCK_ME.sub,
      created_at: new Date().toISOString(),
    }, { status: 201 })
  }),

  // ── Reminders ─────────────────────────────────────────────────────────────
  http.get('/api/v1/patients/:mrn/reminders', ({ params }) =>
    HttpResponse.json(MOCK_REMINDERS[params.mrn as string] ?? [])
  ),

  http.patch('/api/v1/patients/:mrn/reminders/:id/acknowledge', ({ params }) => {
    const reminders = MOCK_REMINDERS[params.mrn as string] ?? []
    const rem = reminders.find(r => r.id === params.id)
    if (!rem) return HttpResponse.json({ error: 'REMINDER_NOT_FOUND' }, { status: 404 })
    return HttpResponse.json({
      ...rem,
      status: 'acknowledged',
      acknowledged_by: MOCK_ME.sub,
      acknowledged_at: new Date().toISOString(),
    })
  }),

  // ── Consultations ─────────────────────────────────────────────────────────
  http.get('/api/v1/patients/:mrn/consultations', ({ params }) =>
    HttpResponse.json(MOCK_CONSULTATIONS[params.mrn as string] ?? [])
  ),

  http.post('/api/v1/patients/:mrn/consultations', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: `con-new-${Date.now()}`,
      patient_mrn: params.mrn,
      from_user_id: MOCK_ME.sub,
      to_user_id: body.to_user_id ?? 'dr-002',
      subject: body.subject ?? '',
      status: 'open',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [
        {
          id: `msg-new-${Date.now()}`,
          consultation_id: `con-new-${Date.now()}`,
          sender_id: MOCK_ME.sub,
          body: body.initial_message ?? '',
          created_at: new Date().toISOString(),
        },
      ],
    }, { status: 201 })
  }),

  // ── Plans ─────────────────────────────────────────────────────────────────
  http.get('/api/v1/plan/:planId', ({ params }) => {
    const plan = MOCK_PLANS[params.planId as string]
    if (!plan) return HttpResponse.json({ error: 'PLAN_NOT_FOUND' }, { status: 404 })
    return HttpResponse.json(plan)
  }),

  // ── MTD sessions ──────────────────────────────────────────────────────────
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

  // ── Drug requisition ──────────────────────────────────────────────────────
  http.get('/api/v1/drug-requisition', () =>
    HttpResponse.json(Object.values(MOCK_DRUG_REQS))
  ),

  http.post('/api/v1/drug-requisition', async () => {
    const req = Object.values(MOCK_DRUG_REQS)[0]
    return HttpResponse.json({
      ...req,
      id: `req-new-${Date.now()}`,
      requisition_id: Math.random().toString(36).slice(2, 8).toUpperCase(),
      created_date: new Date().toISOString().slice(0, 10),
    }, { status: 201 })
  }),

  http.get('/api/v1/drug-requisition/:id/preview', ({ params }) => {
    const req = Object.values(MOCK_DRUG_REQS).find(r => r.id === params.id) ?? Object.values(MOCK_DRUG_REQS)[0]
    const html = `<html><body style="font-family:sans-serif;padding:2rem">
      <h2>藥物申請單 ${req.requisition_id}</h2>
      <p>病患：${req.patient_name_initials} / ${req.patient_birth_year}</p>
      <p>診斷：${req.diagnosis_text} ${req.stage}</p>
      <p>方案：${req.regimen_name_zh || req.regimen_name_en}</p>
      <p>NCCN：${req.evidence.nccn_category} 類</p>
      <hr/><p style="color:#888;font-size:0.8rem">Demo 預覽 — 非正式文件</p>
    </body></html>`
    return new HttpResponse(html, { headers: { 'Content-Type': 'text/html' } })
  }),

  // ── KB admin ──────────────────────────────────────────────────────────────
  http.get('/api/v1/admin/kb/status', () => HttpResponse.json(MOCK_KB_STATUS)),

  http.post('/api/v1/admin/kb/refresh', () =>
    HttpResponse.json({ ...MOCK_KB_STATUS, last_refreshed_at: new Date().toISOString() })
  ),

  // ── Admin users ───────────────────────────────────────────────────────────
  http.get('/api/v1/admin/users', () =>
    HttpResponse.json([
      { id: 'dr-001', email: 'lin.zhiming@hospital.tw', display_name: '林志明 醫師', role: 'tumor_board_hcp', created_at: '2026-01-01T00:00:00Z' },
      { id: 'dr-002', email: 'chen.jianzhi@hospital.tw', display_name: '陳建志 醫師', role: 'tumor_board_hcp', created_at: '2026-01-01T00:00:00Z' },
      { id: 'dr-003', email: 'huang.sufang@hospital.tw', display_name: '黃素芳 醫師', role: 'clinic_hcp', created_at: '2026-01-01T00:00:00Z' },
      { id: 'coord-001', email: 'zhao.xiuying@hospital.tw', display_name: '趙秀英 個管師', role: 'clinic_hcp', created_at: '2026-01-01T00:00:00Z' },
      { id: 'nurse-001', email: 'wu.lizhen@hospital.tw', display_name: '吳麗珍 護理師', role: 'clinic_hcp', created_at: '2026-01-01T00:00:00Z' },
    ])
  ),

  http.patch('/api/v1/admin/users/:id/role', async ({ params, request }) => {
    const body = await request.json() as { role: string }
    return HttpResponse.json({ id: params.id, role: body.role })
  }),

  // ── Appointments (ClinicPage) ─────────────────────────────────────────────
  http.get('/api/v1/clinic/today', () =>
    HttpResponse.json([
      { patient_mrn: 'MRN-001', scheduled_time: '09:00', reason: '化療回診', checked_in: true },
      { patient_mrn: 'MRN-002', scheduled_time: '09:30', reason: '術後追蹤', checked_in: true },
      { patient_mrn: 'MRN-004', scheduled_time: '10:00', reason: 'BRCA 諮詢', checked_in: false },
    ])
  ),
]
