# Migration draft — Soft tissue sarcoma (STS) (DIS-SOFT-TISSUE-SARCOMA)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_cascade_lfs_carrier_family_testing.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Index patient (proband) has confirmed Li-Fraumeni syndrome germline pathogenic or likely-pathogenic (ACMG class 4/5) variant in TP53"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Index patient has living first-degree relatives (parents, full siblings, biological children) at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "FDR is age ≥18 (adult capacity for consent) OR FDR is age <18 + family + pediatric-genetics team consensus that testing supports clinical surveillance entry per Toronto Protocol"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "FDR / legal surrogate provides informed consent after pre-test counseling addressing: lifetime ~85-100% cancer risk, surveillance burden, psychological implications, GINA / EU GDPR insurance considerations, family-system implications"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Second- or third-degree relative is available, eligible (age + consent + counseling), and motivated to test"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Relative completes pre-test genetic counseling — LFS-specific intensified content: lifetime ~85-100% cancer risk, multi-organ surveillance burden including annual whole-body MRI from infancy / childhood (Toronto Protocol), psychological support pathway, insurance / GINA / EU GDPR considerations, family-system implications, reproductive-options discussion (PGT-M, prenatal testing)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "Targeted single-site TP53 test ordered (NOT full LFS panel — wasteful when family variant is documented); for sentinel-tumor probands without family history, comprehensive TP53 sequencing + del/dup analysis indicated"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Single-site test result available + post-test disclosure counseling + multidisciplinary follow-up plan (medical oncology + medical genetics + radiology + psychology) confirmed"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_chompret_2015_lfs.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Proband with LFS-spectrum tumor (premenopausal breast cancer, soft tissue sarcoma, osteosarcoma, ACC, CNS tumor, leukemia, lung adenocarcinoma) diagnosed at age <46"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "≥1 first-degree or second-degree relative with LFS-spectrum tumor (excluding breast cancer if proband has breast cancer) at age <56, OR multiple primary tumors at any age"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Patient with multiple primary tumors (≥2), two of which belong to LFS-spectrum (premenopausal breast, soft tissue sarcoma, osteosarcoma, ACC, CNS, leukemia, lung adenocarcinoma)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "First tumor diagnosed at age <46"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Patient with adrenocortical carcinoma (ACC) at any age, regardless of family history"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Patient with choroid plexus carcinoma at any age, regardless of family history"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[2]`** (step 3, SOLE_ANY): `condition: "Patient with anaplastic rhabdomyosarcoma with embryonal-anaplastic histology at any age, regardless of family history"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Patient with breast cancer diagnosed at age <31, regardless of family history"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "BRCA1/2 germline pathogenic variant excluded"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_brca1_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_brca1_pathogenic_variant_confirmed`

## `algo_classic_lfs_criteria.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Proband with sarcoma (soft tissue or bone — STS, osteosarcoma, rhabdomyosarcoma, leiomyosarcoma, etc.) diagnosed at age <45"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "First-degree relative (parent, sibling, child) with any cancer diagnosed at age <45"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "An additional first-degree or second-degree relative in the same lineage with sarcoma at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "An additional first-degree or second-degree relative in the same lineage with any cancer diagnosed at age <45"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_sts_advanced_1l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Soft tissue sarcoma confirmed by pathology (histology + IHC)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "NOT GIST (KIT/PDGFRA — use imatinib algorithm)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 1, SOLE_ALL): `condition: "NOT Ewing sarcoma (EWSR1 fusion — use VDC-IE algorithm)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 1, SOLE_ALL): `condition: "NOT rhabdomyosarcoma (pediatric protocols)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[4]`** (step 1, SOLE_ALL): `condition: "NOT bone sarcoma / chondrosarcoma (separate disease entity)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "ECOG PS 0-1"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "ECOG PS 2 (doxorubicin mono consideration only)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Neoadjuvant intent (tumor shrinkage goal for borderline resectable disease)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Rapidly progressive disease with visceral threat requiring fast response"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[2]`** (step 3, SOLE_ANY): `condition: "Synovial sarcoma histology (ifosfamide-sensitive; AI preferred)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[3]`** (step 3, SOLE_ANY): `condition: "Young ECOG 0-1 patient requesting most aggressive curative-intent approach"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "ECOG PS 0-1"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "CrCl ≥50 mL/min"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "No prior Grade ≥3 ifosfamide encephalopathy or hemorrhagic cystitis"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_sts_advanced_2l.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "STS subtype confirmed as non-GIST, non-Ewing, non-RMS"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "ECOG PS 0-2"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "ecog_status"}`
  - Candidate finding key(s): `ecog_status`
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "STS subtype = leiomyosarcoma (uterine LMS or extra-uterine LMS) OR undifferentiated pleomorphic sarcoma (UPS)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "STS subtype = liposarcoma (well-differentiated, dedifferentiated, myxoid, pleomorphic)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "ECOG PS 0-2 AND adequate renal function (CrCl ≥30 mL/min)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `ecog_status`
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "No severe peripheral neuropathy (Grade ≥2)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "peripheral_neuropathy_grade"}`
  - Candidate finding key(s): `peripheral_neuropathy_grade`
