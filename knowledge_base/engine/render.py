"""HTML render layer — Plan / DiagnosticPlan / Revision → single-file
A4-printable HTML document.

Design language adapted from the project's reference patient deliverables
(infograph/*план лікування.html — gitignored, not the source of patient
data; only the visual idiom is borrowed): green medical palette, DM Serif
Display headings, Source Sans 3 body, badges + alerts + cards.
Layout adapted for A4 print + browser preview (no scroll-snap, single
flow column). UI patterns avoid automation bias per CHARTER §15.2 C6
(both tracks shown side-by-side, alternative is not buried, every
recommendation cites sources).

Three render entry points (one per document type):

- render_plan_html(plan_result, mdt=None) — treatment Plan with tracks
- render_diagnostic_brief_html(diag_result, mdt=None) — Workup Brief
- render_revision_note_html(prev, new, transition) — Revision Note

Each returns a complete single-file HTML string (CSS embedded). Caller
decides where to write it.

Per CHARTER §15.2 C7 — diagnostic banner mandatory in DiagnosticBrief,
treatment-Plan-not-applicable disclaimer surfaced above the fold.
"""

from __future__ import annotations

import functools
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import yaml

from ._actionability import _biomarker_keys_match, _extract_variant
from ._ask_doctor import select_questions as _select_ask_doctor_questions
from ._citation_guard import (
    needs_guard as _citation_needs_guard,
    render_citation_warn_badge as _render_citation_warn_badge,
    render_stripped_block as _render_stripped_block,
    resolve_citation_status as _resolve_citation_status,
)
from ._emergency_rf import (
    filter_emergency_rfs,
    is_emergency_rf,
    patient_emergency_label,
)
from ._nszu import lookup_nszu_status, nszu_label
from ._patient_rationale import build_track_rationale_html as _build_track_rationale_html
from ._patient_vocabulary import (
    NSZU_PATIENT_LABEL,
    ESCAT_TIER_PATIENT_LABEL,
    expand_first_use as _expand_first_use,
    explain as _explain_patient,
)
from .diagnostic import _DIAGNOSTIC_BANNER, DiagnosticPlanResult
from .mdt_orchestrator import MDTOrchestrationResult
from .plan import PlanResult
from .render_styles import PATIENT_MODE_CSS as _PATIENT_CSS
from .render_styles import STYLESHEET as _CSS




# ── Helpers ───────────────────────────────────────────────────────────────


def _h(s) -> str:
    """Escape for HTML output."""
    if s is None:
        return ""
    return html.escape(str(s))


# ── Regimen phase iteration (PR2 of regimen-phases-refactor) ─────────────
#
# `regimen_data` flows through render as a raw dict from the YAML loader
# (knowledge_base/validation/loader.py stores `"data": raw`). Pydantic's
# `Regimen._auto_wrap_legacy_components` validator never runs on this
# path, so we cannot rely on `phases` being populated post-load — the
# dict has whatever the YAML literally has:
#
#   * legacy YAML — `phases` absent, `components: [...]` → use components
#   * migrated YAML (axi-cel post-PR2) — `phases: [...]`, `components: []`
#     → iterate phases[*].components; ignore the empty top-level list
#   * (theoretical authored) — both populated → phases is canonical
#
# The helper below is the single source of truth. Three render call
# sites consume it — `_render_treatment_phases`, `_render_track_drugs`
# (patient bundle), `_render_ask_doctor_section` (predicate decoration).
# Without it, migrated regimens would silently drop drugs from the
# patient HTML and the ask-doctor questions.
def _iter_regimen_components(regimen_dict: Optional[dict]):
    """Yield component dicts from `phases[*].components` if populated,
    else fall back to top-level `components`. Skips non-dict entries
    defensively (loader returns plain Python types, but YAML errors can
    leave None inside lists)."""
    if not regimen_dict:
        return
    phases = regimen_dict.get("phases") or []
    if phases:
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            for comp in phase.get("components") or []:
                if isinstance(comp, dict):
                    yield comp
        return
    for comp in regimen_dict.get("components") or []:
        if isinstance(comp, dict):
            yield comp


# ── Sign-off badge (CHARTER §6.1) ─────────────────────────────────────────
#
# Indications carry `reviewer_signoffs_v2: list[ReviewerSignoff]` after the
# `scripts/clinical_signoff.py` CLI is run. The plan render surfaces the
# coverage state as a coloured badge so the clinician sees at a glance
# whether the recommendation has the two Clinical Co-Lead approvals
# CHARTER §6.1 requires.


@functools.lru_cache(maxsize=1)
def _load_reviewer_labels() -> dict[str, str]:
    """REV-* → display_name. Cached. Returns empty dict on failure."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    rev_dir = repo_root / "knowledge_base" / "hosted" / "content" / "reviewers"
    if not rev_dir.is_dir():
        return {}
    out: dict[str, str] = {}
    for p in sorted(rev_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("id"):
            out[data["id"]] = str(data.get("display_name") or data["id"])
    return out


def _signoff_label(reviewer_id: str) -> str:
    return _load_reviewer_labels().get(reviewer_id, reviewer_id)


@functools.lru_cache(maxsize=1)
def _load_defined_bio_ids() -> frozenset:
    """Return frozenset of BIO-* ids defined in biomarkers/. Cached."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    bio_dir = repo_root / "knowledge_base" / "hosted" / "content" / "biomarkers"
    if not bio_dir.is_dir():
        return frozenset()
    ids: set[str] = set()
    for p in bio_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("id"):
            ids.add(str(data["id"]).upper())
    return frozenset(ids)


def _render_signoff_badge(entity_data: Optional[dict]) -> str:
    """Render a clinician-mode sign-off badge. 0/1/≥2 sign-offs."""
    if not isinstance(entity_data, dict):
        return ""
    sigs = entity_data.get("reviewer_signoffs_v2") or []
    sigs = [s for s in sigs if isinstance(s, dict) and s.get("reviewer_id")]
    n = len(sigs)
    if n == 0:
        return (
            '<span class="signoff-badge signoff-pending">'
            '⚠ Очікує підпису Clinical Co-Lead</span>'
        )
    if n == 1:
        rid = sigs[0]["reviewer_id"]
        return (
            '<span class="signoff-badge signoff-partial">'
            f'🟡 Підписано (1/2): {_h(_signoff_label(rid))}'
            '</span>'
        )
    names = ", ".join(_signoff_label(s["reviewer_id"]) for s in sigs[:3])
    if n > 3:
        names += f" + {n - 3}"
    return (
        '<span class="signoff-badge signoff-complete">'
        f'✓ Клінічно затверджено: {_h(names)}'
        '</span>'
    )


