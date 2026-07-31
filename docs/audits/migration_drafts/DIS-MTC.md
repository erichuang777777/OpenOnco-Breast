# Migration draft — Medullary thyroid carcinoma (MTC) (DIS-MTC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_men2_carrier_prophylactic_thyroidectomy_timing.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Confirmed RET germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_ret_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_ret_pathogenic_variant_confirmed`
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "RET codon M918T (MEN2B classical mutation)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "Clinical MEN2B phenotype: mucosal neuromas (lips, tongue, GI tract) + marfanoid habitus + ganglioneuromatosis + corneal nerve thickening + slipped capital femoral epiphysis"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "RET codon C634 substitution (C634R, C634Y, C634F, C634G, C634S, C634W — classical MEN2A severe)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "RET codon A883F"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "RET pathogenic variant at codons 533, 609, 611, 618, 620, 630, 666, 768, 790, 791, 804 (V804M / V804L), 891, or other RET P/LP variants not classified as HST or H"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_mtc_1l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "RET wild-type (RAS-mutant OR unknown OR negative)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
