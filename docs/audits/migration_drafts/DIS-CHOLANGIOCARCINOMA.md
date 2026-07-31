# Migration draft — Cholangiocarcinoma (bile duct cancer) (DIS-CHOLANGIOCARCINOMA)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_cholangio_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "ECOG 0-2 AND advanced/unresectable/metastatic AND no IO contraindication (active autoimmune disease, prior solid-organ transplant, ICI-incompatible immunosuppression)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `ecog_status`
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "IO-eligible patient without durvalumab access (regional formulary / reimbursement)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "IO contraindicated (active autoimmune, transplant, immunosuppression) OR no IO access"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_cholangio_2l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "HER2 amplification (IHC 3+ OR IHC 2+/ISH-amp) or HER2 overexpression per ASCO/CAP gastric criteria"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `her2_ihc`
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Disease progression on 1L gem+cis ± durvalumab; no actionable driver biomarker"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