def _render_signoff_badge_patient(entity_data: Optional[dict]) -> str:
    """Patient-mode sign-off — simpler vocabulary, no reviewer names."""
    if not isinstance(entity_data, dict):
        return ""
    sigs = entity_data.get("reviewer_signoffs_v2") or []
    sigs = [s for s in sigs if isinstance(s, dict) and s.get("reviewer_id")]
    n = len(sigs)
    if n >= 2:
        return (
            '<span class="patient-badge patient-good signoff-complete">'
            'Затверджено лікарями</span>'
        )
    if n == 1:
        return (
            '<span class="patient-badge patient-warn signoff-partial">'
            'Очікує перевірки лікарями (1 з 2)</span>'
        )
    return (
        '<span class="patient-badge patient-emergency signoff-pending">'
        'Очікує перевірки лікарями</span>'
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ── i18n: live translation client for long free-text ─────────────────────
#
# Phase B of auto-translate render: long free-text from KB (Indication
# notes, do_not_do bullets, RedFlag definitions, MDT role reasons) goes
# through a configured translate client (DeepL Free + LibreTranslate
# fallback + glossary protection + on-disk cache).
#
# Graceful degrade: if neither DEEPL_API_KEY nor LIBRETRANSLATE_URL is
# set in the environment, `_translate_kb_text` returns the original UA
# text unchanged. Render still produces a usable document, just with
# UA-only KB content embedded.
#
# Per CHARTER §8.3 every cached translation is marked
# `machine_translated: true` for clinician review.

_TRANSLATE_CLIENT = None
_TRANSLATE_CLIENT_INIT = False


def _get_translate_client():
    """Lazy-load the translate client once per process. Returns None if
    no upstream is configured — caller falls back to original text."""
    global _TRANSLATE_CLIENT, _TRANSLATE_CLIENT_INIT
    if _TRANSLATE_CLIENT_INIT:
        return _TRANSLATE_CLIENT
    _TRANSLATE_CLIENT_INIT = True
    import os
    if not (os.environ.get("DEEPL_API_KEY") or os.environ.get("LIBRETRANSLATE_URL")):
        _TRANSLATE_CLIENT = None
        return None
    try:
        from knowledge_base.clients.translate_client import build_full_stack
        _TRANSLATE_CLIENT = build_full_stack()
    except Exception:
        _TRANSLATE_CLIENT = None
    return _TRANSLATE_CLIENT


def _set_translate_client(client) -> None:
    """Test hook — inject a stub client. Pass None to clear + force
    re-init from env on next call."""
    global _TRANSLATE_CLIENT, _TRANSLATE_CLIENT_INIT
    _TRANSLATE_CLIENT = client
    _TRANSLATE_CLIENT_INIT = client is not None


def _translate_kb_text(text: str, target_lang: str, source_lang: str = "uk") -> str:
    """Translate a UA free-text fragment to target_lang. Resolution order:

    1. Built-in deterministic UA→EN overrides (engine-emitted strings —
       MDT reasons, open questions, etc.) — works in Pyodide / offline.
    2. Live translation client (DeepL / LibreTranslate) if configured.
    3. Original text as graceful degrade.

    Returns the original text if target_lang is source_lang, text is empty,
    or no rule + no client matches.
    """
    if not text or not text.strip():
        return text
    if target_lang == source_lang or not target_lang:
        return text
    if (target_lang or "").lower().startswith("en") and source_lang == "uk":
        from ._translation_overrides import lookup as _override_lookup
        hit = _override_lookup(text)
        if hit is not None:
            return hit
    client = _get_translate_client()
    if client is None:
        return text
    try:
        return client.translate(text, target_lang=target_lang, source_lang=source_lang)
    except Exception:
        return text


def _h_t(text, target_lang: str = "uk", source_lang: str = "uk") -> str:
    """HTML-escape AND translate (where applicable). Drop-in replacement
    for `_h(...)` at sites that emit long UA free-text from the KB.
    Translation happens BEFORE escaping — the cached translation is in
    natural language, escape is just transport."""
    if text is None:
        return ""
    return html.escape(_translate_kb_text(str(text), target_lang, source_lang))


def _pick_name(names: dict | None, target_lang: str = "uk", default: str = "") -> str:
    """Pick the right localized name from a `names: {ukrainian, english,
    preferred, ...}` block based on target_lang.

    UA: ukrainian → preferred → english → default
    EN: english → preferred → ukrainian → default

    Used uniformly across tests / drugs / workups / mdt_skills lookups so a
    single helper change controls every name-emission site."""
    if not isinstance(names, dict):
        return default
    if target_lang == "en":
        order = ("english", "preferred", "ukrainian")
    else:
        order = ("ukrainian", "preferred", "english")
    for key in order:
        v = names.get(key)
        if v:
            return str(v)
    return default


# ── i18n: UI label dictionary (UA + EN) ───────────────────────────────────
#
# Used by render to switch static section headers / banners / disclaimers
# between UA and EN. Long free-text from KB is handled by
# `_translate_kb_text` (live translation, configured via env vars).
# For `target_lang` outside {uk, en}, falls back to UA on UI labels;
# free-text still translated by the client if it supports the language.

def _code_value(value) -> str:
    """Render scalar/list code values without exposing Python repr syntax."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    return str(value)


def _diagnosis_codes(plan_result: PlanResult) -> dict[str, str]:
    """Merge disease KB codes with patient-supplied codes."""
    disease_data = (plan_result.kb_resolved or {}).get("disease") or {}
    kb_codes = disease_data.get("codes") if isinstance(disease_data, dict) else {}
    codes: dict[str, str] = {}
    if isinstance(kb_codes, dict):
        for key, value in kb_codes.items():
            rendered = _code_value(value)
            if rendered:
                codes[key] = rendered

    snapshot = (plan_result.plan and plan_result.plan.patient_snapshot) or {}
    patient_disease = snapshot.get("disease") if isinstance(snapshot, dict) else {}
    if isinstance(patient_disease, dict):
        patient_codes = patient_disease.get("codes")
        if isinstance(patient_codes, dict):
            for key, value in patient_codes.items():
                rendered = _code_value(value)
                if rendered:
                    codes[key] = rendered
        for key in ("icd_10", "icd_o_3_morphology", "icd_o_3_topography"):
            rendered = _code_value(patient_disease.get(key))
            if rendered:
                codes[key] = rendered
    return codes


def _finding_value(plan_result: PlanResult, *keys: str) -> str:
    snapshot = (plan_result.plan and plan_result.plan.patient_snapshot) or {}
    findings = snapshot.get("findings") if isinstance(snapshot, dict) else {}
    if not isinstance(findings, dict):
        return ""
    for key in keys:
        rendered = _code_value(findings.get(key))
        if rendered:
            return rendered
    return ""


def _diagnosis_name(plan_result: PlanResult, target_lang: str = "uk") -> str:
    disease_data = (plan_result.kb_resolved or {}).get("disease") or {}
    names = disease_data.get("names") if isinstance(disease_data, dict) else None
    return _pick_name(names, target_lang, default=plan_result.disease_id or "")


def _render_patient_strip(plan_result: PlanResult, target_lang: str = "uk") -> str:
    plan = plan_result.plan
    patient_id = (plan.patient_id if plan is not None else plan_result.patient_id) or ""
    algorithm_id = (plan.algorithm_id if plan is not None else plan_result.algorithm_id) or ""
    diagnosis = _diagnosis_name(plan_result, target_lang)
    codes = _diagnosis_codes(plan_result)
    stage = _finding_value(plan_result, "tnm_stage", "clinical_stage", "stage", "stage_group")
    histology = _finding_value(plan_result, "histology", "morphology")

    meta: list[tuple[str, str]] = []
    if diagnosis:
        meta.append((_t("diagnosis_label", target_lang), diagnosis))
    if codes.get("icd_10"):
        meta.append((_t("moh_icd10_label", target_lang), codes["icd_10"]))
    icdo_parts = [codes.get("icd_o_3_morphology"), codes.get("icd_o_3_topography")]
    icdo = "; ".join(part for part in icdo_parts if part)
    if icdo:
        meta.append(("ICD-O-3", icdo))
    if stage:
        meta.append((_t("stage_label", target_lang), stage))
    if histology:
        meta.append((_t("histology_label", target_lang), histology))

    details = "".join(
        '<div class="patient-meta-item">'
        f'<span class="meta-label">{_h(label)}</span>'
        f'<span class="meta-value">{_h(value)}</span>'
        '</div>'
        for label, value in meta
    )
    details_html = f'<div class="patient-meta-grid">{details}</div>' if details else ""
    return (
        '<div class="patient-strip">'
        f'<div class="label">{_h(_t("patient_label", target_lang))}</div>'
        f'<div class="value">{_h(patient_id)} · Algorithm: {_h(algorithm_id)}</div>'
        f'{details_html}'
        '</div>'
    )


_UI_STRINGS: dict[str, dict[str, str]] = {
    # Section headers
    "treatment_options":           {"uk": "Варіанти лікування", "en": "Treatment options"},
    "etiological_driver":          {"uk": "Етіологічний драйвер", "en": "Etiological driver"},
    "etiological_driver_label":    {"uk": "Etiological driver · etiologically_driven archetype",
                                    "en": "Etiological driver · etiologically_driven archetype"},
    "pretreatment":                {"uk": "Pre-treatment investigations",
                                    "en": "Pre-treatment investigations"},
    "pretreatment_sub":            {"uk": "Дослідження перед стартом терапії · критичні / стандарт / бажано · поєднані по треках",
                                    "en": "Investigations before treatment start · critical / standard / desired · merged across tracks"},
    "redflags_pro_contra":         {"uk": "Red flags — PRO / CONTRA aggressive",
                                    "en": "Red flags — PRO / CONTRA aggressive"},
    "what_not":                    {"uk": "Що НЕ робити", "en": "What NOT to do"},
    "what_not_sub":                {"uk": "Прямі прохібітивні правила, кожне з обґрунтуванням у regimen / supportive care / contraindication",
                                    "en": "Explicit prohibitive rules, each grounded in a regimen / supportive care / contraindication entity"},
    "monitoring":                  {"uk": "Monitoring schedule", "en": "Monitoring schedule"},
    "monitoring_sub":              {"uk": "Графік моніторингу за фазами лікування",
                                    "en": "Monitoring schedule by treatment phase"},
    "timeline":                    {"uk": "Timeline", "en": "Timeline"},
    "timeline_sub":                {"uk": "Хронологія лікування — derived from regimen + monitoring schedule",
                                    "en": "Treatment timeline — derived from regimen + monitoring schedule"},
    "skills_required":             {"uk": "Скіли (required) — обов'язкові віртуальні спеціалісти",
                                    "en": "Skills (required) — mandatory virtual specialists"},
    "skills_recommended":          {"uk": "Скіли (recommended) — рекомендовані для розгляду",
                                    "en": "Skills (recommended) — for consideration"},
    "skills_optional":             {"uk": "Скіли (optional) — опціональні",
                                    "en": "Skills (optional)"},
    "mdt_brief":                   {"uk": "MDT brief", "en": "MDT brief"},
    "open_questions":              {"uk": "Питання для обговорення", "en": "Discussion questions"},
    "data_quality":                {"uk": "Якість даних", "en": "Data quality"},
    "dq_status_complete":          {"uk": "Готово до розгляду MDT", "en": "Complete for MDT review"},
    "dq_status_caveats":           {"uk": "Можна використовувати з застереженнями", "en": "Usable with caveats"},
    "dq_status_incomplete_mdt":    {"uk": "Неповно для підписання MDT", "en": "Incomplete for MDT sign-off"},
    "dq_status_incomplete_default": {"uk": "Неповно для розгляду default-треку", "en": "Incomplete for default-track review"},
    "dq_status_fallback":          {"uk": "Статус якості даних", "en": "Data quality status"},
    "dq_summary_complete":         {"uk": "Обов'язкові перевірки даних MDT завершені для поточного профілю кейсу.",
                                    "en": "Required MDT data checks are complete for the current case profile."},
    "dq_summary_caveats":          {"uk": "Критичних прогалин default-треку не знайдено, але MDT має переглянути наведені застереження перед фінальним підписанням.",
                                    "en": "No critical default-track gap was found, but the MDT should review the listed caveats before final sign-off."},
    "dq_summary_incomplete_mdt":   {"uk": "Підписання MDT неповне, доки не усунені критичні прогалини клінічних даних.",
                                    "en": "MDT sign-off is incomplete until critical clinical data gaps are resolved."},
    "dq_summary_incomplete_default": {"uk": "Розгляд default-треку неповний, доки не усунені обов'язкові прогалини біомаркерів.",
                                      "en": "Default-track review is incomplete until required biomarker gaps are resolved."},
    "dq_biomarker_coverage":       {"uk": "Покриття біомаркерів", "en": "Biomarker coverage"},
    "dq_known":                    {"uk": "відомо", "en": "known"},
    "dq_missing":                  {"uk": "відсутньо", "en": "missing"},
    "dq_default_gaps":             {"uk": "прогалин default-треку", "en": "default-track gaps"},
    "dq_missing_critical":         {"uk": "Відсутні критичні", "en": "Missing critical"},
    "dq_missing_recommended":      {"uk": "Відсутні рекомендовані", "en": "Missing recommended"},
    "dq_unevaluated_redflags":     {"uk": "Неоцінені RedFlags", "en": "Unevaluated RedFlags"},
    "dq_doctor_action_heading":    {"uk": "Відсутні дані для дії лікаря", "en": "Missing data for doctor action"},
    "dq_th_clinical_item":         {"uk": "Клінічний пункт", "en": "Clinical item"},
    "dq_th_owner":                 {"uk": "Власник", "en": "Owner"},
    "dq_th_why":                   {"uk": "Чому важливо", "en": "Why it matters"},
    "dq_th_next_action":           {"uk": "Наступна дія", "en": "Next action"},
    "dq_th_blocks":                {"uk": "Блокує", "en": "Blocks"},
    "dq_priority_critical":        {"uk": "КРИТИЧНО", "en": "CRITICAL"},
    "dq_priority_recommended":     {"uk": "РЕКОМЕНДОВАНО", "en": "RECOMMENDED"},
    "dq_missing_biomarker":        {"uk": "Відсутній біомаркер", "en": "Missing biomarker"},
    "dq_label":                    {"uk": "Назва", "en": "Label"},
    "dq_mdt_owner":                {"uk": "Власник MDT", "en": "MDT owner"},
    "dq_default_track":            {"uk": "Default-трек", "en": "Default track"},
    "dq_required_by":              {"uk": "Потрібно для", "en": "Required by"},
    "dq_yes":                      {"uk": "так", "en": "yes"},
    "dq_no":                       {"uk": "ні", "en": "no"},
    "dq_biomarker_action_base":    {"uk": "Перевірити результат, метод, матеріал і дату звіту перед підписанням.",
                                    "en": "Verify result, method, specimen, and report date before sign-off."},
    "dq_biomarker_action_constraint": {"uk": "Очікуване значення/умова", "en": "Expected/constraint"},
    "dq_more_missing_data":        {"uk": "більше відсутніх пунктів даних", "en": "more missing data items"},
    "dq_more_missing_biomarkers":  {"uk": "більше відсутніх вимог до біомаркерів", "en": "more missing biomarker requirements"},
    "blocking":                    {"uk": "BLOCKING", "en": "BLOCKING"},
    "sources_cited":               {"uk": "Sources cited", "en": "Sources cited"},
    # Track labels (matches plan.py track id semantics)
    "track_standard":              {"uk": "Стандартний план", "en": "Standard plan"},
    "track_aggressive":            {"uk": "Агресивний план", "en": "Aggressive plan"},
    "track_surveillance":          {"uk": "Активне спостереження (watch-and-wait)",
                                    "en": "Active surveillance (watch-and-wait)"},
    "track_palliative":            {"uk": "Паліативний план", "en": "Palliative plan"},
    "track_trial":                 {"uk": "План у рамках клінічного дослідження", "en": "Clinical-trial-only plan"},
    "track_local_therapy":         {"uk": "Локальна терапія", "en": "Local therapy plan"},
    "track_transplant":            {"uk": "Трансплантаційний план", "en": "Transplant plan"},
    # Document headers
    "doc_label_plan":              {"uk": "OpenOnco · Treatment Plan", "en": "OpenOnco · Treatment Plan"},
    "doc_title_plan_prefix":       {"uk": "План лікування", "en": "Treatment plan"},
    "doc_label_brief":             {"uk": "OpenOnco · Workup Brief · DIAGNOSTIC PHASE",
                                    "en": "OpenOnco · Workup Brief · DIAGNOSTIC PHASE"},
    "doc_title_brief":             {"uk": "Brief підготовки до тумор-борду", "en": "Pre-tumor-board workup brief"},
    "doc_label_revision":          {"uk": "OpenOnco · Revision Note", "en": "OpenOnco · Revision Note"},
    "doc_title_revision":          {"uk": "Перегляд плану", "en": "Plan revision"},
    # Banners and labels
    "diagnostic_banner_strong":    {"uk": "⚠ DIAGNOSTIC PHASE — TREATMENT PLAN NOT YET APPLICABLE",
                                    "en": "⚠ DIAGNOSTIC PHASE — TREATMENT PLAN NOT YET APPLICABLE"},
    "patient_label":               {"uk": "Пацієнт", "en": "Patient"},
    "diagnosis_label":             {"uk": "Діагноз", "en": "Diagnosis"},
    "moh_icd10_label":             {"uk": "МОЗ / ICD-10", "en": "MOH / ICD-10"},
    "stage_label":                 {"uk": "Стадія", "en": "Stage"},
    "histology_label":             {"uk": "Гістологія", "en": "Histology"},
    "default_badge":                {"uk": "★ DEFAULT", "en": "★ DEFAULT"},
    "indication_label":            {"uk": "Indication", "en": "Indication"},
    "regimen_label":               {"uk": "Regimen", "en": "Regimen"},
    "supportive_label":            {"uk": "Supportive care", "en": "Supportive care"},
    "ci_label":                    {"uk": "Hard contraindications", "en": "Hard contraindications"},
    "reason_label":                {"uk": "Reason", "en": "Reason"},
    # Skill catalog
    "skill_catalog_prefix":        {"uk": "Технічні метадані MDT skills", "en": "Technical MDT skill metadata"},
    "skill_catalog_active_in":     {"uk": "активовано в цьому плані", "en": "activated in this plan"},
    "skill_catalog_legend":        {"uk": "Усі зареєстровані віртуальні спеціалісти. ✓ — активовано для цього кейсу; ○ — не активовано (доступні для інших клінічних сценаріїв).",
                                    "en": "All registered virtual specialists. ✓ — activated for this case; ○ — not activated (available for other clinical scenarios)."},
    "th_specialist":               {"uk": "Спеціаліст", "en": "Specialist"},
    "th_skill_id":                 {"uk": "skill_id", "en": "skill_id"},
    "th_version":                  {"uk": "Версія", "en": "Version"},
    "th_last_reviewed":            {"uk": "Last reviewed", "en": "Last reviewed"},
    "th_signoffs":                 {"uk": "Sign-offs", "en": "Sign-offs"},
    "th_domain":                   {"uk": "Domain", "en": "Domain"},
    "th_id":                       {"uk": "ID", "en": "ID"},
    "th_name":                     {"uk": "Назва", "en": "Name"},
    "th_priority":                 {"uk": "Пріоритет", "en": "Priority"},
    "th_category":                 {"uk": "Категорія", "en": "Category"},
    "th_needed_for":               {"uk": "Потрібно для", "en": "Needed for"},
    "th_where_to_order":           {"uk": "Де замовити", "en": "Where to order"},
    "lab_avail_code_tbc":          {"uk": "код TBC", "en": "code TBC"},
    "lab_avail_none":              {"uk": "—", "en": "—"},
    "th_phase":                    {"uk": "Фаза", "en": "Phase"},
    "th_window":                   {"uk": "Вікно", "en": "Window"},
    "th_tests":                    {"uk": "Тести", "en": "Tests"},
    "th_checkpoints":              {"uk": "Контрольні точки", "en": "Checkpoints"},
    "scope_all_tracks":            {"uk": "усі треки", "en": "all tracks"},
    "scope_desired_prefix":        {"uk": "бажано", "en": "desired"},
    # Priority labels
    "priority_critical":           {"uk": "Критично", "en": "Critical"},
    "priority_standard":           {"uk": "Стандарт", "en": "Standard"},
    "priority_desired":            {"uk": "Бажано", "en": "Desired"},
    "priority_calculation_based":  {"uk": "Розрахунок", "en": "Calculation"},
    # PRO/CONTRA columns
    "pro_aggressive":              {"uk": "PRO-AGGRESSIVE", "en": "PRO-AGGRESSIVE"},
    "pro_aggressive_sub":          {"uk": "Тригери що штовхають до агресивного треку",
                                    "en": "Triggers that push toward the aggressive track"},
    "contra_aggressive":           {"uk": "CONTRA-AGGRESSIVE", "en": "CONTRA-AGGRESSIVE"},
    "contra_aggressive_sub":       {"uk": "Жорсткі протипоказання до ескалації",
                                    "en": "Hard contraindications to escalation"},
    # Timeline phase names
    "tl_baseline":                 {"uk": "Baseline", "en": "Baseline"},
    "tl_induction":                {"uk": "Induction", "en": "Induction"},
    "tl_response":                 {"uk": "Response assessment", "en": "Response assessment"},
    "tl_maintenance":              {"uk": "Maintenance", "en": "Maintenance"},
    "tl_followup":                 {"uk": "Follow-up", "en": "Follow-up"},
    # Disclaimers
    "medical_disclaimer":          {
        "uk": "Цей документ — інформаційний ресурс для підтримки обговорення в "
              "тумор-борді (per CHARTER §11). Не система, що приймає клінічні рішення. "
              "Усі рекомендації потребують перевірки лікуючим лікарем.",
        "en": "This document is an informational resource supporting tumor-board "
              "discussion (per CHARTER §11). It is not a system that makes clinical "
              "decisions. Every recommendation must be verified by the treating physician.",
    },
    "fda_disclosure_label":        {"uk": "Per FDA non-device CDS positioning (CHARTER §15):",
                                    "en": "Per FDA non-device CDS positioning (CHARTER §15):"},
    # Variant actionability (ESCAT)
    "actionability_heading":       {"uk": "Клінічна значущість мутацій (ESCAT)",
                                    "en": "Clinical significance of mutations (ESCAT)"},
    "actionability_sub":           {"uk": "Контекст для тумор-борду — інженер не використовує ці тіри для вибору треку",
                                    "en": "Tumor-board context — the engine does not use these tiers to rank tracks"},
    "actionability_th_biomarker":  {"uk": "Біомаркер", "en": "Biomarker"},
    "actionability_th_variant":    {"uk": "Варіант", "en": "Variant"},
    "actionability_th_escat":      {"uk": "ESCAT", "en": "ESCAT"},
    "actionability_th_evidence":   {"uk": "Доказова база", "en": "Evidence"},
    "actionability_th_action":     {"uk": "Клінічна дія", "en": "Clinical significance"},
    "actionability_th_combos":     {"uk": "Препарати", "en": "Drugs"},
    "actionability_th_sources":    {"uk": "Джерела", "en": "Sources"},
    "actionability_empty":         {"uk": "Не знайдено клінічно значущих варіантів у цьому профілі.",
                                    "en": "No clinically actionable variants matched in this profile."},
    "actionability_gene_level":    {"uk": "(гено-рівень)", "en": "(gene-level)"},
    "actionability_covered_heading":   {"uk": "✅ Покриті біомаркери (знайдено в KB)",
                                        "en": "✅ Covered biomarkers (matched in KB)"},
    "actionability_uncovered_heading": {"uk": "⚠️ Не враховані при побудові плану",
                                        "en": "⚠️ Not included in plan"},
    "actionability_uncovered_th_status": {"uk": "Статус", "en": "Status"},
    "actionability_uncovered_negative":  {"uk": "Виключено (негативний)", "en": "Excluded (negative)"},
    "actionability_uncovered_unmatched": {"uk": "Немає в KB — рекомендуйте лікарю уточнити",
                                          "en": "Not in KB — ask clinician to verify"},
    "actionability_uncovered_bio_exists": {"uk": "BIO-визначення є в KB; ESCAT BMA-запис відсутній — уточніть у лікаря",
                                           "en": "BIO definition in KB; no ESCAT BMA entry — verify with clinician"},
    # Experimental options (clinical-trial track)
    "exp_heading":                 {"uk": "Експериментальні опції (клінічні дослідження)",
                                    "en": "Experimental options (clinical trials)"},
    "exp_unset_sub":               {"uk": "Третій трек плану — open-enrollment trials з ClinicalTrials.gov.",
                                    "en": "Third plan track — open-enrollment trials from ClinicalTrials.gov."},
    "exp_unset_msg":               {"uk": "🔬 Дані недоступні — синхронізація з ClinicalTrials.gov не виконана. "
                                          "Передайте experimental_search_fn у generate_plan() "
                                          "або синхронізуйте офлайн (per ua-ingestion plan §3.3).",
                                    "en": "🔬 Data unavailable — ClinicalTrials.gov sync has not run. "
                                          "Pass experimental_search_fn to generate_plan() "
                                          "or sync offline (per ua-ingestion plan §3.3)."},
    "exp_last_synced_prefix":      {"uk": "Останнє оновлення:", "en": "Last synced:"},
    "exp_empty_default":           {"uk": "Жодного активного трайла для цього сценарію в ctgov не знайдено.",
                                    "en": "No active trials matched this scenario in ctgov."},
    "exp_table_sub":               {"uk": "Третій трек плану — open-enrollment trials з ClinicalTrials.gov. "
                                          "Render-time metadata; engine selection не змінюється цим блоком (CHARTER §8.3).",
                                    "en": "Third plan track — open-enrollment trials from ClinicalTrials.gov. "
                                          "Render-time metadata; engine selection is not affected by this block (CHARTER §8.3)."},
    "exp_th_nct":                  {"uk": "NCT", "en": "NCT"},
    "exp_th_title":                {"uk": "Назва", "en": "Title"},
    "exp_th_phase":                {"uk": "Фаза", "en": "Phase"},
    "exp_th_status":               {"uk": "Статус", "en": "Status"},
    "exp_th_sponsor":              {"uk": "Спонсор", "en": "Sponsor"},
    "exp_th_ua":                   {"uk": "UA", "en": "UA"},
    "exp_th_eligibility":          {"uk": "Включення (фрагмент)", "en": "Eligibility (excerpt)"},
    "exp_disclaimer":              {"uk": "Перевіряти статус набору безпосередньо у дослідницькому центрі. "
                                          "Дані ctgov можуть відставати від поточного статусу UA-сайтів.",
                                    "en": "Verify recruitment status directly with the trial site. "
                                          "ctgov data can lag behind current UA-site status."},
    # Trial outlook — per-trial structured signals (CHARTER §8.3 invariant:
    # render-time only, engine never reads these back)
    "exp_th_outlook":              {"uk": "Сигнали", "en": "Signals"},
    "exp_outlook_enriched":        {"uk": "Біомаркер: збагачено",
                                    "en": "Biomarker: enriched"},
    "exp_outlook_unclear":         {"uk": "Біомаркер: неоднозначно",
                                    "en": "Biomarker: unclear"},
    "exp_outlook_phase1":          {"uk": "Лише фаза 1", "en": "Phase 1 only"},
    "exp_outlook_small_n":         {"uk": "Малий набір (N<50)",
                                    "en": "Small N (<50)"},
    "exp_outlook_surrogate":       {"uk": "Сурогатна кінцева точка",
                                    "en": "Surrogate endpoint only"},
    "exp_outlook_single_country":  {"uk": "Одна країна",
                                    "en": "Single country"},
    # Access matrix
    "matrix_heading":              {"uk": "Доступність опцій в Україні",
                                    "en": "Option availability in Ukraine"},
    "matrix_sub":                  {"uk": "Per-track UA registration · НСЗУ · cost · access pathway. "
                                          "Render-time metadata; engine selection не залежить від цих полів (CHARTER §8.3).",
                                    "en": "Per-track UA registration · NSZU · cost · access pathway. "
                                          "Render-time metadata; engine selection does not depend on these fields (CHARTER §8.3)."},
    "matrix_th_option":            {"uk": "Опція", "en": "Option"},
    "matrix_th_registration":      {"uk": "Реєстрація UA", "en": "UA registration"},
    "matrix_th_nszu":              {"uk": "НСЗУ", "en": "NSZU"},
    "matrix_th_cost":              {"uk": "Cost orientation", "en": "Cost orientation"},
    "matrix_th_pathway":           {"uk": "Access pathway", "en": "Access pathway"},
    "matrix_avail_registered":     {"uk": "зареєстровано", "en": "registered"},
    "matrix_avail_not_registered": {"uk": "не зареєстровано", "en": "not registered"},
    "matrix_avail_covered":        {"uk": "покривається", "en": "covered"},
    "matrix_avail_oop":            {"uk": "out-of-pocket", "en": "out-of-pocket"},
    "matrix_avail_unknown":        {"uk": "— невідомо", "en": "— unknown"},
    "matrix_path_trial_sponsor":   {"uk": "Trial sponsor", "en": "Trial sponsor"},
    "matrix_path_nszu_formulary":  {"uk": "НСЗУ formulary", "en": "NSZU formulary"},
    "matrix_path_not_recorded":    {"uk": "not recorded", "en": "not recorded"},
    "matrix_cost_trial":           {"uk": "0 для пацієнта (sponsor pays)",
                                    "en": "0 for patient (sponsor pays)"},
    "matrix_cost_unknown":         {"uk": "₴-? — verify pathway",
                                    "en": "₴-? — verify pathway"},
    "matrix_cost_label_nszu":      {"uk": "НСЗУ:", "en": "NSZU:"},
    "matrix_cost_label_selfpay":   {"uk": "self-pay:", "en": "self-pay:"},
    "matrix_disclaimer":           {"uk": "Інформація про ціни — orientation. Перевіряти у конкретній аптеці / foundation / трайл-сайті.",
                                    "en": "Cost information is orientation. Verify with a specific pharmacy / foundation / trial site."},
    "matrix_status_updated":       {"uk": "Status updated:", "en": "Status updated:"},
    # ── MDT orchestrator strings ──────────────────────────────────────────
    # The orchestrator (knowledge_base/engine/mdt_orchestrator.py) emits
    # role `reason`s and OpenQuestion `question`/`rationale` strings as
    # Ukrainian literals. The render layer pipes them through `_h_t`
    # which only translates when a translate client is configured;
    # without one, UA leaks into EN renders. We register the literals
    # here so `_localize_html`'s post-pass substitutes them. Keep
    # `uk` values byte-identical to the source — fragments must match
    # whole-word for `str.replace` to fire.
    "mdt_role_lymphoma":           {"uk": "Лімфомний діагноз — провідна спеціальність для терапевтичного ведення.",
                                    "en": "Lymphoma diagnosis — primary specialty for therapeutic management."},
    "mdt_role_hcv_hbv":            {"uk": "Активна вірусна етіологія (HCV/HBV) потребує паралельного ведення антивірусної терапії та оцінки реактивації.",
                                    "en": "Active viral etiology (HCV/HBV) requires concurrent antiviral management and reactivation monitoring."},
    "mdt_role_imaging":            {"uk": "Наявні візуалізаційні знахідки — потрібен радіолог для staging/restaging.",
                                    "en": "Imaging findings present — radiologist needed for staging/restaging."},
    "mdt_role_pathology":          {"uk": "Підтвердження гістології лімфоми + оцінка ризику трансформації (DLBCL/Richter).",
                                    "en": "Lymphoma histology confirmation + transformation risk assessment (DLBCL/Richter)."},
    "mdt_role_pharmacist":         {"uk": "Хіміоімунотерапевтичний схема — drug-drug interactions, dose adjustments, premedication.",
                                    "en": "Chemoimmunotherapy regimen — drug-drug interactions, dose adjustments, premedication."},
    "mdt_role_radonc":             {"uk": "Екстранодальна MALT-лімфома — у частини локалізацій локальна променева терапія є опцією.",
                                    "en": "Extranodal MALT lymphoma — for some sites, local radiotherapy is a treatment option."},
    "mdt_role_social_worker":      {"uk": "У плані використовуються препарати без реімбурсації НСЗУ — потрібна оцінка доступу для пацієнта.",
                                    "en": "The plan uses drugs without NSZU reimbursement — patient access needs to be assessed."},
    "mdt_role_palliative":         {"uk": "Знижений performance status / декомпенсована коморбідність — потрібна оцінка цілей лікування.",
                                    "en": "Reduced performance status / decompensated comorbidity — goals-of-care assessment needed."},
    "mdt_role_molgen":             {"uk": "Indication посилається на actionable геномний біомаркер — потрібна інтерпретація мутації / target / actionability.",
                                    "en": "Indication references an actionable genomic biomarker — mutation / target / actionability interpretation needed."},
    # Escalation suffix appended to an existing role reason when a fired
    # RedFlag bumps the role's priority. Preserve the leading space.
    "mdt_escalation_suffix":       {"uk": " Ескальовано через RedFlag ",
                                    "en": " Escalated via RedFlag "},
    # Open-question text + rationale (deterministic strings emitted from
    # `_apply_open_question_rules`).
    "oq_hbv_q":                    {"uk": "Чи проведена серологія HBV (HBsAg, anti-HBc total)? До початку anti-CD20 терапії статус має бути відомий.",
                                    "en": "Has HBV serology been done (HBsAg, anti-HBc total)? Status must be known before starting anti-CD20 therapy."},
    "oq_hbv_r":                    {"uk": "Anti-CD20 без HBV профілактики при HBsAg+/anti-HBc+ несе значний ризик реактивації (CI-HBV-NO-PROPHYLAXIS).",
                                    "en": "Anti-CD20 without HBV prophylaxis in HBsAg+/anti-HBc+ patients carries significant reactivation risk (CI-HBV-NO-PROPHYLAXIS)."},
    "oq_fibrosis_q":               {"uk": "Який стадій фіброзу/цирозу печінки (Child-Pugh, FIB-4)? Це впливає на вибір DAA та dosing бендамустину.",
                                    "en": "What is the liver fibrosis/cirrhosis stage (Child-Pugh, FIB-4)? It affects DAA choice and bendamustine dosing."},
    "oq_fibrosis_r":               {"uk": "Декомпенсований цироз — RF-DECOMP-CIRRHOSIS, вимагає змін у схемі.",
                                    "en": "Decompensated cirrhosis — RF-DECOMP-CIRRHOSIS, requires regimen changes."},
    "oq_cd20_q":                   {"uk": "Чи підтверджено CD20+ статус гістологією (IHC)? Без CD20+ rituximab/obinutuzumab не показані.",
                                    "en": "Has CD20+ status been confirmed by histology (IHC)? Without CD20+, rituximab/obinutuzumab are not indicated."},
    "oq_cd20_r":                   {"uk": "Anti-CD20 терапія — основа для більшості ліній; відсутність експресії CD20 повністю змінює regimen.",
                                    "en": "Anti-CD20 therapy is the backbone of most lines; absence of CD20 expression entirely changes the regimen."},
    "oq_staging_q":                {"uk": "Чи виконано повне стадіювання (Lugano + PET/CT або CT)?",
                                    "en": "Has complete staging been performed (Lugano + PET/CT or CT)?"},
    "oq_staging_r":                {"uk": "Прогноз і вибір треку залежать від stage та tumor burden.",
                                    "en": "Prognosis and track selection depend on stage and tumor burden."},
    "oq_ldh_q":                    {"uk": "Який актуальний LDH? Маркер пухлинного навантаження і трансформації.",
                                    "en": "What is the current LDH? A marker of tumor burden and transformation."},
    "oq_ldh_r":                    {"uk": "LDH входить у прогностичні індекси індолентних лімфом.",
                                    "en": "LDH is a component of indolent-lymphoma prognostic indices."},
    # OQ-DRUG-AVAILABILITY question is built dynamically with non-reimbursed
    # drug IDs interpolated in the middle. Register the static prefix and
    # suffix separately; substitution is longest-first so each fragment
    # is replaced independently of the dynamic IDs.
    "oq_drugavail_q_prefix":       {"uk": "Чи доступні препарати без реімбурсації НСЗУ для пацієнта (",
                                    "en": "Are non-NSZU-reimbursed drugs available for the patient ("},
    "oq_drugavail_q_suffix":       {"uk": ")? Чи потрібна social work consult / альтернативний схема?",
                                    "en": ")? Is a social work consult / alternative regimen needed?"},
    "oq_drugavail_r":              {"uk": "Препарати з reimbursed_nszu=false означають out-of-pocket вартість для пацієнта; це впливає на adherence та реалістичність плану.",
                                    "en": "Drugs with reimbursed_nszu=false mean out-of-pocket cost for the patient; this affects adherence and the plan's feasibility."},
    # ── Diagnostic-mode MDT strings (pre-biopsy Workup Brief) ─────────────
    # Mirrors the treatment-mode set above for the orchestrator's
    # `_apply_diagnostic_role_rules` / `_apply_diagnostic_open_question_rules`.
    "mdt_diag_lymphoma":           {"uk": "Підозра на лімфому — провідна спеціальність для diagnostic workup та подальшого ведення.",
                                    "en": "Lymphoma suspected — primary specialty for diagnostic workup and ongoing management."},
    "mdt_diag_pathology":          {"uk": "Будь-яка підозра вимагає біопсії — патолог планує вибір місця, IHC панель, ancillary tests.",
                                    "en": "Any suspicion warrants biopsy — pathologist plans the biopsy site, IHC panel, and ancillary tests."},
    "mdt_diag_imaging":            {"uk": "Stage / restaging imaging + biopsy guidance — радіолог.",
                                    "en": "Stage / restaging imaging + biopsy guidance — radiologist."},
    "mdt_diag_solid":              {"uk": "Підозра на солідну пухлину — оцінка resectability, biopsy approach.",
                                    "en": "Solid tumor suspected — resectability assessment, biopsy approach."},
    "mdt_diag_idhep":              {"uk": "Перед anti-CD20 treatment status HCV/HBV має бути відомий — ще на діагностичній фазі.",
                                    "en": "HCV/HBV status must be known before any anti-CD20 treatment — establish during the diagnostic phase."},
    "mdt_diag_palliative":         {"uk": "Знижений performance status / ознаки декомпенсації — рання оцінка цілей лікування.",
                                    "en": "Reduced performance status / decompensation signs — early goals-of-care assessment."},
    # Diagnostic-mode open questions
    "oq_diag_cd20_q":              {"uk": "Який результат CD20 IHC буде після біопсії? Без CD20+ rituximab/obinutuzumab не показані.",
                                    "en": "What will the post-biopsy CD20 IHC result show? Without CD20+, rituximab/obinutuzumab are not indicated."},
    "oq_diag_cd20_r":              {"uk": "Базис для будь-якого anti-CD20-containing regimen у майбутньому.",
                                    "en": "Foundation for any future anti-CD20-containing regimen."},
    # The HBV-pre-biopsy question contains an apostrophe in "обов'язкова",
    # so `_localize_html` will register both the raw and `&#x27;`-escaped
    # variants. Either form will substitute correctly.
    "oq_diag_hbv_q":               {"uk": "Серологія HBV (HBsAg, anti-HBc) — обов'язкова перед anti-CD20; почати workup зараз.",
                                    "en": "HBV serology (HBsAg, anti-HBc) is mandatory before anti-CD20; start workup now."},
    "oq_diag_hbv_r":               {"uk": "HBV reactivation risk при anti-CD20 без prophylaxis.",
                                    "en": "HBV reactivation risk with anti-CD20 absent prophylaxis."},
    "oq_diag_staging_q":           {"uk": "Чи запланований повний staging (PET/CT + bone marrow за показаннями)?",
                                    "en": "Is full staging planned (PET/CT + bone marrow as indicated)?"},
    "oq_diag_staging_r":           {"uk": "Stage визначає track і treatment intensity.",
                                    "en": "Stage determines track and treatment intensity."},
    # Differential-diagnosis question is built dynamically with hypothesis
    # IDs interpolated mid-sentence; register prefix and suffix separately
    # so each substitutes independently of the dynamic content.
    "oq_diag_diffdiag_q_prefix":   {"uk": "Який план диференціальної діагностики між гіпотезами: ",
                                    "en": "What is the differential-diagnosis plan among the hypotheses: "},
    "oq_diag_diffdiag_q_suffix":   {"uk": "? Які молекулярні / IHC тести розрізняють?",
                                    "en": "? Which molecular / IHC tests distinguish them?"},
    "oq_diag_diffdiag_r":          {"uk": "Множинні гіпотези — розрізнити їх перед treatment discussion.",
                                    "en": "Multiple hypotheses — resolve them before any treatment discussion."},
}


def _t(key: str, target_lang: str = "uk") -> str:
    """Look up a UI label in the desired language. Falls back to UA if
    the key is missing in the target language. Falls back to the key
    itself if the key is missing entirely (defensive — surfaces missing
    translations clearly in the rendered output)."""
    entry = _UI_STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(target_lang) or entry.get("uk") or key


def _track_label(track_id: str, target_lang: str = "uk") -> str:
    """Map a track_id to its localized display label."""
    return _t(f"track_{track_id}", target_lang) or track_id


def _localize_html(html_text: str, target_lang: str) -> str:
    """Post-process a fully-rendered UA HTML document into another language
    by targeted UI-label substitution. The render layer always produces UA
    first; if the caller asks for `target_lang != "uk"`, we do longest-first
    string replacements over the known UI labels in `_UI_STRINGS` plus a
    handful of common phrases used inside f-strings.

    Free-text KB content (Indication.rationale, Indication.notes, RedFlag
    definitions, etc.) is NOT translated here — that's the next iteration
    via `knowledge_base.clients.translate_client`. Only UI labels.

    Also flips `<html lang="uk">` to `<html lang="en">` for proper a11y.
    """
    if target_lang == "uk" or not target_lang:
        return html_text

    # Build the substitution map: UA-side string → target-lang string, only
    # when both sides exist and differ. Include both the raw and the
    # HTML-escaped form (the render layer pipes most strings through _h()
    # which encodes apostrophes as `&#x27;` etc.) — without the escaped
    # variant a UA literal like "обов'язкові" would never match. Longest-
    # first to avoid collisions ("Стандартний план" before "Стандарт").
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entry in _UI_STRINGS.values():
        ua = entry.get("uk")
        out = entry.get(target_lang)
        if not ua or not out or ua == out:
            continue
        for src, dst in (
            (ua, out),
            (html.escape(ua, quote=True), html.escape(out, quote=True)),
        ):
            if src in seen or src == dst:
                continue
            pairs.append((src, dst))
            seen.add(src)
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    out_html = html_text
    for src, dst in pairs:
        out_html = out_html.replace(src, dst)

    # Doc-language attribute
    out_html = out_html.replace('<html lang="uk">', f'<html lang="{target_lang}">')
    return out_html


def _doc_shell(title: str, body: str, target_lang: str = "uk") -> str:
    """Wrap rendered body in a complete HTML document with embedded CSS."""
    lang_attr = "en" if target_lang == "en" else "uk"
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang_attr}">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{_h(title)}</title>\n"
        '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900'
        '&family=Source+Sans+3:wght@300;400;500;600;700'
        '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
        f"<style>{_CSS}</style>\n"
        "</head>\n<body>\n"
        f'<div class="page">{body}</div>\n'
        "</body>\n</html>\n"
    )


# EN-side display labels for MDT role_id values. The canonical UA labels
# live in `mdt_orchestrator._ROLE_CATALOG` (out of scope per the render
# refactor brief — render.py is the only file we modify). This dict is
# the render-side EN mirror; when a role_id is missing, we fall back to
# the UA label that the orchestrator already baked into r.role_name.
# Keys here MUST match the keys in `_ROLE_CATALOG` — when a role is added
# upstream, mirror the entry here too.
_ROLE_NAME_EN: dict[str, str] = {
    "hematologist": "Hematologist / oncohematologist",
    "medical_oncologist": "Medical oncologist (solid-tumor chemotherapist)",
    "infectious_disease_hepatology": "Infectious disease / hepatology",
    "radiologist": "Radiologist",
    "pathologist": "Pathologist (general)",
    "hematopathologist": "Hematopathologist (lymphoma / leukemia / myeloma)",
    "molecular_geneticist": "Molecular geneticist / molecular oncologist",
    "clinical_pharmacist": "Clinical pharmacist",
    "radiation_oncologist": "Radiation oncologist",
    "surgical_oncologist": "Surgical oncologist",
    "transplant_specialist": "Transplant specialist (BMT)",
    "cellular_therapy_specialist": "Cellular therapy specialist (CAR-T)",
    "psychologist": "Psycho-oncologist",
    "palliative_care": "Palliative care",
    "social_worker_case_manager": "Social worker / case manager",
    "primary_care": "Primary care / family physician",
}


def _localized_role_name(role_id: str, fallback_name: str,
                         target_lang: str = "uk") -> str:
    """EN side: prefer `_ROLE_NAME_EN[role_id]`; otherwise emit the UA
    label baked in by the orchestrator. UA side: pass through unchanged."""
    if (target_lang or "uk").lower().startswith("en"):
        return _ROLE_NAME_EN.get(role_id) or fallback_name
    return fallback_name


def _render_mdt_section(mdt: Optional[MDTOrchestrationResult],
                        target_lang: str = "uk") -> str:
    if mdt is None:
        return ""
    parts: list[str] = []
    # `Owns` and `Open questions` are emitted in English on both sides
    # today (UA team chose to keep these MDT-internal labels in English);
    # `_localize_html` is a no-op for them. If a UA-translated form is
    # ever desired, add keys to `_UI_STRINGS` and route through `_t`.

    def _role_block(label: str, badge_cls: str, roles) -> str:
        if not roles:
            return ""
        items = []
        for r in roles:
            qs = (
                f'<div class="role-questions">Owns: {_h(", ".join(r.linked_questions))}</div>'
                if r.linked_questions else ""
            )
            display_name = _localized_role_name(r.role_id, r.role_name, target_lang)
            items.append(
                f"<li>"
                f'<span class="role-name">{_h(display_name)}</span> '
                f'<span class="badge {badge_cls}">{_h(r.priority)}</span>'
                f'<div class="role-reason">{_h_t(r.reason, target_lang)}</div>'
                f"{qs}"
                f"</li>"
            )
        return (
            f"<h3>{_h(label)} ({len(roles)})</h3>"
            f'<ul class="role-list">{"".join(items)}</ul>'
        )

    qs = mdt.open_questions
    if qs:
        blocking = sum(1 for q in qs if q.blocking)
        items = []
        for q in qs:
            cls = " blocking" if q.blocking else ""
            tag = '<span class="badge badge--blocking">BLOCKING</span> ' if q.blocking else ""
            items.append(
                f'<li class="{cls.strip()}">'
                f'<div class="q-id">{tag}{_h(q.id)}</div>'
                f'<div class="q-text">{_h_t(q.question, target_lang)}</div>'
                f'<div class="q-rationale">{_h_t(q.rationale, target_lang)}</div>'
                f'<div class="q-owner">→ {_h(q.owner_role)}</div>'
                f"</li>"
            )
        parts.append(
            f"<h3>{_h(_t('open_questions', target_lang))} ({len(qs)}, {blocking} blocking)</h3>"
            f'<ul class="q-list q-list--featured">{"".join(items)}</ul>'
        )

    talk_tree = getattr(mdt, "talk_tree", []) or []
    if talk_tree:
        rows = []
        for node in talk_tree[:14]:
            step = getattr(node, "step", None)
            owner = getattr(node, "owner_role", "")
            topic = getattr(node, "topic", "")
            action = getattr(node, "action", "")
            blocking = getattr(node, "blocking", False)
            badge = '<span class="badge badge--blocking">BLOCKING</span>' if blocking else ""
            rows.append(
                "<tr>"
                f'<td class="mono">{_h(step if step is not None else "")}</td>'
                f'<td>{_h(owner)}</td>'
                f'<td>{_h(topic)} {badge}</td>'
                f'<td>{_h_t(action, target_lang)}</td>'
                "</tr>"
            )
        more = len(talk_tree) - 14
        more_txt = (
            f'<div class="section-sub">+{more} more MDT talk steps.</div>'
            if more > 0 else ""
        )
        parts.append(
            f"<h3>MDT talk tree ({len(talk_tree)} steps)</h3>"
            '<table class="tbl"><thead><tr>'
            '<th>#</th><th>Owner</th><th>Topic</th><th>Action</th>'
            '</tr></thead><tbody>'
            f'{"".join(rows)}'
            '</tbody></table>'
            f'{more_txt}'
        )

    parts.append(_role_block(
        _t("skills_required", target_lang),
        "badge--required", mdt.required_roles))
    parts.append(_role_block(
        _t("skills_recommended", target_lang),
        "badge--recommended", mdt.recommended_roles))
    parts.append(_role_block(
        _t("skills_optional", target_lang),
        "badge--optional", mdt.optional_roles))

    dq = mdt.data_quality_summary or {}
    crit = dq.get("missing_critical_fields") or []
    rec = dq.get("missing_recommended_fields") or []
    unevaluated = dq.get("unevaluated_red_flags") or []
    field_unlocks = dq.get("field_unlocks") or {}
    biomarker_coverage = dq.get("biomarker_coverage") or {}
    missing_field_details = dq.get("missing_field_details") or []

    def _dq_status_label(status: str) -> str:
        return {
            "complete_for_mdt_review": _t("dq_status_complete", target_lang),
            "usable_with_caveats": _t("dq_status_caveats", target_lang),
            "incomplete_for_mdt_review": _t("dq_status_incomplete_mdt", target_lang),
            "incomplete_for_default_track": _t("dq_status_incomplete_default", target_lang),
        }.get(status or "", status or _t("dq_status_fallback", target_lang))

    def _dq_status_summary(status: str, fallback: str) -> str:
        return {
            "complete_for_mdt_review": _t("dq_summary_complete", target_lang),
            "usable_with_caveats": _t("dq_summary_caveats", target_lang),
            "incomplete_for_mdt_review": _t("dq_summary_incomplete_mdt", target_lang),
            "incomplete_for_default_track": _t("dq_summary_incomplete_default", target_lang),
        }.get(status or "", fallback or "")

    def _dq_badge(severity: str) -> str:
        cls = "badge--required" if severity == "critical" else "badge--recommended"
        label = (
            _t("dq_priority_critical", target_lang)
            if severity == "critical"
            else _t("dq_priority_recommended", target_lang)
        )
        return f'<span class="badge {cls}">{label}</span>'

    def _dq_detail_text(item: dict, key: str) -> str:
        if target_lang == "uk":
            return item.get(f"{key}_uk") or item.get(key) or ""
        return item.get(key) or item.get(f"{key}_uk") or ""

    def _dq_field(f: str) -> str:
        rfs = field_unlocks.get(f)
        if not rfs:
            return _h(f)
        rf_txt = _h(", ".join(rfs))
        return (
            f'{_h(f)} <span style="color:var(--gray-500);font-size:11px;">'
            f"blocks: {rf_txt}</span>"
        )

    if crit or rec or unevaluated or biomarker_coverage:
        status = dq.get("status") or ""
        summary = _dq_status_summary(status, dq.get("doctor_summary") or "")
        status_line = (
            f'<div class="section-sub"><strong>{_h(_dq_status_label(status))}.</strong> '
            f'{_h(summary)}</div>'
            if status or summary else ""
        )
        parts.append(f"<h3>{_h(_t('data_quality', target_lang))}</h3>{status_line}<ul>")
        if biomarker_coverage:
            total = biomarker_coverage.get("required_total", 0)
            known = biomarker_coverage.get("required_known", 0)
            missing = biomarker_coverage.get("required_missing", 0)
            pct = biomarker_coverage.get("coverage_percent", 100)
            default_missing = dq.get("missing_default_biomarkers", 0)
            parts.append(
                f"<li>{_h(_t('dq_biomarker_coverage', target_lang))}: "
                f"{known}/{total} {_h(_t('dq_known', target_lang))} "
                f"({pct}%), {missing} {_h(_t('dq_missing', target_lang))}, "
                f"{default_missing} {_h(_t('dq_default_gaps', target_lang))}</li>"
            )
        if crit:
            parts.append(
                f"<li>{_h(_t('dq_missing_critical', target_lang))}: "
                f"{', '.join(_dq_field(f) for f in crit)}</li>"
            )
        if rec:
            parts.append(
                f"<li>{_h(_t('dq_missing_recommended', target_lang))}: "
                f"{', '.join(_dq_field(f) for f in rec)}</li>"
            )
        if unevaluated:
            parts.append(
                f"<li>{_h(_t('dq_unevaluated_redflags', target_lang))}: "
                f"{_h(', '.join(unevaluated))}</li>"
            )
        parts.append("</ul>")

        if missing_field_details:
            rows = []
            for item in missing_field_details[:12]:
                blocks = ", ".join(item.get("blocked_red_flags") or []) or "-"
                rows.append(
                    "<tr>"
                    f'<td>{_dq_badge(item.get("severity") or "")}</td>'
                    f'<td><strong>{_h(_dq_detail_text(item, "label") or item.get("field") or "")}</strong>'
                    f'<div class="section-sub"><code>{_h(item.get("field") or "")}</code></div></td>'
                    f'<td>{_h(item.get("owner_role") or "")}</td>'
                    f'<td>{_h(_dq_detail_text(item, "why_it_matters"))}</td>'
                    f'<td>{_h(_dq_detail_text(item, "doctor_action"))}</td>'
                    f'<td>{_h(blocks)}</td>'
                    "</tr>"
                )
            more = len(missing_field_details) - 12
            more_txt = (
                f'<div class="section-sub">+{more} {_h(_t("dq_more_missing_data", target_lang))}.</div>'
                if more > 0 else ""
            )
            parts.append(
                f"<h4>{_h(_t('dq_doctor_action_heading', target_lang))}</h4>"
                '<table class="tbl"><thead><tr>'
                f'<th>{_h(_t("th_priority", target_lang))}</th>'
                f'<th>{_h(_t("dq_th_clinical_item", target_lang))}</th>'
                f'<th>{_h(_t("dq_th_owner", target_lang))}</th>'
                f'<th>{_h(_t("dq_th_why", target_lang))}</th>'
                f'<th>{_h(_t("dq_th_next_action", target_lang))}</th>'
                f'<th>{_h(_t("dq_th_blocks", target_lang))}</th>'
                '</tr></thead><tbody>'
                f'{"".join(rows)}'
                '</tbody></table>'
                f'{more_txt}'
            )

        missing_biomarkers = biomarker_coverage.get("missing") or []
        if missing_biomarkers:
            rows = []
            for item in missing_biomarkers[:12]:
                tracks = ", ".join(item.get("tracks") or [])
                default = _t("dq_yes", target_lang) if item.get("default_track") else _t("dq_no", target_lang)
                action = _t("dq_biomarker_action_base", target_lang)
                constraint = item.get("value_constraint")
                if constraint:
                    action = f"{action} {_t('dq_biomarker_action_constraint', target_lang)}: {constraint}"
                rows.append(
                    "<tr>"
                    f'<td><code>{_h(item.get("biomarker_id") or "")}</code></td>'
                    f'<td>{_h(item.get("label") or "")}</td>'
                    f'<td>{_h(item.get("owner_role") or "")}</td>'
                    f"<td>{_h(default)}</td>"
                    f'<td>{_h(tracks)}</td>'
                    f'<td>{_h(action)}</td>'
                    "</tr>"
                )
            more = len(missing_biomarkers) - 12
            more_txt = (
                f'<div class="section-sub">+{more} {_h(_t("dq_more_missing_biomarkers", target_lang))}.</div>'
                if more > 0 else ""
            )
            parts.append(
                '<table class="tbl"><thead><tr>'
                f'<th>{_h(_t("dq_missing_biomarker", target_lang))}</th>'
                f'<th>{_h(_t("dq_label", target_lang))}</th>'
                f'<th>{_h(_t("dq_mdt_owner", target_lang))}</th>'
                f'<th>{_h(_t("dq_default_track", target_lang))}</th>'
                f'<th>{_h(_t("dq_required_by", target_lang))}</th>'
                f'<th>{_h(_t("dq_th_next_action", target_lang))}</th>'
                '</tr></thead><tbody>'
                f'{"".join(rows)}'
                '</tbody></table>'
                f'{more_txt}'
            )

    # Skill catalog — full list of registered skills with activation marker
    activated_ids = {s.skill_id for s in mdt.activated_skills}
    catalog_rows = []
    # Pull the full registry via the dict surfaced through to_dict()
    full = mdt.to_dict().get("skill_catalog", [])
    for s in full:
        sid = s["skill_id"]
        is_active = sid in activated_ids
        cls = "activated" if is_active else "dormant"
        # `s["name"]` is the UA-only `name` field on mdt_skills/<role>.yaml
        # (no `names:` block, no `name_en` today). EN-side render maps via
        # `_ROLE_NAME_EN` keyed on skill_id (== role_id); falls back to the
        # baked UA label when no entry is registered.
        display_name = _localized_role_name(sid, s["name"], target_lang)
        catalog_rows.append(
            f'<tr class="{cls}">'
            f'<td>{_h(display_name)}</td>'
            f'<td><code>{_h(sid)}</code></td>'
            f'<td class="ver">v{_h(s["version"])}</td>'
            f'<td>{_h(s["last_reviewed"])}</td>'
            f'<td>{s["signoffs"]}</td>'
            f'<td>{_h(s.get("domain") or "—")}</td>'
            "</tr>"
        )
    parts.append(
        '<details class="skill-catalog">'
        f'<summary>{_h(_t("skill_catalog_prefix", target_lang))} '
        f'({len(activated_ids)}/{len(full)} {_h(_t("skill_catalog_active_in", target_lang))})</summary>'
        f'<div class="section-sub">{_h(_t("skill_catalog_legend", target_lang))}</div>'
        '<table><thead><tr>'
        f'<th>{_h(_t("th_specialist", target_lang))}</th>'
        f'<th>{_h(_t("th_skill_id", target_lang))}</th>'
        f'<th>{_h(_t("th_version", target_lang))}</th>'
        f'<th>{_h(_t("th_last_reviewed", target_lang))}</th>'
        f'<th>{_h(_t("th_signoffs", target_lang))}</th>'
        f'<th>{_h(_t("th_domain", target_lang))}</th>'
        "</tr></thead><tbody>"
        f'{"".join(catalog_rows)}'
        "</tbody></table>"
        "</details>"
    )

    return (
        f'<section><h2>{_h(_t("mdt_brief", target_lang))}</h2>'
        f'<div class="mdt">{"".join(parts)}</div></section>'
    )


def _render_fda_disclosure(text: str) -> str:
    return (
        f'<div class="fda-disclosure">'
        f"<strong>Per FDA non-device CDS positioning (CHARTER §15):</strong> "
        f"{_h(text)}"
        f"</div>"
    )


def _render_version_chain(plan_id, version, supersedes, superseded_by, generated_at) -> str:
    parts = [f"plan_id: {_h(plan_id)} | version: {_h(version)} | generated: {_h(generated_at)}"]
    if supersedes:
        parts.append(f"supersedes: {_h(supersedes)}")
    if superseded_by:
        parts.append(f"superseded_by: {_h(superseded_by)}")
    return f'<div class="version-chain">{" | ".join(parts)}</div>'


_MEDICAL_DISCLAIMER = (
    "Цей документ — інформаційний ресурс для підтримки обговорення в "
    "тумор-борді (per CHARTER §11). Не система, що приймає клінічні рішення. "
    "Усі рекомендації потребують перевірки лікуючим лікарем."
)


# ── Section helpers (treatment Plan) ──────────────────────────────────────


def _render_etiological_driver(disease: Optional[dict],
                               target_lang: str = "uk") -> str:
    """Etiologically-driven archetype gets a featured card explaining WHY
    a particular driver (HCV, H. pylori, EBV, etc.) shapes treatment.
    Returns empty string for non-etiologically_driven diseases.

    Disease name uses `_pick_name` so EN-side renders surface
    `names.english`/`names.preferred` when present (EN side previously
    leaked the raw UA name)."""
    if not disease:
        return ""
    archetype = disease.get("archetype")
    if archetype != "etiologically_driven":
        return ""
    factors = disease.get("etiological_factors") or []
    name = _pick_name(
        disease.get("names"), target_lang, default=disease.get("id", "")
    )
    factor_items = "".join(f"<li>{_h(f)}</li>" for f in factors) or "<li>—</li>"
    return (
        '<section>'
        f'<h2>{_h(_t("etiological_driver", target_lang))}</h2>'
        '<div class="etiology-card">'
        f'<div class="label">{_h(_t("etiological_driver_label", target_lang))}</div>'
        f'<div class="archetype">{_h(name)}</div>'
        f'<ul>{factor_items}</ul>'
        '</div>'
        '</section>'
    )


_PRIORITY_LABEL_UA = {
    "critical": "Критично",
    "standard": "Стандарт",
    "desired": "Бажано",
    "calculation_based": "Розрахунок",
}
_PRIORITY_LABEL_EN = {
    "critical": "Critical",
    "standard": "Standard",
    "desired": "Desired",
    "calculation_based": "Calculation",
}


def _priority_label(priority: str, target_lang: str = "uk") -> str:
    """priority_class → localized badge text."""
    table = _PRIORITY_LABEL_EN if (target_lang or "uk").lower().startswith("en") \
        else _PRIORITY_LABEL_UA
    return table.get(priority, priority)


_PRIORITY_BADGE_CLS = {
    "critical": "badge--required",
    "standard": "badge--recommended",
    "desired": "badge--optional",
    "calculation_based": "badge--optional",
}
_PRIORITY_RANK = {"critical": 0, "standard": 1, "desired": 2, "calculation_based": 3}


def _render_lab_availability_cell(test: dict, target_lang: str = "uk") -> str:
    """Render the per-test "Where to order" cell from `lab_availability_ua`.

    Each entry becomes one chip: `<lab>: <code>` if a product code is verified,
    `<lab> ✓` if only the category is confirmed. Chips link to the lab's
    public catalog page; coverage_notes go in a `title` tooltip. Multiple
    entries (e.g. M081 + M065 fallback for NSCLC NGS) join with `<br>`.
    """
    entries = test.get("lab_availability_ua") or []
    if not entries:
        return _h(_t("lab_avail_none", target_lang))

    chips: list[str] = []
    for e in entries:
        lab = e.get("lab") or ""
        code = e.get("product_code")
        url = e.get("url") or ""
        notes = e.get("coverage_notes") or e.get("product_name") or ""
        if code:
            label = f"{lab}: {code}"
        else:
            label = f"{lab} ✓ ({_t('lab_avail_code_tbc', target_lang)})"
        title_attr = f' title="{_h(notes.strip())}"' if notes else ""
        if url:
            chips.append(
                f'<a class="lab-chip" href="{_h(url)}" target="_blank" '
                f'rel="noopener"{title_attr}>{_h(label)}</a>'
            )
        else:
            chips.append(f'<span class="lab-chip"{title_attr}>{_h(label)}</span>')
    return "<br>".join(chips)


def _render_pretreatment_investigations(
    plan, kb_resolved: dict, target_lang: str = "uk"
) -> str:
    """Pre-treatment investigations table: union of required + desired tests
    across all tracks, sorted by priority_class. Each row shows test name,
    priority badge, category, and which tracks need it.
    Per REFERENCE_CASE_SPECIFICATION §3.5.

    Names route through `_pick_name` so EN-side renders pull
    `names.english`/`names.preferred` (TEST-* YAMLs already carry both).
    Section/column labels and the priority badge text resolve via the
    `_t` UI dictionary; "all tracks" / "desired (...)" scope strings
    use the `scope_*` keys in `_UI_STRINGS`."""
    tests_lookup = (kb_resolved or {}).get("tests") or {}
    if not tests_lookup:
        return ""

    # Collect: test_id → {required_by: set[track_id], desired_by: set[track_id]}
    test_use: dict[str, dict] = {}
    for t in plan.tracks:
        ind = t.indication_data or {}
        for tid in ind.get("required_tests") or []:
            test_use.setdefault(tid, {"required_by": set(), "desired_by": set()})
            test_use[tid]["required_by"].add(t.track_id)
        for tid in ind.get("desired_tests") or []:
            test_use.setdefault(tid, {"required_by": set(), "desired_by": set()})
            test_use[tid]["desired_by"].add(t.track_id)
    if not test_use:
        return ""

    scope_all = _t("scope_all_tracks", target_lang)
    scope_desired_prefix = _t("scope_desired_prefix", target_lang)

    rows = []
    for tid, use in sorted(
        test_use.items(),
        key=lambda kv: (
            _PRIORITY_RANK.get((tests_lookup.get(kv[0]) or {}).get("priority_class", "standard"), 1),
            kv[0],
        ),
    ):
        test = tests_lookup.get(tid) or {}
        name = _pick_name(test.get("names"), target_lang, default=tid)
        priority = test.get("priority_class") or "standard"
        category = test.get("category") or "—"
        # If required by every track → "all"; else list which tracks
        all_track_ids = {t.track_id for t in plan.tracks}
        if use["required_by"] == all_track_ids:
            scope = scope_all
        elif use["required_by"]:
            scope = ", ".join(sorted(use["required_by"]))
        else:
            scope = f"{scope_desired_prefix} (" + ", ".join(sorted(use["desired_by"])) + ")"
        priority_badge = (
            f'<span class="badge {_PRIORITY_BADGE_CLS.get(priority, "badge--optional")}">'
            f'{_h(_priority_label(priority, target_lang))}</span>'
        )
        lab_cell = _render_lab_availability_cell(test, target_lang)
        rows.append(
            f'<tr><td>{_h(tid)}</td><td>{_h(name)}</td>'
            f'<td>{priority_badge}</td>'
            f'<td>{_h(category)}</td>'
            f'<td class="lab-avail-cell">{lab_cell}</td>'
            f'<td>{_h(scope)}</td></tr>'
        )

    return (
        '<section>'
        f'<h2>{_h(_t("pretreatment", target_lang))}</h2>'
        f'<div class="section-sub">{_h(_t("pretreatment_sub", target_lang))}</div>'
        '<table class="tbl">'
        f'<thead><tr><th>{_h(_t("th_id", target_lang))}</th>'
        f'<th>{_h(_t("th_name", target_lang))}</th>'
        f'<th>{_h(_t("th_priority", target_lang))}</th>'
        f'<th>{_h(_t("th_category", target_lang))}</th>'
        f'<th>{_h(_t("th_where_to_order", target_lang))}</th>'
        f'<th>{_h(_t("th_needed_for", target_lang))}</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        '</section>'
    )


def _render_branch_explanation(
    plan_result, kb_resolved: dict, target_lang: str = "uk"
) -> str:
    """Surface the actually-fired RedFlags from the engine trace.

    For each step that resolved a branch (`outcome=True` and `result` set),
    list the RFs that fired in that step and which one won the conflict-
    resolution tiebreak (`winner_red_flag` set by walk_algorithm in P2).

    This is the "Why this branch was chosen" answer — distinct from the
    PRO/CONTRA section above, which lists *possible* triggers. This one
    lists what actually drove the chosen branch on this specific patient.
    """
    rf_lookup = (kb_resolved or {}).get("red_flags") or {}
    src_lookup = (kb_resolved or {}).get("sources") or {}
    trace = getattr(plan_result, "trace", None) or []

    explained_steps: list[str] = []
    for step in trace:
        fired = step.get("fired_red_flags") or []
        if not fired:
            continue
        winner = step.get("winner_red_flag")
        branch = step.get("branch") or {}
        step_id = step.get("step")
        result_target = branch.get("result") or branch.get("next_step")

        rf_items: list[str] = []
        for rid in fired:
            rf = rf_lookup.get(rid) or {}
            defn = (
                rf.get("definition_ua")
                if target_lang == "uk" and rf.get("definition_ua")
                else rf.get("definition") or "—"
            )
            srcs = rf.get("sources") or []
            src_chips = "".join(
                f'<span class="src-chip">{_h(sid)}</span>'
                for sid in srcs
            )
            winner_mark = (
                ' <span class="rf-winner-tag">★ winner</span>'
                if rid == winner else ""
            )
            rf_items.append(
                f'<li><strong>{_h(rid)}</strong>{winner_mark}: '
                f'{_h(defn)} {src_chips}</li>'
            )

        head = (
            f"Step {step_id} → branch <code>{_h(str(result_target))}</code>"
            if result_target
            else f"Step {step_id}"
        )
        explained_steps.append(
            f'<div class="branch-step">'
            f'<div class="branch-step-head">{head}</div>'
            f'<ul>{"".join(rf_items)}</ul>'
            f'</div>'
        )

    if not explained_steps:
        return ""

    title = "Чому обрано саме цей трек" if target_lang == "uk" else "Why this branch was chosen"
    sub = (
        "Тригери з профілю пацієнта, що активувалися та визначили вибір."
        if target_lang == "uk"
        else "Triggers from the patient profile that fired and drove the chosen branch."
    )
    return (
        '<section class="branch-explanation">'
        f'<h2>{title}</h2>'
        f'<div class="section-sub">{sub}</div>'
        f'{"".join(explained_steps)}'
        '</section>'
    )


def _render_red_flags_pro_contra(plan, kb_resolved: dict, target_lang: str = "uk") -> str:
    """RedFlag PRO/CONTRA categorization for the aggressive escalation:

    - PRO-AGGRESSIVE: red flags that, when present, push the engine toward
      the aggressive track. Source: indication.red_flags_triggering_alternative
      on the STANDARD track + algorithm.decision_tree any_of red_flag clauses
      that resolve to the aggressive indication.
    - CONTRA-AGGRESSIVE: hard contraindications attached to the AGGRESSIVE
      track's indication / regimen — reasons NOT to escalate.

    Per REFERENCE_CASE_SPECIFICATION §3.8.
    """
    rf_lookup = (kb_resolved or {}).get("red_flags") or {}
    if not plan.tracks:
        return ""

    # PRO: union of red_flags_triggering_alternative across non-aggressive tracks
    pro_ids: set[str] = set()
    for t in plan.tracks:
        if t.track_id == "aggressive":
            continue
        ind = t.indication_data or {}
        pro_ids.update(ind.get("red_flags_triggering_alternative") or [])
    # Also pick up red flags from algorithm decision tree pointing to aggressive
    algo = (kb_resolved or {}).get("algorithm") or {}
    aggr_ind_ids = {
        t.indication_id for t in plan.tracks if t.track_id == "aggressive"
    }
    for step in algo.get("decision_tree") or []:
        if_true = (step.get("if_true") or {}).get("result")
        if if_true in aggr_ind_ids:
            ev = step.get("evaluate") or {}
            for clause in (ev.get("any_of") or []) + (ev.get("all_of") or []):
                if isinstance(clause, dict) and clause.get("red_flag"):
                    pro_ids.add(clause["red_flag"])

    # CONTRA: hard contraindications on aggressive track
    contra_items: list[dict] = []
    for t in plan.tracks:
        if t.track_id != "aggressive":
            continue
        for c in t.contraindications_data or []:
            contra_items.append(c)

    if not pro_ids and not contra_items:
        return ""

    def _rf_li(rid: str) -> str:
        rf = rf_lookup.get(rid) or {}
        # Prefer the bilingual EN field if target_lang=en — saves a translate
        # call when curator already provided an English definition. Fall back
        # to translating the UA field if only UA is present.
        if target_lang == "en" and rf.get("definition"):
            defn = rf["definition"]
            return f'<li>{_h(defn)}<span class="rf-id">{_h(rid)}</span></li>'
        defn = rf.get("definition_ua") or rf.get("definition") or "—"
        return f'<li>{_h_t(defn, target_lang)}<span class="rf-id">{_h(rid)}</span></li>'

    def _ci_li(c: dict) -> str:
        cid = c.get("id", "?")
        if target_lang == "en" and c.get("description"):
            descr = c["description"]
            return f'<li>{_h(descr)}<span class="rf-id">{_h(cid)}</span></li>'
        descr = c.get("description_ua") or c.get("description") or "—"
        return f'<li>{_h_t(descr, target_lang)}<span class="rf-id">{_h(cid)}</span></li>'

    pro_html = (
        '<div class="pc-col pc-col--pro">'
        f'<h3>{_h(_t("pro_aggressive", target_lang))}</h3>'
        f'<div class="section-sub">{_h(_t("pro_aggressive_sub", target_lang))}</div>'
        f'<ul>{"".join(_rf_li(r) for r in sorted(pro_ids)) or "<li>—</li>"}</ul>'
        '</div>'
    )
    contra_html = (
        '<div class="pc-col pc-col--contra">'
        f'<h3>{_h(_t("contra_aggressive", target_lang))}</h3>'
        f'<div class="section-sub">{_h(_t("contra_aggressive_sub", target_lang))}</div>'
        f'<ul>{"".join(_ci_li(c) for c in contra_items) or "<li>—</li>"}</ul>'
        '</div>'
    )
    return (
        '<section>'
        f'<h2>{_h(_t("redflags_pro_contra", target_lang))}</h2>'
        f'<div class="pro-contra">{pro_html}{contra_html}</div>'
        '</section>'
    )


def _render_what_not_to_do(plan, target_lang: str = "uk") -> str:
    """Explicitly prohibitive 'do_not_do' list per track.
    Per REFERENCE_CASE_SPECIFICATION §1.3 critical.

    Bullet language selection (target_lang == "en"):
      1. If `Indication.do_not_do_en[i]` is populated, use it as-is.
      2. Otherwise fall back to `Indication.do_not_do[i]` routed through
         `_h_t` — which calls the translation client when configured, or
         leaves UA in place when not.
    On the UA side we always emit the canonical UA bullet."""
    is_en = (target_lang or "").lower().startswith("en")
    blocks = []
    for t in plan.tracks:
        ind = t.indication_data or {}
        items_ua = ind.get("do_not_do") or []
        items_en = ind.get("do_not_do_en") or []
        if not items_ua and not items_en:
            continue
        bullets = []
        if is_en:
            # Prefer EN bullet positionally; fall back to UA-via-_h_t
            # for any tail not yet translated. Also handles the case
            # where an Indication only has do_not_do_en populated.
            count = max(len(items_ua), len(items_en))
            for i in range(count):
                en = items_en[i] if i < len(items_en) else None
                ua = items_ua[i] if i < len(items_ua) else None
                if en:
                    bullets.append(_h(en))
                elif ua:
                    bullets.append(_h_t(ua, target_lang))
        else:
            for ua in items_ua:
                bullets.append(_h(ua))
        if not bullets:
            continue
        li = "".join(f"<li>{b}</li>" for b in bullets)
        blocks.append(
            '<div class="do-not">'
            f'<div class="track-name">{_h(t.label)} ({_h(t.indication_id)})</div>'
            f'<ul>{li}</ul>'
            '</div>'
        )
    if not blocks:
        return ""
    return (
        '<section>'
        f'<h2>{_h(_t("what_not", target_lang))}</h2>'
        f'<div class="section-sub">{_h(_t("what_not_sub", target_lang))}</div>'
        f'{"".join(blocks)}'
        '</section>'
    )


def _render_monitoring_phases(plan, target_lang: str = "uk") -> str:
    """Monitoring schedule phases as a per-track table.
    Per REFERENCE_CASE_SPECIFICATION §1.3 critical."""
    blocks = []
    seen_monitoring_ids: set[str] = set()
    th_phase = _h(_t("th_phase", target_lang))
    th_window = _h(_t("th_window", target_lang))
    th_tests = _h(_t("th_tests", target_lang))
    th_checks = _h(_t("th_checkpoints", target_lang))
    for t in plan.tracks:
        mon = t.monitoring_data
        if not mon:
            continue
        mid = mon.get("id") or ""
        if mid in seen_monitoring_ids:
            continue  # dedupe — both tracks may share the same monitoring schedule
        seen_monitoring_ids.add(mid)
        phases = mon.get("phases") or []
        if not phases:
            continue
        rows = []
        for ph in phases:
            tests = ", ".join(ph.get("tests") or []) or "—"
            checks = ph.get("checkpoints") or []
            checks_html = (
                "<ul style='padding-left:16px;margin:0;'>"
                + "".join(f"<li>{_h_t(c, target_lang)}</li>" for c in checks)
                + "</ul>"
            ) if checks else "—"
            rows.append(
                f'<tr><td><strong>{_h_t(ph.get("name", "?"), target_lang)}</strong></td>'
                f'<td>{_h_t(ph.get("window", "—"), target_lang)}</td>'
                f'<td style="font-family:var(--font-mono);font-size:11px;">{_h_t(tests, target_lang)}</td>'
                f'<td>{checks_html}</td></tr>'
            )
        blocks.append(
            f'<h3>{_h(t.label)} · {_h(mid)}</h3>'
            '<table class="tbl">'
            f'<thead><tr><th>{th_phase}</th><th>{th_window}</th>'
            f'<th>{th_tests}</th><th>{th_checks}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
        )
    if not blocks:
        return ""
    return (
        '<section>'
        f'<h2>{_h(_t("monitoring", target_lang))}</h2>'
        f'<div class="section-sub">{_h(_t("monitoring_sub", target_lang))}</div>'
        f'{"".join(blocks)}'
        '</section>'
    )


def _render_timeline(plan, target_lang: str = "uk") -> str:
    """Horizontal timeline strip composed from Regimen.cycle_length_days +
    total_cycles + MonitoringSchedule.phases. CSS-only, no SVG/JS.
    Per REFERENCE_CASE_SPECIFICATION §1.3 should-have."""
    if not plan.tracks:
        return ""

    blocks = []
    seen: set[tuple] = set()
    for t in plan.tracks:
        reg = t.regimen_data or {}
        mon = t.monitoring_data or {}
        key = (reg.get("id"), mon.get("id"))
        if key in seen or key == (None, None):
            continue
        seen.add(key)

        phases_html: list[str] = []

        # Baseline phase from monitoring (always first if present)
        mon_phases = mon.get("phases") or []
        baseline = next((p for p in mon_phases if p.get("name") == "baseline"), None)
        if baseline:
            phases_html.append(
                '<div class="tl-phase tl-phase--baseline">'
                f'<div class="name">{_h(_t("tl_baseline", target_lang))}</div>'
                f'<div class="window">{_h_t(baseline.get("window", "—"), target_lang)}</div>'
                '</div>'
            )

        # Induction phase from regimen cycle metadata
        cycle_len = reg.get("cycle_length_days")
        total_cycles = reg.get("total_cycles") or "—"
        if cycle_len:
            cycles_str = str(total_cycles).strip()
            window = (
                f"{cycle_len}-day cycles × {cycles_str}"
                if cycles_str and cycles_str != "—"
                else f"{cycle_len}-day cycles"
            )
            phases_html.append(
                '<div class="tl-phase tl-phase--induction">'
                f'<div class="name">{_h(_t("tl_induction", target_lang))} · {_h(reg.get("name", "—"))}</div>'
                f'<div class="window">{_h(window)}</div>'
                '</div>'
            )

        # Response assessment phase from monitoring
        ra = next((p for p in mon_phases if "response" in (p.get("name", "").lower())), None)
        if ra:
            phases_html.append(
                '<div class="tl-phase tl-phase--response">'
                f'<div class="name">{_h(_t("tl_response", target_lang))}</div>'
                f'<div class="window">{_h_t(ra.get("window", "—"), target_lang)}</div>'
                '</div>'
            )

        # Maintenance phase if present
        maint = next((p for p in mon_phases if "maint" in (p.get("name", "").lower())), None)
        if maint:
            phases_html.append(
                '<div class="tl-phase tl-phase--maintenance">'
                f'<div class="name">{_h(_t("tl_maintenance", target_lang))}</div>'
                f'<div class="window">{_h_t(maint.get("window", "—"), target_lang)}</div>'
                '</div>'
            )

        # Follow-up phase if present
        fu = next(
            (p for p in mon_phases if "follow" in (p.get("name", "").lower())),
            None,
        )
        if fu:
            phases_html.append(
                '<div class="tl-phase tl-phase--followup">'
                f'<div class="name">{_h(_t("tl_followup", target_lang))}</div>'
                f'<div class="window">{_h_t(fu.get("window", "—"), target_lang)}</div>'
                '</div>'
            )

        if phases_html:
            blocks.append(
                f'<h3>{_h(t.label)}</h3>'
                f'<div class="timeline">{"".join(phases_html)}</div>'
            )

    if not blocks:
        return ""
    return (
        '<section>'
        f'<h2>{_h(_t("timeline", target_lang))}</h2>'
        f'<div class="section-sub">{_h(_t("timeline_sub", target_lang))}</div>'
        f'{"".join(blocks)}'
        '</section>'
    )


# ── Experimental-options track (Phase C) ─────────────────────────────────


_OUTLOOK_FLAG_KEYS = {
    "phase1_only": "exp_outlook_phase1",
    "small_enrollment": "exp_outlook_small_n",
    "surrogate_endpoint_only": "exp_outlook_surrogate",
    "single_country": "exp_outlook_single_country",
}


def _render_trial_outlook(outlook, notes_index: dict[str, str], target_lang: str) -> str:
    """Render a `TrialOutlook` as a sequence of badges. Returns "—" when
    the outlook is None (older cached trials) or has no surfaceable
    signals. Each badge gets a `title` tooltip from `outlook.notes`
    where one is available — index by partial substring match because
    `notes` is a parallel free-text list, not a per-flag dict."""
    if outlook is None:
        return "—"

    parts: list[str] = []

    if outlook.biomarker_stratification == "enriched":
        label = _t("exp_outlook_enriched", target_lang)
        title = notes_index.get("enriched", label)
        parts.append(
            f'<span class="badge badge--strat-enriched" title="{_h(title)}">'
            f'{_h(label)}</span>'
        )
    elif outlook.biomarker_stratification == "unclear":
        label = _t("exp_outlook_unclear", target_lang)
        title = notes_index.get("unclear", label)
        parts.append(
            f'<span class="badge badge--strat-unclear" title="{_h(title)}">'
            f'{_h(label)}</span>'
        )
    # "open_label" intentionally renders nothing — it's the absence of signal.

    for flag in outlook.design_flags:
        key = _OUTLOOK_FLAG_KEYS.get(flag)
        if key is None:
            continue
        label = _t(key, target_lang)
        title = notes_index.get(flag, label)
        parts.append(
            f'<span class="badge badge--design-flag" title="{_h(title)}">'
            f'{_h(label)}</span>'
        )

    return " ".join(parts) if parts else "—"


def _outlook_notes_index(outlook) -> dict[str, str]:
    """Build a {flag_or_strat -> note} lookup from `outlook.notes`.

    `notes` is a parallel list authored by `engine.trial_outlook.score_trial`
    in a fixed order: stratification note (if any) first, then one note
    per design flag. We match heuristically on substring tokens so the
    tooltip surfaces the original explanation."""
    if outlook is None:
        return {}
    idx: dict[str, str] = {}
    for note in outlook.notes:
        low = note.lower()
        if "inclusion criteria reference" in low:
            idx["enriched"] = note
        elif "partial biomarker" in low or "exclusion" in low:
            idx["unclear"] = note
        elif "phase 1" in low:
            idx["phase1_only"] = note
        elif "target enrollment" in low:
            idx["small_enrollment"] = note
        elif "surrogate" in low:
            idx["surrogate_endpoint_only"] = note
        elif "single-country" in low:
            idx["single_country"] = note
    return idx


def _render_cited_trials_status(
    body_html: str,
    target_lang: str = "uk",
    cache_root=None,
) -> str:
    """Decorate cited pivotal trials with live status from the per-NCT
    cache. Closes Gap 3 from `docs/reviews/ctgov-wiring-audit-2026-05-18.md`.

    Strategy: extract every NCT that already appears in the rendered
    Plan body (so we decorate exactly what was cited, no more), look up
    each in the per-NCT cache, render a status badge block. Skips the
    section entirely when no cached badge is available — never invents
    placeholder content.

    Render-time only (CHARTER §8.3): does not influence routing.
    """
    from .citation_enrichment import (
        DEFAULT_CACHE_ROOT,
        extract_nct_ids,
        trial_status_badge,
    )

    if not body_html:
        return ""

    root = cache_root if cache_root is not None else DEFAULT_CACHE_ROOT
    cited = extract_nct_ids(body_html)
    if not cited:
        return ""

    rows = []
    for nct in cited:
        badge = trial_status_badge(nct, cache_root=root)
        if badge is None:
            continue
        status_class = "trial-status--recruiting" if badge.is_recruiting else "trial-status--closed"
        status_label = badge.status.replace("_", " ").title()
        synced = badge.last_synced or ""
        if synced and len(synced) >= 10:
            synced_short = synced[:10]
        else:
            synced_short = synced
        rows.append(
            '<li class="cited-trial">'
            f'<a href="https://clinicaltrials.gov/study/{_h(nct)}" '
            f'target="_blank" rel="noopener" class="cited-trial-nct">{_h(nct)}</a>'
            f' <span class="badge {status_class}">{_h(status_label)}</span>'
            + (f' <span class="cited-trial-synced">({_h(synced_short)})</span>' if synced_short else "")
            + "</li>"
        )

    if not rows:
        # NCTs were cited but none have cached status — suppress the
        # section rather than emit an empty list. The cache may be
        # unpopulated (fresh checkout) or the prewarm hasn't run.
        return ""

    heading = (
        "Цитовані випробування — поточний статус"
        if target_lang == "uk"
        else "Cited trials — current status"
    )
    sub = (
        "Поточний статус набору з ClinicalTrials.gov, оновлено через "
        "кеш per-NCT (`scripts/sync_ctgov_studies.py`)."
        if target_lang == "uk"
        else "Recruiting status from ClinicalTrials.gov, refreshed via "
             "the per-NCT cache (`scripts/sync_ctgov_studies.py`)."
    )
    return (
        '<section class="cited-trials-status">'
        f'<h2>{_h(heading)}</h2>'
        f'<p class="section-sub">{_h(sub)}</p>'
        f'<ul class="cited-trials-list">{"".join(rows)}</ul>'
        '</section>'
    )


def _render_experimental_options(option, target_lang: str = "uk") -> str:
    """Render the clinical-trial track surfaced after engine selection.

    `option` is an `ExperimentalOption` (or None when no `search_fn` was
    wired). Output is render-time-only metadata — engine never reads
    these fields back (CHARTER §8.3 + plan §3.2 invariant).

    When option is None: emit a small placeholder so clinicians know the
    track exists but ctgov sync hasn't run. When option is present but
    has zero open trials, emit an empty-state message instead of a table.

    All static UA labels route through `_t(...)` so the EN render emits
    English at the source rather than relying on `_localize_html`
    post-processing."""

    heading = _t("exp_heading", target_lang)

    if option is None:
        return (
            '<section class="experimental-track experimental-track--unset">'
            f'<h2>{_h(heading)}</h2>'
            f'<div class="section-sub">{_h(_t("exp_unset_sub", target_lang))}</div>'
            f'<p class="empty-state">{_h(_t("exp_unset_msg", target_lang))}</p>'
            '</section>'
        )

    trials = option.trials or []
    last_synced = option.last_synced or ""
    last_synced_prefix = _t("exp_last_synced_prefix", target_lang)

    if not trials:
        # `option.notes` is curator-authored UA free-text; only fall back
        # to the localized default when it is empty.
        msg = option.notes or _t("exp_empty_default", target_lang)
        return (
            '<section class="experimental-track experimental-track--empty">'
            f'<h2>{_h(heading)}</h2>'
            f'<div class="section-sub">{_h(last_synced_prefix)} {_h(last_synced)} · ctgov.</div>'
            f'<p class="empty-state">{_h(msg)}</p>'
            '</section>'
        )

    rows = []
    for t in trials:
        ua_badge = ""
        if t.sites_ua:
            ua_badge = '<span class="badge badge--ua" title="Site present in Ukraine">UA</span>'
        elig = t.inclusion_summary or ""
        elig_short = (elig[:140] + "…") if len(elig) > 140 else elig
        outlook_cell = _render_trial_outlook(
            t.outlook, _outlook_notes_index(t.outlook), target_lang
        )
        rows.append(
            "<tr>"
            f'<td class="trial-nct"><a href="https://clinicaltrials.gov/study/{_h(t.nct_id)}" '
            f'target="_blank" rel="noopener">{_h(t.nct_id)}</a></td>'
            f'<td class="trial-title">{_h(t.title)}</td>'
            f'<td class="trial-phase">{_h(t.phase or "—")}</td>'
            f'<td class="trial-status">{_h(t.status)}</td>'
            f'<td class="trial-sponsor">{_h(t.sponsor or "—")}</td>'
            f'<td class="trial-ua">{ua_badge or "—"}</td>'
            f'<td class="trial-outlook">{outlook_cell}</td>'
            f'<td class="trial-elig">{_h(elig_short)}</td>'
            "</tr>"
        )

    return (
        '<section class="experimental-track">'
        f'<h2>{_h(heading)}</h2>'
        '<div class="section-sub">'
        f'{_h(_t("exp_table_sub", target_lang))} '
        f'{_h(last_synced_prefix)} {_h(last_synced)}.'
        '</div>'
        '<table class="trials-table">'
        '<thead><tr>'
        f'<th>{_h(_t("exp_th_nct", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_title", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_phase", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_status", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_sponsor", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_ua", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_outlook", target_lang))}</th>'
        f'<th>{_h(_t("exp_th_eligibility", target_lang))}</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        f'<p class="trial-disclaimer">{_h(_t("exp_disclaimer", target_lang))}</p>'
        '</section>'
    )


# ── Access Matrix (Phase D) ──────────────────────────────────────────────


def _fmt_uah_range(lo, hi, per_unit) -> str:
    """Format `(min, max)` UAH cost range as a short readable string.
    Returns "—" when both bounds are absent (no cost data on any
    component). The `per_unit` suffix is appended in plain text."""
    if lo is None and hi is None:
        return "—"
    suffix = f"/{_h(per_unit)}" if per_unit else ""
    if lo is not None and hi is not None and lo != hi:
        return f"₴{int(lo):,}–{int(hi):,}{suffix}".replace(",", " ")
    val = lo if lo is not None else hi
    return f"₴{int(val):,}{suffix}".replace(",", " ")


def _avail_badge(value, *, true_label: str, false_label: str,
                 target_lang: str = "uk") -> str:
    """Tri-state status cell — True/False/None each render distinctly so
    the matrix never silently coalesces 'unknown' into 'no'."""
    if value is True:
        return f'<span class="badge badge--ok">✓ {_h(true_label)}</span>'
    if value is False:
        return f'<span class="badge badge--no">✗ {_h(false_label)}</span>'
    return f'<span class="badge badge--unknown">{_h(_t("matrix_avail_unknown", target_lang))}</span>'


def _render_access_matrix(matrix, target_lang: str = "uk") -> str:
    """Render the per-Plan Access Matrix block (ua-ingestion plan §4).

    The matrix surfaces UA-availability metadata — registered, reimbursed,
    cost orientation, primary access pathway — for every track presented
    in the Plan, including any clinical-trial rows from the experimental
    track. Render-only; the engine never reads any field on `matrix`
    back as a selection signal (CHARTER §8.3, plan §0 invariant).

    Default-collapsed via <details>; auto-expanded when at least one row
    indicates a non-reimbursed component (so clinicians see the funding
    gap without an extra click). `matrix is None` (older Plans, or
    aggregator failure) renders nothing — the section is opt-in.
    """
    if matrix is None or not matrix.rows:
        return ""

    # Auto-expand when any track has non-reimbursed component or stale cost
    auto_open = any(
        (r.reimbursed_nszu is False) or r.cost_is_stale or (r.registered_in_ua is False)
        for r in matrix.rows
    )
    open_attr = " open" if auto_open else ""

    rows_html: list[str] = []
    for r in matrix.rows:
        track_class = "track-trial" if r.track_id.startswith("trial:") else f"track-{_h(r.track_id)}"
        regimen_label = _h(r.regimen_name or r.regimen_id or "—")
        if r.regimen_name and r.regimen_id:
            regimen_label = f"<strong>{_h(r.regimen_name)}</strong> <span class='regimen-id'>({_h(r.regimen_id)})</span>"

        cost_cell_parts: list[str] = []
        # Reimbursed bucket first (NSZU/НСЗУ tariff), self-pay second (retail)
        nszu_cost_label = _t("matrix_cost_label_nszu", target_lang)
        selfpay_cost_label = _t("matrix_cost_label_selfpay", target_lang)
        reimb_cell = _fmt_uah_range(r.cost_reimbursed_min, r.cost_reimbursed_max, r.cost_per_unit)
        if reimb_cell != "—":
            cost_cell_parts.append(f"<div class='cost-row'><span class='cost-label'>{_h(nszu_cost_label)}</span> {reimb_cell}</div>")
        sp_cell = _fmt_uah_range(r.cost_self_pay_min, r.cost_self_pay_max, r.cost_per_unit)
        if sp_cell != "—":
            cost_cell_parts.append(f"<div class='cost-row'><span class='cost-label'>{_h(selfpay_cost_label)}</span> {sp_cell}</div>")
        if not cost_cell_parts:
            if r.track_id.startswith("trial:"):
                cost_cell_parts.append(f"<span class='cost-trial'>{_h(_t('matrix_cost_trial', target_lang))}</span>")
            else:
                cost_cell_parts.append(f"<span class='cost-unknown'>{_h(_t('matrix_cost_unknown', target_lang))}</span>")

        # Pathway cell
        if r.primary_pathway_id:
            path_cell = f'<a href="#path-{_h(r.primary_pathway_id)}">{_h(r.primary_pathway_id)}</a>'
            if r.pathway_alternative_ids:
                path_cell += f' <span class="alt-paths">(+{len(r.pathway_alternative_ids)})</span>'
        elif r.track_id.startswith("trial:"):
            path_cell = _h(_t("matrix_path_trial_sponsor", target_lang))
        elif r.reimbursed_nszu:
            path_cell = _h(_t("matrix_path_nszu_formulary", target_lang))
        else:
            path_cell = f'<em>{_h(_t("matrix_path_not_recorded", target_lang))}</em>'

        # Notes cell — collapse to one line, full list on hover
        notes_cell = ""
        if r.notes:
            head = r.notes[0]
            tail = ""
            if len(r.notes) > 1:
                tail_attr = _h(" · ".join(r.notes[1:]))
                tail = f' <span class="more-notes" title="{tail_attr}">+{len(r.notes) - 1}</span>'
            cls = "notes-stale" if r.cost_is_stale else "notes"
            notes_cell = f'<div class="{cls}">{_h(head)}{tail}</div>'

        rows_html.append(
            f'<tr class="{track_class}">'
            f'<td class="track-cell"><strong>{_h(r.track_label)}</strong>'
            f'<div class="regimen-name">{regimen_label}</div>{notes_cell}</td>'
            f'<td>{_avail_badge(r.registered_in_ua, true_label=_t("matrix_avail_registered", target_lang), false_label=_t("matrix_avail_not_registered", target_lang), target_lang=target_lang)}</td>'
            f'<td>{_avail_badge(r.reimbursed_nszu, true_label=_t("matrix_avail_covered", target_lang), false_label=_t("matrix_avail_oop", target_lang), target_lang=target_lang)}</td>'
            f'<td class="cost-cell">{"".join(cost_cell_parts)}</td>'
            f'<td class="pathway-cell">{path_cell}</td>'
            f'</tr>'
        )

    plan_notes = ""
    if matrix.notes:
        items = "".join(f"<li>{_h(n)}</li>" for n in matrix.notes)
        plan_notes = f'<ul class="matrix-plan-notes">{items}</ul>'

    return (
        f'<section class="access-matrix">'
        f'<details{open_attr}>'
        f'<summary><h2>{_h(_t("matrix_heading", target_lang))}</h2>'
        f'<span class="section-sub">{_h(_t("matrix_sub", target_lang))}</span></summary>'
        f'{plan_notes}'
        f'<table class="access-matrix-table">'
        f'<thead><tr>'
        f'<th>{_h(_t("matrix_th_option", target_lang))}</th>'
        f'<th>{_h(_t("matrix_th_registration", target_lang))}</th>'
        f'<th>{_h(_t("matrix_th_nszu", target_lang))}</th>'
        f'<th>{_h(_t("matrix_th_cost", target_lang))}</th>'
        f'<th>{_h(_t("matrix_th_pathway", target_lang))}</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table>'
        f'<p class="matrix-disclaimer">'
        f'{_h(_t("matrix_disclaimer", target_lang))} '
        f'{_h(_t("matrix_status_updated", target_lang))} {_h((matrix.generated_at or "")[:10])}.'
        f'</p>'
        f'</details>'
        f'</section>'
    )


# ── NSZU availability badges (per-drug) ─────────────────────────────────


_NSZU_DRUGS_LABEL = {
    "uk": "Препарати + НСЗУ",
    "en": "Drugs + NSZU",
}


# ── Phase-aware render labels (PR2 of regimen-phases-refactor) ──────────
#
# Maps the curator-facing `phase.name` vocabulary
# (KNOWLEDGE_SCHEMA_SPECIFICATION §6.4) to a UA/EN heading prefix. The
# block heading combines the prefix with the phase's `purpose_ua` so a
# clinician sees both the role ("Перед основною терапією") and the
# specific intent ("виснаження лімфоцитів перед CAR-T"). Auto-wrapped
# legacy phases use name="main", which renders without a heading-prefix
# noise — the visible behavior stays close to pre-PR2.
_PHASE_HEADING_PREFIX_UK = {
    "lymphodepletion": "Перед основною терапією: лімфодеплеція",
    "bridging": "Бриджинг до основної терапії",
    "induction": "Індукція",
    "consolidation": "Консолідація",
    "maintenance": "Підтримуюча терапія",
    "main": None,  # auto-wrapped legacy — no heading prefix
    "premedication": "Премедикація",
    "conditioning": "Кондиціонування",
    "salvage_induction": "Salvage-індукція",
    "alternating_block_a": "Чергуючий блок A",
    "alternating_block_b": "Чергуючий блок B",
    "il2_support": "IL-2 підтримка",
}
_PHASE_HEADING_PREFIX_EN = {
    "lymphodepletion": "Before main therapy: lymphodepletion",
    "bridging": "Bridging to main therapy",
    "induction": "Induction",
    "consolidation": "Consolidation",
    "maintenance": "Maintenance",
    "main": None,
    "premedication": "Premedication",
    "conditioning": "Conditioning",
    "salvage_induction": "Salvage induction",
    "alternating_block_a": "Alternating block A",
    "alternating_block_b": "Alternating block B",
    "il2_support": "IL-2 support",
}
_BRIDGING_OPTIONS_LABEL = {
    "uk": "Якщо очікування на основну терапію >2 тиж — допустимий бриджинг",
    "en": "If wait for main therapy >2 weeks — acceptable bridging regimens",
}


def _render_nszu_badge(drug_entity, patient_disease_id, disease_names, target_lang="uk") -> str:
    """One drug → one `<span class="nszu-badge nszu-{status}">…</span>`.

    `drug_entity` is the dict-shape Drug record from the loader. When
    None (e.g. a drug_id referenced by a regimen but not present in the
    KB), renders an explicit `not-registered` badge so the row never
    silently drops a component."""
    badge = lookup_nszu_status(
        drug_entity or {},
        patient_disease_id,
        disease_names=disease_names,
    )
    cls = f"nszu-badge nszu-{badge.status}"
    label = nszu_label(badge.status, target_lang)
    tip = badge.notes_excerpt or badge.indication_match or ""
    title_attr = f' title="{_h(tip)}"' if tip else ""
    return f'<span class="{cls}"{title_attr}>{_h(label)}</span>'


def _render_drug_row(
    comp: dict,
    drugs_lookup: dict,
    patient_disease_id: str,
    disease_names: dict,
    target_lang: str,
) -> str:
    """Render a single component dict as one `<li class="drug-row">` with
    drug name + dose/schedule/route + NSZU availability badge.

    Extracted from the legacy `_render_track_drug_list` so multi-phase
    regimens can reuse the same per-drug formatting inside each phase
    block. Returns "" when the component has no `drug_id` (defensive)."""
    drug_id = comp.get("drug_id")
    if not drug_id:
        return ""
    drug = drugs_lookup.get(drug_id)
    # Drug display name — `_pick_name` enforces the lang priority chain
    # uniformly across every name-emission site (tests/drugs/workups).
    name = _pick_name((drug or {}).get("names"), target_lang, default=drug_id)
    dose_bits: list[str] = []
    for k in ("dose", "schedule", "route"):
        v = comp.get(k)
        if v:
            dose_bits.append(str(v))
    dose_str = " · ".join(dose_bits)
    nszu = _render_nszu_badge(drug, patient_disease_id, disease_names, target_lang)
    meta = (
        f'<span class="drug-name">{_h(name)}</span>'
        f' <span class="drug-id">({_h(drug_id)})</span>'
    )
    if dose_str:
        meta += f' <span class="drug-dose">{_h(dose_str)}</span>'
    return f'<li class="drug-row">{meta} {nszu}</li>'


def _render_treatment_phases(
    track,
    drugs_lookup: dict,
    patient_disease_id: str,
    disease_names: dict,
    target_lang: str = "uk",
) -> str:
    """Render the regimen as one or more phase blocks (PR2 of
    regimen-phases-refactor; replaces the flat single-block drug list).

    Each phase becomes a `<section class="phase-block">` with:
      - heading combining the phase-name prefix
        (`_PHASE_HEADING_PREFIX_UK[phase.name]`) and the curator-authored
        `purpose_ua`. Auto-wrapped legacy phases (`name="main"`) skip
        the prefix to keep the visual close to pre-PR2.
      - the phase's drug rows formatted by `_render_drug_row`.

    Falls back to the regimen's flat `components` when the loaded
    `regimen_data` dict has no `phases` key — covers legacy YAMLs that
    have not been migrated to multi-phase shape (the Pydantic auto-wrap
    only runs at `model_validate`, not at render time when YAML is loaded
    into a raw dict). See `_iter_regimen_components` docstring.

    Returns empty string when no drug components are renderable — keeps
    the `<dl>` tidy and matches the legacy contract.

    `bridging_options` (CAR-T / TIL manufacturing-window slot) renders as
    a separate `<div class="bridging-options">` block listed AFTER the
    phase blocks, naming the acceptable bridging regimen IDs.
    """
    reg = track.regimen_data or {}
    if not reg:
        return ""

    label = _NSZU_DRUGS_LABEL.get(
        "en" if (target_lang or "uk").lower().startswith("en") else "uk",
        _NSZU_DRUGS_LABEL["uk"],
    )

    # Build the phase list — explicit phases when populated, else a synthetic
    # single phase wrapping the flat components list (mirrors the schema's
    # auto-wrap; needed at render time because regimen_data is the raw dict,
    # not a validated Regimen).
    phases: list[dict] = []
    raw_phases = reg.get("phases") or []
    if raw_phases:
        for ph in raw_phases:
            if isinstance(ph, dict):
                phases.append(ph)
    elif reg.get("components"):
        phases.append({
            "name": "main",
            "purpose_ua": "основна терапія",
            "components": reg.get("components") or [],
        })

    prefix_map = (
        _PHASE_HEADING_PREFIX_EN
        if (target_lang or "uk").lower().startswith("en")
        else _PHASE_HEADING_PREFIX_UK
    )

    blocks: list[str] = []
    for ph in phases:
        ph_name = ph.get("name") or ""
        ph_components = ph.get("components") or []
        ph_rows = [
            _render_drug_row(
                c, drugs_lookup, patient_disease_id, disease_names, target_lang
            )
            for c in ph_components
            if isinstance(c, dict)
        ]
        ph_rows = [r for r in ph_rows if r]
        if not ph_rows:
            continue

        # Heading: prefix (when defined for this phase name) + purpose_ua.
        # Legacy auto-wrap (name="main") gets prefix=None → no heading;
        # the block wrapper alone is a discreet structural marker so it
        # does not look broken next to a real two-phase render.
        prefix = prefix_map.get(ph_name)
        if (target_lang or "uk").lower().startswith("en"):
            purpose = ph.get("purpose_en") or ph.get("purpose_ua") or ""
        else:
            purpose = ph.get("purpose_ua") or ph.get("purpose_en") or ""

        heading_html = ""
        if prefix:
            heading = prefix
            if purpose and purpose.strip():
                heading = f"{prefix} — {purpose.strip()}"
            heading_html = f'<h4 class="phase-heading">{_h(heading)}</h4>'

        # data-phase carries the canonical phase name for tests + tooling
        # (legacy auto-wrap → "main"; explicit phases → curator-authored).
        blocks.append(
            f'<section class="phase-block" data-phase="{_h(ph_name)}">'
            f'{heading_html}'
            f'<ul class="drug-list">{"".join(ph_rows)}</ul>'
            f'</section>'
        )

    bridging_html = ""
    bridging_ids = reg.get("bridging_options") or []
    if bridging_ids:
        items = "".join(
            f'<li class="bridging-option">{_h(bid)}</li>'
            for bid in bridging_ids
            if isinstance(bid, str) and bid
        )
        if items:
            br_label = _BRIDGING_OPTIONS_LABEL.get(
                "en" if (target_lang or "uk").lower().startswith("en") else "uk",
                _BRIDGING_OPTIONS_LABEL["uk"],
            )
            bridging_html = (
                f'<div class="bridging-options">'
                f'<div class="bridging-options-label">{_h(br_label)}</div>'
                f'<ul class="bridging-options-list">{items}</ul>'
                f'</div>'
            )

    if not blocks and not bridging_html:
        return ""

    inner = "".join(blocks) + bridging_html
    return f'<dt>{_h(label)}</dt><dd>{inner}</dd>'


# Back-compat alias — `_render_track_drug_list` was the pre-PR2 entry point.
# Kept as a thin wrapper so any out-of-tree code that imported the legacy
# name keeps working. The internal call site below now calls the new
# function directly.
_render_track_drug_list = _render_treatment_phases


# ── Variant actionability (ESCAT) ───────────────────────────────────────
# Phase 4 (CIViC pivot, 2026-04-27): ESCAT tier is the primary actionability
# label (vendor-neutral, source-of-truth). evidence_sources renders the
# per-source detail BELOW the ESCAT tag — SRC-CIVIC entries link to
# civicdb.org, "Does Not Support" / "Resistance" entries get a ⚠ flag.
# Per OncoKB ToS (see review-2026-04-27 §3.4), SRC-ONCOKB entries are
# never rendered; if evidence_sources is empty after that skip, the
# render falls back to primary_sources (sans OncoKB) as citation cards.


def _escat_class(tier: Optional[str]) -> str:
    """ESCAT tier → CSS class. Falls back to escat-X for unknown values."""
    if not tier:
        return "escat-X"
    valid = {"IA", "IB", "IIA", "IIB", "IIIA", "IIIB", "IV", "X"}
    t = str(tier).strip().upper()
    return f"escat-{t}" if t in valid else "escat-X"


# Sources that must NEVER appear in rendered HTML, per their license
# Terms of Use. OncoKB ToS forbids "use for patient services" and
# "generation of reports in a hospital or other patient care setting,"
# which is exactly what OpenOnco produces; therefore SRC-ONCOKB-attested
# evidence is skipped from both `evidence_sources` and `primary_sources`
# at render time, regardless of any legacy data still present in YAMLs.
# See docs/reviews/oncokb-public-civic-coverage-2026-04-27.md §3.4.
_RENDER_SKIP_SOURCES = frozenset({"SRC-ONCOKB"})


def _is_skipped_source(source_id: str) -> bool:
    """Per ToS, do not render anything attributed to OncoKB to user-facing
    HTML. Match is case-insensitive and on prefix so SRC-ONCOKB-* legacy
    variants are also caught."""
    if not source_id:
        return False
    s = str(source_id).strip().upper()
    if s in _RENDER_SKIP_SOURCES:
        return True
    return s.startswith("SRC-ONCOKB")


def _civic_evidence_url(evidence_ids: list) -> Optional[str]:
    """Return a civicdb.org link for the first numeric evidence id, or
    fall back to the gene-page URL pattern if no numeric id is present.

    CIViC evidence-item URL pattern: civicdb.org/links/evidence_items/<id>.
    Some imports store ids as `EID12345`; we strip a leading `EID`.
    """
    for raw in (evidence_ids or []):
        s = str(raw).strip()
        if s.upper().startswith("EID"):
            s = s[3:]
        if s.isdigit():
            return f"https://civicdb.org/links/evidence_items/{s}"
    return None


def _is_resistance_entry(direction, significance) -> bool:
    """CIViC `direction == 'Does Not Support'` flips a Sensitivity item
    into anti-evidence; `significance == 'Resistance'` is the explicit
    resistance signal. Either condition gets a ⚠ flag at render time."""
    d = (direction or "").strip().lower() if direction else ""
    s = (significance or "").strip().lower() if significance else ""
    if d in {"does not support", "does_not_support"}:
        return True
    if "resistance" in s:
        return True
    return False


_EVIDENCE_LANE_LABELS = {
    "standard_care": "Standard care",
    "molecular_evidence_option": "Molecular evidence option",
    "resistance_or_avoidance_signal": "Resistance or avoidance signal",
    "trial_research_option": "Trial or research option",
    "insufficient_evidence": "Insufficient evidence",
}


def _source_ref_get(es, key: str, default=None):
    if isinstance(es, dict):
        return es.get(key, default)
    return getattr(es, key, default)


def _evidence_lane_for_source_ref(es, is_resistance: bool) -> str:
    lane = _source_ref_get(es, "evidence_lane")
    if lane in _EVIDENCE_LANE_LABELS:
        return lane
    if is_resistance:
        return "resistance_or_avoidance_signal"
    source = str(_source_ref_get(es, "source", "") or "").upper()
    level = str(_source_ref_get(es, "level", "") or "").upper()
    if source == "SRC-CIVIC":
        if level in {"A", "B"}:
            return "molecular_evidence_option"
        if level in {"C", "D", "E"}:
            return "trial_research_option"
        return "insufficient_evidence"
    return "standard_care"


def _format_evidence_sources(
    evidence_sources: list, primary_sources: Optional[list] = None
) -> str:
    """Render evidence_sources entries as a short list per BMA cell.

    Render rules (Phase-4 CIViC pivot, see review-2026-04-27):
      1. Iterate `evidence_sources`. For each entry:
         - SKIP source=SRC-ONCOKB entirely (OncoKB ToS forbids surfacing
           OncoKB labels in patient-care reports).
         - Otherwise render as `<source>: Level <level>`. SRC-CIVIC
           entries get a clickable civicdb.org link via the first
           numeric evidence_id (or gene-page fallback).
         - "Does Not Support" / "Resistance" entries get a ⚠ marker +
           "Resistance evidence" label.
         - Deduplicate (source, level, resistance-flag) so multiple
           CIViC evidence items at the same level collapse into one row.
      2. Fallback (Phase 3-O finding): if `evidence_sources` is empty
         after the SRC-ONCOKB skip, promote `primary_sources` (filtered
         for non-OncoKB) as citation cards without a level, plus a note
         pointing to the Phase-2-of-CIViC-pivot re-cite roadmap.
    """
    lane_items: dict[str, list[str]] = {lane: [] for lane in _EVIDENCE_LANE_LABELS}
    seen: set = set()
    for es in (evidence_sources or []):
        source = _source_ref_get(es, "source", "") or ""
        level = _source_ref_get(es, "level", "") or ""
        direction = _source_ref_get(es, "direction")
        significance = _source_ref_get(es, "significance")
        evidence_ids = _source_ref_get(es, "evidence_ids", None) or []
        if not source or _is_skipped_source(source):
            continue
        is_resistance = _is_resistance_entry(direction, significance)
        lane = _evidence_lane_for_source_ref(es, is_resistance)
        # Dedupe key — collapse same source+level+resistance-flag rows.
        key = (lane, str(source).upper(), str(level).upper(), is_resistance)
        if key in seen:
            continue
        seen.add(key)

        # Source label + optional clickable link (CIViC for SRC-CIVIC;
        # other SRC-* render plain since URL lookup needs kb_resolved
        # which we don't carry into this helper — see TODO below).
        source_label = _h(source)
        if str(source).upper() == "SRC-CIVIC":
            href = _civic_evidence_url(evidence_ids) or "https://civicdb.org/"
            source_label = (
                f'<a href="{_h(href)}" target="_blank" rel="noopener">'
                f'{_h(source)}</a>'
            )

        # Resistance flag
        if is_resistance:
            badge = (
                ' <span class="evidence-resistance" '
                'title="Resistance evidence">⚠ Resistance</span>'
            )
        else:
            badge = ""

        # Fine-grained metadata (direction/significance) — surfaced as a
        # muted suffix when present and non-resistance (resistance is
        # already conveyed by the badge).
        suffix_parts: list[str] = []
        if direction and not is_resistance:
            suffix_parts.append(_h(str(direction)))
        if significance and not is_resistance:
            suffix_parts.append(_h(str(significance)))
        suffix = (
            f' <span class="evidence-meta">({", ".join(suffix_parts)})</span>'
            if suffix_parts
            else ""
        )

        lane_items[lane].append(
            f'<li>{source_label}: Level {_h(level)}{badge}{suffix}</li>'
        )

    rendered_lanes: list[str] = []
    for lane, label in _EVIDENCE_LANE_LABELS.items():
        items = lane_items[lane]
        if not items:
            continue
        rendered_lanes.append(
            f'<div class="evidence-lane evidence-lane--{_h(lane)}">'
            f'<div class="evidence-lane-title">{_h(label)}</div>'
            f'<ul class="evidence-sources">{"".join(items)}</ul>'
            "</div>"
        )

    if rendered_lanes:
        return "".join(rendered_lanes)

    # Fallback: promote primary_sources (sans OncoKB) into citation cards
    # so the cell still surfaces something meaningful for the 18 J-drafts
    # that carry only SRC-ONCOKB in evidence_sources after the skip.
    fallback_items: list[str] = []
    fallback_seen: set = set()
    for sid in (primary_sources or []):
        if not sid or _is_skipped_source(sid):
            continue
        key = str(sid).upper()
        if key in fallback_seen:
            continue
        fallback_seen.add(key)
        fallback_items.append(f'<li class="evidence-fallback">{_h(sid)}</li>')

    if fallback_items:
        note = (
            '<div class="evidence-fallback-note">'
            'Evidence cited from clinical guidelines; per-source evidence '
            'levels not yet structured. See Phase-2-of-CIViC-pivot for '
            're-cite roadmap.'
            '</div>'
        )
        return (
            f'<ul class="evidence-sources evidence-sources--fallback">'
            f'{"".join(fallback_items)}</ul>{note}'
        )

    return '<span style="color:var(--gray-500)">—</span>'


def _render_variant_actionability(
    plan, target_lang: str = "uk", *, strict_citation_guard: bool = False
) -> str:
    """Render the ESCAT tier-badges + per-source evidence section.

    Inserted between the diagnostic profile (patient strip + etiological
    driver) and the treatment-plan tracks. When the patient has no
    matching BMA cells, render a single placeholder row — the section
    is always present so HCPs see that the lookup ran.

    The section is split into two visual sub-sections:
    - ✅ Covered biomarkers: patient biomarkers that matched a BMA cell,
      shown with full ESCAT detail so the HCP can verify what the engine
      acted on.
    - ⚠️ Not included in plan: biomarkers present in the patient profile
      that were either negative (excluded by design) or positive but
      absent from the KB (unmatched). This makes the coverage gap
      explicit for verification.

    The split is computed purely from `plan.patient_snapshot["biomarkers"]`
    and `plan.variant_actionability` — no schema changes required.
    Falls back to a single table (no sub-headers) when the patient
    snapshot has no biomarkers field (older plan shapes / tests).

    PR5 citation-presence guard: each BMA hit row gets a status check on
    its `primary_sources` + `evidence_sources`. WARN mode prepends a
    `❓ без цитати` badge to the biomarker cell; STRICT mode replaces
    the row's body with a single stripped-block placeholder cell.
    """
    hits = list(getattr(plan, "variant_actionability", None) or [])

    # ── Biomarker audit: classify patient profile into covered / uncovered ──
    snap = getattr(plan, "patient_snapshot", None) or {}
    patient_biomarkers: dict = (
        snap.get("biomarkers") if isinstance(snap, dict) else {}
    ) or {}

    # Which patient keys matched at least one hit?
    covered_keys: set[str] = set()
    for pk in patient_biomarkers:
        for hit in hits:
            if _biomarker_keys_match(pk, hit.biomarker_id):
                covered_keys.add(pk)
                break

    defined_bio_ids = _load_defined_bio_ids()
    uncovered_rows: list[dict] = []
    for key, raw_value in patient_biomarkers.items():
        if key in covered_keys:
            continue
        variant = _extract_variant(raw_value)
        if variant is None:
            reason = "negative"
        elif str(key).upper() in defined_bio_ids:
            reason = "bio_exists"
        else:
            reason = "unmatched"
        uncovered_rows.append({"key": key, "reason": reason})

    show_audit = bool(patient_biomarkers)  # only split when snapshot is available

    # ── Build covered hits table ────────────────────────────────────────────
    th = (
        "<thead><tr>"
        f"<th>{_h(_t('actionability_th_biomarker', target_lang))}</th>"
        f"<th>{_h(_t('actionability_th_variant', target_lang))}</th>"
        f"<th>{_h(_t('actionability_th_escat', target_lang))}</th>"
        f"<th>{_h(_t('actionability_th_evidence', target_lang))}</th>"
        f"<th>{_h(_t('actionability_th_action', target_lang))}</th>"
        f"<th>{_h(_t('actionability_th_combos', target_lang))}</th>"
        f"<th>{_h(_t('actionability_th_sources', target_lang))}</th>"
        "</tr></thead>"
    )

    rows: list[str] = []
    if not hits:
        rows.append(
            f'<tr class="empty-row"><td colspan="7">'
            f'{_h(_t("actionability_empty", target_lang))}'
            f'</td></tr>'
        )
    else:
        for h in hits:
            # PR5 — per-cell citation-presence: feed a hit-shaped dict
            # into the resolver. Hits expose primary_sources +
            # evidence_sources at the top level, mirroring BMA YAML.
            cell_data = {
                "primary_sources": list(h.primary_sources or []),
                "evidence_sources": list(getattr(h, "evidence_sources", None) or []),
            }
            cell_status = _resolve_citation_status(cell_data)

            # STRICT mode: redact the entire row
            if strict_citation_guard and _citation_needs_guard(cell_status["status"]):
                rows.append(
                    '<tr class="stripped-row">'
                    f'<td colspan="7">{_render_stripped_block(target_lang)}</td>'
                    '</tr>'
                )
                continue

            biomarker = _h(h.biomarker_id or "")
            qualifier = h.variant_qualifier
            variant_cell = (
                _h(qualifier)
                if qualifier
                else f'<span style="color:var(--gray-500)">{_h(_t("actionability_gene_level", target_lang))}</span>'
            )
            escat_cls = _escat_class(h.escat_tier)
            escat_label = _h(h.escat_tier or "X")
            evidence_cell = _format_evidence_sources(
                getattr(h, "evidence_sources", None) or [],
                primary_sources=list(h.primary_sources or []),
            )
            summary = _h_t(h.evidence_summary or "", target_lang)
            combos = (
                "<br>".join(_h(c) for c in (h.recommended_combinations or []))
                or '<span style="color:var(--gray-500)">—</span>'
            )
            # Per OncoKB ToS, filter SRC-ONCOKB from the user-visible
            # primary-sources column as well.
            visible_sources = [
                s for s in (h.primary_sources or []) if not _is_skipped_source(s)
            ]
            sources = (
                "".join(f"<li>{_h(s)}</li>" for s in visible_sources)
                or '<li style="color:var(--gray-500)">—</li>'
            )

            # WARN-mode badge prepended to biomarker cell when status is
            # uncited / broken. Strict mode is handled above (early-continue).
            badge_html = (
                _render_citation_warn_badge(target_lang)
                if _citation_needs_guard(cell_status["status"])
                else ""
            )

            rows.append(
                "<tr>"
                f'<td>{badge_html}<span class="gene">{biomarker}</span></td>'
                f'<td><span class="variant">{variant_cell}</span></td>'
                f'<td><span class="tier-badge {escat_cls}">{escat_label}</span></td>'
                f'<td class="evidence">{evidence_cell}</td>'
                f'<td class="summary">{summary}</td>'
                f'<td class="combos">{combos}</td>'
                f'<td><ul class="src-list">{sources}</ul></td>'
                "</tr>"
            )

    covered_table = (
        f'<table class="actionability-table">{th}<tbody>{"".join(rows)}</tbody></table>'
    )

    # ── Build uncovered table ───────────────────────────────────────────────
    uncovered_html = ""
    if show_audit and uncovered_rows:
        unc_th = (
            "<thead><tr>"
            f"<th>{_h(_t('actionability_th_biomarker', target_lang))}</th>"
            f"<th>{_h(_t('actionability_uncovered_th_status', target_lang))}</th>"
            "</tr></thead>"
        )
        unc_rows: list[str] = []
        for row in uncovered_rows:
            reason_key = f"actionability_uncovered_{row['reason']}"
            status_cls = f"biomarker-status-{row['reason']}"
            unc_rows.append(
                "<tr>"
                f'<td><span class="gene">{_h(row["key"])}</span></td>'
                f'<td><span class="{status_cls}">{_h(_t(reason_key, target_lang))}</span></td>'
                "</tr>"
            )
        uncovered_html = (
            '<div class="biomarker-subsection uncovered">'
            f'<div class="biomarker-subsection-header">'
            f'{_h(_t("actionability_uncovered_heading", target_lang))}'
            f'</div>'
            f'<table class="actionability-table uncovered-table">'
            f'{unc_th}<tbody>{"".join(unc_rows)}</tbody></table>'
            f'</div>'
        )

    # ── Assemble section ────────────────────────────────────────────────────
    if show_audit and uncovered_html:
        covered_html = (
            '<div class="biomarker-subsection covered">'
            f'<div class="biomarker-subsection-header">'
            f'{_h(_t("actionability_covered_heading", target_lang))}'
            f'</div>'
            f'{covered_table}'
            f'</div>'
        )
    else:
        covered_html = covered_table

    return (
        '<section class="variant-actionability">'
        f'<h2>{_h(_t("actionability_heading", target_lang))}</h2>'
        f'<div class="section-sub">{_h(_t("actionability_sub", target_lang))}</div>'
        f'{covered_html}'
        f'{uncovered_html}'
        '</section>'
    )


# ── Citation-presence guard helpers (PR5) ───────────────────────────────────


def _track_citation_dd(
    indication_id: str,
    regimen_label: str,
    ind_status: dict,
    reg_status: dict,
    target_lang: str,
    strict: bool,
) -> tuple[str, str]:
    """Build the `<dd>` cell content for the Indication and Regimen rows
    in a track block, applying the PR5 citation-presence guard.

    Returns `(indication_dd, regimen_dd)` — each is a complete `<dd>...</dd>`
    string. WARN mode prepends a badge; STRICT mode replaces the cell
    body with a stripped-block placeholder."""
    if _citation_needs_guard(ind_status["status"]):
        if strict:
            ind_dd = f"<dd>{_render_stripped_block(target_lang)}</dd>"
        else:
            ind_dd = (
                f'<dd>{_render_citation_warn_badge(target_lang)} '
                f'{_h(indication_id)}</dd>'
            )
    else:
        ind_dd = f'<dd>{_h(indication_id)}</dd>'

    if _citation_needs_guard(reg_status["status"]):
        if strict:
            reg_dd = f"<dd>{_render_stripped_block(target_lang)}</dd>"
        else:
            reg_dd = (
                f'<dd>{_render_citation_warn_badge(target_lang)} '
                f'{_h(regimen_label)}</dd>'
            )
    else:
        reg_dd = f'<dd>{_h(regimen_label)}</dd>'
    return ind_dd, reg_dd


# ── Treatment Plan render ─────────────────────────────────────────────────


def render_plan_html(
    plan_result: PlanResult,
    mdt: Optional[MDTOrchestrationResult] = None,
    *,
    target_lang: str = "uk",
    mode: str = "clinician",
    strict_citation_guard: bool = False,
    sibling_link: Optional[str] = None,
) -> str:
    """Render a PlanResult as a single-file HTML document.

    `mode="clinician"` (default) emits the full tumor-board brief with
    technical IDs, ESCAT tiers, MDT block, FDA disclosure, etc.

    `mode="patient"` emits a stripped-down plain-Ukrainian patient-facing
    bundle: technical IDs (BMA-*, ALGO-*, BIO-*, IND-*, REG-*, RF-*) are
    removed from user-visible text and replaced with vocabulary lookups
    from `_patient_vocabulary`. Emergency RedFlags surface as a banner
    via `_emergency_rf`; an 'ask your doctor' section is generated via
    `_ask_doctor`. CHARTER §8.3 invariant — patient-mode never changes
    the engine's track selection.

    `sibling_link` (PATIENT_MODE_SPEC §3.5) — relative URL of the
    cross-mode bundle. When set, both modes render a header chip
    pointing at the sibling. CLI `--render-mode both` populates this
    automatically; single-mode callers may pass a placeholder or leave
    `None` to suppress the chip.

    `strict_citation_guard=False` (default) is WARN mode: any
    Regimen / Indication / BMA cell whose declared sources fail to
    resolve to a real Source entity gets a visible
    ``<aside class="no-citation-badge">❓ без цитати</aside>`` flag, but
    the underlying clinical content still renders.
    `strict_citation_guard=True` is STRICT mode: those cells'
    bodies are replaced with a ``<div class="stripped-block">`` placeholder
    so unsourced content cannot reach the patient. STRICT is the
    target post-cleanup; WARN is the current-state default for KB
    drift visibility (PR5)."""
    if (mode or "").lower() == "patient":
        return _render_patient_mode(plan_result, target_lang, sibling_link=sibling_link)

    plan = plan_result.plan
    if plan is None:
        warnings = plan_result.warnings or []
        if warnings:
            warning_items = "".join(
                f"<li><code>{_h(w)}</code></li>" for w in warnings
            )
            warning_html = (
                "<p><strong>Engine details:</strong></p>"
                f"<ul style='line-height:1.65'>{warning_items}</ul>"
            )
        else:
            warning_html = (
                "<p><strong>Engine details:</strong> "
                "No specific warning was returned by the engine.</p>"
            )
        return _doc_shell(
            "OpenOnco — no indications found",
            "<div style='padding:2rem 2.5rem;font-family:system-ui,sans-serif;max-width:52rem'>"
            "<h2 style='color:#c0392b;margin-top:0'>⚠ No treatment plan generated</h2>"
            "<p>The engine matched <strong>no active indications</strong> for this patient profile.</p>"
            f"{warning_html}"
            "<p><strong>Common causes:</strong></p>"
            "<ul style='line-height:1.8'>"
            "<li>Disease not yet covered — check <a href='/diseases.html'>disease coverage</a></li>"
            "<li>Patient profile missing <code>disease.id</code> or <code>disease.icd_o_3</code></li>"
            "<li>All matching treatment tracks blocked by ECOG PS ≥ 4 gate or active contraindications</li>"
            "<li>Diagnostic profile without <code>disease.suspicion</code> field</li>"
            "</ul>"
            "<p style='color:#666;font-size:.9rem'>Review the patient JSON, fill required fields, and generate again.</p>"
            "</div>",
        )

    fda = plan.fda_compliance

    # Header
    body: list[str] = []
    disease_title = _diagnosis_name(plan_result, target_lang) or plan_result.disease_id
    cross_link = _render_mode_toggle(sibling_link, "Версія для пацієнта →")
    body.append(
        '<div class="doc-header">'
        '<div class="doc-label">OpenOnco · Treatment Plan</div>'
        f'<div class="doc-title">План лікування — {_h(disease_title)}</div>'
        f'<div class="doc-sub">{_h(plan.id)} · v{_h(plan.version)} · {_h(plan.generated_at[:10])}</div>'
        f'{cross_link}'
        '</div>'
    )

    # Patient strip
    body.append(_render_patient_strip(plan_result, target_lang))

    # Etiological driver — only for etiologically_driven archetype
    body.append(_render_etiological_driver(
        (plan_result.kb_resolved or {}).get("disease"), target_lang
    ))

    # Variant actionability (ESCAT) — inserted between the
    # diagnostic profile and the treatment-plan tracks. Render-time
    # context only; engine never re-reads tier values to rank tracks.
    body.append(_render_variant_actionability(
        plan, target_lang, strict_citation_guard=strict_citation_guard
    ))

    # Tracks
    drugs_lookup = (plan_result.kb_resolved or {}).get("drugs") or {}
    disease_data = (plan_result.kb_resolved or {}).get("disease") or {}
    disease_names = (disease_data.get("names") if isinstance(disease_data, dict) else None) or {}
    track_html = []
    for t in plan.tracks:
        track_class = f"track track--{(t.track_id or 'standard')}"
        if t.is_default:
            badge = '<span class="track-default-badge">★ DEFAULT</span>'
        else:
            badge = ""
        regimen_str = (t.regimen_data or {}).get("name", "—") if t.regimen_data else "—"
        sup = (
            f'<dt>Supportive care</dt><dd>{_h(", ".join(s.get("id", "?") for s in t.supportive_care_data))}</dd>'
            if t.supportive_care_data else ""
        )
        ci = (
            f'<dt>Hard contraindications</dt><dd>{_h(", ".join(c.get("id", "?") for c in t.contraindications_data))}</dd>'
            if t.contraindications_data else ""
        )
        # Treatment phases — phase-aware drug list (PR2 of phases-refactor).
        # Each phase renders as its own <section class="phase-block">.
        # Legacy single-phase regimens (auto-wrapped from `components`) emit
        # a single block without a heading prefix, visually close to pre-PR2.
        # Engine never reads any of this — render-time metadata only,
        # same contract as ESCAT tiers / NSZU badges.
        drugs_dd = _render_treatment_phases(
            t, drugs_lookup, plan_result.disease_id or "", disease_names, target_lang
        )
        # TODO(phase-4): inline resistance-conflict banner once the
        # CIViC reader (SnapshotActionabilityClient) is wired and the
        # actionability_layer is populated. Surface-only — the inline
        # banner is the T3 mitigation for clinicians scrolling top-down.
        actionability_inline = ""

        # PR5 citation-presence guard — Indication + Regimen each get an
        # independent check. Two badges (vs. one worst-of) is more truthful
        # and lets clinicians see exactly which entity broke the chain.
        # Surveillance / watch-and-wait tracks have no regimen by design;
        # we suppress the regimen guard for those (no entity → no badge)
        # to avoid spurious flags that would conflate "missing citation"
        # with "no regimen exists". Same guard applies to a missing
        # indication_data (degenerate case — track wouldn't normally
        # render meaningfully anyway).
        _CITED_NOOP = {
            "status": "cited", "cited_count": 0,
            "resolved_count": 0, "unresolved_ids": [],
        }
        ind_status = (
            _resolve_citation_status(t.indication_data)
            if t.indication_data is not None
            else _CITED_NOOP
        )
        reg_status = (
            _resolve_citation_status(t.regimen_data)
            if t.regimen_data is not None
            else _CITED_NOOP
        )
        ind_dd, reg_dd = _track_citation_dd(
            indication_id=t.indication_id,
            regimen_label=regimen_str,
            ind_status=ind_status,
            reg_status=reg_status,
            target_lang=target_lang,
            strict=strict_citation_guard,
        )
        track_html.append(
            f'<div class="{track_class}">'
            f'<div class="track-head"><div class="track-name">{_h(t.label)}</div>{badge}</div>'
            f'{actionability_inline}'
            f'<dl>'
            f'<dt>Indication</dt>{ind_dd}'
            f'<dt>Regimen</dt>{reg_dd}'
            f'{drugs_dd}'
            f'{sup}'
            f'{ci}'
            f'<dt>Reason</dt><dd>{_h(t.selection_reason)}</dd>'
            f'</dl>'
            f'</div>'
        )
    primary_html = track_html[0] if track_html else ""
    if primary_html:
        body.append(
            "<section><h2>Primary current-line option</h2>"
            f'<div class="tracks">{primary_html}</div></section>'
        )
    alternative_html = "".join(track_html[1:])
    if alternative_html:
        body.append(
            "<section><details>"
            f"<summary><h2>Other current-line alternatives ({len(track_html) - 1} tracks)</h2>"
            "<span class=\"section-sub\">Same treatment line; review when biomarker, access, contraindication, or patient-context assumptions change.</span>"
            "</summary>"
            f'<div class="tracks">{alternative_html}</div>'
            "</details></section>"
        )

    # Why this branch was chosen — actual fired RFs from the trace,
    # with the conflict-resolution winner tagged. Distinct from the
    # PRO/CONTRA section, which lists possible triggers in the abstract.
    sequencing_tracks = getattr(plan, "sequencing_tracks", []) or []
    if sequencing_tracks:
        seq_rows: list[str] = []
        for t in sequencing_tracks:
            authored_line = ((t.indication_data or {}).get("applicable_to") or {}).get("line_of_therapy")
            regimen_name = (t.regimen_data or {}).get("name", "-") if t.regimen_data else "-"
            line_note = f"line {authored_line}" if authored_line is not None else "line not authored"
            seq_rows.append(
                "<tr>"
                f"<td><code>{_h(t.indication_id)}</code></td>"
                f"<td>{_h(line_note)}</td>"
                f"<td>{_h(regimen_name)}</td>"
                f"<td>{_h(t.selection_reason or '')}</td>"
                "</tr>"
            )
        body.append(
            "<section><details>"
            "<summary><h2>Sequencing / non-current-line candidates</h2>"
            "<span class=\"section-sub\">Shown for audit and future-line context; not part of the current treatment choice.</span>"
            "</summary>"
            "<table class=\"tbl\"><thead><tr>"
            "<th>Indication</th><th>Authored line</th><th>Regimen</th><th>Why separated</th>"
            "</tr></thead><tbody>"
            f"{''.join(seq_rows)}"
            "</tbody></table>"
            "</details></section>"
        )

    body.append(_render_branch_explanation(plan_result, plan_result.kb_resolved, target_lang))

    # Pre-treatment investigations · RedFlag PRO/CONTRA · What NOT to do ·
    # Monitoring phases · Timeline (REFERENCE_CASE_SPECIFICATION §1.3)
    body.append(_render_pretreatment_investigations(plan, plan_result.kb_resolved, target_lang))
    body.append(_render_red_flags_pro_contra(plan, plan_result.kb_resolved, target_lang))
    body.append(_render_what_not_to_do(plan, target_lang))

    # Phase 4 (CIViC pivot, 2026-04-27): the per-cell `evidence_sources`
    # rendering inside `_render_variant_actionability` is now ESCAT-primary
    # + CIViC-detailed. SRC-ONCOKB entries are skipped per OncoKB ToS, and
    # `primary_sources` (sans OncoKB) are promoted as a fallback when the
    # post-skip evidence_sources list is empty (Phase 3-O finding). See
    # `_format_evidence_sources` for the full rule set.
    # TODO(phase-5-cleanup): when SnapshotActionabilityClient is wired,
    # actionability_layer can replace the inline cell renderer below with
    # a richer card-grid view.
    # actionability_layer = getattr(plan_result, "actionability_layer", None)

    body.append(_render_monitoring_phases(plan, target_lang))
    body.append(_render_timeline(plan, target_lang))

    # MDT brief inline
    body.append(_render_mdt_section(mdt, target_lang))

    # Sources
    if fda.data_sources_summary:
        items = "".join(f"<li>{_h(s)}</li>" for s in fda.data_sources_summary)
        body.append(f"<section><h2>Sources cited</h2><ul class='sources'>{items}</ul></section>")

    # Cited trials — live status decoration for cited pivotal NCT IDs.
    # Scans the in-progress body for `NCT\d{8}` occurrences and looks up
    # cached ctgov data via `_render_cited_trials_status`. Render-time
    # only (CHARTER §8.3); empty when the cache has nothing.
    # See docs/reviews/ctgov-wiring-audit-2026-05-18.md Gap 3.
    body.append(_render_cited_trials_status("".join(body), target_lang))

    # Experimental options (Phase C — clinical-trial track)
    body.append(_render_experimental_options(plan_result.experimental_options, target_lang))

    # Access Matrix (Phase D — UA-availability per track)
    body.append(_render_access_matrix(plan.access_matrix, target_lang))

    # Footer
    body.append('<div class="doc-footer">')
    body.append(_render_version_chain(
        plan.id, plan.version, plan.supersedes, plan.superseded_by, plan.generated_at,
    ))
    body.append(_render_fda_disclosure(fda.intended_use))
    if fda.automation_bias_warning:
        body.append(_render_fda_disclosure(fda.automation_bias_warning))
    body.append(f'<div class="medical-disclaimer">{_h(_MEDICAL_DISCLAIMER)}</div>')
    body.append('</div>')

    out = _doc_shell(f"План лікування — {disease_title}", "".join(body))
    return _localize_html(out, target_lang)


# ── Patient-mode render ───────────────────────────────────────────────────
#
# Plain-Ukrainian patient-facing bundle. Technical entity IDs (BMA-*,
# ALGO-*, BIO-*, IND-*, REG-*, RF-*) are NEVER rendered as visible text
# in patient mode (they may appear in HTML attributes for testing /
# debugging, e.g. `data-bma-id="..."`, but never in `<p>` / `<li>` /
# `<td>` content). All clinician-vocabulary terms route through
# `_patient_vocabulary.explain()`.


def _patient_doc_shell(title: str, body: str) -> str:
    """Patient-mode HTML shell — embeds STYLESHEET + PATIENT_MODE_CSS so
    the bundle is a single self-contained document. Distinct from
    `_doc_shell` because patient mode wraps the body in
    `<div class="patient-report">` rather than `<div class="page">` and
    doesn't ship the Google Fonts <link> (patient bundles favour system
    fonts for offline-readability)."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="uk">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{_h(title)}</title>\n"
        f"<style>{_CSS}{_PATIENT_CSS}</style>\n"
        "</head>\n<body>\n"
        f'<div class="patient-report">{body}</div>\n'
        "</body>\n</html>\n"
    )


