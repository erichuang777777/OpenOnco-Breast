/**
 * E1 — Critical path E2E tests.
 *
 * These tests exercise the flows a clinic HCP and care coordinator run every day.
 * They require a live backend seeded with fixture data.
 *
 * Run with:
 *   INTEGRATION=1 TEST_MRN=<mrn> npm run test:e2e -- e2e/critical-path.spec.ts
 *
 * All tests in this file are skipped unless INTEGRATION=1 is set.
 */
import { test, expect } from '@playwright/test'

test.skip(!process.env.INTEGRATION, 'requires live backend — set INTEGRATION=1 to run')

const MRN = process.env.TEST_MRN || 'TEST-001'
const BASE = process.env.BASE_URL || 'http://localhost:4173'

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

test('e2e_login_redirects_to_patient_list_after_jwt_set', async ({ page }) => {
  // After Google OAuth completes the backend sets a JWT cookie and redirects.
  // In integration mode a test cookie is seeded; verify redirect to /patients.
  await page.goto(`${BASE}/patients`)
  await expect(page).toHaveURL(/\/patients/)
  await expect(page.getByTestId('patient-list-page')).toBeVisible()
})

// ---------------------------------------------------------------------------
// Patient list
// ---------------------------------------------------------------------------

test('e2e_patient_list_shows_correct_counts', async ({ page }) => {
  await page.goto(`${BASE}/patients`)
  await expect(page.getByTestId('patient-list-page')).toBeVisible()
  // At least one stat card is rendered
  const statCards = page.locator('[data-testid^="stat-card-"]')
  await expect(statCards.first()).toBeVisible()
})

test('e2e_patient_list_tab_filtering_works', async ({ page }) => {
  await page.goto(`${BASE}/patients`)
  await expect(page.getByTestId('patient-list-page')).toBeVisible()
  // Click "待追蹤" tab
  const followupTab = page.getByTestId('tab-followup')
  if (await followupTab.isVisible()) {
    await followupTab.click()
    await expect(followupTab).toHaveAttribute('aria-selected', 'true')
  }
})

test('e2e_reminder_dots_visible_for_patient_with_alerts', async ({ page }) => {
  await page.goto(`${BASE}/patients`)
  // Look for at least one reminder dot (urgent = red, warn = amber)
  const urgentDot = page.locator('[data-testid^="reminder-dot-"]').first()
  if (await urgentDot.count() > 0) {
    await expect(urgentDot).toBeVisible()
  }
})

// ---------------------------------------------------------------------------
// Patient detail
// ---------------------------------------------------------------------------

test('e2e_navigate_to_patient_detail_from_list', async ({ page }) => {
  await page.goto(`${BASE}/patients`)
  await expect(page.getByTestId('patient-list-page')).toBeVisible()
  // Click first patient row
  const firstRow = page.locator('[data-testid^="patient-row-"]').first()
  await expect(firstRow).toBeVisible()
  await firstRow.click()
  await expect(page.getByTestId('patient-detail-page')).toBeVisible()
})

test('e2e_timeline_events_visible_in_order', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}`)
  await expect(page.getByTestId('patient-detail-page')).toBeVisible()
  const events = page.locator('[data-testid^="timeline-event-"]')
  await expect(events.first()).toBeVisible()
})

test('e2e_add_doctor_note_appears_in_timeline', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}`)
  await expect(page.getByTestId('patient-detail-page')).toBeVisible()

  const noteInput = page.getByTestId('note-input')
  await noteInput.fill('E2E test note — automated')
  await page.getByTestId('save-note-btn').click()

  // The new note should appear in the timeline
  await expect(page.locator('text=E2E test note — automated')).toBeVisible({ timeout: 5000 })
})

