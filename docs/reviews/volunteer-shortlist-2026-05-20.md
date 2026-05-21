# Volunteer Contributor Shortlist — 2026-05-20

**Audience:** maintainer (you) + one incoming volunteer contributor.
**Goal:** answer "what can the volunteer actually pick up today?" by
auditing the OpenOnco KB state across the four areas you named
(prevention, diagnostic, tumor board / MDT, red flags) plus the two
that bleed into volunteer-friendly work (algorithm wiring,
line-of-therapy indication backfill), surveying the existing
TaskTorrent shelf, and proposing five new chunk-spec candidates.

**Status correction:** your "we don't have any tasks" prior is stale.
`romeo111/task_torrent/chunks/openonco/README.md` already carries **7
queued chunk specs** — see §2. The volunteer can claim one of those
*today*. The five new candidates in §3 fill gaps the existing shelf
does not cover, and §4 fully drafts one of them as
`docs/plans/proposed-chunks-2026-05-20-1500/algo-branch-wiring-ovarian-2l.md`
ready to push to `romeo111/task_torrent` and open a `[Chunk]` issue
against.

---

## 1. KB state — six areas

### 1.1 Prevention (v0.2 workstream)

**What's live.** v0.2 schema + engine landed 2026-05-18 (commits
`553595b2f5` + `24ff626661`). 100+ prevention `Indication` files now
exist (intent=prevention; two-track per §15.2 C4); coverage spans
infectious (HCV, HBV, HPV, HIV, EBV, HTLV-1, H.pylori, HHV-8, EBV),
hereditary (BRCA/HBOC, Lynch, FAP, VHL, HLRCC, FAMMM, Cowden, BAP1,
HPRC), iatrogenic (15 drug-class late-effect pairs), environmental
(arsenic, UV, air pollution, secondhand smoke), and chronic
predisposing conditions (Barrett's, autoimmune thyroiditis, achalasia,
chronic pancreatitis, hemochromatosis, A1AT-deficiency, atrophic
gastritis, refractory celiac).

**What's missing.**

- **Prevention regimens are nearly empty** — only 3 `regimens/`
  entries (`reg_exemestane_chemoprevention.yaml`,
  `reg_raloxifene_chemoprevention.yaml`,
  `reg_tamoxifen_chemoprevention.yaml`). The v0.2-A authoring backlog
  ([roadmap entry, commit `a66f47760b`]) explicitly names 6 missing
  regimens whose drug entities already exist:
  `REG-HP-BISMUTH-QUADRUPLE`, `REG-HBV-ENTECAVIR`,
  `REG-HBV-TENOFOVIR-AF`, `REG-HPV-GARDASIL-9`,
  `REG-HIV-BICTARVY`, `REG-HP-PPI-CLAR-AMOX-TRIPLE`. Until these
  land, every cited prevention `Indication` carries a placeholder
  `recommended_regimen: null`.
- **v0.2-B hereditary continuation** is `[/]` in flight but the
  confirmed-carrier surveillance pathways
  (`RF-*-CONFIRMED-CARRIER` + `IND-*-CARRIER-SURVEILLANCE`
  post-test-positive) are not yet authored for any of the 5
  pilot syndromes. Risk-model algorithms (PREMM5, Tyrer-Cuzick v8,
  BOADICEA v6, Manchester, Amsterdam II) — partly present
  (`algo_brcapro.yaml`, `algo_boadicea_v6_breast_ovarian.yaml`,
  `algo_manchester_brca.yaml`, `algo_chompret_2015_lfs.yaml`),
  others still gaps. HPRC, MEN1/2, Peutz-Jeghers not started.
- **v0.3 occupational + chronic conditions** (Barrett's high-grade
  dysplasia, IBD long-standing, PSC, celiac refractory etc. with
  full intervention coverage) — not started.
- **Render** — PreventionPlan render works for both clinician + patient
  modes (commit `f38d072b09`); no known render-side blockers.

### 1.2 Diagnostic plans (workups)