def _patient_disease_label(plan_result: PlanResult) -> str:
    """Plain-UA disease label, never the DIS- ID. Falls back to a generic
    label so user-visible text never contains a technical ID."""
    disease_data = (plan_result.kb_resolved or {}).get("disease") or {}
    names = disease_data.get("names") if isinstance(disease_data, dict) else None
    if isinstance(names, dict):
        for key in ("ukrainian", "preferred", "english"):
            v = names.get(key)
            if v:
                return str(v)
    return "ваш діагноз"


def _patient_drug_label(drug_dict: dict, drug_id: str) -> str:
    """Plain-UA drug label, never the DRUG- ID."""
    if isinstance(drug_dict, dict):
        names = drug_dict.get("names") or {}
        if isinstance(names, dict):
            for key in ("ukrainian", "preferred", "english"):
                v = names.get(key)
                if v:
                    return str(v)
        nm = drug_dict.get("name")
        if nm:
            return str(nm)
    # Last-resort fallback: humanize the ID. We deliberately strip the
    # `DRUG-` prefix so no raw entity ID leaks into rendered text.
    raw = (drug_id or "").strip()
    if raw.upper().startswith("DRUG-"):
        raw = raw[5:]
    return raw.replace("-", " ").replace("_", " ").lower() or "препарат"


