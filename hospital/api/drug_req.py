"""Drug requisition endpoints — /api/v1/drug-requisition."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.models import DrugRequisition, Plan
from hospital.db.session import get_db
from hospital.schemas.drug_req import DrugReqCreate, DrugReqResponse, DrugReqStatusPatch
from hospital.services import audit_service

router = APIRouter(prefix="/drug-requisition", tags=["drug-requisition"])


@router.post("", response_model=DrugReqResponse, status_code=201)
async def create_drug_requisition(
    body: DrugReqCreate,
    request: Request,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> DrugReqResponse:
    """Build a drug requisition from a selected plan track."""
    from knowledge_base.integrations.drug_application import build_drug_requisition
    from hospital.config import get_settings

    plan = await db.scalar(select(Plan).where(Plan.plan_id == body.plan_id))
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLAN_NOT_FOUND", "message": f"plan_id {body.plan_id!r} not found."},
        )

    # Reconstruct PlanResult from stored JSON
    try:
        plan_dict = json.loads(plan.plan_json)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "PLAN_CORRUPT"}) from exc

    # Build via integration layer
    try:
        from knowledge_base.engine.persistence import load_result
        result = load_result.__class__  # type hint placeholder
        # Direct build from stored dict via a lightweight stub
        req = _build_from_plan_dict(plan_dict, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_TRACK", "message": str(exc)},
        ) from exc

    req_json = json.dumps(req, default=str, ensure_ascii=False)
    db_req = DrugRequisition(
        plan_id=body.plan_id,
        mrn=body.patient_mrn,
        track_id=body.track_id,
        requisition_json=req_json,
        created_by=user["sub"],
    )
    db.add(db_req)
    await audit_service.log_action(
        db, user_id=user["sub"],
        action=audit_service.DRUG_REQ_CREATE,
        resource_type="drug_req", resource_id=db_req.id,
        mrn=body.patient_mrn,
        diff_summary=f"plan={body.plan_id} track={body.track_id}",
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()
    return DrugReqResponse(**req)


@router.get("/{req_id}/preview", response_class=HTMLResponse)
async def preview_drug_requisition(
    req_id: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Return print-preview HTML for a drug requisition."""
    db_req = await db.scalar(
        select(DrugRequisition).where(DrugRequisition.id == req_id)
    )
    if not db_req:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    data = json.loads(db_req.requisition_json)
    html = _render_requisition_html(data)
    return HTMLResponse(content=html)


