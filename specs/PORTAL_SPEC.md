# Portal Specification

**Version:** 0.1 draft  
**Status:** pending review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Overview

Three user-facing portals + one admin portal.  All rendered server-side
(Jinja2 + HTMX); no SPA framework required.  CSS framework: Tailwind CSS
(utility-first, no build step via CDN for MVP).

| Portal | Path | Primary user | Auth required |
|--------|------|-------------|---------------|
| Tumor Board | `/board` | `tumor_board_hcp` | Yes |
| Clinic | `/clinic` | `clinic_hcp` | Yes |
| Patient | `/patient/{token}` | `patient` | Token (URL-signed) |
| Admin | `/admin` | `kb_admin`, `auditor` | Yes |

---

## 2  Tumor Board portal (`/board`)

### 2.1  Purpose

Pre-meeting preparation tool for multidisciplinary tumor board.  
Input: structured form or pasted clinical note (LLM extraction).  
Output: full clinical plan + MDT checklist + decision gaps + trial options.

### 2.2  Page layout

```
┌──────────────────────────────────────────────────────────────┐
│ OpenOnco  [乳癌 DIS-BREAST]           [Dr. Wang] [Logout]   │
├──────────────┬───────────────────────┬───────────────────────┤
│ PATIENT      │  TREATMENT PLAN       │  BOARD TOOLS          │
│              │                       │                        │
│ MRN: ─────── │  [T1 ★ DEFAULT]       │  MDT Roles Required:  │
│ Age: 55F     │  THP 1L (HER2+)       │  ✓ 醫腫 ✓ 外科        │
│ ECOG: 1      │  REG-THP-METASTATIC   │  ✓ 放腫 ─ 病理        │
│              │  NCCN Cat. 1          │                        │
│ Biomarkers:  │  OS mdn: 57mo         │  Open Questions (2):  │
│ HER2+ 3+/ISH │                       │  ⚠ brain_mets (Tier2) │
│ ER+  PR-     │  [T2] Tucatinib 3L    │  ⚠ BRCA status        │
│ Stage IV     │  (Brain mets variant) │                        │
│              │                       │  Decision Gaps:       │
│ [Edit] [New] │  Sources:             │  If BRCA+ →           │
│              │  NCCN 2025 §2.3       │  PARPi track unlocks  │
│ Timeline:    │  DESTINY-Breast03     │                        │
│ 2026-05-01   │  HER2CLIMB-Murthy19   │  Trials (3):          │
│  Dx confirmed│                       │  NCT12345678 Ph.III   │
│ 2026-06-03   │  [Export DrugReq]     │  NCT23456789 Ph.II    │
│  Plan v1     │  [Print HCP]          │  [View all →]         │
│              │  [Send to Patient]    │                        │
└──────────────┴───────────────────────┴───────────────────────┘
```

### 2.3  Patient input panel (left)

- **Manual entry**: structured form with Tier 1 fields required (HER2/ER/stage),
  Tier 2 as optional expandable section, Tier 3 collapsible.
- **Free-text paste**: textarea + "AI Extract" button → calls `/api/v1/extract`,
  result populates form fields in place.  LLM questions displayed inline.
- **Timeline strip**: previous plan versions (v1→v2→v3 chain), click to view.

### 2.4  Treatment plan panel (center)

- Default track highlighted (★ badge).
- Each track shows: indication name (Chinese), regimen name, NCCN category,
  evidence level, median OS/PFS if available.
- Expand track → regimen components with dosing table, cycle schedule,
  dose adjustments, premedication.
- Source citations as clickable chips (open source details in modal).
- **Export DrugReq**: opens drug requisition preview (calls `/api/v1/drug-requisition`).
- **Print HCP**: opens `/api/v1/render/plan/{id}?mode=clinician` in new tab.
- **Send to Patient**: generates a signed URL → `/patient/{token}` → show QR.

### 2.5  Board tools panel (right)

- **MDT Roles**: required vs recommended roles from `mdt_orchestrator`.
  Checkboxes for "present today" (stored in annotation).
- **Open Questions**: from MDT orchestrator.  Each shows owning role + question
  text.  Blocking questions flagged in red.
- **Decision Gaps**: from `/api/v1/plan/gaps`.  Shows field name, tier, and
  what indication would change to if positive.
- **Trials**: top 3 matching from `/api/v1/trials`.  "View all" expands full list
  with inclusion criteria summary.

### 2.6  MDT annotation

"Add Board Decision" button (bottom of center panel) → inline form:

```
Annotation type: [Approve ▾]
Role:            [Medical Oncologist ▾]
Text:            MDT consensus 2026-06-03: proceed with THP...
                                                    [Save]
```

Annotations are append-only; shown in a log below the plan.

---

## 3  Clinic portal (`/clinic`)

### 3.1  Purpose

Outpatient HCP consultation tool.  Left pane: HCP clinical view.  
Right pane: live patient-friendly Chinese explanation.  QR code output
to share plan with patient on their phone.

### 3.2  Page layout

```
┌─────────────────────────────────────────────────────┐
│ OpenOnco Clinic   [MRN: ──────────]  [Load] [New]  │
├───────────────────────────┬─────────────────────────┤
│  HCP VIEW                 │  PATIENT VIEW  [ZH-TW]  │
│                           │                          │
│  Disease: 乳癌 (HER2+)    │  您的治療計畫            │
│  Stage: IV  ECOG: 1       │                          │
│                           │  第一線建議治療：         │
│  ★ THP (trastuzumab +    │  THP 組合療法            │
│    pertuzumab + docetaxel)│  (賀癌平 + 賀疾寧 +      │
│  NCCN Category 1          │   紫杉醇類藥物)           │
│  Evidence: high           │                          │
│  OS mdn: 57 months        │  預期效益：              │
│                           │  中位整體存活期約 57 個月  │
│  Alt: Tucatinib triplet   │                          │
│  (if brain mets present)  │  主要副作用：            │
│                           │  • 疲倦、噁心             │
│  [Generate Plan]          │  • 心臟功能監測           │
│  [View Gaps]              │  • 定期抽血               │
│  [Find Trials]            │                          │
│                           │  下一步：                 │
│                           │  您的主治醫師將安排...    │
│                           │                          │
│                           │  [列印]  [QR碼分享]       │
└───────────────────────────┴─────────────────────────┘
```

