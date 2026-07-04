# Migration draft — Colorectal carcinoma (CRC) (DIS-CRC)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_amsterdam_ii_lynch.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Familial adenomatous polyposis (FAP) confirmed or strongly suspected in pedigree"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "≥3 relatives with histologically verified Lynch-spectrum cancer (CRC, endometrial, small bowel, urothelial, gastric, ovarian, hepatobiliary, brain, sebaceous skin)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 2, SOLE_ALL): `condition: "One is a first-degree relative of the other two"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Lynch-spectrum cancers span at least two successive generations"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "At least one Lynch-spectrum cancer diagnosed at age <50 years"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Tumors verified by pathology (histologic confirmation)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_carrier_cascade_lynch.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Index patient (proband) has confirmed Lynch syndrome germline pathogenic or likely-pathogenic (ACMG class 4/5) variant in MLH1, MSH2, MSH6, PMS2, or EPCAM"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Index patient has living first-degree relatives (parents, full siblings, biological children) age ≥18"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Each adult FDR offered pre-test genetic counseling (informed consent, implications, GINA/EU GDPR considerations)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Targeted single-site testing for the known family variant ordered (NOT full Lynch panel — wasteful when family variant is documented)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Second- or third-degree relative is available (≥18), eligible (consent + counseling), and motivated to test"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Single-site test result available + post-test disclosure counseling completed"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_cascade_family_testing.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Index patient (proband) has confirmed germline pathogenic or likely-pathogenic (ACMG class 4/5) variant in any hereditary cancer syndrome gene"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Index patient has living first-degree relatives (parents, full siblings, biological children)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "FDR is age ≥18 OR is a minor with confirmed pediatric-onset syndrome (FAP / LFS / VHL / MEN2 / DICER1 / Beckwith-Wiedemann / retinoblastoma — testing from age of clinical surveillance initiation, typically 5-12 depending on syndrome)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "FDR has decision-making capacity OR a legal surrogate consents (for minors / cognitively impaired adults)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Second- or third-degree relative is available, eligible (age + consent + counseling), and motivated to test"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Relative completes pre-test genetic counseling (informed consent, implications discussion, insurance/GINA considerations)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "Targeted single-site (or family-variant-specific) germline test ordered — NOT full panel (faster, cheaper ~$250-500, higher analytic specificity for the known variant)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Single-site germline test result available + post-test counseling completed"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_classic_fap_criteria.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "≥100 colorectal adenomatous polyps on endoscopy or pathology, at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Known family history of APC germline pathogenic / likely-pathogenic variant identified in first-degree relative"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "10-99 colorectal adenomatous polyps cumulative on endoscopy / pathology"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1].any_of[0]`** (step 3, SOLE_ANY): `condition: "Personal history of colorectal cancer + polyposis"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1].any_of[1]`** (step 3, SOLE_ANY): `condition: "First-degree relative with polyposis (≥10 polyps) or CRC <50"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[2]`** (step 3, SOLE_ANY): `condition: "Extracolonic FAP-spectrum features: desmoid tumor, congenital hypertrophy of retinal pigment epithelium (CHRPE), osteoma, epidermoid cyst, duodenal/ampullary adenoma, hepatoblastoma in childhood, papillary thyroid cancer (cribriform-morular variant)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Desmoid tumor at any age in patient without other known cause"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[1]`** (step 4, SOLE_ANY): `condition: "Hepatoblastoma in infancy / childhood"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[2]`** (step 4, SOLE_ANY): `condition: "Cribriform-morular variant papillary thyroid cancer"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[3]`** (step 4, SOLE_ANY): `condition: "Multiple CHRPE lesions on ophthalmologic exam"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_crc_adjuvant.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Stage II (T3-4 N0 M0) post-R0 resection"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Stage III (any T, N1-2, M0) post-R0 resection"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, MIXED_ALL): `condition: "Stage II (T3-4 N0 M0)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Stage II (T3-4 N0 M0)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "High-risk features absent: T3, ≥12 nodes examined, no perforation, no obstruction, no LVI, no PNI, moderately differentiated"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Stage III (any T, N1-2, M0)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "stage_iii"}`
  - Candidate finding key(s): `stage_iii`