**What's live.** 24 workup YAML files across solid tumors + heme +
pan-symptom triage (`workups/workup_lymphadenopathy_nonspecific.yaml`,
`workups/workup_cytopenia_evaluation.yaml`,
`workups/workup_monoclonal_gammopathy_incidental.yaml`, etc.).
Diagnostic-mode engine + MDT orchestrator (DiagnosticMDT) shipped.

**What's missing.**

- **5 CRITICAL zero-RF zero-Ind diseases also have no workup** per
  the 2026-04-27 redflag-indication audit
  ([docs/reviews/redflag-indication-coverage-2026-04-27.md:208](docs/reviews/redflag-indication-coverage-2026-04-27.md:208)):
  `DIS-THYROID-PAPILLARY`, `DIS-THYROID-ANAPLASTIC`, `DIS-MTC`,
  `DIS-MASTOCYTOSIS`, `DIS-GLIOMA-LOW-GRADE`. Sources exist
  (`SRC-NCCN-THYROID-2025`, `SRC-NCCN-SM-2025`, `SRC-NCCN-CNS-2025`).
- **5 BLOCKED zero-RF diseases** lack any in-repo source:
  `DIS-IFS`, `DIS-IMT`, `DIS-MPNST`, `DIS-SALIVARY`,
  `DIS-CHONDROSARCOMA`, `DIS-CHOLANGIOCARCINOMA`. These are
  source-ingest-first, workup-second.
- **Prevention-derived new diseases**: `DIS-KAPOSI`, `DIS-NPC`,
  `DIS-PTLD` now exist (per the diseases/ glob), but
  `DIS-GASTRIC-MALT` is still missing (called out as v0.2-A
  follow-up backlog item d). No corresponding workups.
- **Brain-MRI test dedup** — `TEST-BRAIN-MRI-CONTRAST` vs
  `TEST-MRI-BRAIN-CONTRAST` open from Plan B 2026-04-26 batch.
- **Schema rename** — `mandatory_questions` →
  `mandatory_questions_to_resolve` still pending (same batch).

### 1.3 Tumor board (MDT orchestrator)

**What's live.** `knowledge_base/engine/mdt_orchestrator.py` — 13
role skills with `SkillMetadata` (in-place uncommitted refactor per
roadmap), DecisionProvenanceGraph persistence + rehydration (commits
`98ec53f` + `52a8917`), event CLI shipped, PreventionPlan-aware
bootstrap (commit `f38d072b09`).

**What's missing.**

- **Per-disease MDT rules** — current rule set is tuned for
  HCV-MZL / lymphoma archetypes. MM uses generic-cancer fallback
  rules; needs MM-specific roles (transplant coordinator,
  plasma-cell-disorder specialist) and MM-specific questions
  (transplant eligibility, cytogenetic risk discussion, daratumumab
  funding pathway). Solid tumours have no disease-specific MDT
  rules at all.
- **Clinician event REST endpoint** — deferred (auth model, CORS,
  CHARTER §9.3 hosting gate all open).
- **DecisionProvenanceGraph interactive viz** — not started.
- **Folder-refactor** `mdt_orchestrator.py` → `knowledge_base/skills/`
  per SKILL_ARCHITECTURE_SPEC §3-5 — waits on 8 Co-Lead questions
  in §8.

### 1.4 Red flags

**Live.** 524 RedFlag entities (per 2026-05-17 state audit). All 28
original-batch diseases closed full 5-type matrix (Phase 1-7
2026-04-25). 3 universal RFs (TLS-RISK, HBV-REACTIVATION,
INFUSION-REACTION-FIRST-CYCLE).

**What's missing** per the 2026-04-27 audit
([docs/reviews/redflag-indication-coverage-2026-04-27.md](docs/reviews/redflag-indication-coverage-2026-04-27.md)):

- **12 diseases still below 5-type matrix** (audit §3; gate
  `test_5type_matrix_coverage` still failing for them).
- **31 HIGH-severity / CRITICAL RF drafts pending clinical
  sign-off** from audit §6 (named-emergency RFs for T-ALL/B-ALL CNS
  + TLS, PMBCL SVC, NSCLC SVC/brain-mets/cord/effusion, prostate
  cord compression, MM hypercalcemia/cord/hyperviscosity, etc.).
  These are *drafted* (commit-land 2026-04-27), `draft: true`, not
  yet signed off → still gating the 2-reviewer publication path.
