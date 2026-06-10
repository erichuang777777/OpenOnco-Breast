/**
 * Frontend feature flags and runtime configuration.
 *
 * Each flag defaults ON (true) so a minimal deploy works without extra env vars.
 * Set VITE_FEATURE_X=false in .env to disable the corresponding module.
 * Flags mirror hospital/config.py FEATURE_* settings for parity.
 */

function flag(key: string, defaultOn = true): boolean {
  const val = (import.meta as unknown as { env: Record<string, string | undefined> }).env[key]
  if (val === undefined) return defaultOn
  return val !== 'false' && val !== '0'
}

/** True when the backend has DEV_LOCAL_LOGIN=true (detected at runtime). */
export const DEV_LOGIN_ENABLED: boolean =
  (import.meta as unknown as { env: Record<string, string | undefined> }).env['VITE_DEV_LOCAL_LOGIN'] === 'true'

/**
 * True when running in demo mode. On 401 from /auth/me, auto-login as
 * demo@openonco.local (clinic_hcp role) without showing the login page.
 */
export const DEMO_MODE: boolean =
  (import.meta as unknown as { env: Record<string, string | undefined> }).env['VITE_DEMO_MODE'] === 'true'

export const FEATURES = {
  /** POST /api/v1/fhir/Patient/$import */
  fhirImport: flag('VITE_FEATURE_FHIR_IMPORT'),
  /** GET /api/v1/trials — ClinicalTrials.gov proxy */
  trialsSearch: flag('VITE_FEATURE_TRIALS_SEARCH'),
  /** GET /api/v1/plan/:id/pdf — reportlab PDF export */
  pdfExport: flag('VITE_FEATURE_PDF_EXPORT'),
  /** GET|PUT /api/v1/me/line-notify-token */
  lineNotifyApi: flag('VITE_FEATURE_LINE_NOTIFY_API'),
  /** CIViC actionability lookup — phase 2 pending */
  civicLookup: flag('VITE_FEATURE_CIVIC_LOOKUP', false),
} as const
