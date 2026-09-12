import { http, HttpResponse } from 'msw'
import { MOCK_KB_STATUS } from '../fixtures'

export const adminHandlers = [
  http.get('/api/v1/admin/kb/status', () => HttpResponse.json(MOCK_KB_STATUS)),

  http.post('/api/v1/admin/kb/refresh', () =>
    HttpResponse.json({ ...MOCK_KB_STATUS, last_refreshed_at: new Date().toISOString() })
  ),

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
]
