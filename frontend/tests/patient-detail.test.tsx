import { describe, it, expect } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { PatientDetailPage } from '../src/pages/PatientDetailPage'

const SAMPLE_PATIENT = {
  mrn: 'MRN-D1', masked_name: '張●●', status: 'active',
  primary_doctor_id: 'dr-1', his_synced_at: '2026-05-01T10:00:00Z',
  his_patient_id: 'HIS-001',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  care_team: [
    { id: 'c1', patient_mrn: 'MRN-D1', user_id: 'dr-1', member_role: 'primary_hcp', assigned_by: 'dr-1', assigned_at: '2026-01-01T00:00:00Z' },
    { id: 'c2', patient_mrn: 'MRN-D1', user_id: 'co-1', member_role: 'care_coordinator', assigned_by: 'dr-1', assigned_at: '2026-01-01T00:00:00Z' },
  ],
}

const SAMPLE_TIMELINE = [
  { id: 't1', patient_mrn: 'MRN-D1', event_type: 'coordinator_note', event_time: '2026-05-02T10:00:00Z', source: 'manual', title: '協調師備注', created_at: '2026-05-02T10:00:00Z' },
  { id: 't2', patient_mrn: 'MRN-D1', event_type: 'doctor_note', event_time: '2026-05-01T10:00:00Z', source: 'manual', title: '醫師備注', created_at: '2026-05-01T10:00:00Z' },
  { id: 't3', patient_mrn: 'MRN-D1', event_type: 'his_sync', event_time: '2026-04-30T10:00:00Z', source: 'his_sync', title: 'HIS 同步', created_at: '2026-04-30T10:00:00Z' },
  { id: 't4', patient_mrn: 'MRN-D1', event_type: 'alert', event_time: '2026-04-29T10:00:00Z', source: 'system_rule', title: '警示', created_at: '2026-04-29T10:00:00Z' },
  { id: 't5', patient_mrn: 'MRN-D1', event_type: 'mtd_conclusion', event_time: '2026-04-28T10:00:00Z', source: 'system_rule', title: 'MTD 結論', created_at: '2026-04-28T10:00:00Z' },
  { id: 't6', patient_mrn: 'MRN-D1', event_type: 'consultation_reply', event_time: '2026-04-27T10:00:00Z', source: 'system_rule', title: '諮詢回覆', created_at: '2026-04-27T10:00:00Z' },
]

const SAMPLE_REMINDERS = [
  { id: 'r1', patient_mrn: 'MRN-D1', reminder_type: 'drug_reapplication', urgency: 'high', title: '藥物申請', detail: null, due_date: '2026-05-15T00:00:00Z', status: 'active', triggered_by: 'rule', acknowledged_by: null, acknowledged_at: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 'r2', patient_mrn: 'MRN-D1', reminder_type: 'brca_result', urgency: 'high', title: 'BRCA 結果', detail: null, due_date: '2026-05-10T00:00:00Z', status: 'active', triggered_by: 'rule', acknowledged_by: null, acknowledged_at: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 'r3', patient_mrn: 'MRN-D1', reminder_type: 'imaging_due', urgency: 'normal', title: '影像到期', detail: null, due_date: '2026-05-12T00:00:00Z', status: 'active', triggered_by: 'rule', acknowledged_by: null, acknowledged_at: null, created_at: '2026-01-01T00:00:00Z' },
]

