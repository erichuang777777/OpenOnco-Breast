# Ubiquitous Language

Domain glossary for OpenOnco. Extracted from CHARTER, specs, code, and ongoing conversations. Update via `/ubiquitous-language` as terminology evolves.

## Patient & clinical record

| Term                | Definition                                                                                              | Aliases to avoid                          |
| ------------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| **Patient**         | The human receiving care; never identified in public artifacts                                          | User, case, subject                       |
| **Patient Profile** | Structured FHIR R4/R5 + mCODE record submitted as engine input                                          | Patient data, input, profile              |
| **Histology**       | The morphologic diagnosis required before any treatment **Plan** can be produced (CHARTER §15.2 C7)    | Diagnosis, pathology                      |
| **Biomarker**       | A measurable molecular or immunophenotypic property used to select **Regimens** or trigger **RedFlags** | Marker, lab, mutation                     |

## Knowledge base entities

| Term           | Definition                                                                                                              | Aliases to avoid                       |
| -------------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| **Disease**    | A clinically distinct oncologic condition (e.g. DLBCL, AML); top-level KB entity                                        | Cancer, tumor, condition               |
| **Indication** | A specific clinical scenario in which a **Regimen** applies (Disease + line + biomarker context)                        | Use case, scenario                     |
| **Regimen**    | A named treatment protocol (e.g. `REG-VRD`) composed of one or more **Drugs** with dosing                               | Protocol, therapy, treatment           |
| **Drug**       | An active pharmaceutical entity referenced by **Regimens**; identified via RxNorm                                       | Medication, agent                      |
| **RedFlag** (**RF**) | A declarative clinical safety/quality trigger evaluated against the **Patient Profile**                           | Alert, warning, rule                   |
| **Algorithm**  | A declarative decision tree producing **Plan** branches from a **Patient Profile**                                      | Workflow, logic, flowchart             |
| **Source**     | A KB entity citing an external authority (guideline, paper, label) backing a clinical claim                             | Citation, reference, link              |

## Plan output

| Term                 | Definition                                                                                                       | Aliases to avoid              |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| **Plan**             | A treatment recommendation produced by the engine; typically delivered as a **Standard Plan** + **Aggressive Plan** pair | Recommendation, treatment plan |
| **DiagnosticPlan**   | A workup recommendation produced when **Histology** is absent — asks for the tests needed to enable a **Plan**   | Workup plan, pre-plan         |
| **Standard Plan**    | The guideline-default branch of the dual-plan output                                                             | Conservative plan             |
| **Aggressive Plan**  | The maximal-evidence-supported branch of the dual-plan output                                                    | Intensive plan                |
| **Plan Section**     | A targetable subdivision of a **Plan** (e.g. `TRACK-AGGRESSIVE`) addressed by **Provenance Events**              | Plan part, section            |

## Source hosting (SOURCE_INGESTION_SPEC §1.4)

| Term            | Definition                                                                                                  | Aliases to avoid              |
| --------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------- |
| **Referenced**  | Default hosting mode — a **Source** is cited by URL, content stays on the publisher's server                | Linked, external              |
| **Hosted**      | A **Source** mirrored locally; allowed only with H1–H5 license justification                                | Cached, mirrored              |
| **Mixed**       | A **Source** with some content hosted (e.g. abstracts) and the rest **Referenced**                          | Hybrid                        |

## Governance & review

| Term                  | Definition                                                                                                              | Aliases to avoid              |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| **CHARTER**           | The governance document at `specs/CHARTER.md`; top of the source-of-truth hierarchy                                     | Constitution, rules           |
| **Spec**              | A versioned authoring document under `specs/` (e.g. `KNOWLEDGE_SCHEMA_SPECIFICATION.md`)                                | Doc, design                   |
| **Clinical Co-Lead**  | One of three named oncologists with sign-off authority on clinical KB content                                           | Reviewer, lead, owner         |
| **Two-Reviewer Merge**| The CHARTER §6.1 rule that any clinical-content change needs approval from two of three Clinical Co-Leads               | Dual review, peer review      |
| **Stub**              | A KB entity that exists structurally but has not received clinical sign-off; not safe for production recommendations    | Draft, placeholder, WIP       |
| **MDT**               | Multidisciplinary Team — the clinical consilium model the product augments                                              | Tumor board, consilium        |

## Provenance & events

