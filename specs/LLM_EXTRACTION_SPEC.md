# LLM Extraction Specification

**Version:** 0.1 draft  
**Status:** pending review  
**Owner:** Engineering  
**Date:** 2026-06-03

---

## 1  Purpose

Convert free-text clinical notes (Chinese or English) into a structured
patient dict suitable for `knowledge_base.engine.plan.generate_plan()`.

**CHARTER §8.3 boundary (hard rule):**
- The LLM **extracts and structures** information present in the input text.
- The LLM **does not** choose treatments, interpret biomarkers for clinical
  decisions, or generate clinical recommendations.
- All clinical decisions come from the declarative rule engine.
- If extraction fails, the engine returns a gap — it never falls back to
  an LLM-generated treatment suggestion.

---

## 2  Field tiers (breast cancer)

Tier 1 — **routing-required**: engine cannot produce a meaningful plan without these.  
Tier 2 — **decision-sensitive optional**: change the recommendation if present.  
Tier 3 — **context-enriching**: improve output quality; engine works without them.

### Tier 1 (block on missing)
| Field | Example values |
|-------|---------------|
| `disease.id` | `"DIS-BREAST"` (inferred from context if not explicit) |
| `er_status` | `"positive"`, `"negative"` |
| `her2_status` | `"positive"`, `"negative"` |
| `stage_group` | `"I"`, `"II"`, `"III"`, `"IV"` |
| `line_of_therapy` | `1`, `2`, `3` |

If any Tier 1 field cannot be extracted and was not answered in a
clarification turn, the API returns `422 MISSING_TIER1_FIELD`.

### Tier 2 (proceed with gap flag)
| Field | Why it matters |
|-------|---------------|
| `pr_status` | Refines HR+ subtype; affects endocrine therapy choices |
| `brain_mets` | Triggers HER2CLIMB tucatinib branch in 2L HER2+ |
| `brca1` / `brca2` | Unlocks PARPi track (OlympiAD / OlympiA) |
| `pik3ca_mutation` | Unlocks alpelisib / capivasertib tracks |
| `esr1_mutation` | Influences endocrine therapy sequencing |
| `pdl1_cps` | Relevant for TNBC PD-L1 checkpoint branch |
| `ecog` | Affects fitness-dependent track filtering |

### Tier 3 (extract if present; skip if absent)
`age`, `sex`, `lvef`, `creatinine_clearance_ml_min`, `bilirubin_uln_x`,
`absolute_neutrophil_count_k_ul`, `platelets_k_ul`, `hbsag`, `hcv_status`

---

## 3  Extraction algorithm

```
Input: free text (zh-TW or EN), optional conversation_id
│
▼
Step 1: LLM extraction pass
  System prompt: "You are a clinical data extractor. Extract the following
  fields from the clinical note. Return only JSON. Do not infer clinical
  meaning; only extract what is explicitly stated or strongly implied by
  lab values (e.g. IHC 3+ → her2_ihc='3+', her2_status='positive')."
  
  Output: partial patient dict (may have null fields)
│
▼
Step 2: Tier 1 completeness check
  For each Tier 1 field:
    if null AND not yet asked in this conversation:
      → return status=needs_clarification with one question
         (only one question per round)
  
  Maximum 2 clarification rounds. After 2 rounds:
    → proceed with available data, remaining Tier 1 nulls = hard gaps
│
▼
Step 3: Tier 2 gap annotation
  For each Tier 2 field that is null:
    compute counterfactual: "if this field were positive, would the
    engine route to a different indication?"
    → add to gaps[] with field, tier, rationale, would_change_to
│
▼
Step 4: Return structured patient dict + gaps + status
```

---

## 4  System prompt (extraction)

