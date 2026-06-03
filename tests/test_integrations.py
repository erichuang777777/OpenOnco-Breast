"""Tests for knowledge_base/integrations — FHIR adapter and drug requisition builder.

Covers:
  - fhir_adapter: Patient, Condition, Observation parsing
  - case_management: fhir_bundle_to_patient round-trip
  - case_management: plan_result_to_fhir_care_plan structure
  - drug_application: build_drug_requisition with a synthetic PlanResult stub
"""

from __future__ import annotations

import pytest

from knowledge_base.integrations.fhir_adapter import (
    fhir_condition_to_disease_findings,
    fhir_observation_to_findings,
    fhir_patient_to_demographics,
    extract_patient_id_from_fhir,
)
from knowledge_base.integrations.case_management import (
    fhir_bundle_to_patient,
    plan_result_to_fhir_care_plan,
)
from knowledge_base.integrations.drug_application import (
    build_drug_requisition,
    DrugRequisition,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

FHIR_PATIENT = {
    "resourceType": "Patient",
    "id": "pat-001",
    "identifier": [
        {
            "type": {"coding": [{"code": "MR"}]},
            "value": "MRN-12345",
        }
    ],
    "birthDate": "1970-06-03",
    "gender": "female",
}

FHIR_CONDITION_BREAST_IV = {
    "resourceType": "Condition",
    "code": {
        "coding": [
            {
                "system": "http://hl7.org/fhir/sid/icd-10-cm",
                "code": "C50.919",
                "display": "Malignant neoplasm of unspecified site of unspecified female breast",
            }
        ]
    },
    "stage": [
        {
            "summary": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "1228882005",
                        "display": "American Joint Commission on Cancer stage IV",
                    }
                ]
            }
        }
    ],
}

FHIR_OBS_HER2_POSITIVE = {
    "resourceType": "Observation",
    "status": "final",
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "85319-2"}]
    },
    "valueCodeableConcept": {"text": "3+"},
}

FHIR_OBS_ER_POSITIVE = {
    "resourceType": "Observation",
    "status": "final",
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "85337-4"}]
    },
    "valueCodeableConcept": {"text": "Positive (>10%)"},
}

FHIR_OBS_HER2_ISH_AMPLIFIED = {
    "resourceType": "Observation",
    "status": "final",
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "85325-9"}]
    },
    "valueCodeableConcept": {"text": "Amplified"},
}

SAMPLE_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "entry": [
        {"resource": FHIR_PATIENT},
        {"resource": FHIR_CONDITION_BREAST_IV},
        {"resource": FHIR_OBS_HER2_POSITIVE},
        {"resource": FHIR_OBS_ER_POSITIVE},
    ],
}


# ── fhir_adapter tests ────────────────────────────────────────────────────────

class TestFhirPatient:
    def test_age_calculated(self):
        demo = fhir_patient_to_demographics(FHIR_PATIENT)
        assert demo["age"] >= 55  # born 1970, should be mid-50s or 56 in 2026

    def test_sex_female(self):
        demo = fhir_patient_to_demographics(FHIR_PATIENT)
        assert demo["sex"] == "female"

    def test_mrn_extracted(self):
        pid = extract_patient_id_from_fhir(FHIR_PATIENT)
        assert pid == "MRN-12345"

    def test_fallback_to_logical_id(self):
        patient_no_mrn = {"resourceType": "Patient", "id": "fhir-logical-id"}
        pid = extract_patient_id_from_fhir(patient_no_mrn)
        assert pid == "fhir-logical-id"


class TestFhirCondition:
    def test_disease_id_extracted(self):
        out = fhir_condition_to_disease_findings(FHIR_CONDITION_BREAST_IV)
        assert out["disease"]["id"] == "DIS-BREAST"

    def test_stage_iv_extracted(self):
        out = fhir_condition_to_disease_findings(FHIR_CONDITION_BREAST_IV)
        assert out["findings"]["stage_group"] == "IV"

    def test_non_breast_returns_no_disease(self):
        condition_lung = {
            "resourceType": "Condition",
            "code": {
                "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "C34.10"}]
            },
        }
        out = fhir_condition_to_disease_findings(condition_lung)
        assert out["disease"].get("id") == "DIS-LUNG"

    def test_unknown_icd10_returns_empty_disease(self):
        condition_unknown = {
            "resourceType": "Condition",
            "code": {
                "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "Z99.99"}]
            },
        }
        out = fhir_condition_to_disease_findings(condition_unknown)
        assert out["disease"] == {}