- **BLOCKED-on-source diseases** for RF authoring: IFS, IMT, MPNST,
  SALIVARY, CHONDROSARCOMA (no in-repo NCCN-PED-CANCERS /
  NCCN-SOFT-TISSUE-SARCOMA / NCCN-BONE-CANCER / NCCN-SALIVARY).
- **BLOCKED-on-second-source diseases** for RF authoring:
  THYROID-PAPILLARY/ANAPLASTIC + MTC (need `SRC-ATA-MTC-2015` etc.
  to clear 2-source gate); HNSCC airway-emergency + hypercalcemia
  RFs need 2nd source.

### 1.5 Algorithm decision trees + line-of-therapy indications

**Live.** 152+ Algorithm files. Worked example PR #597 (commit
`14062cdb6a`) translated `ALGO-AITL-2L` step 2 from three free-text
`condition:` strings into structured `finding:` clauses against
existing patient-profile fields (`prior_hdaci_exposure`,
`romidepsin_accessible`, `qtc_ms`, `baseline_cardiac_arrhythmia`) —
making `IND-AITL-2L-ROMIDEPSIN` reachable while preserving the
AZACITIDINE default fall-through.

**What's missing** per the 2026-05-17 state audit
([docs/reviews/openonco-state-audit-2026-05-17.md](docs/reviews/openonco-state-audit-2026-05-17.md))
and the 2026-05-18 backlog
([docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md](docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md)):

- **376 of 443 (85%)** `condition:` strings in algorithms are prose
  shape that `_eval_clause` silently treats as False. **45 of 152
  algorithms** have step-1 entirely prose → fall through to
  `default_indication` on every patient.
- **89 unreached indications** across **52 algorithms**. Top 3 by
  unreached count: `ALGO-OVARIAN-2L` (6), `ALGO-BREAST-1L` (5),
  `ALGO-ESOPH-METASTATIC-1L` (5).
- **16 MEDIUM line-shift indication gaps** in audit §5: cervical L2,
  GBM L2, GIST L2, HCC L2, HNSCC L2, melanoma L2 post-IO, ovarian
  L2 platinum-resistant, PDAC L2, prostate L3 mCRPC, SCLC L2,
  urothelial L2, MASTOCYTOSIS L2, MTC advanced L2, T-ALL L3,
  T-PLL L3, EATL L3. Each is a single missing `Indication` YAML
  with an existing source.

### 1.6 BMA (biomarker actionability)

**Live.** 448 BMA entities. CIViC pivot Phase 1+1.5 landed (commits
`5384348` + `c72e45b`). 23 BMA drafts from 2026-04-27 batch sit
`pending_clinical_signoff`.

**What's missing.**

- **14 diseases still without ANY BMA** per 2026-04-27 audit
  ([docs/reviews/bma-coverage-2026-04-27.md:159](docs/reviews/bma-coverage-2026-04-27.md:159)):
  APL, ATLL, CHONDROSARCOMA, EATL, GLIOMA-LOW-GRADE, HNSCC, HSTCL,
  IMT, MF-SEZARY, MPNST, NK-T-NASAL, PMBCL, PTCL-NOS, T-PLL.
- **12 BMA cells blocked on missing in-repo source** (§3.2 of same
  audit) — best yield from ingesting INDIGO (vorasidenib LGG),
  KEYNOTE-158/177 (tumor-agnostic ICI), AUGMENT-101 (revumenib),
  EMERALD (elacestrant), DESTINY-Gastric01 (T-DXd HER2), CAPItello-291
  (capivasertib + fulvestrant).
- **3 documented in-repo NCCN-vs-ESMO disagreements** in 23 drafts
  (`BMA-MGMT-METHYLATION-GBM`, `BMA-HRD-STATUS-OVARIAN`,
  `BMA-HRD-STATUS-PROSTATE`) — must NOT be resolved by drafter
  per CLINICAL_CONTENT_STANDARDS §1.2.

---

## 2. Existing TaskTorrent shelf

