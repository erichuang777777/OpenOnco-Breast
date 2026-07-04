# Migration draft — Pancreatic ductal adenocarcinoma (PDAC) (DIS-PDAC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_nccn_pancreatic_caps_surveillance.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Confirmed STK11 germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_stk11_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_stk11_pathogenic_variant_confirmed`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Clinical Peutz-Jeghers syndrome (mucocutaneous pigmentation + hamartomatous polyposis + family pattern) without confirmed STK11 variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Confirmed CDKN2A germline pathogenic / likely-pathogenic variant (FAMMM)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_cdkn2a_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_cdkn2a_pathogenic_variant_confirmed`
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Confirmed PRSS1 germline pathogenic variant (hereditary pancreatitis, autosomal dominant)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Biallelic SPINK1 / CTRC / CFTR pathogenic variants with chronic pancreatitis phenotype"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 3, SOLE_ANY): `condition: "Clinical hereditary pancreatitis (≥2 family members with chronic pancreatitis, onset <30, AD pattern) without confirmed gene"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Confirmed BRCA2 OR BRCA1 OR PALB2 germline pathogenic / likely-pathogenic variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{any_of: [{finding: "brca2_status"}, {finding: "brca1_status"}, {finding: "palb2_germline_pathogenic"}]}`
  - Candidate finding key(s): `brca2_status; brca1_status; palb2_germline_pathogenic`
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "≥1 first-degree or second-degree relative with pancreatic adenocarcinoma at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Confirmed ATM germline pathogenic / likely-pathogenic variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "atm_germline"}`
  - Candidate finding key(s): `atm_germline`
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "≥1 first-degree relative with pancreatic adenocarcinoma at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Confirmed MLH1 / MSH2 / MSH6 / PMS2 / EPCAM germline pathogenic / likely-pathogenic variant (Lynch syndrome)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 6, SOLE_ALL): `condition: "≥1 first-degree relative with pancreatic adenocarcinoma at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 7, SOLE_ALL): `condition: "≥2 first-degree relatives with pancreatic adenocarcinoma"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 7, SOLE_ALL): `condition: "Comprehensive hereditary cancer panel performed and negative for known PDAC-risk genes (BRCA1/2, PALB2, ATM, CDKN2A, STK11, MMR, TP53, etc.)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_pdac_metastatic_2l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Total bilirubin ≤ 2× ULN OR biliary obstruction drained with stent/drain"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `bilirubin_uln_x`
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Prior 1L was gemcitabine-based (gemcitabine monotherapy, gem+nab-paclitaxel, or gem+erlotinib)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
