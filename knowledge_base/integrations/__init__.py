"""External system integration adapters.

Two integration targets:
  case_management  — bidirectional FHIR R4 bridge to 個案管理系統 (CMS).
                     Inbound: FHIR Patient/Condition/Observation → OpenOnco
                     patient dict.  Outbound: PlanResult → FHIR CarePlan.
  drug_application — structured 藥物申請單 generator from a selected
                     PlanTrack.  Output JSON is suitable for POST to
                     hospital 藥物申請系統 (DAS) or rendered to PDF.

CHARTER constraints enforced here:
  §8.3 — LLMs are not involved in clinical decisions; adapters only
         reshape data, never choose regimens.
  §9.3 — No patient-identifiable data is written to git or logs.
"""

from .case_management import (
    fhir_bundle_to_patient,
    plan_result_to_fhir_care_plan,
)
from .drug_application import build_drug_requisition

__all__ = [
    "fhir_bundle_to_patient",
    "plan_result_to_fhir_care_plan",
    "build_drug_requisition",
]