def _render_findings_plain(plan_result: PlanResult) -> str:
    """Plain-UA rendering of the variant_actionability hits.

    Each hit becomes a friendly statement: 'У вас знайдено [variant
    explanation]. Це означає: [ESCAT tier patient label].' Technical
    IDs (BMA-*, BIO-*) are stripped — only gene + variant fragment
    survive (e.g. "BRAF V600E"), which is patient-facing biology, not
    a KB ID."""
    plan = plan_result.plan
    hits = list((plan and plan.variant_actionability) or [])
    if not hits:
        return (
            '<p>За результатами наявних аналізів значущих молекулярних мішеней '
            "поки не виявлено. Це не означає, що лікування неможливе — стандартна терапія "
            "залишається повністю чинною. Якщо у вас ще не було молекулярного тестування "
            "пухлини, обговоріть це з лікарем.</p>"
        )

    parts: list[str] = ['<ul class="findings-list">']
    for h in hits:
        # Strip BIO- prefix from the biomarker label — keep only gene-name
        # fragment (BRAF, EGFR, etc.) which is patient-readable biology,
        # not an internal KB ID.
        bio = (h.biomarker_id or "").strip()
        gene = bio[4:].split("-", 1)[0] if bio.upper().startswith("BIO-") else bio.split("-", 1)[0]
        variant = (h.variant_qualifier or "").strip() or ""
        # Variant explanation from vocabulary (e.g. V600E → "конкретна
        # заміна валіну на глутамат…"). Falls back to the literal variant
        # string when vocabulary has no entry.
        v_expl = _explain_patient(variant) or _explain_patient(gene) or ""
        tier = (h.escat_tier or "").strip().upper()
        tier_label = ESCAT_TIER_PATIENT_LABEL.get(tier, "")
        # Compose a short human paragraph. We render gene + variant
        # together (e.g. "BRAF V600E") because that's biology a patient
        # can search for; ESCAT tier is wrapped in a friendly label.
        gene_variant = f"{gene} {variant}".strip() if variant else gene
        bits = [f"<li><strong>{_h(gene_variant)}</strong>"]
        if v_expl:
            bits.append(f" — {_h(v_expl)}")
        if tier_label:
            bits.append(f'. <span class="patient-badge patient-info">{_h(tier_label)}</span>')
        else:
            bits.append(".")
        bits.append("</li>")
        parts.append("".join(bits))
    parts.append("</ul>")
    return "".join(parts)


