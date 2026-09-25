import { http, HttpResponse } from 'msw'
import { MOCK_DRUG_REQS } from '../fixtures'

export const drugReqHandlers = [
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
]
