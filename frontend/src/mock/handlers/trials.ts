import { http, HttpResponse } from 'msw'

const MOCK_TRIALS = [
  {
    nct_id: 'NCT00567190',
    title: 'CLEOPATRA: Pertuzumab + Trastuzumab + Docetaxel vs Placebo + Trastuzumab + Docetaxel in HER2-Positive MBC',
    status: 'COMPLETED', phase: 'PHASE3', enrollment: 808,
    start_date: '2008-02', completion_date: '2019-09',
    brief_summary: 'A phase III study of pertuzumab plus trastuzumab plus docetaxel vs placebo plus trastuzumab plus docetaxel as first-line treatment for HER2-positive metastatic breast cancer.',
    primary_outcomes: ['Progression-free survival (PFS)'],
    eligibility_summary: 'HER2-positive metastatic breast cancer, no prior chemotherapy for metastatic disease.',
    age_range: '18 Years–', sex: 'ALL', sponsor: 'Hoffmann-La Roche',
    countries: ['Taiwan', 'United States', 'Germany', 'France'],
    site_count: 24, url: 'https://clinicaltrials.gov/study/NCT00567190',
  },
  {
    nct_id: 'NCT03529110',
    title: 'DESTINY-Breast03: T-DXd vs T-DM1 in HER2-Positive MBC After Prior Trastuzumab',
    status: 'COMPLETED', phase: 'PHASE3', enrollment: 524,
    start_date: '2018-07', completion_date: '2023-06',
    brief_summary: 'Trastuzumab deruxtecan (T-DXd) compared with ado-trastuzumab emtansine (T-DM1) in patients with HER2-positive unresectable or metastatic breast cancer.',
    primary_outcomes: ['Progression-free survival (PFS)'],
    eligibility_summary: 'HER2-positive metastatic breast cancer, previously treated with trastuzumab and taxane.',
    age_range: '18 Years–', sex: 'ALL', sponsor: 'Daiichi Sankyo',
    countries: ['Taiwan', 'Japan', 'United States', 'South Korea'],
    site_count: 15, url: 'https://clinicaltrials.gov/study/NCT03529110',
  },
  {
    nct_id: 'NCT04191512',
    title: 'KEYNOTE-522: Pembrolizumab + Chemotherapy Neoadjuvant/Adjuvant for TNBC',
    status: 'ACTIVE_NOT_RECRUITING', phase: 'PHASE3', enrollment: 1174,
    start_date: '2018-12', completion_date: '2024-12',
    brief_summary: 'A study of pembrolizumab plus chemotherapy as neoadjuvant treatment and pembrolizumab as adjuvant treatment for high-risk, early-stage triple-negative breast cancer.',
    primary_outcomes: ['Pathological complete response (pCR)', 'Event-free survival (EFS)'],
    eligibility_summary: 'Stage II or III TNBC, newly diagnosed, no prior treatment.',
    age_range: '18 Years–', sex: 'ALL', sponsor: 'Merck Sharp & Dohme LLC',
    countries: ['Taiwan', 'United States', 'Germany'],
    site_count: 18, url: 'https://clinicaltrials.gov/study/NCT04191512',
  },
]

export const trialsHandlers = [
  http.get('/api/v1/trials', ({ request }) => {
    const url = new URL(request.url)
    const condition = url.searchParams.get('condition') ?? ''
    const filtered = MOCK_TRIALS.filter(t =>
      !condition ||
      t.title.toLowerCase().includes(condition.toLowerCase()) ||
      t.brief_summary.toLowerCase().includes(condition.toLowerCase())
    )
    return HttpResponse.json(filtered)
  }),
]
