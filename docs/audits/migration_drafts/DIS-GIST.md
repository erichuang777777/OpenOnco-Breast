# Migration draft — Gastrointestinal stromal tumor (GIST) (DIS-GIST)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_gist_1l.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "KIT exon 11 mutation positive"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "kit_mutation"}`
  - Candidate finding key(s): `kit_mutation`
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "KIT exon 9 mutation positive"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "kit_mutation"}`
  - Candidate finding key(s): `kit_mutation`
- **`any_of[2]`** (step 2, SOLE_ANY): `condition: "PDGFRA non-D842V exon 18 OR exon 12 OR exon 14 mutation positive"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `pdgfra_d842v`
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "KIT/PDGFRA wild-type (SDH-deficient OR NF1-mutant OR uncharacterized)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `nf1_status`

## `algo_gist_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "PDGFRA D842V mutation positive"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "pdgfra_mutation"}`
  - Candidate finding key(s): `pdgfra_mutation`
