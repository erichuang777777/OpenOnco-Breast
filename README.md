# OpenOnco

> **Open-source clinical decision support for oncology tumor boards.**
> Upload a patient profile → get two alternative treatment plans
> (standard + aggressive), side by side, with every recommendation cited.
> Plans refresh as new data arrives. All clinical logic lives in a
> declarative rule engine over a curated knowledge base — **no LLM
> picks regimens** ([CHARTER §8.3](specs/CHARTER.md)).

**Live demo:** **[openonco.info](https://openonco.info)** — try it in the browser, no install needed.
**Knowledge base:** 420 indications · 377 sources · 140 algorithms across hematologic + GI + pulmonary oncology (growing).
**FDA non-device CDS positioning** per [CHARTER §15](specs/CHARTER.md) — informational support tool, not a medical device.
**License:** Code MIT · Content / specs CC BY 4.0.

---

## Why this exists

Picking a regimen for a real patient is **2–4 hours of manual desk work**: open NCCN PDF, cross-check ESMO, re-read the local МОЗ protocol, verify formulary reimbursement, look up renal/hepatic dose adjustments, layer supportive care, remember vaccinations and OI prophylaxis. Every patient. One missed contraindication can be fatal.

OpenOnco automates the chore work. The clinician gets a **drafted plan with every citation already attached** and only verifies / tailors it. The logic mirrors a **classical multidisciplinary tumor board (MDT)** — each "virtual specialist" is a versioned rule module with its own sources and `last_reviewed` stamp.

→ Live KB metrics, per-disease coverage, sign-off ratio: **[openonco.info/capabilities](https://openonco.info/capabilities.html)**

---

## What it does

- **Two-track plan generator.** Always ≥2 alternative tracks side by side — never a single "system-prescribes-X" output. Each track ships rationale, red-flag triggers, hard contraindications, supportive care, monitoring schedule, sourced outcome numbers, and a "what NOT to do" list.
- **Versioned MDT skill registry.** Hematology, hematopathology, ID/hepatology, radiology, molecular genetics, clinical pharmacy, radiation oncology, surgical oncology, transplant, CAR-T, and more — each a versioned rule bundle with `last_reviewed`, `clinical_lead`, and reviewer sign-offs.
- **Diagnostic-phase MDT.** No histology → Workup Brief, never a treatment Plan.
- **Plan revisions / supersedes loop.** Immutable audit chain; refuses illegal downgrades.
- **ESCAT + CIViC actionability.** Biomarker × disease × drug evidence tiers surfaced as render badges. CIViC (CC0) is the primary actionability source.
- **HTML render layer.** Single-file A4-printable HTML per Plan / Diagnostic Brief / Revision Note. Patient-mode and HCP-mode. UA / EN.
- **In-browser Pyodide demo.** The actual Python engine runs in the browser — no backend, no patient data leaves the device. This is a showcase property of the `try.html` demo specifically, not a system-wide guarantee: Hospital Edition and the CQL/ELM decision engine ([ADR-0005](docs/adr/0005-production-decision-engine-runs-server-side.md)) run server-side, prioritizing decision-logic correctness over client-only execution.

---

## Try it

**Clinicians:** **[openonco.info/try.html](https://openonco.info/try.html)** — paste a patient JSON profile and the Pyodide-loaded engine generates a treatment plan. No installation required, no PHI server-side.

**Tumor-board questions:** **[openonco.info/ask.html](https://openonco.info/ask.html)** — optional server-backed prototype for free-text oncology vignettes. ChatGPT structures the case, OpenOnco runs the deterministic rule engine, then the response is framed as an answer, alternatives, or clarifying questions. Do not paste identifiable real-patient data.

**Sample patients:** **[openonco.info/gallery.html](https://openonco.info/gallery.html)** — pre-rendered cases across DLBCL, FL, CLL/SLL, MCL, MZL, MM (hematologic) and gastric, esophageal, PDAC, cholangiocarcinoma, CRC, NSCLC, SCLC, mesothelioma (solid tumors).

**Contributors:** start with [`specs/`](specs/) and [`CLAUDE.md`](CLAUDE.md) — these define scope, schemas, and authoring conventions before any KB or code change.

**AI-assisted contributions:** OpenOnco accepts distributed contributor work through the [TaskTorrent chunk-shelf](https://github.com/romeo111/task_torrent/tree/main/chunks/openonco). Read [`docs/contributing/HELP_WANTED.md`](docs/contributing/HELP_WANTED.md) — pick an active `[Chunk]` issue, run with your AI tool, submit a sidecar PR. Safety boundaries: no medical advice, no treatment recommendations, no patient-specific outputs; everything reviewed before merge.

**Developers:**

```bash
git clone https://github.com/romeo111/OpenOnco.git
cd OpenOnco
pip install -e .
python scripts/audit_validator.py --human
pytest tests/
```

Python 3.11+ required.

---

## How to contribute

**Try it and tell us what's wrong.** A clinician's eye on a rendered Plan is the most valuable contribution right now. Try the [demo](https://openonco.info/try.html) on a case you know, then **[open a clinical-feedback issue](https://github.com/romeo111/OpenOnco/issues/new?labels=clinical-feedback)** — even one line ("this regimen is missing the CrCl <30 dose adjustment") helps.

**Add a disease or fix a regimen.** KB is YAML under `knowledge_base/hosted/content/`. Read [`specs/CLINICAL_CONTENT_STANDARDS.md`](specs/CLINICAL_CONTENT_STANDARDS.md) for citation format and [`specs/REDFLAG_AUTHORING_GUIDE.md`](specs/REDFLAG_AUTHORING_GUIDE.md) for RedFlags (≥2 Source citations required). New clinical content stays `draft` / `proposed` / `partial` / `stub_full_chain` until two of three Clinical Co-Leads sign off ([CHARTER §6.1](specs/CHARTER.md)) — **never set `reviewed: true` yourself.**

**Engine / render / infrastructure.** Standard PR — `pytest` must pass, new code needs tests. Schema and spec changes go through CHARTER §6 review.

**Become a Clinical Co-Lead.** Hematology / oncology / clinical pharmacology sub-specialty depth needed to dual-sign content out of STUB. **[Open a PR](https://github.com/romeo111/OpenOnco/compare)** that adds your name + area + CV / public profile link to [`specs/CLINICAL_LEADS.md`](specs/CLINICAL_LEADS.md), or **[open an issue](https://github.com/romeo111/OpenOnco/issues/new?labels=co-lead-application&title=Co-Lead+application:+%5Byour+area%5D)** with the same — public audit trail by design.

---

## Specifications

All specifications live in [`specs/`](specs/) (Ukrainian, English technical terms inline). **Read [`CHARTER.md`](specs/CHARTER.md) first** — it governs scope, FDA positioning, dual-review process, and what the project explicitly does **not** do.

Key specs: [`CLINICAL_CONTENT_STANDARDS`](specs/CLINICAL_CONTENT_STANDARDS.md) · [`KNOWLEDGE_SCHEMA_SPECIFICATION`](specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md) · [`SOURCE_INGESTION_SPEC`](specs/SOURCE_INGESTION_SPEC.md) · [`REDFLAG_AUTHORING_GUIDE`](specs/REDFLAG_AUTHORING_GUIDE.md).

---

## Medical disclaimer

OpenOnco is an **informational resource** to support tumor-board discussion. It is **not** a system that makes clinical decisions, **not** a medical device, and **not** for use without a qualified oncologist. Every recommendation must be verified by the treating physician with access to the full clinical picture and discussed by a multidisciplinary team. See [`specs/CHARTER.md`](specs/CHARTER.md) §11 + §15 for the full positioning statement.

---

## License

- **Code:** MIT.
- **Specifications & generated content:** CC BY 4.0.
- **Source citations** retain their original licenses — NCCN, ESMO, EHA, BSH, EASL, МОЗ України НСЗУ, etc. are **referenced, not redistributed** ([CHARTER §2](specs/CHARTER.md) non-commercial scope; many source licenses depend on this).

---

**Oncologist or clinical pharmacologist?** [Try the demo](https://openonco.info/try.html) on a case you know, then [open an issue](https://github.com/romeo111/OpenOnco/issues/new?labels=clinical-feedback) with what you'd change. That's the loop we're optimizing for.