def _render_mode_toggle(sibling_link: Optional[str], label_ua: str) -> str:
    """Cross-link chip per PATIENT_MODE_SPEC §3.5.

    Renders an `<a class="mode-toggle">` pointing at the sibling bundle.
    `sibling_link=None` suppresses the chip entirely (callers that
    don't know the sibling URL upfront — e.g. single-mode renders that
    will never have a sibling — get nothing). Empty string `""` and
    `"#"` are treated as placeholder values: the chip renders so a
    downstream caller (web app, CLI rewrite) can patch the href."""
    if sibling_link is None:
        return ""
    href = sibling_link if sibling_link else "#"
    return f'<a class="mode-toggle" href="{_h(href)}">{_h(label_ua)}</a>'


def _track_label_ua(track_index: int, track_count: int, t) -> tuple[str, str]:
    """Return (display_label, css_modifier) for a patient-mode track card.

    Single-track plans get a bare label without the А/Б prefix; multi-
    track plans use Cyrillic enumeration so no Latin leaks into visible
    text. `is_default` drives the CSS modifier so the default track gets
    the green border and the alternative gets indigo (per §3.2)."""
    if track_count <= 1:
        base = "Рекомендований план"
    else:
        prefix = "А" if track_index == 0 else "Б"
        suffix = "Стандартний варіант" if getattr(t, "is_default", False) else "Альтернативний варіант"
        base = f"{prefix}) {suffix}"
    modifier = "default" if getattr(t, "is_default", False) else "alternative"
    return base, modifier


