import { http, HttpResponse } from 'msw'
import { MOCK_PLANS } from '../fixtures'

export const planHandlers = [
  http.get('/api/v1/plan/:planId', ({ params }) => {
    const plan = MOCK_PLANS[params.planId as string]
    if (!plan) return HttpResponse.json({ error: 'PLAN_NOT_FOUND' }, { status: 404 })
    return HttpResponse.json(plan)
  }),

  http.get('/api/v1/plan/:planId/pdf', ({ params }) => {
    const html = `<html><body style="font-family:sans-serif;padding:2rem">
      <h2>治療計畫 ${params.planId}</h2>
      <p style="color:#888">[Demo — PDF 預覽，實際部署時由 reportlab 產生]</p>
    </body></html>`
    return new HttpResponse(html, {
      headers: {
        'Content-Type': 'text/html',
        'Content-Disposition': `attachment; filename="plan-${params.planId}.pdf"`,
      },
    })
  }),
]
