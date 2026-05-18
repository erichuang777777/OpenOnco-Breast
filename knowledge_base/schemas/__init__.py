"""OpenOnco Pydantic schemas for the knowledge base.

Every entity under `hosted/content/<type>/` validates against one of
these models on load. See `validation/loader.py`.
"""

from .access_pathway import AccessPathway, CostOrientation
from .algorithm import Algorithm
from .biomarker import Biomarker
from .biomarker_actionability import BiomarkerActionability, RegulatoryApproval
from .contraindication import Contraindication
from .diagnostic import (
    BiopsyApproach,
    DiagnosticPlan,
    DiagnosticWorkup,
    IHCPanel,
    SuspicionSnapshot,
    WorkupStep,
)
from .disease import Disease
from .drug import Drug
from .experimental_option import ExperimentalOption, ExperimentalTrial, UaSiteDetail
from .indication import (
    Indication,
    IndicationPhase,
    IndicationPhaseStage,
    IndicationPhaseType,
)
from .mdt_skill import MdtSkill
from .monitoring import MonitoringSchedule
from .plan import (
    AccessMatrix,
    AccessMatrixRow,
    FDAComplianceMetadata,
    Plan,
    PlanAnnotation,
    PlanTrack,
    VariantActionabilityHit,
)
from .questionnaire import (
    QGroup,
    Question,
    QuestionOption,
    Questionnaire,
)
from .radiation_course import RadiationCourse, RadiationIntent
from ._reviewer_signoff import ReviewerSignoff
from .red_flag import RedFlag
from .regimen import Regimen, RegimenComponent, RegimenPhase
from .reviewer_profile import ReviewerProfile, SignOffScope
from .source import Source
from .supportive_care import SupportiveCare
from .surgery import Surgery, SurgeryComplication, SurgeryIntent
from .test import Test

# Map content directory name → entity class.
# Used by the loader to pick the right schema for each YAML file.
# Plan / DiagnosticPlan are NOT included — instances live outside the
# public KB (in patient_plans/<patient_id>/v<N>.yaml, gitignored per
# CHARTER §9.3). Only DiagnosticWorkup (curated content) belongs here.
ENTITY_BY_DIR: dict[str, type] = {
    "diseases": Disease,
    "drugs": Drug,
    "regimens": Regimen,
    "indications": Indication,
    "biomarkers": Biomarker,
    "biomarker_actionability": BiomarkerActionability,
    "contraindications": Contraindication,
    "redflags": RedFlag,
    "algorithms": Algorithm,
    "tests": Test,
    "supportive_care": SupportiveCare,
    "monitoring": MonitoringSchedule,
    "sources": Source,
    "workups": DiagnosticWorkup,
    "questionnaires": Questionnaire,
    "access_pathways": AccessPathway,
    "mdt_skills": MdtSkill,
    "reviewers": ReviewerProfile,
    # §17 ratified 2026-05-07 — solid-tumor extensions. Empty / non-existent
    # folders are tolerated by the loader (loader.py walks dirs that exist).
    # First content lands in Phase C of the GI-2 wave.
    "procedures": Surgery,
    "radiation_courses": RadiationCourse,
}

__all__ = [
    "AccessMatrix",
    "AccessMatrixRow",
    "AccessPathway",
    "Algorithm",
    "Biomarker",
    "BiomarkerActionability",
    "CostOrientation",
    "BiopsyApproach",
    "Contraindication",
    "DiagnosticPlan",
    "DiagnosticWorkup",
    "Disease",
    "Drug",
    "ENTITY_BY_DIR",
    "BiomarkerStratification",
    "DesignFlag",
    "ExperimentalOption",
    "ExperimentalTrial",
    "FDAComplianceMetadata",
    "TrialOutlook",
    "IHCPanel",
    "Indication",
    "IndicationPhase",
    "IndicationPhaseStage",
    "IndicationPhaseType",
    "MdtSkill",
    "MonitoringSchedule",
    "Plan",
    "PlanAnnotation",
    "PlanTrack",
    "QGroup",
    "Question",
    "QuestionOption",
    "Questionnaire",
    "RadiationCourse",
    "RadiationIntent",
    "RedFlag",
    "Regimen",
    "RegimenComponent",
    "RegimenPhase",
    "RegulatoryApproval",
    "ReviewerProfile",
    "ReviewerSignoff",
    "SignOffScope",
    "Source",
    "SupportiveCare",
    "Surgery",
    "SurgeryComplication",
    "SurgeryIntent",
    "SuspicionSnapshot",
    "Test",
    "VariantActionabilityHit",
    "WorkupStep",
]