Per `romeo111/task_torrent/chunks/openonco/README.md` (fetched
2026-05-20), **7 chunks are queued** and available for the volunteer
to claim. None has a `claimed` status I can see; the shelf carries
workflow state (`queued` → `active` → `done`), not contributor
attribution. Volunteer needs to open a `[Chunk]` issue per the
trusted-agent-WIP-branch-first claim method.

| # | Chunk id | Drops | What it does | Volunteer-suitable? |
|---|---|---|---|---|
| 1 | `civic-bma-reconstruct-all` | ~12 | Rebuild BMA evidence reconstruction from CIViC snapshot (CIViC pivot Phase 3 backlog). | **Yes** — mechanical, source-driven. Already partly executed in `contributions/civic-bma-reconstruct-all/` (commits 2026-04-27 / 2026-05-01). Volunteer extends. |
| 2 | `citation-verify-914-audit` | ~10 | Triage the 914 findings from `docs/reviews/citation-verification-2026-04-27.md` — replace_source / revise_claim / source_stub_needed / maintainer_review. | **Yes** — uses `citation-verification` skill. Triage queues already drafted in `contributions/citation-semantic-verify-v2/`. |
| 3 | `rec-wording-audit-claim-bearing` | ~10 | Audit `rationale` + `notes` prose across claim-bearing entities for treatment-recommendation language that should not be there (per CHARTER §8.3). | Maybe — needs ear for clinical phrasing. Triage queue drafted in `contributions/rec-wording-audit-claim-bearing/triage-queue-critical.md`. |
| 4 | `ua-translation-review-batch` | ~12 | Review Ukrainian translations of patient-facing fields against the English canonical. | **Yes** if volunteer is UA-native. Otherwise pass. |
| 5 | `redflag-indication-coverage-fill` | ~15 | Fill the 65-disease × ~30-redflag empty cells from the 2026-04-27 audit (applicable / not_applicable / uncertain). | Tagged in spec as "highest clinical-risk chunk in the shelf"; first-claim only after #1 and #2 validate the workflow. |
| 6 | `bma-drafting-gap-diseases` | ~15 | Draft BMA cells for the 14 zero-BMA diseases (§1.6 above). | Higher complexity — needs source-extraction + ESCAT tiering. Hold for after first claim. |
| 7 | `source-stub-ingest-batch` | ~10 | Author `source_stub_<source-id>.yaml` for the missing in-repo sources flagged in `bma-coverage` §3.2 + `redflag-indication-coverage` §6. Unblocks #5, #6, several others. | **Yes** — uses `openonco-contributor:source-stub-prep` skill. Mechanical, low clinical risk. |