- **`any_of[1]`** (step 4, SOLE_ANY): `condition: "Stage II high-risk (T4 OR <12 nodes OR perforation OR obstruction OR LVI OR PNI OR poor differentiation)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Stage III (N1-2 M0)"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "stage_iii"}`
  - Candidate finding key(s): `stage_iii`
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "Low-risk: T1-3 N1 (not T4, not N2)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 6, SOLE_ANY): `condition: "Stage III high-risk: T4 or N2 (per IDEA stratification)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `stage_iii`
- **`any_of[1]`** (step 6, SOLE_ANY): `condition: "Stage II high-risk (T4 OR adverse features, MSS)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 7, SOLE_ANY): `condition: "CrCl <30 mL/min OR patient cannot reliably take oral medications"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_crc_metastatic_1l.yaml`

- **`all_of[1]`** (step 2, MIXED_ALL): `condition: "Left-sided primary (splenic flexure or distal)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 3, MIXED_ALL): `condition: "ECOG PS 0-1 AND age <75"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{all_of: [{finding: "ecog_status"}, {finding: "age"}]}`
  - Candidate finding key(s): `ecog_status; age`
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "ECOG PS 0-1 AND age <75"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{all_of: [{finding: "ecog_status"}, {finding: "age"}]}`
  - Candidate finding key(s): `ecog_status; age`
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "High tumour burden OR liver-limited disease with conversion-to-surgery intent"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_crc_metastatic_2l.yaml`

- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "KRAS G12C confirmed by NGS (tissue OR ctDNA)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
  - Candidate finding key(s): `kras_g12c`
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "BRAF V600E excluded (ruled out via step 2)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1].all_of[0]`** (step 4, SOLE_ALL): `condition: "HER2 amplified (IHC 3+ OR IHC 2+/ISH+)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
  - Candidate finding key(s): `her2_ihc`
