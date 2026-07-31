import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { GuidelinesPage } from '../src/pages/GuidelinesPage'

const LIST = {
  algorithms: [
    { algorithm_id: 'ALGO-BREAST-1L', disease_id: 'DIS-BREAST', line_of_therapy: 1, purpose: '1L' },
    { algorithm_id: 'ALGO-BREAST-HR-POS-2L', disease_id: 'DIS-BREAST', line_of_therapy: 2, purpose: '2L' },
  ],
}

const GRAPH = {
  algorithm_id: 'ALGO-BREAST-1L',
  disease_id: 'DIS-BREAST',
  line_of_therapy: 1,
  purpose: 'Select 1L regimen.',
  default_indication: 'IND-X',
  alternative_indication: null,
  sources: ['SRC-NCCN-BREAST-2025'],
  has_trace: false,
  nodes: [
    { id: 'start', kind: 'start', label: 'Patient profile', conditions: [], red_flags: [], on_path: false },
    { id: 'step:1', kind: 'decision', label: 'Step 1', step: 1, match: 'any', conditions: ['HER2+'], red_flags: [], on_path: false },
  ],
  edges: [{ source: 'start', target: 'step:1', branch: null, label: null, on_path: false }],
}

describe('GuidelinesPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/guidelines', () => HttpResponse.json(LIST)),
      http.get('/api/v1/guidelines/:id', () => HttpResponse.json(GRAPH)),
    )
  })

  it('lists algorithms for the default disease', async () => {
    render(<MemoryRouter><GuidelinesPage /></MemoryRouter>)
    expect(await screen.findByTestId('guideline-item-ALGO-BREAST-1L')).toBeInTheDocument()
    expect(screen.getByTestId('guideline-item-ALGO-BREAST-HR-POS-2L')).toBeInTheDocument()
  })

  it('renders the flowchart after selecting an algorithm', async () => {
    render(<MemoryRouter><GuidelinesPage /></MemoryRouter>)
    const item = await screen.findByTestId('guideline-item-ALGO-BREAST-1L')
    fireEvent.click(item)
    await waitFor(() => expect(screen.getByTestId('guideline-flowchart')).toBeInTheDocument())
    expect(screen.getByTestId('flowchart-step-1')).toBeInTheDocument()
  })

  it('shows a placeholder before any selection', async () => {
    render(<MemoryRouter><GuidelinesPage /></MemoryRouter>)
    expect(await screen.findByTestId('guidelines-placeholder')).toBeInTheDocument()
  })
})
