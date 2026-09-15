import { http, HttpResponse } from 'msw'

export const fhirHandlers = [
  http.post('/api/v1/fhir/Patient/$import', async ({ request }) => {
    const body = await request.json() as { resource: Record<string, unknown>; primary_doctor_id?: string }
    const res = body.resource as Record<string, unknown>
    const identifiers = (res.identifier as Array<Record<string, unknown>>) ?? []
    const mrn = identifiers[0]?.value as string ?? `FHIR-${res.id ?? Date.now()}`
    return HttpResponse.json({
      mrn, fhir_id: res.id ?? null, action: 'created',
      masked_name: '●●', dob_year: null, sex: null, warnings: [],
    }, { status: 200 })
  }),
]