**Best first-claim from existing shelf:** `source-stub-ingest-batch`
(#7) — it's the dependency of multiple other chunks, low clinical
risk, has a dedicated skill in the openonco-contributor plugin
(`openonco-contributor:source-stub-prep`). After it lands, the
volunteer (or a second volunteer) can pick up #1, #2, then #5.

---

## 3. Five new chunk candidates (gaps not on existing shelf)

These are areas the existing shelf does not cover. None requires
clinical sign-off to be useful — they are mechanical, source-driven
KB authoring or wiring tasks.

### 3.1 `algo-branch-wiring` (one chunk per algorithm)

**Closes:** §1.5 89-unreached-indications gap.
**Source of truth:** [docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md](docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md).
**Worked example:** PR [#597](https://github.com/romeo111/cancer-autoresearch/pull/597) (`14062cdb6a`).
**Per-chunk scope:** one Algorithm YAML, translate ≤5 free-text
`condition:` strings to structured `finding:` clauses.
**Drop estimate:** ~1 Drop per algorithm. Pool = 52 algorithms → 52
possible chunks.
**Drafted as §4 below** (`ALGO-OVARIAN-2L`, the top-of-backlog
candidate with 6 unreached indications).

### 3.2 `prevention-regimen-authoring` (one chunk per regimen wave)

**Closes:** §1.1 prevention-regimens-empty gap.
**Per-chunk scope:** 6 regimens explicitly named in v0.2-A backlog
(REG-HP-BISMUTH-QUADRUPLE, REG-HBV-ENTECAVIR, REG-HBV-TENOFOVIR-AF,
REG-HPV-GARDASIL-9, REG-HIV-BICTARVY, REG-HP-PPI-CLAR-AMOX-TRIPLE).
**Drop estimate:** ~2-3 Drops total.
**Sources:** AASLD-HBV-2024, AASLD-IDSA-HCV-2023, AGA-H-pylori-2024,
ACG-H-pylori-2024, IARC-Monograph-100B-2012 (all in repo).
**Acceptance:** all 6 referenced prevention Indications can replace
their `recommended_regimen: null` placeholder; validator green.

### 3.3 `workup-zero-disease-fill` (one chunk per disease)

**Closes:** §1.2 zero-workup-zero-RF gap for 5 source-available diseases.
**Per-chunk scope:** one workup YAML per disease + (recommended)
backfill of the missing RFs for the same disease in a paired commit.
**Pool:** DIS-THYROID-PAPILLARY, DIS-THYROID-ANAPLASTIC, DIS-MTC,
DIS-MASTOCYTOSIS, DIS-GLIOMA-LOW-GRADE.
**Drop estimate:** ~1 Drop per disease.
**Sources:** NCCN-THYROID-2025, NCCN-SM-2025, NCCN-CNS-2025
(all in repo); MTC + Thyroid Anaplastic + Papillary also need
2nd-source ingestion (which `source-stub-ingest-batch` from §2 can
unblock as a dependency).

### 3.4 `mdt-per-disease-rules-mm` (and follow-ups per disease)

**Closes:** §1.3 generic-fallback-rules gap. MM is the most-mature
disease in the KB after HCV-MZL and currently uses generic
lymphoma/cancer fallback rules.
**Per-chunk scope:** add MM-specific MDT roles (transplant
coordinator, plasma-cell-disorder specialist) + MM-specific
questions (transplant eligibility / cytogenetic-risk discussion /
daratumumab funding pathway) inside `mdt_orchestrator.py` and back
them with tests in `tests/test_mdt_orchestrator.py`.
**Drop estimate:** ~2 Drops.
**Higher complexity** — requires reading existing MDT rules,
schema-aligned new role IDs per CHARTER §6, and a clinical sense for
which questions matter. Hold for second or third volunteer claim.

### 3.5 `hereditary-confirmed-carrier-surveillance` (one chunk per syndrome)

**Closes:** §1.1 v0.2-B continuation gap. Pilot covered 5 syndromes
with pedigree-suspicion RF + genetic-counseling/testing tracks but
NOT the post-test-positive surveillance pathway.
**Per-chunk scope:** for one syndrome, author the
`RF-*-CONFIRMED-CARRIER` + `IND-*-CARRIER-SURVEILLANCE` pair plus
optional algorithm-step extension.
**Pool:** BRCA-HBOC, Lynch, FAP, VHL, HLRCC (5 chunks possible).
**Drop estimate:** ~1.5 Drops per syndrome.
**Sources:** NCCN-Genetic-Familial-CRC-2025,
NCCN-Genetic-Familial-Breast-Ovarian-2025, ASCO-ACMG-Lynch-2014
(all in repo). NCCN-Genetic-Familial currently has
`legal_review.status: escalated` per roadmap — depending on the
resolution, may need a non-NCCN replacement source.

---

## 4. Drafted chunk specs ready to push to `task_torrent`

All five drafts written under
[docs/plans/proposed-chunks-2026-05-20-1500/](../plans/proposed-chunks-2026-05-20-1500/)
in v0.4 chunk-spec format (12 required sections + Severity / Min
Contributor Tier / Queue soft-required). Each needs to be pushed
to `romeo111/task_torrent` as
`chunks/openonco/<name>.md` and a `[Chunk]` issue opened.

| # | Chunk file | Severity / Tier | Drops | Closes which §3 candidate | First-claim fit |
|---|---|---|---|---|---|
| 1 | [`algo-branch-wiring-ovarian-2l.md`](../plans/proposed-chunks-2026-05-20-1500/algo-branch-wiring-ovarian-2l.md) | low / new | ~1 | §3.1 (top of backlog, 6 unreached) | **Recommended first-claim for any volunteer** — lowest cognitive load, worked example PR #597, no clinical sign-off needed |
| 2 | [`algo-branch-wiring-breast-1l.md`](../plans/proposed-chunks-2026-05-20-1500/algo-branch-wiring-breast-1l.md) | low / new | ~1 | §3.1 (#2 in backlog, 5 unreached) | Same pattern as #1; natural second claim |
| 3 | [`algo-branch-wiring-esoph-metastatic-1l.md`](../plans/proposed-chunks-2026-05-20-1500/algo-branch-wiring-esoph-metastatic-1l.md) | low / new | ~1 | §3.1 (#3 in backlog, 5 unreached) | Same pattern; natural third claim |
| 4 | [`prevention-regimen-authoring-wave1.md`](../plans/proposed-chunks-2026-05-20-1500/prevention-regimen-authoring-wave1.md) | medium / established | ~2-3 | §3.2 (6 named regimens) | Different skill set (source-verbatim dose extraction); good for a contributor with a clinical background |
| 5 | [`workup-thyroid-papillary.md`](../plans/proposed-chunks-2026-05-20-1500/workup-thyroid-papillary.md) | low / new | ~1 | §3.3 (smallest of 5 source-available zero-RF diseases) | Smallest possible KB-authoring scope; good first KB-authoring chunk if volunteer wants to write content not just wire |
| 6 | [`hereditary-brca-carrier-surveillance.md`](../plans/proposed-chunks-2026-05-20-1500/hereditary-brca-carrier-surveillance.md) | medium / established | ~1.5 | §3.5 (most-mature of 5 syndromes) | v0.2-B continuation; visible KB delta for user-facing v0.2 story |

**Why these five together (not just one):**

- **Variety across complexity** — 3 mechanical wire-up chunks for
  first-time volunteers; 2 KB-authoring chunks for contributors with
  clinical background.
- **Variety across domains** — engine wiring, prevention regimens,
  diagnostic workups, hereditary surveillance — different KB areas
  exercised so the contributor doesn't pigeonhole.
- **Spin-up template established** — once `algo-branch-wiring-ovarian-2l`
  validates, maintainer can clone for the remaining 49 algorithms in
  ~15 min each. Same for `workup-thyroid-papillary` (4 sibling
  diseases) and `hereditary-brca-carrier-surveillance` (4 sibling
  syndromes).

**No chunk drafted for §3.4 (MDT per-disease rules):** higher
complexity, needs clinical judgment about which MM-specific roles
to add. Hold for a contributor who's already landed one chunk and
shown clinical fluency.

---

## 5. Recommended sequencing

1. **Tell the volunteer the existing shelf exists.** Point them at
   `romeo111/task_torrent/chunks/openonco/README.md` and recommend
   `source-stub-ingest-batch` (chunk #7) as the first claim — lowest
   clinical risk, unblocks downstream chunks, has a dedicated skill.
2. **Push the new chunk in §4** to `romeo111/task_torrent` as
   `chunks/openonco/algo-branch-wiring-ovarian-2l.md` and open a
   `[Chunk]` issue. If volunteer prefers small-scope mechanical work
   over source ingestion, this becomes their first claim instead.
3. **Decide on §3.2 / §3.3 / §3.4 / §3.5** — pick one to draft next
   based on which gap matters most to you. §3.2 (prevention regimens)
   unblocks ~15 of the v0.2-A indications and would be a natural pair
   with the v0.2-B work in flight.
4. **Don't draft §3.4** (MDT per-disease) until you have a volunteer
   who's already landed one chunk and shows clinical fluency — it's
   the most-judgment-driven of the five.

---

## 6. Out of scope here

- Editing existing live KB entities — drafts only.
- Pushing patches to `romeo111/task_torrent` — that's the next step
  for the maintainer; this doc + the drafted chunk-spec are the
  prerequisite.
- Drafting new clinical content for BLOCKED-on-source diseases
  (IFS, IMT, MPNST, SALIVARY, CHOLANGIO, CHONDROSARCOMA) — they
  need source-stub-ingest-batch (existing shelf chunk #7) first.
- Resolving the 3 in-repo NCCN-vs-ESMO disagreements in §1.6 — per
  CLINICAL_CONTENT_STANDARDS §1.2 those are Co-Lead-only, not
  volunteer-drafted.
