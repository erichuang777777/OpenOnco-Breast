/**
 * MSW request handlers — used in:
 *   • dev mode  (via browser.ts + main.tsx when VITE_MOCK=true)
 *   • Vitest    (via tests/setup.ts)
 *
 * Handlers are split by domain under ./handlers/.
 * Import this file to get the full combined array.
 */
import {
  authHandlers,
  patientHandlers,
  timelineHandlers,
  reminderHandlers,
  consultationHandlers,
  planHandlers,
  mtdHandlers,
  drugReqHandlers,
  adminHandlers,
  trialsHandlers,
  fhirHandlers,
  meHandlers,
} from './handlers/index'

export const handlers = [
  ...authHandlers,
  ...patientHandlers,
  ...timelineHandlers,
  ...reminderHandlers,
  ...consultationHandlers,
  ...planHandlers,
  ...mtdHandlers,
  ...drugReqHandlers,
  ...adminHandlers,
  ...trialsHandlers,
  ...fhirHandlers,
  ...meHandlers,
]
