# OpenOnco Prevention / Early-Diagnosis Scope — Proposal

**Status:** DRAFT, 2026-05-18. Not authoritative. Adoption requires
Clinical Co-Lead signoff under CHARTER §12 (governance of governance —
amendments to CHARTER itself need consensus + 7-day public comment).
**Prerequisite documents:** `specs/CHARTER.md` (especially §1, §2, §3, §15),
`specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md` (especially §3 Disease, §4 Biomarker,
§7 Indication, §9 RedFlag, §19), `specs/PATIENT_MODE_SPEC.md`.
**Anchor session:** conversation 2026-05-18 with project initiator
re. "prevention / early diagnosis" as a parallel deliverable to the
treatment plan.

---

## 1. Why this exists

The project initiator proposes adding a second deliverable alongside the
treatment plan: a **prevention / early-diagnosis plan** for at-risk
individuals (most concretely: family members of cancer patients) that
captures risk factors across multiple causal categories — not only
germline genetics — and produces an actionable, cited recommendation.

The triggering observation is the project's own reference case (patient
zero, HCV-associated marginal-zone lymphoma): for this patient, **treating
the underlying HCV with DAA therapy is the highest-leverage prevention
pathway for that lymphoma type**, and is in fact codified as first-line
treatment for indolent low-grade HCV-positive B-cell lymphomas in NCCN
guidelines. Had a prevention/causal framework been available earlier,
the at-risk pathway would have been visible.

This proposal scopes the addition, identifies the binding regulatory
constraint, recommends a path, and proposes the smallest schema delta
that lets the existing engine compose a prevention plan without
inventing new top-level entities.

---

## 2. The binding constraint: CHARTER §15 C1

CHARTER §15 deliberately positions OpenOnco under the FDA non-device CDS
carve-out (FD&C §520(o)(1)(E)). The four criteria are load-bearing for
the project's regulatory posture in the US, EU, and UK.

**§15.2 C1** (verbatim): *"HCP-only, never patient-facing. Direct-to-patient
→ device."*

**§15.3** lists "Pivot to a patient-facing version" as an explicit trigger
for governance review and likely re-classification as a medical device.

**§2** restates this: *"Is not intended for patients / caregivers directly
— HCP only ... Direct-to-patient deployment would require re-classification
as a medical device — outside CHARTER scope (per §15)."*

PATIENT_MODE_SPEC §1.2 preserves this by framing the patient bundle as a
**translation** of an HCP-targeted plan, not as a separate clinical product
delivered to the patient. The engine treats the case for an HCP; the patient
view is a derived render.

Any prevention proposal must respect §15 C1 or explicitly trigger §15.3
re-classification. There is no in-between.

### 2.1. Three paths

| Path | Persona | §15 implication | Effort |
|---|---|---|---|
| **A — HCP-mediated** | Genetic counselor, oncologist, PCP using OpenOnco to draft a prevention/screening plan for an at-risk individual. Patient sees translated bundle (existing patient-mode pattern). | **Non-device preserved.** No §15 trigger. | Small. Schema deltas + KB content. |
| **B — Patient-direct (medical device)** | User uploads their own family/medical/exposure history and receives a prevention plan with no clinician in the loop. | **Triggers §15.3 re-classification.** Full FDA/EMA/MHRA pathway. Clinical validation studies. Several years and a different governance structure (CHARTER §13). | Outside current charter scope. |
| **C — Hybrid (informational only, HCP-handoff baked in)** | Patient-direct but every output ends with "show this to your doctor" and disclaims clinical recommendation. | **Regulatory gray zone.** Some screening apps occupy this space; FDA enforcement has been inconsistent. Higher risk of post-hoc re-classification. | Medium. Requires explicit handoff UX + stricter disclaimers + ongoing regulatory monitoring. |

### 2.2. Recommendation: Path A — but name the trade-off

The HCP-mediated path:
- Preserves the §15 non-device positioning the entire CHARTER is designed
  around.
- Reuses the existing patient-mode translation layer (PATIENT_MODE_SPEC):
  the engine output is for the HCP; the patient gets the same translated
  bundle treatment plans get today.
