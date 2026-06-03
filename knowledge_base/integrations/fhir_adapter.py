"""Low-level FHIR R4 ↔ OpenOnco patient-dict conversion helpers.

Converts FHIR R4 resources (Patient, Condition, Observation) into the flat
patient dict that `knowledge_base.engine.plan.generate_plan()` expects, and
vice-versa for plan output.

Only the subset of FHIR codes relevant to breast cancer is mapped here;
extend LOINC_TO_FINDING and ICD10_TO_DISEASE for other disease sites.

No PHI is logged; only coded values are touched.  Raw FHIR resources must
be sanitised by the caller before passing here.

FHIR spec refs:
  Patient   https://hl7.org/fhir/R4/patient.html
  Condition https://hl7.org/fhir/R4/condition.html
  Observation https://hl7.org/fhir/R4/observation.html
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any


# ── ICD-10 prefix → OpenOnco disease id ──────────────────────────────────────
ICD10_TO_DISEASE: dict[str, str] = {
    "C50": "DIS-BREAST",
    "C91": "DIS-LEUKEMIA-ALL",
    "C92": "DIS-LEUKEMIA-AML",
    "C34": "DIS-LUNG",
    "C16": "DIS-GASTRIC",
    "C18": "DIS-COLORECTAL",
    "C19": "DIS-COLORECTAL",
    "C20": "DIS-COLORECTAL",
}

# ── LOINC code → OpenOnco findings key ───────────────────────────────────────
# Values are (findings_key, value_transform_fn | None).
# transform_fn receives the FHIR Observation valueCodeableConcept.text or
# valueString and returns the normalised OpenOnco string value.

def _pos_neg(v: str) -> str:
    """Map FHIR valueCodeableConcept.text to 'positive' / 'negative'."""
    v = (v or "").lower().strip()
    if any(kw in v for kw in ("pos", "detected", "amplif", "reactive", "yes", "3+", "2+")):
        return "positive"
    return "negative"


def _her2_ihc(v: str) -> str:
    """Return IHC score as-is if it looks like 0/1+/2+/3+, else normalise."""
    v = (v or "").strip()
    if re.match(r"^[0-3]\+?$", v):
        return v if v.endswith("+") else v
    return _pos_neg(v)


def _her2_ish(v: str) -> str:
    v = (v or "").lower().strip()
    return "amplified" if any(k in v for k in ("amplif", "positive", "high")) else "non-amplified"


LOINC_TO_FINDING: dict[str, tuple[str, Any]] = {
    # HER2
    "85319-2": ("her2_ihc",    _her2_ihc),
    "85325-9": ("her2_ish",    _her2_ish),
    "18474-7": ("her2_status", _pos_neg),
    # ER / PR
    "85337-4": ("er_status",   _pos_neg),
    "85339-0": ("pr_status",   _pos_neg),
    # BRCA
    "55233-1": ("brca1",       _pos_neg),   # BRCA1
    "55107-7": ("brca2",       _pos_neg),   # BRCA2
    # PD-L1
    "85147-7": ("pdl1_cps",    lambda v: v),
    # Ki-67
    "85319-3": ("ki67_pct",    lambda v: v),
    # Stage
    "21908-9": ("stage_group", lambda v: v),   # clinical T/N/M stage group
    "21902-2": ("stage_group", lambda v: v),   # pathologic stage group
    # ECOG
    "89243-0": ("ecog",        lambda v: int(v) if str(v).isdigit() else v),
    # ESR1 mutation (circulating tumour DNA)
    "94077-4": ("esr1_mutation", _pos_neg),
    # PIK3CA
    "94076-6": ("pik3ca_mutation", _pos_neg),
}

# ── SNOMED CT + NCI Thesaurus stage codes ────────────────────────────────────
SNOMED_STAGE_MAP: dict[str, str] = {
    "258219007": "I",
    "258220001": "II",
    "258221002": "III",
    "258222009": "IV",
    "1228882005": "IV",   # metastatic
}


def _age_from_fhir_patient(patient: dict) -> int | None:
    bd = patient.get("birthDate")
    if not bd:
        return None
    try:
        birth = date.fromisoformat(bd[:10])
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except ValueError:
        return None


def _sex_from_fhir_patient(patient: dict) -> str | None:
    gender = patient.get("gender", "")
    return {"male": "male", "female": "female"}.get(gender.lower())


# ── Public helpers ────────────────────────────────────────────────────────────

def fhir_patient_to_demographics(patient: dict) -> dict:
    out: dict[str, Any] = {}
    age = _age_from_fhir_patient(patient)
    if age is not None:
        out["age"] = age
    sex = _sex_from_fhir_patient(patient)
    if sex:
        out["sex"] = sex
    return out


def fhir_condition_to_disease_findings(condition: dict) -> dict:
    """Extract disease id and stage findings from a FHIR Condition resource."""
    out: dict[str, Any] = {"disease": {}, "findings": {}}

    # ICD-10 code → disease id
    coding = (
        condition.get("code", {}).get("coding", [])
    )
    for c in coding:
        sys = c.get("system", "")
        code = c.get("code", "")
        if "icd-10" in sys.lower() or "icd10" in sys.lower():
            prefix = code[:3]
            dis = ICD10_TO_DISEASE.get(prefix)
            if dis:
                out["disease"]["id"] = dis
                break

    # Stage from Condition.stage
    for stage_entry in condition.get("stage", []):
        for c in stage_entry.get("summary", {}).get("coding", []):
            code = c.get("code", "")
            display = c.get("display", "")
            snomed_stage = SNOMED_STAGE_MAP.get(code)
            if snomed_stage:
                out["findings"]["stage_group"] = snomed_stage
                break
            # fallback: stage in display text like "Stage IV"
            m = re.search(r"stage\s+([IVX]+)", display, re.I)
            if m:
                out["findings"]["stage_group"] = m.group(1).upper()
                break

    return out


def fhir_observation_to_findings(observation: dict) -> dict:
    """Extract a single key→value pair from a FHIR Observation resource."""
    findings: dict[str, Any] = {}

    for coding in observation.get("code", {}).get("coding", []):
        loinc = coding.get("code", "")
        if loinc in LOINC_TO_FINDING:
            key, transform = LOINC_TO_FINDING[loinc]
            raw_value = (
                observation.get("valueCodeableConcept", {}).get("text")
                or observation.get("valueString")
                or (observation.get("valueQuantity") or {}).get("value")
                or observation.get("valueBoolean")
            )
            if raw_value is not None:
                findings[key] = transform(str(raw_value)) if transform else raw_value
            break

    return findings


def extract_patient_id_from_fhir(patient: dict) -> str | None:
    """Return the first MRN identifier value, falling back to FHIR logical id."""
    for ident in patient.get("identifier", []):
        type_codes = [
            c.get("code", "")
            for c in ident.get("type", {}).get("coding", [])
        ]
        if "MR" in type_codes or "MRN" in type_codes:
            return ident.get("value")
    return patient.get("id")
