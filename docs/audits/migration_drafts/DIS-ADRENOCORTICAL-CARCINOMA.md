# Migration draft — Adrenocortical carcinoma (ACC) (DIS-ADRENOCORTICAL-CARCINOMA)

**Draft only. Not applied. Every clause below still needs a Clinical Co-Lead's sign-off (CHARTER Sec 6.1) before any of this lands in a real Algorithm YAML.** See `docs/reviews/fable-opinion.md` Phase 3 and `docs/reviews/dead-clause-cleanup-candidates-2026-07-04.md` for why even a routing-snapshot-clean change isn't sufficient proof of safety on its own in this repo.

## `algo_pediatric_cancer_predisposition_triage.yaml` ⚠️ **step 1 entirely prose — every patient falls through to default_indication**

- **`any_of[0]`** (step 1, SOLE_ANY): `condition: "Pediatric adrenocortical carcinoma (ACC) at any age — Chompret C; ~50-80% germline TP53 yield"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 1, SOLE_ANY): `condition: "Pediatric choroid plexus carcinoma (CPC) at any age — Chompret C; ~50% germline TP53 yield"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 1, SOLE_ANY): `condition: "Pediatric anaplastic rhabdomyosarcoma with embryonal-anaplastic histology — Chompret C; ~10-20% TP53 yield"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[3]`** (step 1, SOLE_ANY): `condition: "Bilateral or familial retinoblastoma at any age — ~100% germline RB1 yield"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[4]`** (step 1, SOLE_ANY): `condition: "Pediatric medulloblastoma SHH-subtype with anaplastic histology — germline TP53 (LFS) yield ~10-20%; PTCH1 / SUFU (Gorlin) yield ~5-15%; SMARCA4 / SMARCB1 (CMMRD / rhabdoid) ~10%"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[5]`** (step 1, SOLE_ANY): `condition: "Pediatric DICER1-spectrum tumor (pleuropulmonary blastoma, ovarian Sertoli-Leydig cell tumor, multinodular goiter / thyroid neoplasms, cystic nephroma, embryonal rhabdomyosarcoma of cervix) — germline DICER1 yield variable but high in pleuropulmonary blastoma (~70%)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 2, SOLE_ALL): `condition: "Pediatric proband with ≥2 primary cancers at any age — multiple primaries are strongly suggestive of underlying predisposition"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 3, SOLE_ANY): `condition: "Neurocutaneous features (café-au-lait macules, neurofibromas, optic glioma, Lisch nodules, axillary / inguinal freckling) → suspect NF1"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[10]`** (step 3, SOLE_ANY): `condition: "Bilateral / multifocal pheochromocytoma + paraganglioma → suspect VHL or SDHx"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[11]`** (step 3, SOLE_ANY): `condition: "RASopathy features (Noonan, Costello, CFC) in proband with hematologic malignancy → suspect RASopathy-associated JMML"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[1]`** (step 3, SOLE_ANY): `condition: "Bilateral vestibular schwannomas or meningiomas + skin neurofibromas → suspect NF2"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[2]`** (step 3, SOLE_ANY): `condition: "Macrocephaly + hemihypertrophy + omphalocele + macroglossia + neonatal hypoglycemia → suspect Beckwith-Wiedemann syndrome"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[3]`** (step 3, SOLE_ANY): `condition: "Aniridia + GU anomalies + intellectual disability → suspect WAGR syndrome (WT1 deletion)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[4]`** (step 3, SOLE_ANY): `condition: "Bone marrow failure + congenital anomalies (radial-ray defects, cafe-au-lait, short stature) → suspect Fanconi anemia"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[5]`** (step 3, SOLE_ANY): `condition: "Short stature + sun-sensitivity + immunodeficiency → suspect Bloom syndrome"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[6]`** (step 3, SOLE_ANY): `condition: "Severe photosensitivity + early skin cancers → suspect xeroderma pigmentosum"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[7]`** (step 3, SOLE_ANY): `condition: "Cerebellar ataxia + immunodeficiency + telangiectasia → suspect ataxia-telangiectasia (ATM biallelic)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[8]`** (step 3, SOLE_ANY): `condition: "Marfanoid habitus + mucosal neuromas + ganglioneuromatosis → suspect MEN2B"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`any_of[9]`** (step 3, SOLE_ANY): `condition: "Café-au-lait macules in a child with ≥1 pediatric cancer AND consanguineous parents → suspect Constitutional Mismatch Repair Deficiency (CMMRD — biallelic MMR)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 4, SOLE_ALL): `condition: "Syndromic features identified at step 3 — refer to clinical genetics for syndrome-specific panel"`
  - Confidence: **NEEDS_CLINICAL_JUDGMENT** — No gene/biomarker-shaped token found — this is vague descriptive prose that needs a clinician to define an operational threshold.
- **`any_of[0]`** (step 5, SOLE_ANY): `condition: "First-degree relative with cancer diagnosed <50, OR ≥2 second-degree relatives with cancer at any age, OR ≥1 family member with sentinel-LFS-tumor (ACC, CPC, anaplastic rhabdomyosarcoma)"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
- **`all_of[0]`** (step 6, SOLE_ALL): `condition: "Pediatric cancer proband without sentinel-tumor + without multi-primary + without syndromic features + without family-history suspicion — consider comprehensive panel per AACR 2017 / COG recommendations"`
  - Confidence: **NEEDS_NEW_FINDING** — No candidate finding key exists in the KB — needs a new biomarker/RedFlag/questionnaire field before this can route on anything.
