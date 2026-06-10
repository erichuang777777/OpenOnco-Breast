import { http, HttpResponse } from 'msw'
import { MOCK_PLANS } from '../fixtures'

// Realistic mock PlanResponse for the PLAN-{MRN}-V1 convention
const DEMO_PLAN_TEMPLATE = (mrn: string, planId: string) => ({
  plan_id: planId,
  disease_id: 'DIS-BREAST-HER2POS-MET',
  algorithm_id: 'ALG-BREAST-HER2POS-1L-MET',
  tracks: [
    {
      track_id: 'standard',
      label: 'HP + Docetaxel（標準一線）',
      label_en: 'Standard plan: Pertuzumab + Trastuzumab + Docetaxel',
      is_default: true,
      indication_id: 'IND-HER2-1L-HPD',
      regimen_id: 'RGM-PHESGO-DOCE',
      regimen_name: 'Pertuzumab + Trastuzumab + Docetaxel',
      evidence_level: 'high',
      nccn_category: '1',
      median_os_months: 57.1,
      selection_reason: `HER2+ 轉移性乳癌首選 (${mrn})：CLEOPATRA 試驗 OS 57.1 月`,
    },
    {
      track_id: 'aggressive',
      label: 'T-DXd（積極二線）',
      label_en: 'Aggressive: Trastuzumab deruxtecan (T-DXd)',
      is_default: false,
      indication_id: 'IND-HER2-2L-TDXD',
      regimen_id: 'RGM-TDXD',
      regimen_name: 'Trastuzumab deruxtecan (T-DXd)',
      evidence_level: 'high',
      nccn_category: '1',
      median_os_months: 29.1,
      selection_reason: 'DESTINY-Breast03：HP+Taxane 後進展，PFS 優於 T-DM1',
    },
    {
      track_id: 'palliative',
      label: '緩和性化療',
      label_en: 'Palliative: Capecitabine monotherapy',
      is_default: false,
      indication_id: 'IND-HER2-PALLIATIVE',
      regimen_id: 'RGM-CAPE',
      regimen_name: 'Capecitabine',
      evidence_level: 'moderate',
      nccn_category: '2A',
      median_os_months: null,
      selection_reason: '體能狀態較差時的緩和選項',
    },
  ],
  gaps: [
    {
      field: 'brca1',
      tier: 2,
      rationale: 'BRCA1/2 胚系突變影響 PARP 抑制劑適應症（olaparib/talazoparib）',
      if_positive_changes_to: 'IND-BRCA-PARP',
      recommended_test: 'BRCA1/2 胚系基因檢測',
    },
    {
      field: 'ki67',
      tier: 3,
      rationale: 'Ki-67 增殖指數影響術後輔助化療決策',
      if_positive_changes_to: null,
      recommended_test: 'Ki-67 免疫組化染色（IHC）',
    },
  ],
  warnings: [] as string[],
})

export const planHandlers = [
  http.get('/api/v1/plan/:planId', ({ params }) => {
    const planId = params.planId as string

    // Support legacy plan-XXX keys from fixtures
    if (MOCK_PLANS[planId]) {
      return HttpResponse.json(MOCK_PLANS[planId])
    }

    // Support PLAN-{MRN}-V1 convention from PatientOncologyPage
    const planV1Match = /^PLAN-(.+)-V1$/.exec(planId)
    if (planV1Match) {
      const mrn = planV1Match[1]
      return HttpResponse.json(DEMO_PLAN_TEMPLATE(mrn, planId))
    }

    return HttpResponse.json({ error: 'PLAN_NOT_FOUND' }, { status: 404 })
  }),

  http.get('/api/v1/plan/:planId/pdf', ({ params }) => {
    const html = `<html><body style="font-family:sans-serif;padding:2rem">
      <h2>治療計畫 ${params.planId}</h2>
      <p style="color:#888">[Demo — PDF 預覽，實際部署時由 reportlab 產生]</p>
    </body></html>`
    return new HttpResponse(html, {
      headers: {
        'Content-Type': 'text/html',
        'Content-Disposition': `attachment; filename="plan-${params.planId}.pdf"`,
      },
    })
  }),
]
