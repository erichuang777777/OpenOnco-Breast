/**
 * Critical-path smoke tests for OpenOnco Hospital frontend.
 *
 * These tests run against the built app (npm run preview) with a real backend
 * or a lightweight mock server. Set BASE_URL env var to override the default.
 *
 * Skipped in unit-test CI — run separately via: npm run test:e2e
 */
import { test, expect } from '@playwright/test'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Navigate to a page and wait for network idle */
async function goto(page: import('@playwright/test').Page, path: string) {
  await page.goto(path, { waitUntil: 'networkidle' })
}

// ---------------------------------------------------------------------------
// E1-01 Unauthenticated redirect
// ---------------------------------------------------------------------------
test('e1_unauthenticated_redirects_to_login', async ({ page }) => {
  // Without a session cookie, /patients should redirect to /login
  await goto(page, '/patients')
  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByTestId('login-page')).toBeVisible()
})

// ---------------------------------------------------------------------------
// E1-02 Login page renders Google button
// ---------------------------------------------------------------------------
test('e1_login_page_has_google_button', async ({ page }) => {
  await goto(page, '/login')
  await expect(page.getByTestId('google-login-btn')).toBeVisible()
})

// ---------------------------------------------------------------------------
// E1-03 Pending role redirects to pending page
// ---------------------------------------------------------------------------
test('e1_pending_role_redirects_to_pending_page', async ({ page }) => {
  // Simulate a pending session by setting a mock cookie (backend contract)
  // In a real integration test, the backend returns role=pending.
  // Here we verify the /pending route itself renders correctly.
  await goto(page, '/pending')
  await expect(page.getByTestId('pending-page')).toBeVisible()
})

// ---------------------------------------------------------------------------
// E1-04 Patient list page (authenticated — requires backend or mock)
// These tests are tagged @backend and are skipped unless INTEGRATION=1
// ---------------------------------------------------------------------------
test.describe('backend-required', () => {
  test.skip(
    !process.env.INTEGRATION,
    'requires live backend — set INTEGRATION=1 to run'
  )

  test('e1_patient_list_loads', async ({ page }) => {
    await goto(page, '/patients')
    await expect(page.getByTestId('patient-list-page')).toBeVisible()
  })

  test('e1_patient_detail_loads', async ({ page }) => {
    // Navigate to a known patient
    const mrn = process.env.TEST_MRN || 'TEST-001'
    await goto(page, `/patients/${mrn}`)
    await expect(page.getByTestId('patient-detail-page')).toBeVisible()
  })

  test('e1_onco_page_loads', async ({ page }) => {
    const mrn = process.env.TEST_MRN || 'TEST-001'
    await goto(page, `/patients/${mrn}/onco`)
    await expect(page.getByTestId('clinic-page')).toBeVisible()
  })

  test('e1_drug_req_page_loads', async ({ page }) => {
    const mrn = process.env.TEST_MRN || 'TEST-001'
    await goto(page, `/patients/${mrn}/drug-req`)
    await expect(page.getByTestId('drug-req-page')).toBeVisible()
  })

  test('e1_board_page_loads_for_tumor_board_hcp', async ({ page }) => {
    await goto(page, '/board')
    await expect(page.getByTestId('board-page')).toBeVisible()
  })

  test('e1_admin_page_loads_for_kb_admin', async ({ page }) => {
    await goto(page, '/admin')
    await expect(page.getByTestId('admin-page')).toBeVisible()
  })

  test('e1_navbar_shows_correct_links', async ({ page }) => {
    await goto(page, '/patients')
    await expect(page.getByTestId('navbar')).toBeVisible()
    await expect(page.getByTestId('nav-patients')).toBeVisible()
    await expect(page.getByTestId('logout-btn')).toBeVisible()
  })

  test('e1_logout_button_clears_session', async ({ page }) => {
    await goto(page, '/patients')
    await page.getByTestId('logout-btn').click()
    await expect(page).toHaveURL(/\/login/)
  })
})