```
You are a clinical data extraction assistant for an oncology decision
support system. Your ONLY job is to extract and structure information
from the clinical text provided. You must NOT:
- Suggest treatments or drugs
- Interpret biomarker results beyond explicit mapping (see below)
- Add clinical information not present in the text
- Generate any medical recommendations

Extract the following fields. If a field is not mentioned, return null.

Explicit mappings:
- IHC 3+ → her2_ihc="3+", her2_status="positive"
- IHC 2+ ISH amplified → her2_ish="amplified", her2_status="positive"
- IHC 0 or 1+ → her2_status="negative"
- ER ≥1% → er_status="positive"; ER <1% or negative → er_status="negative"
- Stage IV / 第四期 / 轉移性 → stage_group="IV"
- 第一線 / first-line / 1L → line_of_therapy=1

Return valid JSON only, no prose:
{
  "disease_id": null,
  "er_status": null,
  "her2_status": null,
  "her2_ihc": null,
  "her2_ish": null,
  "pr_status": null,
  "stage_group": null,
  "line_of_therapy": null,
  "ecog": null,
  "age": null,
  "sex": null,
  "brain_mets": null,
  "brca1": null,
  "brca2": null,
  "pik3ca_mutation": null,
  "esr1_mutation": null,
  "pdl1_cps": null
}
```

---

## 5  Clarification question generation

When a Tier 1 field is missing, the LLM generates a single, plain-language
question in the same language as the input (zh-TW or EN).

System prompt addition for clarification:
```
The following required field could not be extracted: {field_name}.
Generate ONE concise clinical question in {language} asking the clinician
to provide this information. Do not suggest an answer. Do not explain
the reason. Return only the question text.
```

Example output (brain_mets, zh-TW):
> 「請問病患目前是否有腦部轉移的影像學確認記錄？（含已接受局部治療之穩定腦轉移）」

---

## 6  Multi-turn conversation state

Conversation state stored in API memory (Redis or in-memory dict) keyed
by `conversation_id` (UUID).  TTL: 30 minutes.

State schema:
```json
{
  "conversation_id": "conv-abc123",
  "turns": 0,
  "extracted_so_far": { ... partial patient dict ... },
  "asked_fields": ["brain_mets"],
  "input_language": "zh-TW"
}
```

On each turn:
1. Merge new answer into `extracted_so_far`
2. Increment `turns`
3. If `turns >= 2` OR all Tier 1 fields resolved → return `status=complete`
4. Else → find next unresolved Tier 1 field → return `status=needs_clarification`

---

## 7  Language detection

Language is auto-detected if not specified:

| Heuristic | Language |
|-----------|----------|
| ≥20% CJK characters | `zh-TW` |
| otherwise | `en` |

Questions and patient-facing output match detected language.  
HCP-facing clinical details always include English drug names in parentheses.

---

## 8  Failure modes

| Situation | Behaviour |
|-----------|-----------|
| LLM API unavailable | Return `503` with `"use_structured_form": true`; portal falls back to manual form |
| Extraction returns no fields | Ask HCP to use structured form; log warning |
| Contradictory extraction (HER2+ AND HER2-) | Flag conflict; return both values for HCP to resolve manually |
| Tier 1 still null after 2 rounds | Proceed with `status=complete`, add to hard gaps; engine will return `422 MISSING_TIER1_FIELD` |
| Text contains potential PHI beyond clinical data | Extraction still proceeds; PHI handling is caller's responsibility per CHARTER §9.3 |

---

## 9  Implementation

Module: `knowledge_base/engine/extraction.py` (to be created)

```python
def extract_patient_from_text(
    text: str,
    *,
    language: str | None = None,
    conversation_id: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> ExtractionResult:
    """
    Returns ExtractionResult(
        conversation_id: str,
        status: "complete" | "needs_clarification",
        patient: dict | None,          # partial or complete
        gaps: list[GapItem],
        question: str | None,          # set when needs_clarification
        missing_field: str | None,
    )
    """
```

The module must:
- Never call `generate_plan()` internally (separation of concerns)
- Log only `(conversation_id, turn, fields_extracted_count)` — no PHI in logs
- Use structured output / JSON mode to guarantee parseable response
- Validate extracted JSON against known field names before returning

---

## 10  Testing

Test file: `tests/test_extraction.py`

Required test cases:
- Chinese HER2+ metastatic note → correct Tier 1 fields extracted
- English note missing stage → status=needs_clarification with stage question
- Two-round conversation resolves all Tier 1 → status=complete
- Contradictory HER2 values → conflict flag
- LLM returns invalid JSON → graceful fallback (empty extraction, no crash)
- Text with no clinical content → empty extraction, no hallucinated fields