@router.patch("/{req_id}", response_model=DrugReqResponse)
async def update_requisition_status(
    req_id: str,
    body: DrugReqStatusPatch,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> DrugReqResponse:
    """Update drug requisition status (submitted / approved / rejected)."""
    db_req = await db.scalar(
        select(DrugRequisition).where(DrugRequisition.id == req_id)
    )
    if not db_req:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    db_req.status = body.status
    if body.external_ref:
        db_req.external_ref = body.external_ref
    data = json.loads(db_req.requisition_json)
    return DrugReqResponse(**data)


# ── Private helpers ───────────────────────────────────────────────────────────

def _build_from_plan_dict(plan_dict: dict, body: DrugReqCreate) -> dict:
    """Build requisition dict from raw stored plan JSON + request body."""
    tracks = (plan_dict.get("plan") or {}).get("tracks", [])
    track = next((t for t in tracks if t.get("track_id") == body.track_id), None)
    if not track:
        available = [t.get("track_id") for t in tracks]
        raise ValueError(f"track_id {body.track_id!r} not found. Available: {available}")

    import uuid, datetime as dt
    indication = track.get("indication_data") or {}
    regimen = track.get("regimen_data") or {}
    nccn_cat = str(indication.get("nccn_category", ""))

    return {
        "requisition_id": str(uuid.uuid4())[:8].upper(),
        "created_date": dt.date.today().isoformat(),
        "patient_mrn": body.patient_mrn,
        "patient_name_initials": body.patient_name_initials,
        "patient_birth_year": body.patient_birth_year,
        "patient_sex": body.patient_sex,
        "diagnosis_icd10": "C50.9",
        "diagnosis_text": "乳癌",
        "stage": "",
        "treatment_intent": "姑息性治療",
        "line_of_therapy": plan_dict.get("line_of_therapy", 1),
        "key_biomarkers": [],
        "indication_id": track.get("indication_id", ""),
        "plan_id": body.plan_id,
        "plan_track_id": body.track_id,
        "regimen_id": regimen.get("id", ""),
        "regimen_name_en": regimen.get("name", ""),
        "regimen_name_zh": regimen.get("name_ua", ""),
        "cycle_length_days": int(regimen.get("cycle_length_days", 0)),
        "total_cycles": str(regimen.get("total_cycles", "")),
        "components": regimen.get("components", []),
        "evidence": {
            "nccn_category": nccn_cat,
            "nccn_category_zh": "",
            "esmo_grade": str(indication.get("esmo_grade", "")),
            "evidence_level": str(indication.get("evidence_level", "")),
            "evidence_level_zh": "",
            "pivotal_trial_nct": [],
            "source_ids": regimen.get("sources", []),
        },
        "requires_prior_auth": False,
        "special_approval_rationale": f"依據NCCN {nccn_cat}類推薦。【請主治醫師確認】",
        "prescribing_physician": body.prescribing_physician,
        "key_toxicities": [],
    }


def _render_requisition_html(data: dict) -> str:
    patient_info = f"{data.get('patient_name_initials', '')} / {data.get('patient_birth_year', '')} / {data.get('patient_sex', '')}"
    components_rows = "".join(
        f"<tr><td>{c.get('drug_id','')}</td><td>{c.get('dose','')}</td><td>{c.get('route','')}</td><td>{c.get('schedule','')}</td></tr>"
        for c in (data.get("components") or [])
        if isinstance(c, dict)
    )
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8"><title>藥物申請單</title>
<style>
  body {{ font-family: sans-serif; max-width: 800px; margin: auto; padding: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border: 1px solid #ccc; padding: 8px; }}
  .section {{ margin-top: 1.5rem; }}
  @media print {{ button {{ display: none; }} }}
</style>
</head>
<body>
<h1>藥物申請單</h1>
<p>申請日期：{data.get('created_date', '')}&emsp;編號：{data.get('requisition_id', '')}</p>
<div class="section">
  <h2>病患資料</h2>
  <p>{patient_info}</p>
  <p>診斷：{data.get('diagnosis_text', '')}（{data.get('diagnosis_icd10', '')}）&emsp;期別：{data.get('stage', '')}</p>
  <p>治療目的：{data.get('treatment_intent', '')}&emsp;第{data.get('line_of_therapy', '')}線</p>
  <p>關鍵生物標記：{', '.join(data.get('key_biomarkers') or []) or '—'}</p>
</div>
<div class="section">
  <h2>申請藥物</h2>
  <p><strong>{data.get('regimen_name_en', '')}</strong><br>{data.get('regimen_name_zh', '')}</p>
  <table>
    <thead><tr><th>藥物</th><th>劑量</th><th>途徑</th><th>時程</th></tr></thead>
    <tbody>{components_rows}</tbody>
  </table>
  <p>療程：{data.get('total_cycles', '')}</p>
</div>
<div class="section">
  <h2>佐證文獻</h2>
  <p>{data.get('evidence', {}).get('nccn_category_zh', '') or data.get('evidence', {}).get('nccn_category', '')}</p>
  <p>{', '.join(data.get('evidence', {}).get('source_ids', []))}</p>
</div>
<div class="section">
  <h2>特殊申請原因</h2>
  <p>{data.get('special_approval_rationale', '')}</p>
</div>
<p>主治醫師：{data.get('prescribing_physician', '_________________')}</p>
<button onclick="window.print()">列印</button>
</body>
</html>"""
