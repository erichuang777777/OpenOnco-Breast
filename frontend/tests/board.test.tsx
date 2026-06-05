import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { BoardPage } from '../src/pages/BoardPage'

const SESSION_1 = {
  id: 'session-1',
  meeting_date: '2026-06-10T09:00:00Z',
  location: 'Room A',
  created_by: 'user-1',
  status: 'scheduled',
  created_at: '2026-06-01T00:00:00Z',
  cases: [
    {
      id: 'case-1',
      mtd_session_id: 'session-1',
      patient_mrn: 'MRN-B1',
      added_by: 'user-1',
      reason: '需要討論',
      status: 'pending',
      created_at: '2026-06-01T00:00:00Z',
    },
    {
      id: 'case-2',
      mtd_session_id: 'session-1',
      patient_mrn: 'MRN-B2',
      added_by: 'user-2',
      status: 'discussed',
      conclusion_text: '決定使用方案A',
      created_at: '2026-06-01T00:00:00Z',
    },
  ],
}

function renderBoard() {
  return render(
    <MemoryRouter initialEntries={['/board']}>
      <Routes>
        <Route path="/board" element={<BoardPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('BoardPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/mtd/sessions', () => HttpResponse.json([SESSION_1]))
    )
  })

  it('test_board_page_renders', async () => {
    renderBoard()
    expect(await screen.findByTestId('board-page')).toBeInTheDocument()
    expect(screen.getByText('腫瘤委員會')).toBeInTheDocument()
  })

  it('test_board_shows_new_session_button', async () => {
    renderBoard()
    expect(await screen.findByTestId('new-session-btn')).toBeInTheDocument()
  })

  it('test_board_shows_export_agenda_button', async () => {
    renderBoard()
    expect(await screen.findByTestId('export-agenda-btn')).toBeInTheDocument()
  })

  it('test_board_case_table_rendered', async () => {
    renderBoard()
    expect(await screen.findByTestId('case-table')).toBeInTheDocument()
  })

  it('test_board_case_rows_loaded', async () => {
    renderBoard()
    expect(await screen.findByTestId('case-row-MRN-B1')).toBeInTheDocument()
    expect(screen.getByTestId('case-row-MRN-B2')).toBeInTheDocument()
  })

  it('test_board_case_mrn_displayed', async () => {
    renderBoard()
    expect(await screen.findByTestId('case-mrn-MRN-B1')).toHaveTextContent('MRN-B1')
  })

  it('test_board_case_status_chip', async () => {
    renderBoard()
    expect(await screen.findByTestId('case-status-chip-MRN-B1')).toHaveTextContent('pending')
    expect(screen.getByTestId('case-status-chip-MRN-B2')).toHaveTextContent('discussed')
  })

  it('test_board_conclude_button_present', async () => {
    renderBoard()
    expect(await screen.findByTestId('conclude-btn-MRN-B1')).toBeInTheDocument()
  })

  it('test_board_click_row_expands_panel', async () => {
    renderBoard()
    const row = await screen.findByTestId('case-row-MRN-B1')
    fireEvent.click(row)
    expect(await screen.findByTestId('case-expanded-MRN-B1')).toBeInTheDocument()
  })

  it('test_board_expanded_panel_shows_recommendation', async () => {
    renderBoard()
    const row = await screen.findByTestId('case-row-MRN-B1')
    fireEvent.click(row)
    expect(await screen.findByTestId('recommendation-panel')).toBeInTheDocument()
  })

  it('test_board_expanded_panel_shows_annotation_timeline', async () => {
    renderBoard()
    const row = await screen.findByTestId('case-row-MRN-B1')
    fireEvent.click(row)
    expect(await screen.findByTestId('annotation-timeline')).toBeInTheDocument()
  })

  it('test_board_annotation_input_present', async () => {
    renderBoard()
    const row = await screen.findByTestId('case-row-MRN-B1')
    fireEvent.click(row)
    expect(await screen.findByTestId('annotation-input')).toBeInTheDocument()
  })

  it('test_board_click_same_row_collapses', async () => {
    renderBoard()
    const row = await screen.findByTestId('case-row-MRN-B1')
    fireEvent.click(row)
    await screen.findByTestId('case-expanded-MRN-B1')
    fireEvent.click(row)
    await waitFor(() => {
      expect(screen.queryByTestId('case-expanded-MRN-B1')).not.toBeInTheDocument()
    })
  })

  it('test_board_new_session_calls_api', async () => {
    let posted = false
    server.use(
      http.post('/api/v1/mtd/sessions', async () => {
        posted = true
        const newSession = { ...SESSION_1, id: 'session-2', cases: [] }
        return HttpResponse.json(newSession, { status: 201 })
      })
    )
    renderBoard()
    await screen.findByTestId('new-session-btn')
    fireEvent.click(screen.getByTestId('new-session-btn'))
    await waitFor(() => expect(posted).toBe(true))
  })

  it('test_board_empty_sessions', async () => {
    server.use(http.get('/api/v1/mtd/sessions', () => HttpResponse.json([])))
    renderBoard()
    await screen.findByTestId('case-table')
    expect(screen.queryByTestId(/case-row-/)).not.toBeInTheDocument()
  })

  it('test_board_conclude_calls_api', async () => {
    let patchCalled = false
    server.use(
      http.patch('/api/v1/mtd/sessions/:sessionId/cases/:mrn/conclude', async () => {
        patchCalled = true
        return HttpResponse.json({ status: 'ok' })
      })
    )
    renderBoard()
    const btn = await screen.findByTestId('conclude-btn-MRN-B1')
    fireEvent.click(btn)
    await waitFor(() => expect(patchCalled).toBe(true))
  })
})
