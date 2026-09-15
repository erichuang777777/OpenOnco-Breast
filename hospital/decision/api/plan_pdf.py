"""Plan PDF export — GET /api/v1/plan/{plan_id}/pdf

Renders an OpenOnco treatment plan as a printable A4 PDF suitable for
MDT meeting handouts and clinical file attachment.

Requires: reportlab (added to pyproject.toml [hospital] extras)
"""

from __future__ import annotations

import io
import json as _json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from hospital.auth.dependencies import HCP_ROLES, require_role
from hospital.db.models import CareTeamMember, Plan as PlanModel
from hospital.db.session import get_db

router = APIRouter(prefix="/plan", tags=["plan"])


# ── PDF builder ───────────────────────────────────────────────────────────────

def _build_pdf(plan: dict) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError("reportlab is required for PDF export: pip install reportlab") from exc

    _BASE = getSampleStyleSheet()
    _TITLE = ParagraphStyle("OOTitle", parent=_BASE["Title"], fontSize=16, leading=20, textColor=colors.HexColor("#1e3a8a"))
    _H2 = ParagraphStyle("OOH2", parent=_BASE["Heading2"], fontSize=12, leading=16, textColor=colors.HexColor("#1e3a8a"), spaceBefore=10)
    _BODY = ParagraphStyle("OOBody", parent=_BASE["Normal"], fontSize=9, leading=13, wordWrap="CJK")
    _SMALL = ParagraphStyle("OOSmall", parent=_BASE["Normal"], fontSize=7.5, leading=11, textColor=colors.HexColor("#64748b"), wordWrap="CJK")
    _WARN = ParagraphStyle("OOWarn", parent=_BASE["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#b45309"), wordWrap="CJK")
    _TABLE_HEADER = colors.HexColor("#dbeafe")
    _TABLE_BORDER = colors.HexColor("#93c5fd")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("OpenOnco — 治療計畫摘要", _TITLE))
    story.append(
        Paragraph(
            f"計畫編號: {plan.get('plan_id', '')} &nbsp;&nbsp; "
            f"疾病: {plan.get('disease_id', '')} &nbsp;&nbsp; "
            f"演算法: {plan.get('algorithm_id', '')}",
            _SMALL,
        )
    )
    story.append(
        Paragraph(
            f"生成時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}　"
            "【本文件供臨床參考，最終決策由主治醫師負責】",
            _SMALL,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=_TABLE_BORDER, spaceAfter=8))

    # ── Warnings ──────────────────────────────────────────────────────────────
    warnings = plan.get("warnings", [])
    if warnings:
        story.append(Paragraph("⚠ 注意事項", _H2))
        for w in warnings:
            story.append(Paragraph(f"• {w}", _WARN))
        story.append(Spacer(1, 6))

    # ── Treatment tracks ──────────────────────────────────────────────────────
    tracks = plan.get("tracks", [])
    if tracks:
        story.append(Paragraph("治療方案", _H2))
        tbl_data = [
            [
                Paragraph("方案", _BODY),
                Paragraph("英文名稱", _BODY),
                Paragraph("NCCN 類別", _BODY),
                Paragraph("中位 OS (月)", _BODY),
                Paragraph("選擇依據", _BODY),
            ]
        ]
        for t in tracks:
            default_mark = "★ " if t.get("is_default") else ""
            tbl_data.append([
                Paragraph(f"{default_mark}{t.get('label', '')}", _BODY),
                Paragraph(t.get("label_en") or t.get("regimen_name") or "", _SMALL),
                Paragraph(t.get("nccn_category") or t.get("evidence_level") or "", _BODY),
                Paragraph(str(t["median_os_months"]) if t.get("median_os_months") else "—", _BODY),
                Paragraph(t.get("selection_reason") or "", _SMALL),
            ])

        tbl = Table(tbl_data, colWidths=[4 * cm, 3.5 * cm, 2 * cm, 2 * cm, None])
        tbl.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, _TABLE_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f9ff")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(tbl)
        story.append(Spacer(1, 4))
        story.append(Paragraph("★ = 系統預設推薦方案", _SMALL))

    # ── Decision gaps ─────────────────────────────────────────────────────────
    gaps = plan.get("gaps", [])
    if gaps:
        story.append(Paragraph("資料缺口 — 補充後可優化建議", _H2))
        gap_data = [
            [
                Paragraph("欄位", _BODY),
                Paragraph("優先", _BODY),
                Paragraph("現值", _BODY),
                Paragraph("建議檢查", _BODY),
                Paragraph("補充後影響", _BODY),
            ]
        ]
        for g in gaps:
            gap_data.append([
                Paragraph(g.get("field", ""), _BODY),
                Paragraph(f"Tier {g.get('tier', '')}", _BODY),
                Paragraph(str(g.get("current_value") or "—"), _SMALL),
                Paragraph(g.get("recommended_test") or "—", _SMALL),
                Paragraph(g.get("rationale") or "", _SMALL),
            ])
        gap_tbl = Table(gap_data, colWidths=[3 * cm, 1.5 * cm, 2 * cm, 3 * cm, None])
        gap_tbl.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("GRID", (0, 0), (-1, -1), 0.5, _TABLE_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff7ed")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(gap_tbl)

    # ── MDT summary ───────────────────────────────────────────────────────────
    mdt = plan.get("mdt")
    if mdt:
        story.append(Paragraph("腫瘤委員會 (MDT) 需求", _H2))
        if mdt.get("required"):
            story.append(Paragraph(f"必要專科: {', '.join(mdt['required'])}", _BODY))
        if mdt.get("recommended"):
            story.append(Paragraph(f"建議專科: {', '.join(mdt['recommended'])}", _BODY))
        if mdt.get("blocking_questions_count", 0):
            story.append(
                Paragraph(
                    f"待決問題: {mdt['blocking_questions_count']} 項需要解答才能確認方案", _WARN
                )
            )

    # ── Footer disclaimer ────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(
        Paragraph(
            "本文件由 OpenOnco 決策支援系統自動產生，供臨床輔助參考之用。"
            "所有治療決策應由具資格之腫瘤科醫師依個別病患狀況決定。"
            "CHARTER §11 免責聲明。",
            _SMALL,
        )
    )

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/{plan_id}/pdf", response_class=StreamingResponse)
async def download_plan_pdf(
    plan_id: str,
    user: dict = Depends(require_role(HCP_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Download a treatment plan as a printable A4 PDF (Traditional Chinese)."""
    row = await db.scalar(sa_select(PlanModel).where(PlanModel.plan_id == plan_id))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PLAN_NOT_FOUND"},
        )
    # Ownership check: requester must be on the patient's care team
    member = await db.scalar(
        sa_select(CareTeamMember).where(
            CareTeamMember.patient_mrn == row.mrn,
            CareTeamMember.user_id == user["sub"],
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "Not on this patient's care team."},
        )
    plan = _json.loads(row.plan_json)
    pdf_bytes = _build_pdf(plan)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="plan-{plan_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