- **`any_of[1].all_of[1]`** (step 4, SOLE_ALL): `condition: "RAS wild-type (MOUNTAINEER eligibility)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 5, MIXED_ALL): `condition: "ctDNA RAS-WT at rechallenge timepoint (CHRONOS biomarker selection)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 5, MIXED_ALL): `condition: "Prior anti-EGFR response (PR or better OR SD ≥6 mo) in 1L"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 5, MIXED_ALL): `condition: "Intervening anti-EGFR-free 2L line completed (typically bev-based)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[4]`** (step 5, MIXED_ALL): `condition: "BRAF V600E excluded (ruled out via step 2)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_integrated_risk_from_multiple_rfs.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Patient has ≥2 fired prevention RedFlags AND fires span ≥2 PreventionRiskCategory buckets (genetic / infectious / chronic_condition / occupational / iatrogenic / lifestyle / reproductive)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Patient has fired RF combination known to be multiplicatively synergistic per IARC: smoking + asbestos / smoking + occupational radon / smoking + alcohol (UADT cancers) / smoking + HPV (oropharyngeal) / smoking + diesel exhaust / chronic HBV + chronic HCV / chronic HBV + aflatoxin (HCC)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Patient has ≥2 fired prevention RFs targeting the SAME cancer (e.g., chronic HCV + chronic HBV both target HCC; chronic HCV + family Lynch both target intra-abdominal cancer hot zone)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Patient has ≥2 fired prevention RFs targeting DIFFERENT cancers with overlapping surveillance modalities (e.g., chronic HBV + Lynch — both require upper GI surveillance)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Integrated-risk profile and prioritized intervention list constructed"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_mmrpro.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "MMRPRO combined MLH1 + MSH2 + MSH6 + PMS2 carrier probability ≥20%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "MMRPRO combined MLH1 + MSH2 + MSH6 + PMS2 carrier probability ≥5%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "MMRPRO combined MLH1 + MSH2 + MSH6 + PMS2 carrier probability ≥2.5%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_multi_syndrome_pedigree_triage.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Pedigree includes ≥2 Lynch-spectrum cancers (CRC, endometrial, ovarian, small bowel, urothelial / renal pelvis / ureter, gastric, hepatobiliary, brain, sebaceous skin) across first- or second-degree relatives"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 1, SOLE_ALL): `condition: "At least one Lynch-spectrum cancer diagnosed at age <50"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Pedigree includes ≥2 HBOC-spectrum cancers (female breast <50, ovarian / fallopian / primary peritoneal at any age, male breast at any age, pancreatic adenocarcinoma at any age, metastatic / Gleason ≥7 prostate cancer at any age, triple-negative breast cancer)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Pedigree includes ≥2 LFS-spectrum cancers (soft-tissue or bone sarcoma at any age, breast <31, brain tumor / choroid plexus carcinoma / medulloblastoma, adrenocortical carcinoma at any age, leukemia, lung adenocarcinoma <46)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Proband has multiple primary cancers at age <46, with ≥1 LFS-spectrum"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 3, SOLE_ANY): `condition: "Proband has childhood adrenocortical carcinoma OR choroid plexus carcinoma"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Pedigree includes hamartomatous / adenomatous polyposis (≥10 adenomatous polyps + family pattern OR juvenile polyps + family pattern OR Peutz-Jeghers hamartomas / mucocutaneous pigmentation + family pattern)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "Pedigree or proband includes hemangioblastoma + RCC + pheochromocytoma cluster (VHL pattern)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 5, SOLE_ANY): `condition: "Pedigree or proband includes paraganglioma + pheochromocytoma + GIST cluster (SDHx pattern)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 5, SOLE_ANY): `condition: "Proband has bilateral / multifocal pheochromocytoma OR paraganglioma at any age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Pedigree shows ≥3 cancers across ≥2 generations without a single-syndrome dominant pattern (mixed cluster)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.

## `algo_peutz_jeghers_carrier_surveillance.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Confirmed STK11 germline pathogenic / likely-pathogenic (ACMG class 4/5) variant"`
  - Confidence: **HIGH_CONFIDENCE_RENAME** — Likely mechanical rename — still needs a clinician's confirmation (polarity, threshold, and any dropped qualifier are not checked).
  - Proposed rewrite (unreviewed): `{finding: "germline_stk11_pathogenic_variant_confirmed"}`
  - Candidate finding key(s): `germline_stk11_pathogenic_variant_confirmed`
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Clinical Peutz-Jeghers syndrome (≥2 of: mucocutaneous melanotic pigmentation, hamartomatous polyps consistent with PJ histology, family history of PJS) without confirmed STK11 variant"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Carrier is age ≥8 (pediatric GI entry)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Upper endoscopy (EGD) q2-3y from age 8-10 (or symptom-driven earlier)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 3, SOLE_ALL): `condition: "Colonoscopy q2-3y from age 8-10"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[2]`** (step 3, SOLE_ALL): `condition: "Small-bowel imaging — video capsule endoscopy q2-3y from age 8-10 — first-line modality; CT enterography or MR enterography acceptable alternates"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[3]`** (step 3, SOLE_ALL): `condition: "Push enteroscopy / double-balloon enteroscopy / spiral enteroscopy for polypectomy of small-bowel polyps ≥1-1.5 cm (prevent intussusception + reduce cancer risk)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Pancreatic surveillance — EUS or MRI / MRCP q1-2y from age 30-35 (CAPS Consortium 2020 PJ-specific entry timing)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Breast: female age ≥25 — clinical breast exam q6mo; female age ≥30 — annual breast MRI + annual mammography (alternating q6mo cadence acceptable)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Female: pelvic exam + transvaginal US q1y from age 18-20 (SCTAT and cervical adenoma malignum surveillance); annual cervical cytology — note PJ cervical cancer is adenoma malignum / minimal-deviation adenocarcinoma which can have NORMAL conventional cytology — TVUS + clinical exam are primary surveillance"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1]`** (step 6, SOLE_ALL): `condition: "Male: annual testicular exam from age 10 (Sertoli-cell large-cell calcifying testicular tumors — risk of feminization / gynecomastia + small-but-real malignancy risk); testicular US if exam-abnormal"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_premm5_lynch.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "PREMM5 carrier probability ≥5% (high-confidence testing indication)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "PREMM5 carrier probability ≥2.5%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "PREMM5 carrier probability 1.0-2.5% (borderline)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_prevention_risk_triage_overview.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`all_of[0]`** (step 1, SOLE_ALL): `condition: "Patient has ≥2 fired prevention RedFlags spanning ≥2 PreventionRiskCategory buckets (genetic / infectious / chronic_condition / occupational / iatrogenic / lifestyle / reproductive)"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Family history of hereditary cancer syndrome fires (RF-LYNCH-FAMILY-HISTORY-SUSPICION / RF-BRCA-HBOC-FAMILY-HISTORY-SUSPICION / RF-FAP-FAMILY-HISTORY-SUSPICION / RF-LI-FRAUMENI-FAMILY-HISTORY-SUSPICION / RF-VHL-FAMILY-HISTORY-SUSPICION / RF-HEREDITARY-PEDIGREE-SUSPICION) AND no confirmed-carrier status"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Confirmed hereditary cancer syndrome carrier fires (RF-LYNCH-CONFIRMED-CARRIER / RF-BRCA-CONFIRMED-CARRIER / RF-FAP-CONFIRMED-CARRIER / RF-LI-FRAUMENI-CONFIRMED-CARRIER / RF-VHL-CONFIRMED-CARRIER / etc.)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Confirmed chronic-condition surveillance eligibility fires (RF-BARRETTS-ESOPHAGUS / RF-CHRONIC-ATROPHIC-GASTRITIS / RF-CHRONIC-HBV / RF-CHRONIC-HCV / RF-CIRRHOSIS / RF-IBD-DURATION-RISK / etc.)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[0]`** (step 4, SOLE_ANY): `condition: "Lifestyle-RF only fires (RF-TOBACCO / RF-OBESITY / RF-ALCOHOL / RF-PHYSICAL-INACTIVITY / RF-LOW-FIBER-DIET / RF-HRT-USE / RF-OCCUPATIONAL-EXPOSURE / RF-IATROGENIC-IMMUNOSUPPRESSION / RF-IATROGENIC-RADIATION-HISTORY / etc.) with no other prevention bucket firing"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.

## `algo_revised_bethesda_lynch.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Colorectal cancer diagnosed in a patient <50 years of age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 2, SOLE_ANY): `condition: "Synchronous (≥2 simultaneous) CRC, OR metachronous CRC (separate primaries at different times), regardless of age"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 2, SOLE_ANY): `condition: "Synchronous or metachronous Lynch-spectrum cancers (CRC + endometrial / gastric / ovarian / pancreatic / urothelial / small bowel / hepatobiliary / brain / sebaceous skin), regardless of age"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 3, SOLE_ALL): `condition: "Colorectal cancer diagnosed at age <60"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1].any_of[0]`** (step 3, SOLE_ANY): `condition: "MSI-H histologic features: tumor-infiltrating lymphocytes (TILs)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[1]`** (step 3, SOLE_ANY): `condition: "MSI-H histologic features: Crohn-like lymphocytic reaction"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[2]`** (step 3, SOLE_ANY): `condition: "MSI-H histologic features: mucinous / signet-ring differentiation"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[1].any_of[3]`** (step 3, SOLE_ANY): `condition: "MSI-H histologic features: medullary growth pattern"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Patient has colorectal cancer"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 4, SOLE_ALL): `condition: "≥1 first-degree relative with Lynch-spectrum cancer (CRC, endometrial, urothelial, small bowel, gastric, ovarian, pancreatic, hepatobiliary, brain, sebaceous)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[2]`** (step 4, SOLE_ALL): `condition: "At least one of these cancers (patient or relative) diagnosed at age <50"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[0]`** (step 5, SOLE_ALL): `condition: "Patient has colorectal cancer"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`all_of[1]`** (step 5, SOLE_ALL): `condition: "≥2 first-degree or second-degree relatives with Lynch-spectrum cancer, regardless of age"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