- Doesn't require a CHARTER §1/§2 amendment — the project already serves
  HCPs and already produces patient-readable bundles.
- Maps cleanly onto real workflows: genetic counselors, primary-care
  physicians doing risk consultations, and oncologists doing
  family-history follow-up are real users with real prescribing/referral
  authority.

**Honest trade-off to surface explicitly:** the project's stated product
vision (per session memory) is *"free public resource: upload patient
profile → get living two-plan treatment plan that auto-refines as new data
arrives"* — read literally, that is Path B (patient-direct). Current
CHARTER §15 forbids Path B. The two have always been misaligned; the
treatment-plan work has been progressing under the patient-mode-as-
translation interpretation, which is compatible with §15 only if the
primary user is the HCP and the patient bundle is a derived render of the
HCP-targeted plan.

**Choosing Path A for prevention is therefore narrowing the vision to fit
the current CHARTER, not extending the CHARTER to fit the vision.** This
is a deliberate call, not a continuity argument. The reason to make it:
the regulatory cost of Path B is at v1.0+ scale (clinical-validation
studies, FDA/EMA/MHRA submission, formalized legal structure per CHARTER
§13). The reason to revisit: if the project initiator's intent is
genuinely patient-direct, Path A is a temporary stance and the v1.0
pivot to Path B should be on the roadmap explicitly, not implicit.

Path C is not recommended — it carries regulatory risk without the
guardrails of either A or B.

---

## 3. Proposed CHARTER amendment (Path A — minimal)

CHARTER §1 and §2 do not need to change. They already describe the
project as an HCP information resource that produces "a structured view
of a case." A prevention plan is such a view for a different patient
state (at-risk asymptomatic) and the same persona (HCP).

CHARTER §3 (Scope at MVP) is currently treatment-focused. The minimal
amendment expands it.

### 3.1. §3 delta

**Current §3 "Included":**

> - First-line treatment for confirmed diagnoses
> - Adult hemato-oncology (starting area)

**Proposed §3 "Included" (additions in bold):**

> - First-line treatment for confirmed diagnoses
> - **Prevention / screening recommendations for HCP-mediated
>   consultation with at-risk asymptomatic individuals (e.g., first-degree
>   relatives of cancer patients, individuals with chronic infections
>   classified by IARC as Group 1 carcinogens, individuals with
>   established occupational exposures). Output: a "Prevention Plan"
>   parallel to the "Treatment Plan", using the same engine, same KB,
>   same sources, same HCP-targeted persona, same patient-mode translation
>   layer.**
> - Adult hemato-oncology (starting area)

**§3 "Not included in MVP" — additions:**

> - **Patient-direct prevention service (per §15 C1 — parked for v1.0+)**
> - **Multi-cancer early-detection (MCED, e.g., Galleri-style ctDNA panels)
>   — references only, never primary recommendation, per §15 C5 (sources
>   must be established/well-understood, MCED still in trials).**
> - **Image- or signal-based risk modeling (mammography AI etc.) — per
>   §15 C1/C3 (no raw image input).**

### 3.2. §15 clarification (no semantic change)