def _regimen_schedule_ua(regimen_data: Optional[dict]) -> str:
    """One-line plain-UA schedule summary for a regimen, or empty string.

    Composes from `cycle_length_days` × `total_cycles` when both are
    present and integer-castable. Strings like 'Continuous until
    progression' for `total_cycles` are passed through verbatim
    (KNOWLEDGE_SCHEMA_SPECIFICATION §6.2 currently allows free-form)."""
    if not isinstance(regimen_data, dict):
        return ""
    cycle = regimen_data.get("cycle_length_days")
    total = regimen_data.get("total_cycles")
    if cycle is None and total is None:
        return ""
    if isinstance(total, str) and total.strip():
        return f"Тривалість: {_h(total)}; цикл — {_h(cycle)} днів" if cycle else f"Тривалість: {_h(total)}"
    try:
        c = int(cycle) if cycle is not None else None
        t_int = int(total) if total is not None else None
    except (TypeError, ValueError):
        return ""
    if c and t_int:
        return f"{t_int} цикл(и) по {c} днів"
    if c:
        return f"Цикл — {c} днів"
    if t_int:
        return f"{t_int} цикл(и)"
    return ""


def _render_track_drugs(
    plan_result: PlanResult,
    t,
    drugs_lookup: dict,
    disease_names: Optional[dict],
) -> str:
    """Render the drug-explanation blocks for a single track.

    Per PATIENT_MODE_SPEC §3.2, dedupe is *within* a track only — the
    same drug appearing in both Standard and Aggressive must surface in
    both cards so the patient sees what each plan actually contains."""
    seen_drug_ids: set[str] = set()
    blocks: list[str] = []
    for comp in _iter_regimen_components(t.regimen_data):
        drug_id = comp.get("drug_id") or ""
        if not drug_id or drug_id in seen_drug_ids:
            continue
        seen_drug_ids.add(drug_id)

        drug = drugs_lookup.get(drug_id) or {}
        label = _patient_drug_label(drug, drug_id)
        drug_class = (drug.get("drug_class") or "") if isinstance(drug, dict) else ""

        # Lay-language explanation: prefer notes_patient (drug-author'd
        # patient-facing blurb) → drug_class vocabulary entry → generic.
        lay = ""
        if isinstance(drug, dict):
            lay = (drug.get("notes_patient") or "").strip()
        if not lay and drug_class:
            lay = _explain_patient(drug_class) or ""
        if not lay:
            lay = "препарат для лікування вашого захворювання — деталі обговоріть з лікарем"

        # NSZU badge — patient-friendly label, render only when we can
        # resolve coverage. Falls back silently when drug entity is
        # missing (don't fabricate a badge).
        badge_html = ""
        if isinstance(drug, dict) and drug:
            try:
                badge = lookup_nszu_status(
                    drug,
                    plan_result.disease_id or "",
                    disease_names=disease_names if isinstance(disease_names, dict) else None,
                )
                p_label = NSZU_PATIENT_LABEL.get(badge.status, "")
                if p_label:
                    cls = f"patient-nszu patient-nszu-{badge.status}"
                    badge_html = (
                        f'<div class="{cls}" data-nszu-status="{_h(badge.status)}">'
                        f"{_h(p_label)}</div>"
                    )
            except Exception:
                badge_html = ""

        blocks.append(
            f'<div class="drug-explanation" data-source-id="{_h(drug_id)}">'
            f"<h3>{_h(label)}</h3>"
            f'<p class="lay-language">{_h(lay)}</p>'
            f"{badge_html}"
            "</div>"
        )
    return "".join(blocks)


