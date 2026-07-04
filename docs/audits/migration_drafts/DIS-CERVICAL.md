# Migration draft — Cervical carcinoma (squamous predominant + adeno) (DIS-CERVICAL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_cervical_locally_advanced_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, MIXED_ALL): `condition: "FIGO IB3-IVA (locally advanced)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_cervical_metastatic_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "FIGO IVB (distant metastases)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Recurrent cervical cancer not amenable to curative-intent surgery or RT"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 1, SOLE_ANY): `condition: "Persistent disease after definitive CRT, not curable with further local therapy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "PD-L1 CPS ≥ 1 (22C3 assay)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "No prior pelvic fistula (vesico-vaginal or recto-vaginal)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "No active uncontrolled hemorrhage"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 3, SOLE_ALL): `condition: "Blood pressure controlled (< 150/100)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[3]`** (step 3, SOLE_ALL): `condition: "Urine protein < 2 g/24h (UPCR < 2)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[4]`** (step 3, SOLE_ALL): `condition: "No therapeutic anticoagulation with active hemorrhagic risk"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
