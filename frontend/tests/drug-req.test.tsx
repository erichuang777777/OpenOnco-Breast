import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { DrugReqPage } from '../src/pages/DrugReqPage'

const MOCK_TIMELINE = [
  {
    id: 'evt-1',
    event_type: 'onco_query_initiated',
    body_json: { plan_id: 'plan-abc' },
    event_time: new Date().toISOString(),
    title: 'OpenOnco 分析已啟動',
  },
]

const MOCK_PLAN = {
  plan_id: 'plan-abc',
  disease_id: 'DIS-BREAST',
  tracks: [
    { track_id: 'T1', label: 'THP 1L', regimen_name: 'THP', nccn_category: '1', is_default: true },
    { track_id: 'T2', label: 'EC-THP 1L', regimen_name: 'EC-THP', nccn_category: '2B', is_default: false },
  ],
  gaps: [],
  warnings: [],
}

function renderDrugReq(mrn = 'MRN-D1') {
  return render(
    <MemoryRouter initialEntries={[`/patients/${mrn}/drug-req`]}>
      <Routes>
        <Route path="/patients/:mrn/drug-req" element={<DrugReqPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('DrugReqPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/patients/:mrn/timeline', () =>
        HttpResponse.json(MOCK_TIMELINE)
      ),
      http.get('/api/v1/plan/:planId', () =>
        HttpResponse.json(MOCK_PLAN)
      ),
      http.post('/api/v1/drug-requisition', () =>
        HttpResponse.json(
          { id: 'db-req-uuid', requisition_id: 'REQ-0001', patient_mrn: 'MRN-D1' },
          { status: 201 }
        )
      ),
    )
  })

  it('test_drug_req_page_renders', () => {
    renderDrugReq()
    expect(screen.getByTestId('drug-req-page')).toBeInTheDocument()
  })

  it('test_drug_req_shows_mrn', () => {
    renderDrugReq()
    expect(screen.getByTestId('patient-info')).toHaveTextContent('MRN-D1')
  })

  it('test_drug_req_track_select_present', async () => {
    renderDrugReq()
    expect(await screen.findByTestId('track-select')).toBeInTheDocument()
  })

  it('test_drug_req_populates_tracks_from_plan', async () => {
    renderDrugReq()
    const select = await screen.findByTestId('track-select')
    const options = select.querySelectorAll('option')
    expect(options.length).toBe(2)
    expect(options[0]).toHaveValue('T1')
    expect(options[1]).toHaveValue('T2')
  })

  it('test_drug_req_track_name_shows_selected_label', async () => {
    renderDrugReq()
    await screen.findByTestId('track-select')
    expect(screen.getByTestId('track-name')).toHaveTextContent('THP 1L')
  })

  it('test_drug_req_select_track_updates_display', async () => {
    renderDrugReq()
    const select = await screen.findByTestId('track-select')
    fireEvent.change(select, { target: { value: 'T2' } })
    expect(screen.getByTestId('track-name')).toHaveTextContent('EC-THP 1L')
  })

  it('test_drug_req_submit_calls_api', async () => {
    let submitted = false
    server.use(
      http.post('/api/v1/drug-requisition', async () => {
        submitted = true
        return HttpResponse.json(
          { id: 'db-req-uuid', requisition_id: 'REQ-0001', patient_mrn: 'MRN-D1' },
          { status: 201 }
        )
      })
    )
    renderDrugReq()
    await screen.findByTestId('submit-drug-req-btn')
    fireEvent.click(screen.getByTestId('submit-drug-req-btn'))
    await waitFor(() => expect(submitted).toBe(true))
  })

  it('test_drug_req_submit_changes_status_to_submitted', async () => {
    renderDrugReq()
    await screen.findByTestId('submit-drug-req-btn')
    fireEvent.click(screen.getByTestId('submit-drug-req-btn'))
    expect(await screen.findByTestId('status-submitted')).toBeInTheDocument()
  })

  it('test_drug_req_no_plan_shows_error', async () => {
    server.use(
      http.get('/api/v1/patients/:mrn/timeline', () => HttpResponse.json([]))
    )
    renderDrugReq()
    await waitFor(() => {
      expect(screen.queryByText(/尚未生成治療計畫/)).toBeInTheDocument()
    })
  })
})
