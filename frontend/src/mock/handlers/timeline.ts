import { http, HttpResponse } from 'msw'
import { MOCK_TIMELINES, MOCK_ME } from '../fixtures'

export const timelineHandlers = [
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
]
