import { http, HttpResponse } from 'msw'
import { MOCK_REMINDERS, MOCK_ME } from '../fixtures'

export const reminderHandlers = [
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
]
