import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { ClinicalReviewPage } from '../src/pages/ClinicalReviewPage'
import * as auth from '../src/hooks/useAuth'

const UNSIGNED = {
  total: 2,
  entities: [
    { entity_type: 'indication', entity_id: 'IND-BREAST-THP', label: 'THP 1L', disease_id: 'DIS-BREAST', signoff_count: 0, draft: false },
    { entity_type: 'indication', entity_id: 'IND-BREAST-TNBC', label: 'TNBC', disease_id: 'DIS-BREAST', signoff_count: 1, draft: false },
  ],
}

const BUNDLE = {
  entity_type: 'indication',
  entity_id: 'IND-BREAST-THP',
  label: 'THP first line',
  disease_id: 'DIS-BREAST',
  signoff_count: 0,
  draft: false,
  claims: [
    { field: 'recommended_regimen', value: 'REG-THP-METASTATIC' },
    { field: 'evidence_level', value: 'high' },
  ],
  citations: [
    {
      source_id: 'SRC-CLEOPATRA', found: true, title: 'CLEOPATRA trial', type: 'clinical_trial',
      hosting: 'referenced', license: 'NEJM',
      citation: { authors: 'Swain SM', journal: 'NEJM', year: 2015, pages: '724-734', doi: '10.1056/x', pmid: '25693012' },
      url: 'https://doi.org/10.1056/x',
      study_design: { type: 'phase_3', n: 808 },
      key_results: { median_os_months: 57 },
      primary_endpoint: 'PFS',
    },
  ],
  citation_count: 1,
  missing_sources: [],
  raw_yaml: 'id: IND-BREAST-THP\nrecommended_regimen: REG-THP-METASTATIC\n',
}

function mockUser(role: string, sub = 'lead-1') {
  vi.spyOn(auth, 'useAuth').mockReturnValue({
    user: { sub, email: 'l@test.com', name: 'L', role }, loading: false, logout: () => {},
  })
}

describe('ClinicalReviewPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/admin/kb/unsigned', () => HttpResponse.json(UNSIGNED)),
      http.get('/api/v1/admin/kb/entity/:type/:id', () => HttpResponse.json(BUNDLE)),
    )
  })

  it('denies non-admin/auditor roles', () => {
    mockUser('clinic_hcp')
    render(<MemoryRouter><ClinicalReviewPage /></MemoryRouter>)
    expect(screen.getByTestId('review-access-denied')).toBeInTheDocument()
  })

  it('lists the unsigned queue', async () => {
    mockUser('kb_admin')
    render(<MemoryRouter><ClinicalReviewPage /></MemoryRouter>)
    expect(await screen.findByTestId('review-item-IND-BREAST-THP')).toBeInTheDocument()
    expect(screen.getByTestId('review-queue-count')).toHaveTextContent('2 unsigned')
  })

  it('shows claims and cited-source evidence with a deep link', async () => {
    mockUser('kb_admin')
    render(<MemoryRouter><ClinicalReviewPage /></MemoryRouter>)
    fireEvent.click(await screen.findByTestId('review-item-IND-BREAST-THP'))
    await waitFor(() => expect(screen.getByTestId('bundle-id')).toHaveTextContent('IND-BREAST-THP'))
    expect(screen.getByTestId('bundle-claims')).toHaveTextContent('REG-THP-METASTATIC')
    expect(screen.getByTestId('citation-SRC-CLEOPATRA')).toBeInTheDocument()
    expect(screen.getByTestId('evidence-key_results')).toHaveTextContent('median_os_months')
    expect(screen.getByTestId('citation-link-SRC-CLEOPATRA')).toHaveAttribute('href', 'https://doi.org/10.1056/x')
  })

  it('records an approve sign-off via POST', async () => {
    mockUser('kb_admin')
    let posted: { decision?: string } = {}
    server.use(
      http.post('/api/v1/admin/kb/entity/:type/:id/signoff', async ({ request }) => {
        posted = (await request.json()) as { decision?: string }
        return HttpResponse.json({ status: 'pending', message: 'First sign-off recorded.', reviewer_1: 'lead-1' })
      }),
    )
    render(<MemoryRouter><ClinicalReviewPage /></MemoryRouter>)
    fireEvent.click(await screen.findByTestId('review-item-IND-BREAST-THP'))
    fireEvent.click(await screen.findByTestId('signoff-approve'))
    await waitFor(() => expect(posted.decision).toBe('approve'))
    expect(await screen.findByTestId('review-message')).toHaveTextContent('First sign-off recorded')
  })

  it('auditor sees the bundle but no sign-off buttons', async () => {
    mockUser('auditor', 'aud-1')
    render(<MemoryRouter><ClinicalReviewPage /></MemoryRouter>)
    fireEvent.click(await screen.findByTestId('review-item-IND-BREAST-THP'))
    await waitFor(() => expect(screen.getByTestId('bundle-id')).toBeInTheDocument())
    expect(screen.getByTestId('review-readonly')).toBeInTheDocument()
    expect(screen.queryByTestId('signoff-approve')).not.toBeInTheDocument()
  })
})