class TestFhirObservation:
    def test_her2_ihc_3plus(self):
        findings = fhir_observation_to_findings(FHIR_OBS_HER2_POSITIVE)
        assert findings.get("her2_ihc") == "3+"

    def test_er_positive(self):
        findings = fhir_observation_to_findings(FHIR_OBS_ER_POSITIVE)
        assert findings.get("er_status") == "positive"

    def test_her2_ish_amplified(self):
        findings = fhir_observation_to_findings(FHIR_OBS_HER2_ISH_AMPLIFIED)
        assert findings.get("her2_ish") == "amplified"

    def test_unknown_loinc_returns_empty(self):
        obs = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "99999-9"}]},
            "valueString": "some value",
        }
        findings = fhir_observation_to_findings(obs)
        assert findings == {}

    def test_preliminary_obs_not_skipped_by_adapter(self):
        # Adapter itself doesn't filter by status; the bundle converter does
        obs = {**FHIR_OBS_HER2_POSITIVE, "status": "preliminary"}
        findings = fhir_observation_to_findings(obs)
        assert "her2_ihc" in findings


# ── case_management tests ─────────────────────────────────────────────────────

class TestFhirBundleToPatient:
    def test_full_bundle_round_trip(self):
        patient = fhir_bundle_to_patient(SAMPLE_BUNDLE)
        assert patient["disease"]["id"] == "DIS-BREAST"
        assert patient["patient_id"] == "MRN-12345"
        assert patient["demographics"]["sex"] == "female"
        assert patient["findings"].get("stage_group") == "IV"
        assert patient["findings"].get("her2_ihc") == "3+"
        assert patient["findings"].get("er_status") == "positive"

    def test_her2_positive_promotes_biomarker(self):
        patient = fhir_bundle_to_patient(SAMPLE_BUNDLE)
        # HER2 3+ → BIO-HER2-OVEREXPRESSED promoted
        assert patient["biomarkers"].get("BIO-HER2-OVEREXPRESSED") == "positive"

    def test_brca_positive_promotes_biomarker(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": FHIR_PATIENT},
                {"resource": FHIR_CONDITION_BREAST_IV},
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": {"coding": [{"system": "http://loinc.org", "code": "55233-1"}]},
                        "valueCodeableConcept": {"text": "Positive"},
                    }
                },
            ],
        }
        patient = fhir_bundle_to_patient(bundle)
        assert patient["biomarkers"].get("BIO-BRCA-GERMLINE") == "positive"

    def test_registered_obs_skipped(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": FHIR_PATIENT},
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "registered",
                        "code": {"coding": [{"system": "http://loinc.org", "code": "85337-4"}]},
                        "valueCodeableConcept": {"text": "Positive"},
                    }
                },
            ],
        }
        patient = fhir_bundle_to_patient(bundle)
        # registered status → observation skipped
        assert patient["findings"].get("er_status") is None

    def test_empty_bundle_returns_skeleton(self):
        patient = fhir_bundle_to_patient({"resourceType": "Bundle", "entry": []})
        assert patient["disease"] == {}
        assert patient["findings"] == {}
        assert patient["demographics"] == {}
        assert patient["line_of_therapy"] == 1


class TestPlanResultToFhirCarePlan:
    """Smoke test with a minimal PlanResult stub."""

    def _make_plan_result(self):
        from unittest.mock import MagicMock
        track = MagicMock()
        track.track_id = "T1"
        track.label = "THP 1L"
        track.label_en = "THP 1L"
        track.indication_id = "IND-BREAST-HER2-POS-MET-1L-THP"
        track.is_default = True
        track.regimen_data = {
            "name": "THP Metastatic",
            "sources": ["SRC-NCCN-BREAST-2025"],
        }

        plan = MagicMock()
        plan.id = "PLAN-TEST-001"
        plan.version = 1
        plan.tracks = [track]

        result = MagicMock()
        result.disease_id = "DIS-BREAST"
        result.algorithm_id = "ALGO-BREAST-1L"
        result.plan = plan
        result.warnings = []
        return result

    def test_care_plan_structure(self):
        result = self._make_plan_result()
        cp = plan_result_to_fhir_care_plan(result, patient_fhir_id="pat-001")
        assert cp["resourceType"] == "CarePlan"
        assert cp["status"] == "draft"
        assert cp["subject"]["reference"] == "Patient/pat-001"
        assert len(cp["activity"]) == 1
        act = cp["activity"][0]
        assert act["detail"]["description"].startswith("THP 1L")
        assert act["extension"][1]["valueBoolean"] is True  # is_default

    def test_plan_id_in_extension(self):
        result = self._make_plan_result()
        cp = plan_result_to_fhir_care_plan(result, patient_fhir_id="pat-001")
        # Extensions have mixed value types (valueString, valueInteger)
        ext_by_url = {e["url"]: e for e in cp["extension"]}
        plan_id_ext = ext_by_url.get(
            "https://openonco.info/fhir/StructureDefinition/plan-id"
        )
        assert plan_id_ext is not None
        assert plan_id_ext.get("valueString") == "PLAN-TEST-001"


# ── drug_application tests ────────────────────────────────────────────────────