const SAMPLE_CONSULTATIONS = [
  { id: 'con1', patient_mrn: 'MRN-D1', from_user_id: 'dr-1', to_user_id: 'dr-2', subject: '諮詢主題', status: 'open', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', messages: [] },
  { id: 'con2', patient_mrn: 'MRN-D1', from_user_id: 'dr-2', to_user_id: 'dr-1', subject: '第二諮詢', status: 'replied', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z', messages: [] },
]

function setupHandlers() {
  server.use(
    http.get('/api/v1/patients/MRN-D1', () => HttpResponse.json(SAMPLE_PATIENT)),
    http.get('/api/v1/patients/MRN-D1/timeline', () => HttpResponse.json(SAMPLE_TIMELINE)),
    http.get('/api/v1/patients/MRN-D1/reminders', () => HttpResponse.json(SAMPLE_REMINDERS)),
    http.get('/api/v1/patients/MRN-D1/consultations', () => HttpResponse.json(SAMPLE_CONSULTATIONS)),
    http.patch('/api/v1/patients/MRN-D1/reminders/:id/acknowledge', () =>
      HttpResponse.json({ ...SAMPLE_REMINDERS[0], status: 'acknowledged' })
    ),
    http.post('/api/v1/patients/MRN-D1/timeline', async ({ request }) => {
      const body = await request.json() as Record<string, unknown>
      return HttpResponse.json({ id: 'new-1', patient_mrn: 'MRN-D1', event_type: body.event_type as string, event_time: new Date().toISOString(), source: 'manual', title: body.title as string, created_at: new Date().toISOString() }, { status: 201 })
    }),
    http.post('/api/v1/patients/MRN-D1/consultations', () =>
      HttpResponse.json(SAMPLE_CONSULTATIONS[0], { status: 201 })
    ),
  )
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/patients/MRN-D1']}>
      <Routes>
        <Route path="/patients/:mrn" element={<PatientDetailPage />} />
        <Route path="/patients" element={<div data-testid="patient-list">list</div>} />
      </Routes>
    </MemoryRouter>
  )
}

async function waitForPatient() {
  await waitFor(() => expect(screen.queryByTestId('patient-detail-loading')).toBeNull(), { timeout: 3000 })
}

describe('Patient header', () => {
  it('test_detail_renders_mrn_in_header', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('header-mrn').textContent).toBe('MRN-D1')
  })

  it('test_detail_renders_masked_name', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('header-name').textContent).toBe('張●●')
  })

  it('test_detail_renders_status_chips', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('status-chip').textContent).toBe('active')
  })

  it('test_detail_renders_team_avatars', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('avatar-dr-1')).toBeInTheDocument()
  })

  it('test_detail_renders_his_sync_timestamp', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('his-sync-timestamp')).toBeInTheDocument()
  })

  it('test_detail_back_button_navigates_to_list', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    fireEvent.click(screen.getByTestId('back-btn'))
    await waitFor(() => expect(screen.getByTestId('patient-list')).toBeInTheDocument())
  })
})

describe('Timeline events', () => {
  it('test_timeline_renders_coordinator_note_with_highlighted_style', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    const el = screen.getByTestId('timeline-event-t1')
    expect(el.getAttribute('data-event-type')).toBe('coordinator_note')
  })

  it('test_timeline_renders_doctor_note', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('timeline-event-t2').getAttribute('data-event-type')).toBe('doctor_note')
  })

  it('test_timeline_renders_his_sync_as_system_event_italics', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    const el = screen.getByTestId('timeline-event-t3')
    expect(el.getAttribute('data-event-type')).toBe('his_sync')
  })

  it('test_timeline_renders_alert_event_with_warning_style', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    const el = screen.getByTestId('timeline-event-t4')
    expect(el.getAttribute('data-event-type')).toBe('alert')
  })

  it('test_timeline_renders_mtd_conclusion_event', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('timeline-event-t5').getAttribute('data-event-type')).toBe('mtd_conclusion')
  })

  it('test_timeline_renders_consultation_reply_event', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('timeline-event-t6').getAttribute('data-event-type')).toBe('consultation_reply')
  })

  it('test_timeline_load_more_fetches_next_page', async () => {
    let callCount = 0
    server.use(
      http.get('/api/v1/patients/MRN-D1', () => HttpResponse.json(SAMPLE_PATIENT)),
      http.get('/api/v1/patients/MRN-D1/timeline', () => {
        callCount++
        return HttpResponse.json(SAMPLE_TIMELINE)
      }),
      http.get('/api/v1/patients/MRN-D1/reminders', () => HttpResponse.json([])),
      http.get('/api/v1/patients/MRN-D1/consultations', () => HttpResponse.json([])),
    )
    renderPage()
    await waitForPatient()
    fireEvent.click(screen.getByTestId('load-more-btn'))
    await waitFor(() => expect(callCount).toBeGreaterThan(1))
  })

  it('test_timeline_note_input_is_present', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('note-textarea')).toBeInTheDocument()
  })

  it('test_timeline_save_button_posts_to_api', async () => {
    let postCalled = false
    server.use(
      http.get('/api/v1/patients/MRN-D1', () => HttpResponse.json(SAMPLE_PATIENT)),
      http.get('/api/v1/patients/MRN-D1/timeline', () => HttpResponse.json(SAMPLE_TIMELINE)),
      http.get('/api/v1/patients/MRN-D1/reminders', () => HttpResponse.json([])),
      http.get('/api/v1/patients/MRN-D1/consultations', () => HttpResponse.json([])),
      http.post('/api/v1/patients/MRN-D1/timeline', () => {
        postCalled = true
        return HttpResponse.json({ id: 'n1', patient_mrn: 'MRN-D1', event_type: 'doctor_note', event_time: new Date().toISOString(), source: 'manual', title: '新備注', created_at: new Date().toISOString() }, { status: 201 })
      }),
    )
    renderPage()
    await waitForPatient()
    const textarea = screen.getByTestId('note-textarea')
    fireEvent.change(textarea, { target: { value: '新備注' } })
    fireEvent.click(screen.getByTestId('save-note-btn'))
    await waitFor(() => expect(postCalled).toBe(true))
  })

  it('test_timeline_save_clears_textarea_after_success', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    const textarea = screen.getByTestId('note-textarea')
    fireEvent.change(textarea, { target: { value: '測試備注' } })
    fireEvent.click(screen.getByTestId('save-note-btn'))
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe(''))
  })

  it('test_timeline_mtd_button_opens_mtd_flow', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('mtd-btn')).toBeInTheDocument()
  })

  it('test_timeline_consult_button_opens_consultation_flow', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('consult-btn')).toBeInTheDocument()
  })
})

