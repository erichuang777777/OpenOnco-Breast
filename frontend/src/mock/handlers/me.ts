import { http, HttpResponse } from 'msw'

export const meHandlers = [
  http.get('/api/v1/me/line-notify-token', () =>
    HttpResponse.json({ registered: false })
  ),
  http.put('/api/v1/me/line-notify-token', async ({ request }) => {
    const body = await request.json() as { token: string | null }
    return HttpResponse.json({ registered: body.token !== null && body.token !== '' })
  }),
]
