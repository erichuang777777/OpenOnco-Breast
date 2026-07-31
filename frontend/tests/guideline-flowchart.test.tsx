import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { GuidelineFlowchart } from '../src/components/GuidelineFlowchart'
import type { GuidelineGraph, TraceEntry } from '../src/api/types'

const GRAPH: GuidelineGraph = {
  algorithm_id: 'ALGO-BREAST-1L',
  disease_id: 'DIS-BREAST',
  line_of_therapy: 1,
  purpose: 'Select 1L breast cancer regimen by receptor subtype.',
  default_indication: 'IND-BREAST-HR-POS-MET-1L-CDKI',
  alternative_indication: 'IND-BREAST-HER2-POS-MET-1L-THP',
  sources: ['SRC-NCCN-BREAST-2025'],
  has_trace: false,
  nodes: [
    { id: 'start', kind: 'start', label: 'Patient profile', conditions: [], red_flags: [], on_path: false },
    {
      id: 'step:1', kind: 'decision', label: 'Step 1', step: 1, match: 'any',
      conditions: ['⚑ HER2 amplification'], red_flags: ['RF-BREAST-HER2-AMP-ACTIONABLE'], on_path: false,
    },
    {
      id: 'step:3', kind: 'decision', label: 'Step 3', step: 3, match: 'any',
      conditions: ['⚑ Triple-negative breast cancer'], red_flags: ['RF-BREAST-TNBC'], on_path: false,
    },
    {
      id: 'ind:IND-BREAST-TNBC-METASTATIC-1L-PEMBRO-CHEMO', kind: 'indication',
      label: 'Breast Tnbc Metastatic 1l Pembro Chemo', indication_id: 'IND-BREAST-TNBC-METASTATIC-1L-PEMBRO-CHEMO',
      regimen_name: 'Pembrolizumab + chemotherapy', nccn_category: '1', evidence_level: 'high',
      conditions: [], red_flags: [], on_path: false,
    },
  ],
  edges: [
    { source: 'start', target: 'step:1', branch: null, label: null, on_path: false },
    { source: 'step:1', target: 'step:3', branch: 'false', label: 'No', on_path: false },
    { source: 'step:3', target: 'ind:IND-BREAST-TNBC-METASTATIC-1L-PEMBRO-CHEMO', branch: 'true', label: 'Yes', on_path: false },
  ],
}

const TRACE: TraceEntry[] = [
  { step: 1, outcome: false, branch: { next_step: 3 } },
  { step: 3, outcome: true, branch: { result: 'IND-BREAST-TNBC-METASTATIC-1L-PEMBRO-CHEMO' } },
]

describe('GuidelineFlowchart', () => {
  it('renders algorithm id, purpose and decision steps', () => {
    render(<GuidelineFlowchart graph={GRAPH} />)
    expect(screen.getByTestId('flowchart-algorithm-id')).toHaveTextContent('ALGO-BREAST-1L')
    expect(screen.getByTestId('flowchart-step-1')).toBeInTheDocument()
    expect(screen.getByTestId('flowchart-step-3')).toBeInTheDocument()
  })

  it('shows conditions and the NCCN badge for indication targets', () => {
    render(<GuidelineFlowchart graph={GRAPH} />)
    expect(screen.getByText('⚑ Triple-negative breast cancer')).toBeInTheDocument()
    expect(screen.getAllByTestId('flowchart-nccn-badge')[0]).toHaveTextContent('NCCN 1')
  })

  it('lists sources', () => {
    render(<GuidelineFlowchart graph={GRAPH} />)
    expect(screen.getByTestId('flowchart-sources')).toHaveTextContent('SRC-NCCN-BREAST-2025')
  })

  it('does not show path legend without a trace', () => {
    render(<GuidelineFlowchart graph={GRAPH} />)
    expect(screen.queryByTestId('flowchart-path-legend')).not.toBeInTheDocument()
  })

  it('overlays the trace path: highlights walked steps and the reached indication', () => {
    render(<GuidelineFlowchart graph={GRAPH} trace={TRACE} />)
    expect(screen.getByTestId('flowchart-path-legend')).toBeInTheDocument()
    expect(screen.getByTestId('flowchart-step-1')).toHaveAttribute('data-on-path', 'true')
    expect(screen.getByTestId('flowchart-step-3')).toHaveAttribute('data-on-path', 'true')
    // the recommendation banner names the reached indication
    const banner = screen.getByTestId('flowchart-selected-indication')
    expect(banner).toHaveTextContent('Pembrolizumab + chemotherapy')
  })
})
