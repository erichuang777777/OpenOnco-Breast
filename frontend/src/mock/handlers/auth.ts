import { http, HttpResponse } from 'msw'
import { MOCK_ME } from '../fixtures'

export const authHandlers = [
  http.get('/auth/me', () =>
    HttpResponse.json({ ...MOCK_ME, name: MOCK_ME.display_name, email: MOCK_ME.email })
  ),
]