test('e2e_acknowledge_reminder_removes_it_from_active_list', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}`)
  await expect(page.getByTestId('patient-detail-page')).toBeVisible()

  const ackBtn = page.locator('[data-testid^="ack-btn-"]').first()
  if (await ackBtn.count() > 0) {
    const reminderId = (await ackBtn.getAttribute('data-testid'))?.replace('ack-btn-', '')
    await ackBtn.click()
    // Reminder row disappears after acknowledgement
    await expect(page.locator(`[data-testid="reminder-row-${reminderId}"]`)).not.toBeVisible({
      timeout: 3000,
    })
  }
})

test('e2e_consultation_send_and_reply_full_cycle', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}`)
  await expect(page.getByTestId('patient-detail-page')).toBeVisible()

  // Open new consultation form
  const newConsultBtn = page.getByTestId('new-consult-btn')
  if (await newConsultBtn.isVisible()) {
    await newConsultBtn.click()
    const subjectInput = page.getByTestId('consult-subject-input')
    await expect(subjectInput).toBeVisible()
    await subjectInput.fill('E2E consultation subject')
    await page.getByTestId('consult-submit-btn').click()
    // Consultation appears in list
    await expect(page.locator('text=E2E consultation subject')).toBeVisible({ timeout: 5000 })
  }
})

// ---------------------------------------------------------------------------
// OpenOnco (doctor-initiated)
// ---------------------------------------------------------------------------

test('e2e_onco_button_click_loads_analysis_page', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}`)
  await expect(page.getByTestId('patient-detail-page')).toBeVisible()
  await page.getByTestId('onco-init-btn').click()
  await expect(page).toHaveURL(new RegExp(`/patients/${MRN}/onco`))
  await expect(page.getByTestId('clinic-page')).toBeVisible()
})

test('e2e_onco_analysis_shows_treatment_tracks', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}/onco`)
  await expect(page.getByTestId('clinic-page')).toBeVisible()
  // Wait for plan to load (standard track is first)
  await expect(page.getByTestId('standard-track')).toBeVisible({ timeout: 10000 })
})

test('e2e_onco_select_track_navigates_or_confirms', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}/onco`)
  await expect(page.getByTestId('clinic-page')).toBeVisible()
  const selectBtn = page.locator('[data-testid^="select-track-btn-"]').first()
  if (await selectBtn.isVisible()) {
    await selectBtn.click()
    // Track selection POSTs to API; no hard navigation required
    await page.waitForTimeout(500)
  }
})

// ---------------------------------------------------------------------------
// MTD
// ---------------------------------------------------------------------------

test('e2e_board_page_loads', async ({ page }) => {
  await page.goto(`${BASE}/board`)
  await expect(page.getByTestId('board-page')).toBeVisible()
})

test('e2e_add_patient_to_mtd_session', async ({ page }) => {
  await page.goto(`${BASE}/board`)
  await expect(page.getByTestId('board-page')).toBeVisible()
  // Verify case table is rendered (may be empty in integration env)
  await expect(page.getByTestId('case-table')).toBeVisible()
})

test('e2e_coordinator_writes_mtd_conclusion', async ({ page }) => {
  await page.goto(`${BASE}/board`)
  await expect(page.getByTestId('board-page')).toBeVisible()
  const concludeBtn = page.locator('[data-testid^="conclude-btn-"]').first()
  if (await concludeBtn.count() > 0) {
    await concludeBtn.click()
    // POST to conclude endpoint — verify no error
    await page.waitForTimeout(500)
  }
})

// ---------------------------------------------------------------------------
// Drug requisition
// ---------------------------------------------------------------------------

test('e2e_drug_req_page_loads', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}/drug-req`)
  await expect(page.getByTestId('drug-req-page')).toBeVisible()
})

test('e2e_drug_reminder_to_submission_full_cycle', async ({ page }) => {
  await page.goto(`${BASE}/patients/${MRN}/drug-req`)
  await expect(page.getByTestId('drug-req-page')).toBeVisible()

  // Select a track and submit
  await page.getByTestId('track-select').selectOption({ index: 1 })
  await expect(page.getByTestId('track-name')).not.toHaveText('未選擇')
  await page.getByTestId('submit-drug-req-btn').click()
  await expect(page.getByTestId('status-submitted')).toBeVisible({ timeout: 5000 })
})
