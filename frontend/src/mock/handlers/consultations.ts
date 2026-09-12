import { http, HttpResponse } from 'msw'
import { MOCK_CONSULTATIONS, MOCK_ME } from '../fixtures'

export const consultationHandlers = [
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
]