def _render_tracks_plain(plan_result: PlanResult) -> str:
    """Plain-UA per-track rendering for the `what-now` section.

    Each track becomes a `<article class="track-card track-card--{mod}">`
    with a Cyrillic А/Б prefix when multi-track. Information parity rule
    (PATIENT_MODE_SPEC §4): the patient never sees fewer tracks than the
    clinician version. Verification anchors via `data-source-id` on each
    card (regimen ID) and each drug-explanation block (drug ID)."""
    plan = plan_result.plan
    if plan is None or not plan.tracks:
        return (
            "<p>Конкретний список препаратів буде сформовано лікарем "
            "після перегляду усіх ваших аналізів.</p>"
        )

    drugs_lookup = (plan_result.kb_resolved or {}).get("drugs") or {}
    disease_data = (plan_result.kb_resolved or {}).get("disease") or {}
    disease_names = disease_data.get("names") if isinstance(disease_data, dict) else None
    track_count = len(plan.tracks)

    cards: list[str] = []
    for idx, t in enumerate(plan.tracks):
        title_ua, modifier = _track_label_ua(idx, track_count, t)
        regimen_data = t.regimen_data or {}
        regimen_id = regimen_data.get("id", "") if isinstance(regimen_data, dict) else ""
        regimen_name = (
            regimen_data.get("name", "") if isinstance(regimen_data, dict) else ""
        )
        schedule_str = _regimen_schedule_ua(regimen_data)
        signoff_badge = _render_signoff_badge_patient(t.indication_data)
        drug_blocks = _render_track_drugs(plan_result, t, drugs_lookup, disease_names)
        if not drug_blocks:
            drug_blocks = (
                "<p>Конкретний список препаратів для цього варіанту буде "
                "уточнений лікарем.</p>"
            )

        regimen_line = (
            f'<p class="track-title">{_h(regimen_name)}</p>'
            if regimen_name else ""
        )
        schedule_line = (
            f'<p class="regimen-schedule">{schedule_str}</p>'
            if schedule_str else ""
        )

        cards.append(
            f'<article class="track-card track-card--{_h(modifier)}" '
            f'data-source-id="{_h(regimen_id)}">'
            f'<p class="track-label">{_h(title_ua)}</p>'
            f'{regimen_line}'
            f'{schedule_line}'
            f'{signoff_badge}'
            f'{drug_blocks}'
            "</article>"
        )

    grid_class = "tracks-grid tracks-grid--two" if track_count == 2 else "tracks-grid"
    return f'<div class="{grid_class}">{"".join(cards)}</div>'


def _render_why_section(plan_result: PlanResult) -> str:
    """Per-track 'why this for you' section.

    Phase 2 emits a placeholder shell so structural anchors exist for
    tests + downstream consumers. Phase 3 (`_patient_rationale.py`)
    fills in the bullets from `PlanResult.trace`. The shell still
    surfaces the section heading + per-track cards so the bundle layout
    is stable across phases."""
    plan = plan_result.plan
    if plan is None or not plan.tracks:
        return (
            '<section class="why-this-plan">'
            "<h2>Чому саме цей план</h2>"
            '<p class="why-fallback">Деталі — у технічній версії звіту.</p>'
            "</section>"
        )

    track_count = len(plan.tracks)
    track_blocks: list[str] = []
    for idx, t in enumerate(plan.tracks):
        title_ua, modifier = _track_label_ua(idx, track_count, t)
        regimen_data = t.regimen_data or {}
        regimen_id = regimen_data.get("id", "") if isinstance(regimen_data, dict) else ""
        bullets_html = _build_why_bullets_html(plan_result, t)
        track_blocks.append(
            f'<div class="why-track" data-source-id="{_h(regimen_id)}">'
            f'<p class="track-label">{_h(title_ua)}</p>'
            f"{bullets_html}"
            "</div>"
        )

    return (
        '<section class="why-this-plan">'
        "<h2>Чому саме цей план</h2>"
        f'{"".join(track_blocks)}'
        "</section>"
    )


