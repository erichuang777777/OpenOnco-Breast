/**
 * E2E test fixtures and seed-data helpers.
 *
 * These utilities call the backend API directly (using the test JWT set in
 * the INTEGRATION_TOKEN env var) to create the minimum data needed for E2E
 * tests to run against a live backend.
 *
 * Usage:
 *   import { seedPatient, seedReminder } from './fixtures'
 *   const mrn = await seedPatient(request)
 */
import type { APIRequestContext } from '@playwright/test'

const API = process.env.BASE_URL ?? 'http://localhost:4173'
const AUTH_HEADER = { Authorization: `Bearer ${process.env.INTEGRATION_TOKEN ?? ''}` }

// ---------------------------------------------------------------------------
// Patient
// ---------------------------------------------------------------------------

export async function seedPatient(
  request: APIRequestContext,
  overrides: Record<string, unknown> = {}
): Promise<string> {
  const mrn = overrides.mrn as string ?? `E2E-${Date.now()}`
  await request.post(`${API}/api/v1/patients`, {
    headers: AUTH_HEADER,
    data: {
      mrn,
      masked_name: overrides.masked_name ?? '測●●',
      status: overrides.status ?? 'active',
      disease_summary: overrides.disease_summary ?? '乳癌 HER2+ · 第一期',
    },
  })
  return mrn
}

// ---------------------------------------------------------------------------
// Care team member
// ---------------------------------------------------------------------------

export async function addCareTeamMember(
  request: APIRequestContext,
  mrn: string,
  userId: string,
  role: 'primary_hcp' | 'care_coordinator' | 'consultant' = 'care_coordinator'
): Promise<void> {
  await request.post(`${API}/api/v1/patients/${mrn}/care-team`, {
    headers: AUTH_HEADER,
    data: { user_id: userId, member_role: role },
  })
}

// ---------------------------------------------------------------------------
// Timeline event (doctor note)
// ---------------------------------------------------------------------------

export async function seedTimelineNote(
  request: APIRequestContext,
  mrn: string,
  text: string
): Promise<void> {
  await request.post(`${API}/api/v1/patients/${mrn}/timeline`, {
    headers: AUTH_HEADER,
    data: {
      event_type: 'doctor_note',
      title: text,
      body_json: { text },
    },
  })
}

// ---------------------------------------------------------------------------
// Reminder
// ---------------------------------------------------------------------------

export async function seedReminder(
  request: APIRequestContext,
  mrn: string,
  overrides: Record<string, unknown> = {}
): Promise<void> {
  const dueDate = new Date(Date.now() + 3 * 24 * 3600 * 1000).toISOString()
  await request.post(`${API}/api/v1/patients/${mrn}/reminders`, {
    headers: AUTH_HEADER,
    data: {
      reminder_type: overrides.reminder_type ?? 'custom',
      title: overrides.title ?? 'E2E test reminder',
      due_date: overrides.due_date ?? dueDate,
      urgency: overrides.urgency ?? 'normal',
    },
  })
}

// ---------------------------------------------------------------------------
// MTD session + case
// ---------------------------------------------------------------------------

export async function seedMtdSession(
  request: APIRequestContext,
  mrn: string
): Promise<string> {
  const meetingDate = new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString()
  const sessionResp = await request.post(`${API}/api/v1/mtd/sessions`, {
    headers: AUTH_HEADER,
    data: { meeting_date: meetingDate },
  })
  const session = await sessionResp.json()

  await request.post(`${API}/api/v1/mtd/sessions/${session.id}/cases`, {
    headers: AUTH_HEADER,
    data: { patient_mrn: mrn, reason: 'E2E test case' },
  })
  return session.id
}