### 3.3  Behaviour

- HCP side uses `render_plan_html(mode="clinician")`.
- Patient side uses `render_plan_html(mode="patient")` — simplified Chinese,
  no raw drug IDs, no source citation codes.
- Both panes update simultaneously when plan is generated/revised.
- **QR code**: calls `POST /api/v1/patient-link` → returns signed URL
  (`/patient/{token}`, 24h expiry) → rendered as QR.
- Language toggle on patient pane: 繁中 / EN (default = system locale).
- Free-text input same as /board (LLM extraction).

---

## 4  Patient portal (`/patient/{token}`)

### 4.1  Purpose

White-label, simplified treatment plan for the patient.  
No PHI beyond what the HCP explicitly included in the patient-link generation.  
Printable, offline-accessible (no auth required — URL is the credential).

### 4.2  Page layout

Single-column, A4-print-friendly, large font.

```
┌──────────────────────────────────────────┐
│  [Hospital logo]  您的治療計畫             │
│  日期：2026-06-03                         │
│                                          │
│  建議治療方式                             │
│  ─────────────────────────────────────  │
│  THP 組合療法                            │
│  (賀癌平 + 賀疾寧 + 紫杉醇類藥物)          │
│                                          │
│  治療目的                                 │
│  控制疾病，延長生命品質                    │
│                                          │
│  預期效益                                 │
│  根據臨床研究，此療法中位整體存活期         │
│  約為 57 個月。                           │
│                                          │
│  主要注意事項                             │
│  • 需定期監測心臟功能 (LVEF)              │
│  • 可能出現疲倦、噁心等副作用              │
│  • 如有不適請立即聯絡您的主治醫師           │
│                                          │
│  ────────────────────────────────────── │
│  本計畫由主治醫師審閱確認。               │
│  如有任何疑問請洽門診護理站。              │
│                                          │
│         [列印此頁面]                      │
└──────────────────────────────────────────┘
```

### 4.3  Constraints

- Token is URL-signed (HMAC-SHA256, 24h TTL by default; HCP can set 7d for
  surgical patients).
- Page contains **no MRN, no full name** — only what HCP chose to include.
- No login required; no patient account.
- Between-visit watchpoints (from regimen YAML `between_visit_watchpoints`)
  rendered as "注意事項" list.

---

## 5  Admin portal (`/admin`)

### 5.1  KB governance (`/admin/kb`)

```
Pending Reviews (3)
─────────────────────────────────────────────────────
[REV-001] indication  IND-BREAST-HER2-POS-MET-1L-THP
  Submitted: 2026-06-01 by agent-session-xyz
  Diff: Added esr1_mutation to required_tests
  Reviewer 1: ─ (pending)  Reviewer 2: ─ (pending)
  [Review] [Approve] [Reject]

CIViC Monthly Diff (last: 2026-06-01)
─────────────────────────────────────────────────────
  +3 new evidence items  |  -1 downgraded  |  2 pending review
  [View diff →]
```

Implements CHARTER §6.1 two-reviewer workflow.  
An entity is marked `approved` only after two distinct `kb_admin` users
click Approve.

### 5.2  Case audit (`/admin/cases`)

```
Cases (128 total)  [Search MRN] [Filter by disease ▾] [Date range]
──────────────────────────────────────────────────────────────────
MRN      Disease    Last plan    Status      Plans  Annotations
MRN-001  乳癌       2026-06-03   Active (v1)   1       2
MRN-002  乳癌       2026-05-28   Revised (v2)  2       5
...

[Click row → case detail]
```

Case detail shows:
- Plan version chain (v1 → v2 → ...) with revision triggers
- Annotation log (who, when, what type, text)
- Audit log entries for this MRN

### 5.3  Audit log (`/admin/audit`)

Queryable read-only log.  Columns:
`timestamp | user_id | action | resource | mrn_hash | summary`

Actions: `plan.generate`, `plan.revise`, `annotation.add`,
`drug_req.create`, `kb.review.approve`, `kb.review.reject`,
`patient_link.create`.

---

## 6  Shared UI components

| Component | Description |
|-----------|-------------|
| `PlanTrackCard` | Indication name, regimen, NCCN badge, evidence badge, expand for details |
| `SourceChip` | Clickable source ID → modal with author, year, trial NCT |
| `GapBadge` | Field name + tier colour (red=Tier1, amber=Tier2) + impact tooltip |
| `MDTRoleList` | Role chips: required (solid) vs recommended (outline) |
| `AnnotationForm` | Type dropdown + role dropdown + textarea + submit |
| `QRModal` | QR code + copyable URL + expiry countdown |
| `ExtractionChat` | Textarea → spinner → extracted fields + clarification Q |

---

## 7  Accessibility + internationalisation

- Language: Traditional Chinese (zh-TW) primary; English secondary.
- Clinical terms: Chinese display name + English in parentheses on first use.
- Print CSS: all portals include `@media print` rules for A4.
- Font size: minimum 14px body; patient portal 16px.
- Colour contrast: WCAG AA minimum.