def _build_why_bullets_html(plan_result: PlanResult, track) -> str:
    """Phase 3: rationale bullets from `PlanResult.trace`.

    Delegates to `_patient_rationale.build_track_rationale_html`, which
    composes 1-4 plain-UA bullets per track based on:

      * Variant actionability hits (ESCAT IA/IB → strong-tier wording).
      * Default vs alternative track distinction.
      * Up to 2 fired RedFlag definitions (first-sentence Ukrainian).
      * Fallback strings when none of the above produce a signal.

    HTML escaping is handled inside the rationale builder so KB content
    with markup-sensitive characters cannot break the document."""
    return _build_track_rationale_html(plan_result, track)


# Urgency tiers from Regimen.between_visit_watchpoints, mapped to the
# patient-bundle headings. Order is important: log → call → ER, so the
# patient sees calmer items first and the most urgent last (the tier
# they're most likely to act on stays at the bottom right above the
# emergency banner).
_BV_URGENCY_ORDER: tuple[str, ...] = (
    "log_at_next_visit",
    "call_clinic_same_day",
    "er_now",
)
_BV_URGENCY_HEADING_UA: dict[str, str] = {
    "log_at_next_visit": "Занотуйте і обговоріть на наступному візиті",
    "call_clinic_same_day": "Подзвоніть у клініку того ж дня",
    "er_now": "Звертайтесь у лікарню негайно",
}
_BV_URGENCY_CSS_CLASS: dict[str, str] = {
    "log_at_next_visit": "bv-urgency-group bv-log",
    "call_clinic_same_day": "bv-urgency-group bv-call",
    "er_now": "bv-urgency-group bv-er",
}
_BV_FALLBACK_HTML = (
    '<p class="bv-fallback">Список того, на що звернути увагу між '
    "візитами, для цього курсу ще не узгоджено клінічною командою. "
    "Запитайте лікаря на наступному візиті, які симптоми треба "
    "занотовувати, а які — приводи дзвонити в клініку.</p>"
)


def _emergency_trigger_keys(plan_result: PlanResult) -> set[str]:
    """Return the lowercase first-sentence text of each emergency-tier
    RedFlag definition. PATIENT_MODE_SPEC §3.4 dedupe rule: an `er_now`
    watchpoint whose `trigger_ua` matches any emergency RF text is
    suppressed so the patient doesn't see the same call-to-action in
    both `between-visits` and `emergency-signals`."""
    rf_lookup = (plan_result.kb_resolved or {}).get("red_flags") or {}
    keys: set[str] = set()
    if not isinstance(rf_lookup, dict):
        return keys
    for rf in rf_lookup.values():
        if not isinstance(rf, dict):
            continue
        if not is_emergency_rf(rf):
            continue
        text = (rf.get("definition_ua") or rf.get("definition") or "")
        # Match patient_emergency_label() truncation — first sentence only.
        first = str(text).split(".")[0].strip().lower()
        if first:
            keys.add(first)
    return keys


def _render_between_visits_section(plan_result: PlanResult) -> str:
    """Per-track 'на що звертати увагу між візитами' section.

    Source: `track.regimen_data['between_visit_watchpoints']` (list of
    BetweenVisitWatchpoint dicts after Pydantic round-trip). Empty list
    or missing field → fallback string per PATIENT_MODE_SPEC §3.4.
    Renderer NEVER fabricates content.

    Dedupe with the emergency banner: an `er_now` item whose
    `trigger_ua` first-sentence matches any emergency RF is dropped
    here (it surfaces in the emergency banner instead). Per §3.4.
    """
    plan = plan_result.plan
    if plan is None or not plan.tracks:
        return (
            '<section class="between-visits">'
            "<h2>На що звернути увагу між візитами</h2>"
            f"{_BV_FALLBACK_HTML}"
            "</section>"
        )

    track_count = len(plan.tracks)
    emergency_keys = _emergency_trigger_keys(plan_result)
    track_blocks: list[str] = []
    any_authored = False

    for idx, t in enumerate(plan.tracks):
        regimen_data = t.regimen_data or {}
        regimen_id = (
            regimen_data.get("id", "") if isinstance(regimen_data, dict) else ""
        )
        watchpoints = []
        if isinstance(regimen_data, dict):
            watchpoints = list(regimen_data.get("between_visit_watchpoints") or [])

        # Dedupe er_now items vs emergency banner.
        kept: list[dict] = []
        for w in watchpoints:
            if not isinstance(w, dict):
                continue
            if (w.get("urgency") or "") == "er_now":
                trig = (w.get("trigger_ua") or "").split(".")[0].strip().lower()
                if trig and trig in emergency_keys:
                    continue
            kept.append(w)

        title_ua, modifier = _track_label_ua(idx, track_count, t)
        if not kept:
            track_blocks.append(
                f'<div class="bv-track" data-source-id="{_h(regimen_id)}">'
                f'<p class="track-label">{_h(title_ua)}</p>'
                f"{_BV_FALLBACK_HTML}"
                "</div>"
            )
            continue

        any_authored = True
        # Group within the track by urgency tier, in canonical order.
        groups_html: list[str] = []
        by_urgency: dict[str, list[dict]] = {u: [] for u in _BV_URGENCY_ORDER}
        for w in kept:
            urg = (w.get("urgency") or "").strip()
            if urg not in by_urgency:
                continue  # defensive: schema rejects bogus values, but be safe
            by_urgency[urg].append(w)
        for urg in _BV_URGENCY_ORDER:
            items = by_urgency.get(urg) or []
            if not items:
                continue
            cls = _BV_URGENCY_CSS_CLASS[urg]
            heading = _BV_URGENCY_HEADING_UA[urg]
            li_parts: list[str] = []
            for w in items:
                trigger = _h(w.get("trigger_ua") or "")
                action = _h(w.get("action_ua") or "")
                window = w.get("cycle_day_window") or ""
                window_html = (
                    f' <span class="bv-window">({_h(window)})</span>'
                    if window else ""
                )
                li_parts.append(
                    "<li>"
                    f'<span class="bv-trigger">{trigger}</span>{window_html}'
                    f' — <span class="bv-action">{action}</span>'
                    "</li>"
                )
            groups_html.append(
                f'<div class="{cls}">'
                f"<h3>{_h(heading)}</h3>"
                f'<ul>{"".join(li_parts)}</ul>'
                "</div>"
            )

        track_blocks.append(
            f'<div class="bv-track" data-source-id="{_h(regimen_id)}">'
            f'<p class="track-label">{_h(title_ua)}</p>'
            f'{"".join(groups_html)}'
            "</div>"
        )

    return (
        '<section class="between-visits">'
        "<h2>На що звернути увагу між візитами</h2>"
        f'{"".join(track_blocks)}'
        "</section>"
    )


def _render_emergency_section(plan_result: PlanResult) -> str:
    """Filter the plan's red flags and render emergency-tier ones as a
    `<section class="emergency-signals">` with one banner item per RF.
    Renders an empty-state placeholder when no emergency RFs apply, so
    the section is always present in the bundle (assertable structural
    contract for downstream tests)."""
    rf_lookup = (plan_result.kb_resolved or {}).get("red_flags") or {}
    emergencies = filter_emergency_rfs(list(rf_lookup.values()))
    if not emergencies:
        return (
            '<section class="emergency-signals">'
            "<h2>Сигнали, що вимагають негайної уваги</h2>"
            '<p class="patient-badge patient-good">'
            "Наразі немає термінових сигналів — продовжуйте планові візити."
            "</p>"
            "</section>"
        )
    items: list[str] = []
    for rf in emergencies:
        # data-rf-id keeps the engine ID accessible to debug tooling /
        # tests, but the visible text is generated solely from the
        # patient_emergency_label() output.
        rf_id = (rf.get("id") or "") if isinstance(rf, dict) else ""
        label = patient_emergency_label(rf)
        items.append(
            f'<li data-rf-id="{_h(rf_id)}">{_h(label)}</li>'
        )
    return (
        '<section class="emergency-signals">'
        "<h2>Сигнали, що вимагають негайної уваги</h2>"
        '<p>Якщо у вас з\'явилися ці симптоми — зверніться у лікарню '
        "негайно, не чекайте планового візиту:</p>"
        f'<ul class="emergency-list">{"".join(items)}</ul>'
        "</section>"
    )


def _render_ask_doctor_section(plan_result: PlanResult) -> str:
    """Build the 'про що варто запитати лікаря' block.

    Pulls a plan dict (model_dump) and decorates it with derived flags
    that the predicates in `_ask_doctor.py` look for (recommended_drugs,
    plan_tracks, etc.). The decoration keeps the predicates simple
    while still surfacing oop-drug / multi-track / germline-variant
    contingent questions."""
    plan = plan_result.plan
    plan_dict: dict = plan.model_dump() if plan is not None else {}

    # Decorate with the derived fields the predicates expect. We don't
    # mutate the persisted Plan — `model_dump()` returns a fresh dict.
    drugs_lookup = (plan_result.kb_resolved or {}).get("drugs") or {}
    disease_data = (plan_result.kb_resolved or {}).get("disease") or {}
    disease_names = disease_data.get("names") if isinstance(disease_data, dict) else None

    recommended: list[dict] = []
    seen: set[str] = set()
    if plan is not None:
        for t in plan.tracks:
            # Iterate via _iter_regimen_components — phase-aware fallback;
            # see helper docstring. The decorated `recommended_drugs` feeds
            # _ask_doctor predicates, which must surface every drug across
            # phases (lymphodepletion + main for axi-cel, etc.).
            for comp in _iter_regimen_components(t.regimen_data):
                did = comp.get("drug_id") or ""
                if not did or did in seen:
                    continue
                seen.add(did)
                drug = drugs_lookup.get(did) or {}
                nszu_status: str = ""
                if isinstance(drug, dict) and drug:
                    try:
                        b = lookup_nszu_status(
                            drug,
                            plan_result.disease_id or "",
                            disease_names=disease_names if isinstance(disease_names, dict) else None,
                        )
                        nszu_status = b.status
                    except Exception:
                        nszu_status = ""
                recommended.append({
                    "drug_id": did,
                    "name": _patient_drug_label(drug, did),
                    "drug_class": (drug.get("drug_class") if isinstance(drug, dict) else None),
                    "nszu_status": nszu_status,
                })

    plan_dict["recommended_drugs"] = recommended
    plan_dict["plan_tracks"] = list(plan_dict.get("tracks") or [])

    questions = _select_ask_doctor_questions(plan_dict, target_count=6)
    if not questions:
        return ""
    items = "".join(f"<li>{_h(q['question_ua'])}</li>" for q in questions)
    return (
        '<div class="ask-doctor">'
        "<h2>Про що варто запитати лікаря</h2>"
        f"<ul>{items}</ul>"
        "</div>"
    )


_PATIENT_DISCLAIMER_HTML = (
    "<p>Цей звіт — інформаційний інструмент, не медичний прилад. Усі рішення "
    "про лікування приймає ваш онколог. Звіт оновлюється, коли з'являються "
    "нові аналізи. Не змінюйте призначене лікування на основі лише цього звіту.</p>"
    "<p>Якщо у вас виникли термінові симптоми, перелічені вище — звертайтесь у "
    "лікарню негайно, не чекайте планового візиту.</p>"
    "<p>Питання про сам інструмент: "
    '<a href="https://github.com/romeo111/OpenOnco/issues">github.com/romeo111/OpenOnco</a></p>'
)


def _render_patient_mode(
    plan_result: PlanResult,
    target_lang: str,
    *,
    sibling_link: Optional[str] = None,
) -> str:
    """Render a Plan as a plain-Ukrainian patient-facing single-file HTML.

    `target_lang` is currently honoured only for the document `<html lang>`
    attribute — the body stays Ukrainian per the patient-mode spec. EN
    patient bundles are out of scope for the current iteration
    (PATIENT_MODE_SPEC §9).

    `sibling_link` populates the cross-link chip in the header
    (PATIENT_MODE_SPEC §3.5). Set by the CLI when `--render-mode both`
    or by web embeds; otherwise None to suppress the chip."""
    plan = plan_result.plan
    if plan is None:
        return _patient_doc_shell(
            "Ваш персональний онкологічний план",
            '<p>Поки що недостатньо даних для побудови плану. '
            'Зверніться до вашого онколога для уточнення.</p>',
        )

    disease_label = _patient_disease_label(plan_result)
    body_parts: list[str] = []

    # Header (PATIENT_MODE_SPEC §3.1 + §3.5)
    cross_link = _render_mode_toggle(sibling_link, "Технічна версія для лікаря →")
    body_parts.append(
        "<header>"
        "<h1>Ваш персональний план</h1>"
        '<p class="patient-subhead">Що показав аналіз і що це означає для вас</p>'
        f'<p><strong>Діагноз:</strong> {_h(disease_label)}</p>'
        f'{cross_link}'
        "</header>"
    )

    body_parts.append(
        '<section class="what-was-found">'
        "<h2>Що знайдено в результаті</h2>"
        f"{_render_findings_plain(plan_result)}"
        "</section>"
    )

    body_parts.append(
        '<section class="what-now">'
        "<h2>Що це означає для лікування</h2>"
        f"{_render_tracks_plain(plan_result)}"
        "</section>"
    )

    body_parts.append(_render_why_section(plan_result))
    body_parts.append(_render_between_visits_section(plan_result))

    body_parts.append(_render_emergency_section(plan_result))
    body_parts.append(_render_ask_doctor_section(plan_result))

    body_parts.append(
        f'<footer class="patient-disclaimer">{_PATIENT_DISCLAIMER_HTML}</footer>'
    )

    return _expand_first_use(
        _patient_doc_shell(
            "Ваш персональний онкологічний план",
            "".join(body_parts),
        )
    )


# ── Diagnostic Brief render ───────────────────────────────────────────────


def render_diagnostic_brief_html(
    diag_result: DiagnosticPlanResult,
    mdt: Optional[MDTOrchestrationResult] = None,
    *,
    target_lang: str = "uk",
    strict_citation_guard: bool = False,
) -> str:
    """Render a DiagnosticPlanResult as a single-file HTML document.

    `strict_citation_guard` is plumbed for signature consistency with
    `render_plan_html`. Diagnostic-brief blocks (workup steps, mandatory
    questions) don't carry source citations in the same shape as
    Regimen/Indication/BMA, so the guard currently has no in-band
    effect — added so callers can pass a single flag through any render
    entry point."""
    _ = strict_citation_guard  # reserved for future diagnostic guard
    dp = diag_result.diagnostic_plan
    if dp is None:
        return _doc_shell("OpenOnco — empty diagnostic brief", "<p>Empty DiagnosticPlanResult.</p>")

    body: list[str] = []

    # Header
    body.append(
        '<div class="doc-header">'
        '<div class="doc-label">OpenOnco · Workup Brief · DIAGNOSTIC PHASE</div>'
        '<div class="doc-title">Brief підготовки до тумор-борду</div>'
        f'<div class="doc-sub">{_h(dp.id)} · v{_h(dp.version)} · {_h(dp.generated_at[:10])}</div>'
        '</div>'
    )

    # MANDATORY diagnostic banner (CHARTER §15.2 C7)
    body.append(
        '<div class="banner banner--diagnostic">'
        '<strong>⚠ DIAGNOSTIC PHASE — TREATMENT PLAN NOT YET APPLICABLE</strong>'
        f'{_h(_DIAGNOSTIC_BANNER)}'
        '</div>'
    )

    # Patient + suspicion strip
    susp = diag_result.suspicion or dp.suspicion_snapshot
    susp_html = ""
    if susp:
        tissues = ", ".join(susp.tissue_locations) if susp.tissue_locations else "—"
        hyps = ", ".join(susp.working_hypotheses) if susp.working_hypotheses else "—"
        susp_html = (
            '<div class="patient-strip">'
            '<div class="label">Patient</div>'
            f'<div class="value">{_h(dp.patient_id)} · suspicion lineage: {_h(susp.lineage_hint)}</div>'
            f'<div class="value" style="margin-top:6px;font-size:13px;color:var(--gray-700);">'
            f'Tissues: {_h(tissues)} · Hypotheses: {_h(hyps)}</div>'
        )
        if susp.presentation:
            susp_html += f'<div class="value" style="margin-top:6px;font-size:13px;color:var(--gray-700);">{_h(susp.presentation)}</div>'
        susp_html += "</div>"
    body.append(susp_html)

    # Matched workup
    body.append(
        f'<div class="banner banner--info">'
        f'<strong>Matched workup:</strong> {_h(diag_result.matched_workup_id)} · '
        f'<strong>Очікуваний термін:</strong> ~{_h(dp.expected_timeline_days)} днів'
        '</div>'
    )

    # Workup steps
    steps_html = []
    for s in dp.workup_steps:
        cat_badge = f'<span class="badge badge--{_h(s.category)}">{_h(s.category)}</span> '
        descr = s.description or s.test_id or "?"
        rationale = (
            f'<div class="step-rationale">{_h(s.rationale)}</div>' if s.rationale else ""
        )
        biopsy = ""
        if s.biopsy_approach:
            biopsy = (
                f'<div class="step-rationale" style="margin-top:6px;">'
                f'<strong>Biopsy preferred:</strong> {_h(s.biopsy_approach.preferred)}'
                f'</div>'
            )
        ihc = ""
        if s.ihc_panel and s.ihc_panel.baseline:
            ihc = (
                f'<div class="step-rationale" style="margin-top:4px;">'
                f'<strong>IHC baseline:</strong> {_h(", ".join(s.ihc_panel.baseline))}'
                f'</div>'
            )
        steps_html.append(
            f'<li>'
            f'<span class="step-num">{_h(s.step)}</span>'
            f'<span class="step-name">{cat_badge}{_h(descr)}</span>'
            f'{rationale}'
            f'{biopsy}'
            f'{ihc}'
            f'</li>'
        )
    body.append(
        f'<section><h2>Workup steps ({len(dp.workup_steps)})</h2>'
        f'<ul class="steps">{"".join(steps_html)}</ul></section>'
    )

    # Mandatory questions
    if dp.mandatory_questions:
        items = "".join(f"<li>{_h(q)}</li>" for q in dp.mandatory_questions)
        body.append(
            f'<section><h2>Питання що мають бути закриті ({len(dp.mandatory_questions)})</h2>'
            f'<ul style="padding-left:20px;font-size:14px;line-height:1.7;color:var(--gray-700);">{items}</ul></section>'
        )

    # MDT brief
    body.append(_render_mdt_section(mdt, target_lang))

    # Footer
    body.append('<div class="doc-footer">')
    body.append(_render_version_chain(
        dp.id, dp.version, dp.supersedes, dp.superseded_by, dp.generated_at,
    ))
    body.append(_render_fda_disclosure(dp.intended_use))
    body.append(_render_fda_disclosure(dp.automation_bias_warning))
    body.append(f'<div class="medical-disclaimer">{_h(_MEDICAL_DISCLAIMER)}</div>')
    body.append('</div>')

    out = _doc_shell("OpenOnco · Workup Brief", "".join(body))
    return _localize_html(out, target_lang)


# ── Revision Note render ──────────────────────────────────────────────────


def render_revision_note_html(
    previous: Union[PlanResult, DiagnosticPlanResult],
    new_result: Union[PlanResult, DiagnosticPlanResult],
    transition: str,
    mdt: Optional[MDTOrchestrationResult] = None,
    *,
    target_lang: str = "uk",
    strict_citation_guard: bool = False,
) -> str:
    """Renders a revision note: shows transition + prev/new IDs, then
    renders the new result inline (so reviewer sees the latest state).

    `strict_citation_guard` is forwarded to the inner Plan / Diagnostic
    render so revision notes inherit the same warn/strict policy."""

    prev_id = (
        previous.diagnostic_plan.id if isinstance(previous, DiagnosticPlanResult)
        and previous.diagnostic_plan
        else (previous.plan.id if isinstance(previous, PlanResult) and previous.plan else "?")
    )
    new_id = (
        new_result.diagnostic_plan.id if isinstance(new_result, DiagnosticPlanResult)
        and new_result.diagnostic_plan
        else (new_result.plan.id if isinstance(new_result, PlanResult) and new_result.plan else "?")
    )
    new_trigger = ""
    if isinstance(new_result, PlanResult) and new_result.plan:
        new_trigger = new_result.plan.revision_trigger or ""
    elif isinstance(new_result, DiagnosticPlanResult) and new_result.diagnostic_plan:
        new_trigger = new_result.diagnostic_plan.revision_trigger or ""

    body: list[str] = []
    body.append(
        '<div class="doc-header">'
        '<div class="doc-label">OpenOnco · Revision Note</div>'
        '<div class="doc-title">Перегляд плану</div>'
        f'<div class="doc-sub">Transition: {_h(transition)} · {_h(_now_iso())}</div>'
        '</div>'
    )

    body.append(
        '<div class="banner banner--info">'
        f'<strong>Previous:</strong> {_h(prev_id)} → <strong>New:</strong> {_h(new_id)}<br>'
        f'<strong>Trigger:</strong> {_h(new_trigger or "(not specified)")}'
        '</div>'
    )

    # Inline render of the NEW result (delegate). The inner render handles
    # localization itself; here we render in UA and let the outer wrap
    # localize the entire revision-note HTML in one pass.
    if isinstance(new_result, DiagnosticPlanResult):
        inner = render_diagnostic_brief_html(
            new_result, mdt=mdt, target_lang="uk",
            strict_citation_guard=strict_citation_guard,
        )
    else:
        inner = render_plan_html(
            new_result, mdt=mdt, target_lang="uk",
            strict_citation_guard=strict_citation_guard,
        )
    start = inner.find('<div class="page">')
    end = inner.rfind('</div>\n</body>')
    if start >= 0 and end >= 0:
        body.append(inner[start + len('<div class="page">'):end])
    else:
        body.append(inner)

    out = _doc_shell("OpenOnco · Revision Note", "".join(body))
    return _localize_html(out, target_lang)


# ── Polymorphic dispatch ──────────────────────────────────────────────────


def render(
    result: Union[PlanResult, DiagnosticPlanResult],
    mdt: Optional[MDTOrchestrationResult] = None,
    *,
    target_lang: str = "uk",
    strict_citation_guard: bool = False,
) -> str:
    """Auto-dispatch by result type."""
    if isinstance(result, DiagnosticPlanResult):
        return render_diagnostic_brief_html(
            result, mdt=mdt, target_lang=target_lang,
            strict_citation_guard=strict_citation_guard,
        )
    return render_plan_html(
        result, mdt=mdt, target_lang=target_lang,
        strict_citation_guard=strict_citation_guard,
    )


__all__ = [
    "render",
    "render_diagnostic_brief_html",
    "render_plan_html",
    "render_revision_note_html",
]
