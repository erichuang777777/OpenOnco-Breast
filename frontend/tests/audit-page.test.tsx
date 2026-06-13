import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './setup'
import { AuditPage } from '../src/pages/AuditPage'
import * as auth from '../src/hooks/useAuth'

const STATUS = {
  generated_at: '2026-06-13',
  content_counts: { algorithms: 180, indications: 424, sources: 383 },
  total_entities: 2500,
  civic: {
    snapshots: [{ date: '2026-04-25', iso_date: '2026-04-25', has_evidence: true }],
    latest: { date: '2026-04-25', iso_date: '2026-04-25' },
    latest_age_days: 49,
    stale: false,
  },
  source_freshness: {
    total: 383,
    stale: 2,
    undated: 1,
    stalest: [
      { source_id: 'SRC-OLD-1', title: 'Old guideline', last_verified: '2025-01-01', age_days: 528 },
    ],
  },
  stale_after_days: 183,
  review_queue: { pending: 1, approved: 0, rejected: 0, awaiting_second_reviewer: 0 },
}

const REVIEWS = {
  pending: [
    {
      review_id: 'REV-1',
      entity_type: 'indication',
      entity_id: 'IND-BREAST-TNBC',
      branch_name: 'feat/x',
      pr_number: 42,
      diff_summary: 'Add TNBC 1L indication',
      submitted_by: 'dr@test.com',
      reviewer_1: null,
      reviewer_2: null,
      status: 'pending',
    },
  ],
}

function mockUser(role: string, sub = 'admin-1') {
  vi.spyOn(auth, 'useAuth').mockReturnValue({
    user: { sub, email: 'a@test.com', name: 'A', role },
    loading: false,
    logout: () => {},
  })
}

describe('AuditPage', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/v1/admin/kb/ingestion-status', () => HttpResponse.json(STATUS)),
      http.get('/api/v1/admin/kb/reviews', () => HttpResponse.json(REVIEWS)),
    )
  })

  it('denies access to non-admin roles', () => {
    mockUser('clinic_hcp')
    render(<MemoryRouter><AuditPage /></MemoryRouter>)
    expect(screen.getByTestId('audit-access-denied')).toBeInTheDocument()
  })

  it('shows ingestion status stat cards and CIViC snapshot', async () => {
    mockUser('kb_admin')
    render(<MemoryRouter><AuditPage /></MemoryRouter>)
    expect(await screen.findByTestId('stat-entities')).toHaveTextContent('2500')
    expect(screen.getByTestId('stat-stale-sources')).toHaveTextContent('2')
    expect(screen.getByTestId('civic-status')).toHaveTextContent('2026-04-25')
  })

  it('lists the verification queue and approves via PATCH with action body', async () => {
    mockUser('kb_admin')
    let patched: { action?: string } = {}
    server.use(
      http.patch('/api/v1/admin/kb/reviews/:id', async ({ request }) => {
        patched = (await request.json()) as { action?: string }
        return HttpResponse.json({ review_id: 'REV-1', status: 'pending' })
      }),
    )
    render(<MemoryRouter><AuditPage /></MemoryRouter>)
    const approve = await screen.findByTestId('approve-btn-REV-1')
    fireEvent.click(approve)
    await waitFor(() => expect(patched.action).toBe('approve'))
  })

  it('auditor sees queue read-only (no approve button)', async () => {
    mockUser('auditor', 'aud-1')
    render(<MemoryRouter><AuditPage /></MemoryRouter>)
    expect(await screen.findByTestId('review-row-REV-1')).toBeInTheDocument()
    expect(screen.queryByTestId('approve-btn-REV-1')).not.toBeInTheDocument()
    expect(screen.getByTestId('review-readonly-REV-1')).toBeInTheDocument()
  })
})
