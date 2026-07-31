# Migration draft — Non-small cell lung cancer (DIS-NSCLC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_nsclc_metastatic_1l.yaml`

- **`any_of[0]`** (step 10, SOLE_ANY): `condition: "Nivo+ipi+2-cycle chemo (CheckMate-9LA) accessible and preferred per MDT"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_nsclc_metastatic_2l.yaml`

- **`any_of[0]`** (step 7, SOLE_ANY): `condition: "G2032R solvent-front resistance mutation OR post-entrectinib failure"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 9, SOLE_ANY): `condition: "Active untreated brain metastases (adagrasib intracranial ORR ~33%)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 11, SOLE_ANY): `condition: "Once-daily dosing preferred (adherence / convenience)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_nsclc_resectable_periop.yaml`

- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Resectable stage II, IIIA, or IIIB (T3-4N2M0) NSCLC eligible for anatomic resection"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