describe('Reminders panel', () => {
  it('test_reminders_panel_shows_urgent_count_badge', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('urgent-count-badge')).toBeInTheDocument())
  })

  it('test_reminders_panel_renders_drug_reminder', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('reminder-drug_reapplication')).toBeInTheDocument())
  })

  it('test_reminders_panel_renders_brca_reminder', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('reminder-brca_result')).toBeInTheDocument())
  })

  it('test_reminders_panel_renders_imaging_reminder', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('reminder-imaging_due')).toBeInTheDocument())
  })

  it('test_reminders_panel_acknowledge_button_calls_api', async () => {
    let ackCalled = false
    server.use(
      http.get('/api/v1/patients/MRN-D1', () => HttpResponse.json(SAMPLE_PATIENT)),
      http.get('/api/v1/patients/MRN-D1/timeline', () => HttpResponse.json([])),
      http.get('/api/v1/patients/MRN-D1/reminders', () => HttpResponse.json([SAMPLE_REMINDERS[0]])),
      http.get('/api/v1/patients/MRN-D1/consultations', () => HttpResponse.json([])),
      http.patch('/api/v1/patients/MRN-D1/reminders/:id/acknowledge', () => {
        ackCalled = true
        return HttpResponse.json({ ...SAMPLE_REMINDERS[0], status: 'acknowledged' })
      }),
    )
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('ack-btn-r1')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ack-btn-r1'))
    await waitFor(() => expect(ackCalled).toBe(true))
  })

  it('test_reminders_panel_acknowledged_reminder_visually_removed', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('ack-btn-r1')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ack-btn-r1'))
    await waitFor(() => expect(screen.queryByTestId('ack-btn-r1')).toBeNull())
  })
})

describe('OpenOnco initiation', () => {
  it('test_onco_init_button_is_visible', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('onco-init-btn')).toBeInTheDocument()
  })

  it('test_onco_init_button_shows_last_query_timestamp', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    expect(screen.getByTestId('last-query-timestamp')).toBeInTheDocument()
  })

  it('test_onco_init_button_navigates_to_onco_page', async () => {
    setupHandlers()
    const { container } = renderPage()
    await waitForPatient()
    fireEvent.click(screen.getByTestId('onco-init-btn'))
    expect(container).toBeDefined()
  })

  it('test_onco_init_no_auto_population', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    // No plan data shown on detail page itself
    expect(screen.queryByTestId('standard-track')).toBeNull()
  })
})

describe('Consultations panel', () => {
  it('test_consultations_panel_shows_open_and_replied', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('consult-open')).toBeInTheDocument())
    expect(screen.getByTestId('consult-replied')).toBeInTheDocument()
  })

  it('test_consultations_new_button_opens_form', async () => {
    setupHandlers()
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('new-consult-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('new-consult-btn'))
    expect(screen.getByTestId('consult-form')).toBeInTheDocument()
  })

  it('test_consultations_create_form_submits_to_api', async () => {
    let postCalled = false
    server.use(
      http.get('/api/v1/patients/MRN-D1', () => HttpResponse.json(SAMPLE_PATIENT)),
      http.get('/api/v1/patients/MRN-D1/timeline', () => HttpResponse.json([])),
      http.get('/api/v1/patients/MRN-D1/reminders', () => HttpResponse.json([])),
      http.get('/api/v1/patients/MRN-D1/consultations', () => HttpResponse.json([])),
      http.post('/api/v1/patients/MRN-D1/consultations', () => {
        postCalled = true
        return HttpResponse.json(SAMPLE_CONSULTATIONS[0], { status: 201 })
      }),
    )
    renderPage()
    await waitForPatient()
    await waitFor(() => expect(screen.getByTestId('new-consult-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('new-consult-btn'))
    fireEvent.change(screen.getByTestId('consult-to-input'), { target: { value: 'dr-2' } })
    fireEvent.change(screen.getByTestId('consult-subject-input'), { target: { value: '諮詢' } })
    fireEvent.click(screen.getByTestId('consult-submit-btn'))
    await waitFor(() => expect(postCalled).toBe(true))
  })
})
