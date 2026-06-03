"""LLM free-text extraction service.

CHARTER §8.3: The LLM extracts and structures information from input text.
It does NOT choose treatments or make clinical decisions.  All clinical
decisions come from the rule engine after extraction.

Multi-turn conversation state is stored in an in-process dict with TTL.
Production deployments should replace this with Redis.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from hospital.schemas.extract import (
    ExtractionGap,
    ExtractionRequest,
    ExtractionResponse,
    ExtractedPatient,
)

# ── Tier 1 fields — block if missing (ask clarifying question) ────────────────
TIER1_FIELDS: list[str] = [
    "disease_id", "er_status", "her2_status", "stage_group", "line_of_therapy"
]

# ── Tier 2 fields — proceed with gap flag ─────────────────────────────────────
TIER2_FIELDS: list[str] = [
    "pr_status", "brain_mets", "brca1", "brca2",
    "pik3ca_mutation", "esr1_mutation", "pdl1_cps", "ecog",
]

MAX_CLARIFICATION_TURNS = 2

# ── In-process conversation store (TTL = 30 min) ─────────────────────────────
_CONVERSATIONS: dict[str, dict] = {}
_CONVERSATION_TTL = 1800  # seconds


def _prune_expired() -> None:
    now = time.time()
    expired = [k for k, v in _CONVERSATIONS.items() if now - v["created_at"] > _CONVERSATION_TTL]
    for k in expired:
        del _CONVERSATIONS[k]


def _detect_language(text: str) -> str:
    cjk_chars = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh-TW" if cjk_chars / max(len(text), 1) >= 0.2 else "en"


_CLARIFICATION_QUESTIONS_ZH: dict[str, str] = {
    "disease_id":      "請問病患的診斷是什麼癌別？（如：乳癌、肺癌）",
    "er_status":       "請問病患的 ER（雌激素受體）檢測結果是陽性還是陰性？",
    "her2_status":     "請問病患的 HER2 檢測結果是陽性還是陰性？",
    "stage_group":     "請問病患目前的疾病期別（如：第一期、第四期、轉移性）？",
    "line_of_therapy": "請問這是第幾線治療？（第一線 / 第二線 / ...）",
}
_CLARIFICATION_QUESTIONS_EN: dict[str, str] = {
    "disease_id":      "What is the patient's cancer diagnosis?",
    "er_status":       "What is the patient's ER (estrogen receptor) status — positive or negative?",
    "her2_status":     "What is the patient's HER2 status — positive or negative?",
    "stage_group":     "What is the patient's current disease stage (e.g. Stage I, Stage IV, metastatic)?",
    "line_of_therapy": "What line of therapy is this? (1st line / 2nd line / ...)",
}


_EXTRACTION_SYSTEM_PROMPT = """\
You are a clinical data extraction assistant for an oncology decision support system.
Your ONLY job is to extract and structure information from the clinical text.

You must NOT:
- Suggest treatments or drugs
- Interpret biomarker results beyond the explicit mappings below
- Add clinical information not present in the text
- Generate any medical recommendations

Explicit mappings:
- IHC 3+  → her2_ihc="3+", her2_status="positive"
- IHC 2+ ISH amplified → her2_ish="amplified", her2_status="positive"
- IHC 0 or 1+ → her2_status="negative"
- ER ≥1%  → er_status="positive";  ER <1% or negative → er_status="negative"
- Stage IV / 第四期 / 轉移性 / metastatic → stage_group="IV"
- 第一線 / 1st line / 1L / first-line → line_of_therapy=1
- 乳癌 / breast cancer / C50 → disease_id="DIS-BREAST"

Return valid JSON only, no prose. Use null for unknown fields:
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
}"""


async def extract_from_text(req: ExtractionRequest) -> ExtractionResponse:
    """Main entry point for the /api/v1/extract endpoint."""
    _prune_expired()

    language = req.language or _detect_language(req.text)
    conv_id = req.conversation_id

    # Load or create conversation state
    if conv_id and conv_id in _CONVERSATIONS:
        state = _CONVERSATIONS[conv_id]
    else:
        conv_id = str(uuid.uuid4())
        state = {
            "conversation_id": conv_id,
            "turns": 0,
            "extracted": {},
            "asked_fields": [],
            "language": language,
            "created_at": time.time(),
        }
        _CONVERSATIONS[conv_id] = state

    state["turns"] += 1

    # Call LLM extraction
    new_fields = await _call_llm_extract(req.text)

    # Merge into conversation state (don't overwrite non-null with null)
    for k, v in new_fields.items():
        if v is not None:
            state["extracted"][k] = v

    extracted = state["extracted"]

    # Check Tier 1 completeness
    if state["turns"] <= MAX_CLARIFICATION_TURNS:
        for field in TIER1_FIELDS:
            if extracted.get(field) is None and field not in state["asked_fields"]:
                state["asked_fields"].append(field)
                questions = (
                    _CLARIFICATION_QUESTIONS_ZH
                    if language == "zh-TW"
                    else _CLARIFICATION_QUESTIONS_EN
                )
                return ExtractionResponse(
                    conversation_id=conv_id,
                    status="needs_clarification",
                    patient=_dict_to_extracted(extracted),
                    question=questions.get(field, f"Please provide: {field}"),
                    missing_field=field,
                )

    # All Tier 1 resolved (or max turns reached) → build gaps for Tier 2
    gaps = _compute_tier2_gaps(extracted)

    return ExtractionResponse(
        conversation_id=conv_id,
        status="complete",
        patient=_dict_to_extracted(extracted),
        gaps=gaps,
    )


async def _call_llm_extract(text: str) -> dict[str, Any]:
    """Call Claude API for extraction.  Returns partial field dict."""
    try:
        import anthropic
        from hospital.config import get_settings

        settings = get_settings()
        if not settings.ANTHROPIC_API_KEY:
            return {}

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=settings.EXTRACTION_MODEL,
            max_tokens=512,
            system=_EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = message.content[0].text.strip()
        # Extract JSON from response (may have markdown fence)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {}
    except Exception:
        return {}


def _dict_to_extracted(d: dict) -> ExtractedPatient:
    known = {k for k in ExtractedPatient.model_fields}
    return ExtractedPatient(**{k: v for k, v in d.items() if k in known})


def _compute_tier2_gaps(extracted: dict) -> list[ExtractionGap]:
    descriptions = {
        "pr_status":        "PR 狀態影響 HR+ 亞型分類",
        "brain_mets":       "腦轉移狀態影響 HER2+ 2L 分支（HER2CLIMB 路徑）",
        "brca1":            "BRCA1 胚系突變影響 PARPi 適用性（OlympiAD）",
        "brca2":            "BRCA2 胚系突變影響 PARPi 適用性（OlympiAD）",
        "pik3ca_mutation":  "PIK3CA 突變影響 PI3K/AKT 抑制劑適用性",
        "esr1_mutation":    "ESR1 突變影響內分泌療法序列",
        "pdl1_cps":         "PD-L1 CPS 影響 TNBC 免疫療法分支",
        "ecog":             "ECOG PS 影響體能狀態相關適用性",
    }
    gaps = []
    for field in TIER2_FIELDS:
        if extracted.get(field) is None:
            gaps.append(ExtractionGap(
                field=field,
                tier=2,
                description=descriptions.get(field, field),
            ))
    return gaps