class TestBuildDrugRequisition:
    def _make_plan_result(self):
        from unittest.mock import MagicMock
        track = MagicMock()
        track.track_id = "T1-DEFAULT"
        track.indication_id = "IND-BREAST-HER2-POS-MET-1L-THP"
        track.is_default = True
        track.indication_data = {
            "nccn_category": "1",
            "esmo_grade": "I",
            "evidence_level": "high",
            "treatment_intent": "palliative",
        }
        track.regimen_data = {
            "id": "REG-THP-METASTATIC",
            "name": "Trastuzumab + pertuzumab + docetaxel (THP)",
            "name_ua": "Трастузумаб + пертузумаб + доцетаксель",
            "cycle_length_days": 21,
            "total_cycles": "6 cycles taxane, then HP maintenance until progression",
            "components": [
                {
                    "drug_id": "DRUG-TRASTUZUMAB",
                    "dose": "8 mg/kg loading, then 6 mg/kg IV q3w",
                    "route": "IV",
                    "schedule": "Day 1 q21d",
                },
                {
                    "drug_id": "DRUG-PERTUZUMAB",
                    "dose": "840 mg loading, then 420 mg IV q3w",
                    "route": "IV",
                    "schedule": "Day 1 q21d",
                },
            ],
            "premedication": ["Antiemetic prophylaxis"],
            "dose_adjustments": [
                {"condition": "LVEF decline ≥10 percentage points"},
                {"condition": "Febrile neutropenia"},
            ],
            "sources": ["SRC-NCCN-BREAST-2025", "SRC-ESMO-BREAST-METASTATIC-2024"],
        }

        plan = MagicMock()
        plan.id = "PLAN-HER2-001"
        plan.version = 1
        plan.tracks = [track]

        result = MagicMock()
        result.disease_id = "DIS-BREAST"
        result.algorithm_id = "ALGO-BREAST-1L"
        result.plan = plan
        result.line_of_therapy = 1
        result.patient = {
            "findings": {"stage_group": "IV", "er_status": "positive"},
            "biomarkers": {},
        }
        result.trace = []
        result.warnings = []
        return result

    def test_requisition_built(self):
        result = self._make_plan_result()
        req = build_drug_requisition(
            result,
            track_id="T1-DEFAULT",
            patient_mrn="MRN-12345",
            patient_name_initials="陳O明",
            patient_birth_year="1970",
            patient_sex="女",
            prescribing_physician="王主治醫師",
        )
        assert isinstance(req, DrugRequisition)
        assert req.patient_mrn == "MRN-12345"
        assert req.diagnosis_icd10 == "C50.9"
        assert req.diagnosis_text == "乳癌"
        assert req.line_of_therapy == 1
        assert req.regimen_id == "REG-THP-METASTATIC"
        assert req.cycle_length_days == 21
        assert req.treatment_intent == "姑息性治療"

    def test_evidence_populated(self):
        result = self._make_plan_result()
        req = build_drug_requisition(result, track_id="T1-DEFAULT")
        assert req.evidence.nccn_category == "1"
        assert "高度共識" in req.evidence.nccn_category_zh
        assert req.evidence.evidence_level == "high"
        assert "高品質" in req.evidence.evidence_level_zh

    def test_components_extracted(self):
        result = self._make_plan_result()
        req = build_drug_requisition(result, track_id="T1-DEFAULT")
        assert len(req.components) == 2
        drug_ids = [c.drug_id for c in req.components]
        assert "DRUG-TRASTUZUMAB" in drug_ids
        assert "DRUG-PERTUZUMAB" in drug_ids
        # Dosing copied verbatim from YAML
        trastuzumab = next(c for c in req.components if c.drug_id == "DRUG-TRASTUZUMAB")
        assert "8 mg/kg" in trastuzumab.dose

    def test_special_rationale_contains_nccn(self):
        result = self._make_plan_result()
        req = build_drug_requisition(result, track_id="T1-DEFAULT")
        assert "NCCN" in req.special_approval_rationale
        assert "請主治醫師" in req.special_approval_rationale

    def test_stage_iv_rendered_zh(self):
        result = self._make_plan_result()
        req = build_drug_requisition(result, track_id="T1-DEFAULT")
        assert "IV" in req.stage

    def test_invalid_track_id_raises(self):
        result = self._make_plan_result()
        with pytest.raises(ValueError, match="track_id"):
            build_drug_requisition(result, track_id="DOES-NOT-EXIST")

    def test_no_plan_raises(self):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.plan = None
        with pytest.raises(ValueError, match="no plan"):
            build_drug_requisition(result, track_id="T1")

    def test_to_dict_serialisable(self):
        import json
        result = self._make_plan_result()
        req = build_drug_requisition(result, track_id="T1-DEFAULT")
        data = req.to_dict()
        # Ensure JSON-serialisable
        json.dumps(data)
        assert data["diagnosis_icd10"] == "C50.9"
