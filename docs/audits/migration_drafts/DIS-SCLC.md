# Migration draft — Small cell lung cancer (DIS-SCLC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_sclc_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Limited-stage (one hemithorax + tolerable RT field)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Concurrent platinum-based chemoradiotherapy (cCRT) completed"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "No disease progression on or after cCRT"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 2, SOLE_ALL): `condition: "Start within 1-42 days of completing last RT fraction (ADRIATIC window)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_sclc_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "No available clinical trial OR patient declines trial enrollment"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "DLL3 IHC positive (≥1% tumour cells; any DLL3 expression per DeLLphi-301 eligibility)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "CTFI ≥ 180 days from end of 1L platinum chemotherapy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "CTFI ≥ 30 days from last platinum dose"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Lurbinectedin accessible (registered/reimbursed or international pharmacy available)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
