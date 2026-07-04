# Migration draft — Pancreatic neuroendocrine tumor (pNET), well-differentiated G1/G2 (DIS-PNET)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_men1_carrier_surveillance.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Confirmed MEN1 germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_men1_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_men1_pathogenic_variant_confirmed`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Confirmed CDKN1B (p27Kip1) germline pathogenic variant (MEN4 — clinical phenocopy with overlapping surveillance protocol)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Carrier is age ≥5 (pediatric pediatric entry) OR pediatric carrier under family-history-modified entry (e.g., proband sibling with onset <10) — see notes"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Annual biochemical surveillance ordered: calcium, ionised calcium, PTH (parathyroid); fasting glucose, insulin, proinsulin (insulinoma); gastrin, chromogranin A (gastrinoma); pancreatic polypeptide, glucagon, VIP, somatostatin (other functional NETs); prolactin, IGF-1 (pituitary); ACTH / cortisol / DHEA-S (adrenal — every 1-3 years per imaging findings)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Pituitary MRI ordered: baseline at age 5-10, then q3y (more frequent if symptoms or biochemical abnormality)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "Abdominal MRI (with pancreatic protocol) ordered: from age 10 q1-3y; or EUS q1-3y as preferred high-sensitivity modality for small pNETs (≤1cm)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "Thymic / bronchial imaging: chest CT (low-dose) or MRI q1-2y from age 15-20 — thymic NETs in MEN1 are high-mortality (median 9.5y survival per Goudet 2015 PMID 25646800)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
