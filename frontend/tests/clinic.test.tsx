import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { ClinicPage } from '../src/pages/ClinicPage'

const PLAN_RESPONSE = {
  plan_id: 'plan-1',
  disease_id: 'BRCA-HER2+',
  tracks: [
    {
      track_id: 'T1',
      label: 'THP 1L',
      is_default: true,
      indication_id: 'ind-1',
      evidence_level: '1A',
      nccn_category: '1',
      nccn_category_zh: '第一類',
      regimen_name: 'THP',
    },
    {
      track_id: 'T2',
      label: 'EC-THP 1L',
      is_default: false,
      indication_id: 'ind-2',
      evidence_level: '2A',
      nccn_category: '2A',
      nccn_category_zh: '第二A類',
      regimen_name: 'EC-THP',
    },
  ],
  gaps: [],
  warnings: [],
}

const TIMELINE_WITH_PLAN = [
  {
    id: 'ev-1',
    event_type: 'onco_query_initiated',
    body_json: { plan_id: 'plan-1' },
    event_time: '2026-06-01T10:00:00Z',
    source: 'system',
    title: 'OpenOnco 分析已啟動',
    patient_mrn: 'MRN-C1',
    created_at: '2026-06-01T10:00:00Z',
  },
]

const PLAN_WITH_GAPS = {
  ...PLAN_RESPONSE,
  gaps: [
    { field: 'ER', tier: 1, rationale: '需要ER狀態' },
    { field: 'PR', tier: 2, rationale: '需要PR狀態' },
  ],
}

function renderClinic(mrn = 'MRN-C1') {
  return render(
    <MemoryRouter initialEntries={[`/patients/${mrn}/onco`]}>
      <Routes>
        <Route path="/patients/:mrn/onco" element={<ClinicPage />} />
        <Route path="/patients/:mrn" element={<div data-testid="patient-detail-page" />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ClinicPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/patients/:mrn/timeline', () => HttpResponse.json(TIMELINE_WITH_PLAN)),
      http.get('/api/v1/plan/:planId', () => HttpResponse.json(PLAN_RESPONSE)),
      http.post('/api/v1/audit', () => HttpResponse.json({ ok: true })),
      http.post('/api/v1/patients/:mrn/track-selection', () => HttpResponse.json({ ok: true }))
    )
  })

  it('test_clinic_page_renders', async () => {
    renderClinic()
    expect(await screen.findByTestId('clinic-page')).toBeInTheDocument()
  })

  it('test_clinic_header_shows_mrn', async () => {
    renderClinic()
    expect(await screen.findByTestId('clinic-mrn')).toHaveTextContent('MRN-C1')
  })

  it('test_clinic_breadcrumb_back_button', async () => {
    renderClinic()
    expect(await screen.findByTestId('breadcrumb')).toBeInTheDocument()
    expect(screen.getByTestId('breadcrumb').querySelector('button')).toBeInTheDocument()
  })

  it('test_clinic_back_button_navigates', async () => {
    renderClinic()
    await screen.findByTestId('clinic-page')
    const backBtn = screen.getByTestId('breadcrumb').querySelector('button')!
    fireEvent.click(backBtn)
    expect(await screen.findByTestId('patient-detail-page')).toBeInTheDocument()
  })

  it('test_clinic_shows_tracks_after_load', async () => {
    renderClinic()
    expect(await screen.findByTestId('standard-track')).toBeInTheDocument()
    expect(screen.getByTestId('aggressive-track')).toBeInTheDocument()
  })

  it('test_clinic_standard_track_label', async () => {
    renderClinic()
    expect(await screen.findByTestId('standard-track')).toHaveTextContent('THP 1L')
  })

  it('test_clinic_nccn_chip_displayed', async () => {
    renderClinic()
    expect(await screen.findByTestId('nccn-chip-T1')).toHaveTextContent('NCCN 1')
    expect(screen.getByTestId('nccn-chip-T2')).toHaveTextContent('NCCN 2A')
  })

  it('test_clinic_evidence_level_displayed', async () => {
    renderClinic()
    expect(await screen.findByTestId('citations-T1')).toHaveTextContent('1A')
    expect(screen.getByTestId('citations-T2')).toHaveTextContent('2A')
  })

  it('test_clinic_select_track_button_present', async () => {
    renderClinic()
    expect(await screen.findByTestId('select-track-btn-T1')).toBeInTheDocument()
    expect(screen.getByTestId('select-track-btn-T2')).toBeInTheDocument()
  })

  it('test_clinic_select_track_calls_api', async () => {
    let trackSelected: string | null = null
    server.use(
      http.post('/api/v1/patients/:mrn/track-selection', async ({ request }) => {
        const body = await request.json() as { track_id: string }
        trackSelected = body.track_id
        return HttpResponse.json({ ok: true })
      })
    )
    renderClinic()
    const btn = await screen.findByTestId('select-track-btn-T1')
    fireEvent.click(btn)
    await waitFor(() => expect(trackSelected).toBe('T1'))
  })

  it('test_clinic_gap_banner_shown_when_gaps_exist', async () => {
    server.use(
      http.get('/api/v1/plan/:planId', () => HttpResponse.json(PLAN_WITH_GAPS))
    )
    renderClinic()
    expect(await screen.findByTestId('gap-banner')).toBeInTheDocument()
    expect(screen.getByTestId('gap-banner')).toHaveTextContent('2')
  })

  it('test_clinic_no_gap_banner_when_no_gaps', async () => {
    renderClinic()
    await screen.findByTestId('standard-track')
    expect(screen.queryByTestId('gap-banner')).not.toBeInTheDocument()
  })

  it('test_clinic_extracted_fields_grid_present', async () => {
    renderClinic()
    expect(await screen.findByTestId('extracted-fields-grid')).toBeInTheDocument()
  })

  it('test_clinic_field_missing_add_button', async () => {
    renderClinic()
    expect(await screen.findByTestId('field-missing-add')).toBeInTheDocument()
  })

  it('test_clinic_loading_state_then_loaded', async () => {
    let resolveTimeline!: (v: unknown) => void
    server.use(
      http.get('/api/v1/patients/:mrn/timeline', () =>
        new Promise((res) => { resolveTimeline = res })
      )
    )
    renderClinic()
    expect(await screen.findByTestId('clinic-loading')).toBeInTheDocument()
    resolveTimeline(HttpResponse.json(TIMELINE_WITH_PLAN))
    await waitFor(() => expect(screen.queryByTestId('clinic-loading')).not.toBeInTheDocument())
  })

  it('test_clinic_no_plan_when_no_timeline_event', async () => {
    server.use(
      http.get('/api/v1/patients/:mrn/timeline', () => HttpResponse.json([]))
    )
    renderClinic()
    await waitFor(() => expect(screen.queryByTestId('clinic-loading')).not.toBeInTheDocument())
    expect(screen.queryByTestId('standard-track')).not.toBeInTheDocument()
  })
})