Add a non-normative note to §15.1 Criterion 3 ("recommendations to HCP
about prevention/diagnosis/treatment") explicitly listing prevention as
in-scope:

> Per §3, OpenOnco produces both treatment plans (for diagnosed patients)
> and prevention plans (for at-risk asymptomatic individuals consulted by
> an HCP). Both surface as ≥2 tracks (standard / aggressive surveillance,
> or standard / extended screening, or analogous pairs), preserving the
> §15.2 C4 invariant against single-binding-directive output.

### 3.3. No change required to §6, §7, §8, §9, §11

- §6 (clinical change process) applies unchanged.
- §7 (transparency) applies unchanged.
- §8 (AI tools) applies unchanged — §8.3 prohibitions on LLM-as-decision-maker
  apply equally to prevention rules.
- §9 (safety) applies unchanged.
- §11 (disclaimer) applies unchanged.

---

## 4. Schema composition (no new top-level entity)

The advisor reading of the schema confirms: existing entities can compose
"risk factor → cancer → intervention" without introducing a new top-level
entity. This is the smallest schema delta.

### 4.1. Existing primitives we reuse

- **`Disease.archetype = etiologically_driven`** (KSS §3.3) — already lists
  HCV-MZL, MALT/H.pylori, HPV-OPC as examples. The treatment-the-cause
  pattern is already first-class.
- **`Disease.etiological_factors`** (KSS §3.1, line 162) — already structured.
- **`Biomarker`** with `actionability_lookup` (KSS §4.3) and germline-aware
  fields — already supports germline-vs-somatic distinction.
- **`RedFlag`** (KSS §9) — already triggers Indication routing based on
  patient features. Pedigree red flags and exposure red flags fit
  natively.
- **`Algorithm`** (KSS §13) — decision tree. Risk-stratification trees
  fit without modification.
- **`Indication`** (KSS §7) — currently implies "treatment." A new
  `intent` field disambiguates.

### 4.2. Required additive deltas (small, §17-style ratification)

| Field | Entity | Current | Proposed | Notes |
|---|---|---|---|---|
| `intent` | `Indication` | implicit `treatment` | enum: `treatment` (default, back-compat) \| `prevention` \| `screening` \| `surveillance` | Same Indication shape, just a typed audience. Engine can filter by intent when assembling Plan vs. Prevention Plan. **Back-compat = default-on-read in the Pydantic loader; no backfill edit required across the existing ~400 Indication YAMLs.** |
| `clinical_context` | `Biomarker` | implicit `tumor_profiling` | array enum: `germline_susceptibility`, `tumor_profiling`, `screening_surveillance`, `prognostic`, `predictive` | Multi-valued (a marker can serve >1 context, e.g., MMR). |
| `applicable_in_asymptomatic` | `Biomarker` | absent | bool, default `false` | Fast filter for prevention plan composition. |
| `risk_category` | `RedFlag` | absent | enum: `genetic`, `infectious`, `chronic_condition`, `occupational`, `iatrogenic`, `lifestyle`, `reproductive`, plus the existing treatment-time categories | Existing RedFlag types stay; new prevention categories are additive. |

**Out of scope for this proposal:** introducing a `RiskFactor` or
`RiskAssociation` top-level entity. The composition above covers the
matrix the project initiator described without expanding the entity
count.

### 4.3. New deliverable: `PreventionPlan`

Parallel to `Plan` (treatment), the engine produces a `PreventionPlan`
when the patient profile carries no confirmed diagnosis but carries
≥1 prevention-eligible RedFlag (family history, chronic infection,
established exposure). The PreventionPlan reuses the existing track
architecture: at least two tracks (e.g., standard-surveillance vs.
intensive-surveillance, or treat-the-cause vs. monitor) per §15.2 C4.

This is render-and-engine work, not new schema. The data shape is the
same as `Plan` with `tracks` differing only in their `Indication.intent`
values.

---

## 5. Risk-factor framework — 7 categories

Adopted from cancer epidemiology (IARC Monographs categorization +
WCRF/AICR continuous update + USPSTF + NCCN Genetic/Familial High-Risk
guidelines). Each category maps to specific patient-profile fields, a
specific RedFlag risk category, and a specific class of intervention.

| Category | Patient input | Intervention class | Example |
|---|---|---|---|
| **Genetic (germline)** | Pedigree (FHIR `FamilyMemberHistory`), optional prior germline test | Cascade testing, syndrome-specific surveillance, genetic counseling referral, prophylactic surgery (when applicable) | BRCA1/2, Lynch (MMR), VHL, FH/HLRCC, FLCN/BHD, MET/HPRC, TP53, APC, MEN1/2 |
| **Infectious** | Past medical history (chronic infections), serologies | Treat infection (DAA for HepC, antivirals for HepB, eradication for H. pylori), vaccinate (HPV, HepB), surveillance (AFP+US for cirrhotics) | HepB/C → HCC + NHL; HPV → cervix/oropharynx/anal; H. pylori → gastric + MALT; EBV → Burkitt/NPC/PTLD; HIV → KS/NHL/cervix; HTLV-1 → ATL |
| **Chronic conditions / autoimmune** | PMH | Optimize disease, surveillance protocols | UC/Crohn → CRC; Barrett's → esophageal AC; PSC → cholangiocarcinoma; celiac → EATL |
| **Occupational / environmental** | Occupational history, environmental exposures | Avoid, PPE, surveillance | Asbestos → mesothelioma; benzene → AML; aromatic amines → bladder; arsenic → skin/bladder; radon → lung |
| **Iatrogenic** | Prior treatments | Monitor, de-escalate where possible | Prior RT → secondary cancers; immunosuppression → PTLD/SCC; tamoxifen → endometrial; alkylators → t-AML |
| **Lifestyle** | Smoking, alcohol, BMI, diet | Counseling, structured cessation/modification | All major epithelial cancers |
| **Reproductive** (for hormone-driven) | Parity, menarche/menopause, HRT history | Counseling | Breast, endometrial, ovarian |

Sources for the framework: IARC Monographs (CC-BY for citation), WCRF/AICR
Continuous Update Project (open access), USPSTF (public domain), NCCN
Genetic/Familial High-Risk guidelines (referenced under existing NCCN
license terms in the project).

**Banned, per CHARTER §2:** OncoKB (already removed), SNOMED CT (license),
MedDRA (license). Existing project policy applies unchanged.

---

## 6. Pilot sequence

**v0.2-A: Infectious etiologies (recommended starter)**
- 6-8 RiskFactor cases as `RedFlag` + `Indication(intent=prevention)`:
  HepB, HepC, HPV, H. pylori, EBV, HIV, HTLV-1 (CHARTER §3 amendment
  preserves adult scope).
- Reuses the existing `Disease.archetype = etiologically_driven` pattern.
- Highest ROI for Ukraine specifically (HepC/HepB prevalence ~3% in
  adults, vs <0.5% in Western Europe).
- Validated by patient zero (HCV-MZL DAA pathway).
- Cleanest source policy (IARC Group 1, public; WHO; AASLD/NCCN
  guidelines already in KB).

**v0.2-B: Hereditary risk (germline + pedigree triage)**
- Multi-syndrome triage: BRCA/HBOC, Lynch (already partially in KB),
  Li-Fraumeni, FAP/MAP, hereditary RCC syndromes (VHL/HLRCC/BHD/HPRC/BAP1).
- Pilot Lynch first (architecture exercise) then expand.
- New: `Biomarker.clinical_context = germline_susceptibility` content for
  the cancer-syndrome genes.
- Risk-model algorithms (Amsterdam II, PREMM5, Manchester, Tyrer-Cuzick
  v8, BOADICEA) implemented as declarative `Algorithm` entities from
  published primary papers. Free-to-use status verified per the
  originating session (PREMM5 cleanest — published JCO 2016 model,
  re-implementable; CanRisk friendly-with-conditions — academic free use,
  third-party embedding requires citation + acknowledgement + usage
  notification; Ask2Me restrictive — per-person license for "individual
  informational purposes only", re-implement from BayesMendel primary
  methods rather than embed).

**v0.3: Occupational + chronic conditions**
- IARC Group 1 environmental carcinogens (asbestos, benzene, radon,
  arsenic, aromatic amines, vinyl chloride).
- Chronic inflammatory predispositions (Barrett's, IBD, PSC, celiac).

**v0.3+: Lifestyle + iatrogenic + reproductive**
- Lifestyle modification framing (WCRF/AICR).
- Prior-treatment surveillance (t-AML, secondary cancers post-RT, PTLD).
- Hormone-driven cancer counseling.

Each phase is one TaskTorrent chunk-class, gated on the §3 amendment
landing.

---

## 7. Open questions for Clinical Co-Leads

1. **§15 read.** Does the Co-Lead group accept the reading that
   HCP-mediated prevention (Path A) does not trigger §15.3 re-classification?
   (The reading is consistent with §15.1 Criterion 3, which already
   mentions "prevention" alongside diagnosis and treatment as eligible
   non-device CDS output.)

2. **§3 amendment language.** Is the proposed §3 wording (4.1) acceptable,
   or does it need narrower phrasing (e.g., explicit list of permitted
   prevention contexts rather than open-ended "at-risk asymptomatic
   individuals")?

3. **PreventionPlan render contract.** Should prevention output reuse the
   `Plan` two-track architecture verbatim, or warrant a separate render
   contract? Argument for reuse: same engine, same §15 C4 invariant.
   Argument for separate: track semantics differ (treatment alternatives
   vs. surveillance intensities).

4. **Pilot order.** Infectious-first (v0.2-A) vs. germline-first (v0.2-B)?
   Proposal recommends infectious based on Ukraine-specific prevalence,
   patient-zero validation, and license cleanliness. Co-Leads may have
   a different clinical priority.

5. **Risk-model re-implementation.** Is re-implementing PREMM5 / Amsterdam
   II from published primary papers (with citation) acceptable, or
   should we redirect users to the upstream calculators (premm.dfci.harvard.edu,
   canrisk.org) for the actual calculation and only embed the
   interpretation layer? Trade-off: simplicity vs. self-containment.

6. **Surveillance Indication category.** Should `Indication.intent =
   surveillance` be folded into `prevention`, or kept distinct? Surveillance
   applies to known carriers (e.g., confirmed BRCA1+); prevention applies
   pre-test. Co-Lead view requested.

7. **NCCN Genetic/Familial High-Risk license posture.** v0.2-B leans on
   NCCN Genetic/Familial High-Risk: Breast/Ovarian/Pancreatic and
   NCCN Genetic/Familial High-Risk: Colorectal/Endometrial as primary
   sources. These may be a different NCCN sub-license than the
   NCCN-Treatment guidelines already cited under the project's existing
   posture. Verify license coverage before relying on them in chunk
   specs. If not covered, fallback sources: USPSTF (public domain),
   ACMG, ESMO Cancer Genetics, primary peer-reviewed publications.

---

## 8. Non-goals (explicit)

- **Patient-direct deployment.** Out of scope per §15 C1.
- **MCED / liquid biopsy as primary screening recommendation.** Per
  §15 C5 (sources must be established/well-understood). Will surface as
  research mention only when relevant.
- **Imaging-based risk models.** Per §15 C3 (no raw image/signal input).
  Can cite mammography risk results from a radiology report extract,
  cannot ingest pixels.
- **Genetic test ordering.** OpenOnco surfaces the indication for testing;
  the HCP orders the test through their usual lab pathway. We do not
  integrate with labs or order systems.
- **PHI hosting.** Same constraint as §9.3 / existing patient_plans
  gitignore.

---

## 9. Status and next steps

This is a scope-decision artifact only. It does **not** propose
implementation, chunk specs, or schema edits. Those land after Co-Lead
signoff on:

1. The §15 C1 reading (Path A vs B vs C).
2. The §3 amendment language.
3. The schema-composition approach (additive fields only, no new
   top-level entity).
4. The pilot order (infectious-first vs germline-first).

Once the above are confirmed, the next artifacts (separate documents) are:

- **Schema §18 ratification proposal** (`specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md`
  §17-style: Indication.intent, Biomarker.clinical_context,
  Biomarker.applicable_in_asymptomatic, RedFlag.risk_category).
- **Chunk spec** for v0.2-A infectious-etiology content (per existing
  TaskTorrent/chunk format).
- **Roadmap memory** entry under "Active roadmap → Prevention /
  early-diagnosis (v0.2 candidate)" tracking the workstream.

---

## 10. Pre-flight / multi-agent coordination notes

- This document is purely additive (one new file under `docs/plans/`).
  No CHARTER edits, no schema edits, no KB content edits.
- Branch: `claude/suspicious-almeida-e4fb10` (worktree).
- Per CLAUDE.md branch ownership: file added in worktree; will not push
  without explicit user confirmation, because this is a scope-decision
  document that the user explicitly wants to review before any further
  workstream is committed.
- Per CLAUDE.md naming convention: filename includes `2026-05-18-1500`
  date stamp + `openonco_prevention_scope` short scope description.
