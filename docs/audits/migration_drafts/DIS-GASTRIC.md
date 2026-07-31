# Migration draft — Gastric / GEJ adenocarcinoma (DIS-GASTRIC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_gastric_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "HER2+ reconfirmed on archival or fresh biopsy (IHC 3+ OR 2+/ISH+)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 1, MIXED_ALL): `condition: "Prior trastuzumab-containing 1L"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[3]`** (step 1, MIXED_ALL): `condition: "ECOG ≤1"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "≥2 prior systemic regimens (incl. platinum + fluoropyrimidine ± taxane/ramucirumab)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, MIXED_ALL): `condition: "Disease progression on or after 1L platinum + fluoropyrimidine ± ICI"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, MIXED_ALL): `condition: "HER2-negative OR HER2 status unknown / unable to test"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `her2_status`

## `algo_gastric_resectable_periop.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, MIXED_ALL): `condition: "Adenocarcinoma histology (gastric or GEJ Siewert II/III)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `histology_adenocarcinoma`
- **`all_of[1]`** (step 1, MIXED_ALL): `condition: "Resectable cT2-T4 or N+ M0 disease (or locally advanced potentially resectable per MDT)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
