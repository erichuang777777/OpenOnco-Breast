import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { DrugReqPage } from '../src/pages/DrugReqPage'

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
      http.post('/api/v1/patients/:mrn/drug-req', () =>
        HttpResponse.json({ id: 'req-1', status: 'submitted' }, { status: 201 })
      )
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

  it('test_drug_req_track_select_present', () => {
    renderDrugReq()
    expect(screen.getByTestId('track-select')).toBeInTheDocument()
  })

  it('test_drug_req_initial_status_draft', () => {
    renderDrugReq()
    expect(screen.getByTestId('status-draft')).toBeInTheDocument()
  })

  it('test_drug_req_track_name_shows_unselected', () => {
    renderDrugReq()
    expect(screen.getByTestId('track-name')).toHaveTextContent('未選擇')
  })

  it('test_drug_req_select_track_updates_name', async () => {
    renderDrugReq()
    fireEvent.change(screen.getByTestId('track-select'), { target: { value: 'T1' } })
    expect(screen.getByTestId('track-name')).toHaveTextContent('T1')
  })

  it('test_drug_req_submit_calls_api', async () => {
    let submitted = false
    server.use(
      http.post('/api/v1/patients/:mrn/drug-req', async () => {
        submitted = true
        return HttpResponse.json({ id: 'req-1', status: 'submitted' }, { status: 201 })
      })
    )
    renderDrugReq()
    fireEvent.change(screen.getByTestId('track-select'), { target: { value: 'T1' } })
    fireEvent.click(screen.getByTestId('submit-drug-req-btn'))
    await waitFor(() => expect(submitted).toBe(true))
  })

  it('test_drug_req_submit_changes_status_to_submitted', async () => {
    renderDrugReq()
    fireEvent.change(screen.getByTestId('track-select'), { target: { value: 'T1' } })
    fireEvent.click(screen.getByTestId('submit-drug-req-btn'))
    expect(await screen.findByTestId('status-submitted')).toBeInTheDocument()
  })

  it('test_drug_req_no_submit_without_track', async () => {
    let submitted = false
    server.use(
      http.post('/api/v1/patients/:mrn/drug-req', async () => {
        submitted = true
        return HttpResponse.json({})
      })
    )
    renderDrugReq()
    fireEvent.click(screen.getByTestId('submit-drug-req-btn'))
    await new Promise((r) => setTimeout(r, 50))
    expect(submitted).toBe(false)
    expect(screen.getByTestId('status-draft')).toBeInTheDocument()
  })
})