| Term                          | Definition                                                                                                       | Aliases to avoid             |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| **Provenance Event**          | An append-only record of a clinician action against a **Plan** target (`confirmed`, `approved`, etc.)            | Event, audit log entry       |
| **Event Log**                 | The per-patient JSONL file at `patient_plans/<patient_id>/events.jsonl` storing **Provenance Events**            | History, audit trail         |
| **Decision Provenance Graph** | The in-memory graph of **Provenance Events** merged into a **Plan** for rendering                                | Provenance, decision graph   |
| **Actor**                     | The person (clinician, reviewer) who emitted a **Provenance Event**; identified by `actor_id` + `actor_role`     | User, author                 |

## Engine & build

| Term            | Definition                                                                                              | Aliases to avoid                 |
| --------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------- |
| **Rule Engine** | The declarative Python evaluator that turns a **Patient Profile** + KB into a **Plan**                  | Engine, brain, solver            |
| **Engine Bundle** | The `openonco-engine.zip` artifact loaded by Pyodide in the browser to run the **Rule Engine** client-side | Wasm bundle, browser engine      |
| **Loader**      | `knowledge_base/validation/loader.py` — reads KB YAMLs, runs schema/ref/contract checks                 | Validator, parser                |
| **Render**      | The step that turns an evaluated **Plan** into HTML for the user                                        | Output, present                  |
| **Diagnostic Mode** | Engine output mode when **Histology** is missing → produces a **DiagnosticPlan**                    | Workup mode                      |
| **Treatment Mode**  | Engine output mode when **Histology** is present → produces a **Plan**                              | Plan mode, normal mode           |

## Relationships

- A **Patient Profile** without **Histology** produces a **DiagnosticPlan**, never a **Plan** (CHARTER §15.2 C7).
- A **Plan** belongs to exactly one **Patient** and contains one **Standard Plan** and one **Aggressive Plan**.
- A **Disease** has zero or more **Indications**; an **Indication** maps to one or more **Regimens**.
- A **Regimen** is composed of one or more **Drugs** and is justified by one or more **Sources**.
- A **RedFlag** is owned by one or more **Diseases** and cites at least two **Sources**.
- A **Source** has exactly one hosting mode: **Referenced**, **Hosted**, or **Mixed**.
- Any clinical **KB entity** change requires a **Two-Reviewer Merge** by **Clinical Co-Leads**.
- A **Provenance Event** targets a **Regimen**, **Plan Section**, or other **Plan**-internal entity, and is appended to one **Event Log**.

## Example dialogue

> **Dev:** "If a **Patient Profile** comes in without **Histology**, what does the **Rule Engine** return?"

> **Domain expert:** "A **DiagnosticPlan** — never a **Plan**. The **Rule Engine** is in **Diagnostic Mode** in that case and lists the workup needed to confirm a **Disease**."

> **Dev:** "And once the path lab confirms, say, DLBCL — the engine flips to **Treatment Mode** and produces both a **Standard Plan** and an **Aggressive Plan**?"

> **Domain expert:** "Right. Each branch points at one or more **Regimens** chosen via the matching **Indications**, and every **Regimen** carries its **Source** citations. If a **RedFlag** trips on the profile — say HBV reactivation risk before rituximab — it surfaces alongside both branches."

> **Dev:** "When a **Clinical Co-Lead** signs off on the **Aggressive Plan**, that's a **Provenance Event** on the **Plan Section**?"

> **Domain expert:** "Yes — `event_type=approved`, `target_type=plan_section`, `target_id=TRACK-AGGRESSIVE`. It appends to the patient's **Event Log** and shows up in the **Decision Provenance Graph** when the **Plan** is re-rendered."

## Flagged ambiguities

- **"Plan"** was used for both the treatment recommendation entity and the workup recommendation. **Plan** is now reserved for treatment output; **DiagnosticPlan** is the distinct workup entity. Don't say "diagnostic plan" in lowercase prose without meaning the entity.
- **"Source"** collided with English "source code" and "source document." In the OpenOnco domain, **Source** always refers to the cited-authority KB entity. Use "source file" or "the original PDF" for other senses.
- **"Reviewer"** is informal; the governance role with sign-off authority is **Clinical Co-Lead**. Reserve "reviewer" for non-binding feedback.
- **"Event"** is overloaded between **Provenance Event** (clinical action) and runtime/build events (e.g. scheduled tasks). When in doubt, prefix as **Provenance Event**.
- **"Engine"** can mean the **Rule Engine** (Python evaluator) or the **Engine Bundle** (Pyodide-loaded zip). They are the same logic in different runtime shells; disambiguate when context is unclear.
- **"Stub"** vs "draft" — use **Stub** for KB entities awaiting clinical sign-off. Don't use "draft" for clinical content; reserve "draft" for spec versioning (e.g. `v0.1 draft`).
