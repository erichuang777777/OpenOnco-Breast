# Migration draft — Urothelial carcinoma (bladder + upper tract) (DIS-UROTHELIAL)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_urothelial_metastatic_1l.yaml`

- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Cisplatin-eligible: CrCl ≥60 mL/min, ECOG PS 0-1, no significant hearing loss, no neuropathy Grade ≥2, no HF NYHA III/IV"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_urothelial_metastatic_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "No available clinical trial OR patient declines trial enrollment"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "ECOG PS 0-2"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "FGFR2/3 activating mutation OR FGFR2/FGFR3 gene fusion detected (Therascreen or NGS)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `fgfr2_fusion`
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Prior platinum-containing therapy AND prior anti-PD-(L)1 therapy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Prior 1L regimen contained EV (enfortumab vedotin) — i.e., EV+pembro (EV-302 pathway)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "CrCl ≥30 mL/min"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "No prior platinum within 6 months (de novo platinum-eligible)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "No prior EV-containing therapy"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 6, SOLE_ALL): `condition: "ECOG PS 0-1"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[2]`** (step 6, SOLE_ALL): `condition: "No severe peripheral neuropathy (Grade ≥2), no uncontrolled DM, no severe ocular disease"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
