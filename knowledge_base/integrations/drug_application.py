"""藥物申請系統 (DAS) integration — structured drug requisition builder.

Generates a 藥物申請單 (DrugRequisition) from a selected PlanTrack.
Output is a structured dict that can be:
  - POST-ed to the hospital DAS REST API as JSON
  - Serialised to PDF via the hospital's document renderer
  - Rendered as an HTML preview in the clinic portal

The requisition format is designed around Taiwan NHI/hospital requirements:
  - 品項名稱 (drug name: 中文 brand + generic INN)
  - 適應症代碼 (ICD-10-CM)
  - 治療目的 (intent: 根治 curative | 輔助 adjuvant | 姑息 palliative)
  - 劑量 / 途徑 / 週期 (dosing / route / cycle)
  - 佐證文獻 (evidence: NCCN category, ESMO grade, NCT number, PMID)
  - 健保給付代碼 (NHI benefit code if applicable)
  - 特殊申請原因 (special approval rationale if non-standard)

CHARTER §8.3: dosing is copied verbatim from the KB regimen YAML.
No LLM modifies dosing or indication text.
CHARTER §9.3: patient fields are accepted as opaque strings; this module
never writes them to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any


# ── NCCN category → 中文說明 ───────────────────────────────────────────────────
_NCCN_CATEGORY_ZH: dict[str, str] = {
    "1":   "NCCN 第1類推薦（高度共識，基於高品質證據）",
    "2A":  "NCCN 第2A類推薦（一致共識，基於低品質證據）",
    "2B":  "NCCN 第2B類推薦（部分共識，基於低品質證據）",
    "3":   "NCCN 第3類推薦（重大爭議）",
}

# ── ESMO grade → 中文說明 ──────────────────────────────────────────────────────
_ESMO_GRADE_ZH: dict[str, str] = {
    "I":    "ESMO 建議等級I（強烈建議）",
    "II":   "ESMO 建議等級II（中等建議）",
    "III":  "ESMO 建議等級III（可考慮）",
    "IV":   "ESMO 建議等級IV（不建議）",
    "V":    "ESMO 建議等級V（強烈不建議）",
}

_EVIDENCE_LEVEL_ZH: dict[str, str] = {
    "high":     "高品質證據（第III期隨機試驗 / meta-analysis）",
    "moderate": "中等品質證據（第II期 / 非隨機試驗）",
    "low":      "低品質證據（case series / 專家共識）",
    "expert":   "專家共識",
}

_INTENT_MAP: dict[str, str] = {
    "curative":   "根治性治療",
    "adjuvant":   "輔助性治療",
    "neoadjuvant": "術前新輔助治療",
    "palliative": "姑息性治療",
    "maintenance": "維持性治療",
}


@dataclass
class DrugComponent:
    """Single drug within a regimen."""
    drug_id: str
    drug_name_en: str
    drug_name_zh: str
    brand_name: str
    atc_code: str
    rxnorm_id: str
    dose: str
    route: str
    schedule: str


@dataclass
class EvidenceSummary:
    """Evidence basis for the requisition (for approval committee)."""
    nccn_category: str = ""
    nccn_category_zh: str = ""
    esmo_grade: str = ""
    esmo_grade_zh: str = ""
    evidence_level: str = ""
    evidence_level_zh: str = ""
    pivotal_trial_nct: list[str] = field(default_factory=list)
    pivotal_trial_pmid: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)


@dataclass
class DrugRequisition:
    """藥物申請單 — complete drug requisition for the DAS.

    Serialise with `asdict(requisition)` for JSON POST, or pass to a
    PDF/HTML renderer.
    """
    # ── Identifiers ──
    requisition_id: str             # hospital-assigned; caller supplies or leave blank
    created_date: str               # ISO-8601 date (YYYY-MM-DD)

    # ── Patient section (opaque — no PHI stored beyond what caller passes) ──
    patient_mrn: str                # 病歷號
    patient_name_initials: str      # 姓名縮寫 (e.g. "陳O明") — de-identified display
    patient_birth_year: str         # 民國年 or YYYY
    patient_sex: str                # 男 / 女

    # ── Clinical context ──
    diagnosis_icd10: str            # 主診斷 ICD-10-CM code
    diagnosis_text: str             # 診斷名稱 (中文)
    stage: str                      # 期別 (e.g. "第IV期", "cT2N1M0")
    treatment_intent: str           # 治療目的 (根治性 / 輔助性 / 姑息性)
    line_of_therapy: int            # 治療線 (1 = 第一線)
    key_biomarkers: list[str]       # 重要生物標記 (e.g. ["HER2陽性", "BRCA1突變"])

    # ── Selected indication & plan ──
    indication_id: str              # OpenOnco indication id
    plan_id: str                    # OpenOnco plan id (for audit trail)
    plan_track_id: str              # The specific track selected by clinician

    # ── Regimen ──
    regimen_id: str
    regimen_name_en: str
    regimen_name_zh: str
    cycle_length_days: int
    total_cycles: str               # "連續使用至疾病進展" etc.
    components: list[DrugComponent] = field(default_factory=list)
    premedication_notes: list[str] = field(default_factory=list)

    # ── Evidence ──
    evidence: EvidenceSummary = field(default_factory=EvidenceSummary)

    # ── NHI / approval fields ──
    nhi_benefit_code: str = ""      # 健保給付品項碼 (if applicable)
    requires_prior_auth: bool = False
    special_approval_rationale: str = ""  # 特殊申請原因 (for non-standard use)
    prescribing_physician: str = ""  # 主治醫師

    # ── Toxicity & monitoring highlights (for pharmacist review) ──
    key_toxicities: list[str] = field(default_factory=list)
    monitoring_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Builder ───────────────────────────────────────────────────────────────────

def build_drug_requisition(
    plan_result: Any,
    track_id: str,
    *,
    patient_mrn: str = "",
    patient_name_initials: str = "",
    patient_birth_year: str = "",
    patient_sex: str = "",
    prescribing_physician: str = "",
    requisition_id: str = "",
    kb_root: Any = None,
) -> DrugRequisition:
    """Build a DrugRequisition from a PlanResult + selected track.

    Args:
        plan_result:           PlanResult from generate_plan().
        track_id:              The track_id the clinician selected.
        patient_mrn:           Hospital MRN (病歷號).
        patient_name_initials: De-identified display name.
        patient_birth_year:    Birth year (民國 or CE).
        patient_sex:           "男" or "女".
        prescribing_physician: Physician name for signature block.
        requisition_id:        Hospital-assigned ID; auto-generated if blank.
        kb_root:               Path to KB content root (for drug name lookups).

    Returns:
        DrugRequisition dataclass.
    """
    import uuid

    plan = getattr(plan_result, "plan", None)
    if plan is None:
        raise ValueError("plan_result has no plan — cannot build requisition.")

    track = next(
        (t for t in plan.tracks if t.track_id == track_id),
        None,
    )
    if track is None:
        available = [t.track_id for t in plan.tracks]
        raise ValueError(
            f"track_id {track_id!r} not found in plan. "
            f"Available: {available}"
        )

    indication_data = track.indication_data or {}
    regimen_data = track.regimen_data or {}

    # ── Evidence ─────────────────────────────────────────────────────────
    nccn_cat = str(indication_data.get("nccn_category", ""))
    esmo_gr = str(indication_data.get("esmo_grade", ""))
    ev_level = str(indication_data.get("evidence_level", ""))

    evidence = EvidenceSummary(
        nccn_category=nccn_cat,
        nccn_category_zh=_NCCN_CATEGORY_ZH.get(nccn_cat, ""),
        esmo_grade=esmo_gr,
        esmo_grade_zh=_ESMO_GRADE_ZH.get(esmo_gr, ""),
        evidence_level=ev_level,
        evidence_level_zh=_EVIDENCE_LEVEL_ZH.get(ev_level.lower(), ev_level),
        source_ids=list(regimen_data.get("sources", []) or []),
    )

    # Extract NCT numbers + PMIDs from source ids
    for src_id in evidence.source_ids:
        if "NCT" in src_id.upper():
            nct = re.search(r"NCT\d+", src_id.upper())
            if nct:
                evidence.pivotal_trial_nct.append(nct.group())
        if "PMID" in src_id.upper() or re.search(r"\d{7,8}", src_id):
            pmid = re.search(r"\d{7,8}", src_id)
            if pmid:
                evidence.pivotal_trial_pmid.append(pmid.group())

    # ── Regimen components ────────────────────────────────────────────────
    components: list[DrugComponent] = []
    for comp in regimen_data.get("components", []) or []:
        drug_id = comp.get("drug_id", "")
        drug_info = _resolve_drug_info(drug_id, kb_root)
        components.append(DrugComponent(
            drug_id=drug_id,
            drug_name_en=drug_info.get("name_en", drug_id),
            drug_name_zh=drug_info.get("name_zh", ""),
            brand_name=drug_info.get("brand_name", ""),
            atc_code=drug_info.get("atc_code", ""),
            rxnorm_id=drug_info.get("rxnorm_id", ""),
            dose=comp.get("dose", ""),
            route=comp.get("route", ""),
            schedule=comp.get("schedule", ""),
        ))

    # ── Treatment intent ──────────────────────────────────────────────────
    line = getattr(plan_result, "line_of_therapy", 1) or 1
    intent_raw = indication_data.get("treatment_intent", "")
    if not intent_raw:
        intent_raw = "palliative" if line >= 2 else "curative"
    intent_zh = _INTENT_MAP.get(intent_raw, intent_raw)

    # ── Biomarker summary ─────────────────────────────────────────────────
    key_biomarkers = _extract_key_biomarkers(plan_result)

    # ── Stage ─────────────────────────────────────────────────────────────
    stage_raw = (plan_result.patient.get("findings", {}).get("stage_group", "")
                 if hasattr(plan_result, "patient") else "")
    stage_zh = _stage_to_zh(stage_raw) if stage_raw else ""

    # ── Diagnosis ─────────────────────────────────────────────────────────
    disease_id = getattr(plan_result, "disease_id", "")
    diagnosis_icd10 = _disease_to_icd10(disease_id)
    diagnosis_text = _disease_to_zh(disease_id)

    # ── Toxicity highlights from regimen ─────────────────────────────────
    key_toxicities = [
        adj.get("condition", "")
        for adj in (regimen_data.get("dose_adjustments", []) or [])
        if adj.get("condition")
    ][:5]  # top 5 for the pharmacist summary block

    premedication_notes = list(regimen_data.get("premedication", []) or [])

    return DrugRequisition(
        requisition_id=requisition_id or str(uuid.uuid4())[:8].upper(),
        created_date=date.today().isoformat(),
        patient_mrn=patient_mrn,
        patient_name_initials=patient_name_initials,
        patient_birth_year=patient_birth_year,
        patient_sex=patient_sex,
        diagnosis_icd10=diagnosis_icd10,
        diagnosis_text=diagnosis_text,
        stage=stage_zh,
        treatment_intent=intent_zh,
        line_of_therapy=line,
        key_biomarkers=key_biomarkers,
        indication_id=track.indication_id,
        plan_id=plan.id,
        plan_track_id=track_id,
        regimen_id=regimen_data.get("id", ""),
        regimen_name_en=regimen_data.get("name", ""),
        regimen_name_zh=regimen_data.get("name_ua", ""),
        cycle_length_days=int(regimen_data.get("cycle_length_days", 0)),
        total_cycles=str(regimen_data.get("total_cycles", "")),
        components=components,
        premedication_notes=premedication_notes,
        evidence=evidence,
        requires_prior_auth=_requires_prior_auth(regimen_data),
        special_approval_rationale=_build_special_rationale(
            track, evidence, line
        ),
        prescribing_physician=prescribing_physician,
        key_toxicities=key_toxicities,
        monitoring_requirements=_extract_monitoring(indication_data),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_drug_info(drug_id: str, kb_root: Any) -> dict:
    """Look up drug name + ATC from KB YAML if kb_root provided."""
    if not kb_root or not drug_id:
        return {}
    try:
        from pathlib import Path
        import yaml
        drugs_dir = Path(kb_root) / "drugs"
        slug = drug_id.lower().replace("drug-", "").replace("-", "_")
        candidates = list(drugs_dir.glob(f"*{slug}*.yaml"))
        if not candidates:
            return {}
        data = yaml.safe_load(candidates[0].read_text(encoding="utf-8"))
        names = data.get("names", {})
        brand_names = names.get("brand_names", [])
        return {
            "name_en": names.get("english", names.get("preferred", drug_id)),
            "name_zh": names.get("ukrainian", ""),   # Ukrainian kept as fallback; zh field TBD
            "brand_name": brand_names[0] if brand_names else "",
            "atc_code": data.get("atc_code", ""),
            "rxnorm_id": str(data.get("rxnorm_id", "")),
        }
    except Exception:
        return {}


def _disease_to_icd10(disease_id: str) -> str:
    mapping = {
        "DIS-BREAST": "C50.9",
        "DIS-LUNG": "C34.90",
        "DIS-GASTRIC": "C16.9",
        "DIS-COLORECTAL": "C18.9",
    }
    return mapping.get(disease_id, "")


def _disease_to_zh(disease_id: str) -> str:
    mapping = {
        "DIS-BREAST": "乳癌",
        "DIS-LUNG": "肺癌",
        "DIS-GASTRIC": "胃癌",
        "DIS-COLORECTAL": "大腸直腸癌",
    }
    return mapping.get(disease_id, disease_id)


def _stage_to_zh(stage: str) -> str:
    roman = {"I": "第I期", "II": "第II期", "III": "第III期", "IV": "第IV期 (轉移性)"}
    return roman.get(stage.upper().strip(), stage)


def _extract_key_biomarkers(plan_result: Any) -> list[str]:
    """Pull fired RedFlags + biomarkers as human-readable Chinese strings."""
    lines = []
    trace = getattr(plan_result, "trace", []) or []
    for entry in trace:
        entry_str = str(entry)
        if "RF-BREAST-HER2" in entry_str and "fired" in entry_str.lower():
            lines.append("HER2陽性 (IHC 3+ 或 ISH擴增)")
        if "RF-BREAST-TNBC" in entry_str and "fired" in entry_str.lower():
            lines.append("三陰性乳癌 (ER-/PR-/HER2-)")
    biomarkers = getattr(plan_result, "patient", {})
    if isinstance(biomarkers, dict):
        bio = biomarkers.get("biomarkers", {})
        if bio.get("BIO-BRCA-GERMLINE") == "positive":
            lines.append("BRCA胚系突變陽性")
        findings = biomarkers.get("findings", {})
        if findings.get("er_status") == "positive":
            lines.append("ER陽性")
        if findings.get("pr_status") == "positive":
            lines.append("PR陽性")
        if findings.get("pik3ca_mutation") == "positive":
            lines.append("PIK3CA突變")
        if findings.get("esr1_mutation") == "positive":
            lines.append("ESR1突變")
    return lines


def _requires_prior_auth(regimen_data: dict) -> bool:
    """Heuristic: ADCs, CDK4/6i, bispecifics typically need prior auth in Taiwan NHI."""
    name = (regimen_data.get("name", "") or "").lower()
    high_cost_keywords = [
        "trastuzumab deruxtecan", "t-dxd", "tdxd", "sacituzumab",
        "tucatinib", "palbociclib", "ribociclib", "abemaciclib",
        "olaparib", "talazoparib", "pertuzumab", "capivasertib",
        "inavolisib", "datopotamab",
    ]
    return any(kw in name for kw in high_cost_keywords)


def _build_special_rationale(
    track: Any, evidence: EvidenceSummary, line: int
) -> str:
    """Auto-draft a special approval rationale paragraph (Chinese).

    This is a template — the clinician must review and edit before
    submitting.  CHARTER §8.3: content is template-driven, not LLM-driven.
    """
    indication_id = getattr(track, "indication_id", "")
    parts = []
    if evidence.nccn_category:
        parts.append(evidence.nccn_category_zh or f"NCCN {evidence.nccn_category}類推薦")
    if evidence.esmo_grade:
        parts.append(evidence.esmo_grade_zh or f"ESMO {evidence.esmo_grade}等級推薦")
    if evidence.pivotal_trial_nct:
        ncts = "、".join(evidence.pivotal_trial_nct)
        parts.append(f"關鍵試驗：{ncts}")
    guideline_part = "；".join(parts) if parts else "根據現行國際指引"
    return (
        f"依據{guideline_part}，"
        f"本藥物為第{line}線治療之標準推薦用藥（{indication_id}）。"
        f"【請主治醫師依個案情況補充說明並確認】"
    )


def _extract_monitoring(indication_data: dict) -> list[str]:
    reqs = indication_data.get("monitoring_requirements", []) or []
    if isinstance(reqs, list):
        return [str(r) for r in reqs]
    return []
