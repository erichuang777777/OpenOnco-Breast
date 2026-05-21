# -*- coding: utf-8 -*-
"""Static-site builder for the OpenOnco GitHub Pages landing.

Two goals (per user direction):

  1. Explain the project + show numerical metrics already achieved
     (KB scope, per-disease coverage, sources, etc.) — public landing.
  2. Let any visitor manually input a virtual patient profile and get
     a generated Plan back, in-browser, no backend.

The interactive engine demo (`try.html`) runs the real Python engine
in the browser via Pyodide:

    Pyodide loads → micropip installs pydantic + pyyaml → we unpack a
    zip of knowledge_base/ into the Pyodide filesystem → user submits
    patient JSON → generate_plan(...) runs → rendered HTML lands in
    an iframe.

Layout produced:

  docs/
    .nojekyll                      # disable Jekyll
    style.css                      # shared landing/gallery styles
    index.html                     # public landing (hero + stats + comparison)
    gallery.html                   # 7 pre-generated sample cases
    try.html                       # interactive Pyodide demo
    cases/<case-id>.html           # one rendered Plan / Diagnostic Brief
    openonco-engine-core.zip       # core engine + shared KB for Pyodide
    openonco-engine-index.json     # disease_id → per-disease bundle URL map
    disease/openonco-<slug>.zip    # per-disease KB modules (lazy-loaded)
    examples.json                  # dropdown payload for try.html

No real patient data ever flows here — only synthetic seed cases under
examples/, guarded by CHARTER §9.3.

Usage:

    python -m scripts.build_site [--output docs/] [--clean]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_base.engine import (
    generate_diagnostic_brief,
    generate_plan,
    is_diagnostic_profile,
    orchestrate_mdt,
    render_diagnostic_brief_html,
    render_plan_html,
)
from knowledge_base.clients.ctgov_client import search_trials
from knowledge_base import __version__ as OPENONCO_VERSION
from knowledge_base import __release_date__ as OPENONCO_RELEASE_DATE
from knowledge_base.stats import collect_stats
from scripts.audit_clinical_gaps import write_outputs as write_clinical_gap_outputs
from scripts.build_kb_wiki import build_kb_wiki
from scripts.site_cases import (
    BROKEN_CASE_IDS,
    CASE_CATEGORIES,
    CASES,
    GALLERY_EXCLUDED_CASE_IDS,
    GALLERY_FEATURED_CASE_IDS,
    CaseEntry,
)
from scripts.site_head import SITE_FAVICON_LINK, SITE_FONT_LINK, finalize_site_discovery
from scripts.site_styles import STYLESHEET as _STYLE_CSS


KB_ROOT = REPO_ROOT / "knowledge_base" / "hosted" / "content"
EXAMPLES = REPO_ROOT / "examples"
CTGOV_CACHE = KB_ROOT / "cache" / "ctgov"

GH_REPO = "romeo111/OpenOnco"
GH_NEW_ISSUE = f"https://github.com/{GH_REPO}/issues/new"

# Custom apex domain on GitHub Pages. The build writes a CNAME file every
# run so wiping docs/ via --clean never breaks the binding.
CUSTOM_DOMAIN = "openonco.info"



# ── Engine bundling for Pyodide ───────────────────────────────────────────


# What we ship to the browser. Engine code + schemas + validation + content.
# Excludes: code_systems/civic/ctcae (huge, not referenced at runtime),
# clients/, ingestion/ (need network), __pycache__, *.pyc.
_BUNDLE_INCLUDE_DIRS = [
    "engine",
    "schemas",
    "validation",
    "hosted/content",
]
_BUNDLE_INCLUDE_FILES = ["__init__.py"]


# Entity directories whose YAMLs are *split out* into per-disease modules
# when they tie to a specific disease via disease_id /
# applicable_to_disease / applicable_to.disease_id / relevant_diseases.
# Files from these dirs that don't resolve to any single disease (e.g.
# universal redflags, cross-disease indications) stay in core.
_DISEASE_SCOPED_DIRS = {
    "indications",
    "algorithms",
    "regimens",
    "redflags",
    "biomarker_actionability",
    "questionnaires",  # disease_id present in every questionnaire; moves ~155 KB compressed out of core
}


def _disease_id_for_yaml(yaml_text: str, arc_path: str) -> str | None:
    """Best-effort: which disease does this YAML belong to?

    Mirrors scripts/profile_engine_bundle.py — same heuristic — so the
    profile and the actual split agree. Returns None when:
      - the YAML doesn't pin to a single disease (universal RFs,
        cross-disease indications), OR
      - the file lives under diseases/ (handled separately — disease
        metadata always stays in core).
    """
    import re as _re
    if "/diseases/" in arc_path:
        # Disease metadata always stays in core, never sharded.
        return None
    m = _re.search(
        r"^\s*disease_id\s*:\s*(DIS-[A-Z0-9_-]+)", yaml_text, _re.MULTILINE,
    )
    if m:
        return m.group(1).upper()
    m = _re.search(
        r"^\s*applicable_to_disease\s*:\s*(DIS-[A-Z0-9_-]+)",
        yaml_text, _re.MULTILINE,
    )
    if m:
        return m.group(1).upper()
    m = _re.search(
        r"applicable_to\s*:\s*\n[\s\S]{0,400}?disease_id\s*:\s*(DIS-[A-Z0-9_-]+)",
        yaml_text,
    )
    if m:
        return m.group(1).upper()
    # redflags: relevant_diseases — only attribute when it pins to a
    # single concrete disease. Universal / multi-disease RFs stay in core.
    # Handles both inline list `[DIS-X]` and block-list format.
    m = _re.search(
        r"^relevant_diseases\s*:\s*\[([^\]]+)\]",
        yaml_text, _re.MULTILINE,
    )
    if m:
        items = [t.strip() for t in m.group(1).split(",") if t.strip()]
        dis = [t.upper() for t in items if t.upper().startswith("DIS-")]
        if len(dis) == 1:
            return dis[0]
    m = _re.search(
        r"^relevant_diseases\s*:\s*\n((?:\s*-\s*\S+\s*\n)+)",
        yaml_text, _re.MULTILINE,
    )
    if m:
        diseases = []
        for line in m.group(1).splitlines():
            tok = line.strip().lstrip("-").strip()
            if tok and tok != "*" and tok.upper().startswith("DIS-"):
                diseases.append(tok.upper())
        if len(diseases) == 1:
            return diseases[0]
    return None


def _disease_bundle_basename(disease_id: str) -> str:
    """`DIS-DLBCL-NOS` → `openonco-dis-dlbcl-nos.zip`. Used both for the
    file name on disk and for the URL in the bundle index."""
    slug = disease_id.lower().replace("_", "-")
    return f"openonco-{slug}.zip"


def _icd_to_disease_id_map() -> dict[str, str]:
    """Walk knowledge_base/hosted/content/diseases/*.yaml and produce a
    `{ICD-O-3 morphology code: DIS-...}` map. Shipped in the bundle index
    so the JS lazy-loader can resolve a `disease_id` from the patient's
    `disease.icd_o_3_morphology` without round-tripping into Pyodide."""
    import yaml as _yaml
    src = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "diseases"
    out: dict[str, str] = {}
    if not src.is_dir():
        return out
    for path in sorted(src.glob("*.yaml")):
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        did = data.get("id")
        code = (data.get("codes") or {}).get("icd_o_3_morphology")
        if did and code:
            out[str(code)] = str(did).upper()
    return out


def _gather_engine_entries() -> list[tuple[Path, str, str | None]]:
    """Walk knowledge_base/ and produce (source_path, archive_name,
    attributed_disease_id) tuples for every file that belongs in any
    bundle. attributed_disease_id is None for files that go in core.
    Code, schemas, validation, and shared content are always None.

    Explicitly excluded from all bundles:
    - ``hosted/content/cache/`` — ClinicalTrials.gov HTTP response caches
      written by the ingestion pipeline. These are build-time artefacts and
      must not be shipped to browsers.
    """
    src = REPO_ROOT / "knowledge_base"
    entries: list[tuple[Path, str, str | None]] = []

    for fname in _BUNDLE_INCLUDE_FILES:
        p = src / fname
        if p.is_file():
            entries.append((p, f"knowledge_base/{fname}", None))

    for sub in _BUNDLE_INCLUDE_DIRS:
        sub_root = src / sub
        if not sub_root.is_dir():
            continue
        for path in sub_root.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            rel = str(path.relative_to(src)).replace("\\", "/")
            if rel.startswith("hosted/content/cache/"):
                continue
            arcname = "knowledge_base/" + rel

            attributed: str | None = None
            # Only YAML under hosted/content/<disease-scoped-dir>/ is
            # eligible to be sharded out.
            if path.suffix == ".yaml":
                parts = arcname.split("/")
                # parts: knowledge_base, hosted, content, <entity_dir>, ...
                if (
                    len(parts) >= 5
                    and parts[1] == "hosted"
                    and parts[2] == "content"
                    and parts[3] in _DISEASE_SCOPED_DIRS
                ):
                    try:
                        text = path.read_text(encoding="utf-8")
                    except OSError:
                        text = ""
                    attributed = _disease_id_for_yaml(text, arcname)

            entries.append((path, arcname, attributed))
    return entries


def bundle_engine(output_dir: Path) -> dict:
    """Build the Pyodide-loadable engine bundles.

    Produces (in `output_dir/`):

      1. `openonco-engine-core.zip` — code + schemas + validation +
         shared content (drugs, sources, biomarkers, tests,
         supportive_care, monitoring, workups, contraindications,
         mdt_skills, diseases, plus universal redflags and any
         indications/algorithms/regimens/RFs/BMAs/questionnaires
         that don't pin to a single disease). /try.html fetches this
         first — small enough to make the page interactive quickly.

      2. `disease/openonco-{slug}.zip` per disease — the disease-scoped
         indications, algorithms, regimens, redflags, and BMA cells.
         Fetched on demand once the patient's `disease_id` is known.

      3. `openonco-engine-index.json` — `{core, core_version, diseases,
         disease_versions, icd_to_disease_id}`. /try.html consults this
         to pick the per-disease bundle once `disease_id` is known.

    CSD-9C (2026-04-27): the legacy monolithic `openonco-engine.zip`
    has been retired. Lazy-load (CSD-5B + CSD-6E) is the canonical
    path — the monolithic bundle had crossed the 3 MB ceiling and was
    only kept as a safety fallback. Any stale monolithic on disk is
    cleaned up so deploys don't carry the old file forever.

    ``hosted/content/cache/`` (ClinicalTrials.gov HTTP response caches)
    is excluded from all bundles — see ``_gather_engine_entries``.

    Returns a dict whose `core_version` field is a 12-char SHA-256
    prefix of the core zip — used as a `?v=...` cache-buster on the
    Pyodide fetch so users always get fresh bundles on KB updates.
    """
    import hashlib

    core_zip = output_dir / "openonco-engine-core.zip"
    disease_dir = output_dir / "disease"
    index_path = output_dir / "openonco-engine-index.json"
    legacy_monolithic = output_dir / "openonco-engine.zip"

    disease_dir.mkdir(parents=True, exist_ok=True)

    # CSD-9C: clean up any stale monolithic bundle from previous builds.
    if legacy_monolithic.exists():
        legacy_monolithic.unlink()

    entries = _gather_engine_entries()
    # Deterministic order — same input → same zip → same SHA-256.
    entries.sort(key=lambda e: e[1])

    # Bucket by destination.
    core_entries: list[tuple[Path, str]] = []
    by_disease: dict[str, list[tuple[Path, str]]] = {}
    for path, arcname, disease in entries:
        if disease is None:
            core_entries.append((path, arcname))
        else:
            by_disease.setdefault(disease, []).append((path, arcname))

    # 1. Core bundle.
    core_files = 0
    core_uncompressed = 0
    with zipfile.ZipFile(core_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in core_entries:
            zf.write(path, arcname)
            core_files += 1
            core_uncompressed += path.stat().st_size
    core_bytes = core_zip.read_bytes()
    core_version = hashlib.sha256(core_bytes).hexdigest()[:12]

    # 2. Per-disease bundles. Wipe stale ones first so disease renames
    # don't leave orphans under docs/disease/.
    for stale in disease_dir.glob("openonco-*.zip"):
        stale.unlink()

    disease_meta: dict[str, dict] = {}
    for disease_id, items in sorted(by_disease.items()):
        out_name = _disease_bundle_basename(disease_id)
        out_path = disease_dir / out_name
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, arcname in items:
                zf.write(path, arcname)
        b = out_path.read_bytes()
        disease_meta[disease_id] = {
            "url": f"disease/{out_name}",
            "files": len(items),
            "compressed_bytes": out_path.stat().st_size,
            "version": hashlib.sha256(b).hexdigest()[:12],
        }

    # 3. Bundle index — what /try.html consults to know which
    # per-disease module to fetch once disease_id is known.
    index_payload = {
        "core": "openonco-engine-core.zip",
        "core_version": core_version,
        "diseases": {
            did: meta["url"] for did, meta in sorted(disease_meta.items())
        },
        "disease_versions": {
            did: meta["version"] for did, meta in sorted(disease_meta.items())
        },
        # CSD-6E: client-side ICD-O-3 → disease_id resolution. The /try.html
        # JS uses this so it can pick the per-disease bundle from a profile
        # whose only disease hint is `disease.icd_o_3_morphology`.
        "icd_to_disease_id": _icd_to_disease_id_map(),
    }
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "core_zip": str(core_zip.relative_to(output_dir)),
        "core_files": core_files,
        "core_uncompressed_bytes": core_uncompressed,
        "core_compressed_bytes": core_zip.stat().st_size,
        "core_version": core_version,
        # `version` retained as alias for `core_version` — older callers
        # (try.html cache-buster wiring) still reference it as a generic
        # "current bundle version" stamp.
        "version": core_version,
        "disease_bundles": disease_meta,
        "index": str(index_path.relative_to(output_dir)),
    }


def write_service_worker(output_dir: Path, *, core_version: str = "") -> dict:
    """Write `docs/sw.js` — a tiny cache-first service worker for the
    bundle artifacts. Stores responses in a versioned `CacheStorage`
    bucket keyed by `core_version`, so a KB push (which rotates the
    SHA-256 prefix) automatically invalidates stale bundles on next
    fetch. CSD-6E polish — speeds up cold loads on repeat visits past
    what localStorage can hold (entire core + all visited diseases)."""
    # 'l3' = navigation network-first. Bumping the layout prefix forces
    # a hard cache invalidation for users whose browser still has an old
    # service worker/cache after a landing-page redesign.
    cache_name = "openonco-bundle-l3-" + (core_version or "v1")
    sw_js = """// OpenOnco bundle service worker (CSD-6E + CSD-11A swr)
// Two strategies in one SW:
//   1. Cache-first for engine bundle artifacts (large, infrequent).
//   2. Stale-while-revalidate for try.html + style.css — repeat visits
//      paint instantly from cache while a fresh copy fetches in the
//      background, so the dropdowns aren't gated on the HTML download.
// Cache name is stamped with the core bundle's SHA-256 prefix so a KB
// push automatically rotates the cache key.
const CACHE_NAME = '__CACHE_NAME__';
const PRECACHE = [
  '/manifest.webmanifest',
  '/logo.svg',
  '/favicon.svg',
  '/openonco-engine-index.json',
  '/openonco-engine-core.zip',
  '/try.html',
  '/ukr/try.html',
  '/style.css',
];
// Routes that use stale-while-revalidate (instant from cache, refresh
// in background). HTML pages must be on this list — never cache-first,
// or the user gets stuck on an old build.
const SWR_PATHS = ['/try.html', '/ukr/try.html', '/about.html', '/ukr/about.html', '/style.css'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // Precache best-effort: don't fail the SW install if a single
      // file 404s (e.g. an old deploy that hasn't shipped the index yet).
      Promise.all(PRECACHE.map((u) => cache.add(u).catch(() => null)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k.startsWith('openonco-bundle-') && k !== CACHE_NAME)
            .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

function staleWhileRevalidate(event) {
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request, { ignoreSearch: true }).then((hit) => {
        const network = fetch(event.request).then((resp) => {
          if (resp && resp.ok) cache.put(event.request, resp.clone());
          return resp;
        }).catch(() => hit);
        return hit || network;
      })
    )
  );
}

function networkFirstNavigation(event) {
  event.respondWith(
    fetch(event.request, { cache: 'no-store' }).catch(() =>
      caches.match(event.request, { ignoreSearch: true })
    )
  );
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  if (event.request.mode === 'navigate') {
    return networkFirstNavigation(event);
  }

  // SWR for the small interactive shell (HTML + CSS).
  if (SWR_PATHS.indexOf(url.pathname) !== -1) {
    return staleWhileRevalidate(event);
  }

  // Cache-first for the heavy engine bundles.
  const cacheFirstMatch =
    url.pathname.endsWith('/openonco-engine-core.zip') ||
    url.pathname.endsWith('/openonco-engine-index.json') ||
    url.pathname.startsWith('/disease/openonco-');
  if (!cacheFirstMatch) return;
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request, { ignoreSearch: true }).then((hit) =>
        hit || fetch(event.request).then((resp) => {
          if (resp && resp.ok) {
            const clone = resp.clone();
            cache.put(event.request, clone);
          }
          return resp;
        })
      )
    )
  );
});
""".replace("__CACHE_NAME__", cache_name)
    out = output_dir / "sw.js"
    out.write_text(sw_js, encoding="utf-8")
    return {"path": "sw.js", "cache_name": cache_name}


def write_web_manifest(output_dir: Path) -> dict:
    """Write the PWA manifest for the static try-page app shell."""
    manifest = {
        "id": "/try.html",
        "name": "OpenOnco Try",
        "short_name": "OpenOnco",
        "description": (
            "In-browser OpenOnco demo for synthetic oncology profiles. "
            "The engine runs locally in Pyodide."
        ),
        "start_url": "/try.html",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f8faf8",
        "theme_color": "#0a2e1a",
        "orientation": "any",
        "categories": ["medical", "education", "productivity"],
        "icons": [
            {
                "src": "/logo.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            },
            {
                "src": "/favicon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any",
            },
        ],
    }
    out = output_dir / "manifest.webmanifest"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": "manifest.webmanifest", "start_url": manifest["start_url"]}


def _public_case_entries() -> list[CaseEntry]:
    """Cases safe to expose through gallery, examples, and static case pages.

    Excludes only genuinely broken cases. Gallery-only-hidden cases still
    get their case HTML built so the /try.html example picker can iframe
    a real generated plan when the user loads them.
    """
    return [c for c in CASES if c.case_id not in BROKEN_CASE_IDS]


def _public_example_entries() -> list[CaseEntry]:
    """Curated examples safe for the try-page picker.

    Auto-generated stubs and variant-matrix smoke cases are useful for
    engine/render QA, but they read as stale low-fill clinical examples in
    the public picker. Keep them out of /try.html and examples.json.

    The picker is intentionally more permissive than the case gallery: it
    only filters out genuinely broken cases (BROKEN_CASE_IDS) and noisy
    auto/variant smoke entries. Cases that are merely curated out of the
    gallery (GALLERY_ONLY_HIDDEN_CASE_IDS — e.g. HCC patient cases without
    ESCAT BMA) still show here so every supported disease has at least
    one usable load-example entry.
    """

    return [
        c for c in CASES
        if c.case_id not in BROKEN_CASE_IDS
        and c.badge_class != "bdg-stub"
        and c.badge.lower() not in {"auto-stub", "variant"}
        and not c.case_id.startswith(("auto-", "variant-"))
    ]


def _case_quality_meta(c: CaseEntry, *, has_case_page: bool) -> dict:
    """Display-only quality tier for public example pickers.

    This does not certify clinical review; it keeps intentionally broad
    starter profiles visually separate from curated showcase/demo plans.
    """
    cid = c.case_id.lower()
    filename = c.file.lower()
    if not has_case_page:
        return {
            "quality_rank": 50,
            "quality_tier": "starter",
            "quality_label": "Старт для форми",
            "quality_label_en": "Form starter",
            "quality_class": "quality-starter",
        }
    if cid.startswith("showcase-"):
        return {
            "quality_rank": 0,
            "quality_tier": "showcase",
            "quality_label": "Кураторський showcase",
            "quality_label_en": "Curated showcase",
            "quality_class": "quality-showcase",
        }
    if cid.startswith("diagnostic-"):
        return {
            "quality_rank": 10,
            "quality_tier": "diagnostic",
            "quality_label": "Діагностичний brief",
            "quality_label_en": "Diagnostic brief",
            "quality_class": "quality-diagnostic",
        }
    if cid.startswith("coverage-") or filename.startswith("patient_coverage_"):
        return {
            "quality_rank": 30,
            "quality_tier": "coverage",
            "quality_label": "Перевірений coverage-план",
            "quality_label_en": "Engine-verified coverage plan",
            "quality_class": "quality-curated",
        }
    if cid.startswith("auto-") or cid.startswith("variant-") or filename.startswith(("auto_", "variant_")):
        return {
            "quality_rank": 40,
            "quality_tier": "starter",
            "quality_label": "Стартовий профіль",
            "quality_label_en": "Coverage starter",
            "quality_class": "quality-starter",
        }
    return {
        "quality_rank": 20,
        "quality_tier": "curated",
        "quality_label": "Кураторський план",
        "quality_label_en": "Curated plan",
        "quality_class": "quality-curated",
    }


def _example_display_labels(
    c: CaseEntry,
    ex_json: dict,
    disease_id: str | None,
    *,
    has_case_page: bool,
) -> tuple[str, str]:
    """Return picker labels that are readable to users, not generator names."""
    label_en = c.label_en or c.label_ua
    label_ua = c.label_ua
    cid = c.case_id.lower()
    filename = c.file.lower()
    generated = (
        not has_case_page
        or cid.startswith("auto-")
        or cid.startswith("variant-")
        or filename.startswith("auto_")
        or filename.startswith("variant_")
        or "auto-stub" in label_en.lower()
        or "auto-stub" in label_ua.lower()
    )
    if not generated:
        return label_ua, label_en

    disease_names = _load_disease_name_map().get(str(disease_id or "").upper()) or {}
    disease = ex_json.get("disease", {}) if isinstance(ex_json, dict) else {}
    disease_label_ua = (
        disease_names.get("ua")
        or disease.get("name_uk")
        or disease.get("name")
        or disease_id
        or c.case_id
    )
    disease_label_en = (
        disease_names.get("en")
        or disease.get("name_en")
        or disease.get("name")
        or disease_id
        or c.case_id
    )

    # For variant_* files, append a human-readable qualifier derived from the
    # filename suffix so that all variants of the same disease get distinct labels
    # (e.g. "Chronic Myeloid Leukemia · frail patient" instead of seven identical
    # "Chronic Myeloid Leukemia · coverage starter" entries).
    _VARIANT_SUFFIX_MAP = {
        "frail": "frail patient",
        "high_risk": "high risk",
        "relapsed_2l": "relapsed 2L",
        "relapsed_3l": "relapsed 3L",
        "biomarker_act": "biomarker-driven",
        "infection_hbv": "HBV+",
        "organ_dysf": "organ dysfunction",
        "biomarker": "biomarker-driven",
        "high_burden": "high burden",
        "transplant_eligible": "transplant-eligible",
        "transplant_ineligible": "transplant-ineligible",
        "fit": "fit",
        "unfit": "unfit",
        "elderly": "elderly",
        "young_fit": "young/fit",
    }
    variant_qualifier = ""
    fname_stem = c.file.lower().removesuffix(".json")
    if fname_stem.startswith("variant_"):
        # Strip "variant_<disease-slug>_" prefix → remainder is the variant suffix
        parts = fname_stem.split("_", 2)  # ["variant", "<disease>", "<suffix>"]
        if len(parts) == 3:
            raw_suffix = parts[2]
            variant_qualifier = _VARIANT_SUFFIX_MAP.get(raw_suffix) or raw_suffix.replace("_", " ")

    if has_case_page:
        if variant_qualifier:
            return (
                f"{disease_label_ua} · {variant_qualifier}",
                f"{disease_label_en} · {variant_qualifier}",
            )
        return (
            f"{disease_label_ua} · стартовий профіль",
            f"{disease_label_en} · coverage starter",
        )
    return (
        f"{disease_label_ua} · старт для форми",
        f"{disease_label_en} · form starter",
    )


def _example_sort_key(entry: dict) -> tuple:
    return (
        str(entry.get("disease_id") or entry.get("disease_icd") or "ZZZ"),
        int(entry.get("quality_rank", 99)),
        str(entry.get("label_en") or entry.get("label") or "").casefold(),
        str(entry.get("case_id") or ""),
    )


def _remove_excluded_case_pages(output_dir: Path) -> int:
    """Delete stale generated pages for broken/auto-stub cases.

    Gallery-only-hidden cases still get their case HTML built (see
    _public_case_entries), so we must not delete them here.
    """
    removed = 0
    for case_id in sorted(BROKEN_CASE_IDS):
        for rel_path in (
            Path("cases") / f"{case_id}.html",
            Path("ukr") / "cases" / f"{case_id}.html",
        ):
            path = output_dir / rel_path
            if path.exists():
                path.unlink()
                removed += 1
    return removed


def bundle_examples(
    output_dir: Path,
    questionnaires_manifest: list[dict] | None = None,
) -> dict:
    """Write docs/examples.json — array of {label, json} entries used as
    the 'Load example' dropdown on try.html.

    Also extracts a thin manifest (label + disease_icd only, ~10× smaller)
    used by /try.html for instant dropdown population. Full payload is
    lazy-fetched only when a user actually picks an example.
    """
    payload = []
    manifest = []
    unique_icd_to_disease_id = _unique_questionnaire_icd_to_disease_id_map()

    def append_case(c: CaseEntry, *, has_case_page: bool) -> str | None:
        p = EXAMPLES / c.file
        if not p.exists():
            return None
        ex_json = json.loads(p.read_text(encoding="utf-8"))
        disease = ex_json.get("disease", {}) if isinstance(ex_json, dict) else {}
        disease_icd = disease.get("icd_o_3_morphology")
        disease_id = (
            disease.get("id")
            or ex_json.get("disease_id")
            or unique_icd_to_disease_id.get(str(disease_icd))
        )
        if disease_id and isinstance(ex_json, dict):
            ex_json.setdefault("disease_id", disease_id)
            disease = ex_json.setdefault("disease", {})
            if isinstance(disease, dict):
                disease.setdefault("id", disease_id)
        # Both UA and EN labels travel in the manifest so the inlined
        # JS constant on /try.html (UA) vs /ukr/try.html — wait, EN is
        # at root → /try.html serves EN labels — can pick the right
        # one per page locale at render time.
        label_ua, label_en = _example_display_labels(
            c, ex_json, disease_id, has_case_page=has_case_page
        )
        quality_meta = _case_quality_meta(c, has_case_page=has_case_page)
        payload_entry = {
            "case_id": c.case_id,
            "label": label_ua,
            "label_en": label_en,
            "disease_id": disease_id,
            "file": c.file,
            "json": ex_json,
            **quality_meta,
        }
        manifest_entry = {
            "case_id": c.case_id,
            "label": label_ua,
            "label_en": label_en,
            "disease_id": disease_id,
            "disease_icd": disease_icd,
            **quality_meta,
        }
        if not has_case_page:
            payload_entry["has_case_page"] = False
            manifest_entry["has_case_page"] = False
        payload.append(payload_entry)
        manifest.append(manifest_entry)
        return disease_id

    for c in _public_example_entries():
        append_case(c, has_case_page=True)

    payload.sort(key=_example_sort_key)
    manifest.sort(key=_example_sort_key)

    out = output_dir / "examples.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "path": "examples.json",
        "count": len(payload),
        "manifest": manifest,
    }


# Universal screening fields injected into every questionnaire at bundle
# time. Audit 2026-04-27 found ~200 RF-disease evaluations were blocked
# because these clinically-universal data points (TB screening, LVEF,
# etc.) were absent from the per-disease questionnaire YAMLs. Rather
# than copy-paste these into 65 questionnaires, the build prepends a
# single "General screening" group at JSON serialisation time. Each
# field is `recommended` (not `critical`) so users can leave it blank
# without blocking the Generate button. RF triggers reference these
# field names directly — no alias needed.
_COMMON_SCREENING_GROUP = {
    "title": "General screening (optional)",
    "description": (
        "Universal fields for fitness assessment, infection status, and organ function. "
        "Fill in whatever is in the chart — empty fields are simply not evaluated by the "
        "engine (replaces 'unevaluated RedFlag' warnings)."
    ),
    "questions": [
        {"field": "findings.lvef_percent", "label": "LVEF (%) — echocardiography",
         "type": "float", "impact": "recommended", "range_min": 10, "range_max": 80,
         "units": "%", "helper": "Before anthracyclines / HER2 agents / alkylating agents — baseline LVEF required."},
        {"field": "findings.active_tb", "label": "Active tuberculosis?",
         "type": "boolean", "impact": "recommended",
         "helper": "Screening before IO / steroids / alloSCT. Quantiferon or screening chest X-ray."},
        {"field": "findings.latent_tb", "label": "Latent TB (Quantiferon+ / IGRA+)?",
         "type": "boolean", "impact": "recommended"},
        {"field": "findings.active_uncontrolled_infection", "label": "Active uncontrolled infection?",
         "type": "boolean", "impact": "recommended",
         "helper": "Any sepsis / pneumonia / uncontrolled fungal infection — treatment delay required."},
        {"field": "findings.albumin_g_dl", "label": "Albumin",
         "type": "float", "impact": "recommended", "range_min": 1.0, "range_max": 6.0,
         "units": "g/dL"},
        {"field": "findings.bilirubin_uln_x", "label": "Total bilirubin (× ULN)",
         "type": "float", "impact": "recommended", "range_min": 0.1, "range_max": 20.0,
         "units": "× upper limit of normal",
         "helper": "Most regimens require bili ≤1.5×ULN; FDA approvals commonly express this in multiples of ULN."},
        {"field": "findings.dlco_percent", "label": "DLCO (% of predicted)",
         "type": "float", "impact": "recommended", "range_min": 10, "range_max": 150,
         "units": "%", "helper": "DLCO <50% — bleomycin contraindicated (cHL ABVD); <40% — caution with CAR-T."},
        {"field": "findings.qtc_ms", "label": "QTc (ms) on ECG",
         "type": "integer", "impact": "recommended", "range_min": 300, "range_max": 700,
         "units": "ms",
         "helper": "QTc >480 → caution with venetoclax, crizotinib, apalutamide, FLT3i."},
        {"field": "findings.potassium_mmol_l", "label": "Potassium",
         "type": "float", "impact": "recommended", "range_min": 1.5, "range_max": 8.0,
         "units": "mmol/L"},
        {"field": "findings.uric_acid_mg_dl", "label": "Uric acid",
         "type": "float", "impact": "recommended", "range_min": 1, "range_max": 20,
         "units": "mg/dL",
         "helper": "Elevated level + bulky disease → TLS risk, rasburicase required."},
        {"field": "findings.tls_active", "label": "Active tumour lysis syndrome?",
         "type": "boolean", "impact": "recommended"},
        {"field": "findings.comorbidity_count", "label": "Number of significant comorbidities",
         "type": "integer", "impact": "recommended", "range_min": 0, "range_max": 20,
         "helper": "Heart failure / COPD / cirrhosis / CKD / diabetes etc. Driver for frailty score."},
        {"field": "findings.charlson_score", "label": "Charlson Comorbidity Index",
         "type": "integer", "impact": "recommended", "range_min": 0, "range_max": 30,
         "helper": "0-1 fit, 2-3 intermediate, ≥4 frail (for elderly + solid tumours)."},
        {"field": "findings.g8_score", "label": "G8 Geriatric Screening (0-17)",
         "type": "integer", "impact": "recommended", "range_min": 0, "range_max": 17,
         "helper": "≤14 — full geriatric assessment required before intensive chemotherapy."},
        {"field": "findings.child_pugh_class", "label": "Child-Pugh class (liver)",
         "type": "enum", "impact": "recommended",
         "options": [
             {"value": "A", "label": "A — compensated"},
             {"value": "B", "label": "B — moderately decompensated"},
             {"value": "C", "label": "C — decompensated"},
         ],
         "helper": "Only if cirrhosis / liver disease present. B/C — excludes most regimens."},
        {"field": "findings.rapid_progression", "label": "Rapid progression (rapid volume increase / new symptoms)?",
         "type": "boolean", "impact": "recommended",
         "helper": "Driver for intensification in aggressive lymphomas / CAR-T bridging."},
        {"field": "findings.new_metastatic_disease", "label": "New metastatic disease on repeat scan?",
         "type": "boolean", "impact": "recommended"},
        {"field": "findings.hcv_rna", "label": "HCV RNA (for patients with anti-HCV+)",
         "type": "enum", "impact": "recommended",
         "options": [
             {"value": "negative", "label": "Negative / below LOD"},
             {"value": "positive", "label": "Positive (active HCV)"},
         ]},
        {"field": "findings.hiv_status", "label": "HIV status",
         "type": "enum", "impact": "recommended",
         "options": [
             {"value": "negative", "label": "Negative"},
             {"value": "positive", "label": "Positive"},
         ]},
        {"field": "findings.peripheral_neuropathy_grade", "label": "Pre-existing peripheral neuropathy (CTCAE)",
         "type": "enum", "impact": "recommended",
         "options": [
             {"value": 0, "label": "0 — none"},
             {"value": 1, "label": "1 — minimal"},
             {"value": 2, "label": "2 — limits ADL"},
             {"value": 3, "label": "3 — severe"},
             {"value": 4, "label": "4 — disabling"},
         ],
         "helper": "Grade ≥3 — bortezomib SC, vincristine, oxaliplatin, cisplatin contraindicated."},
        {"field": "findings.nyha_class", "label": "NYHA class (heart failure)",
         "type": "enum", "impact": "recommended",
         "options": [
             {"value": "I", "label": "I — no limitation"},
             {"value": "II", "label": "II — mild limitation"},
             {"value": "III", "label": "III — marked limitation"},
             {"value": "IV", "label": "IV — symptoms at rest"},
         ],
         "helper": "Only if HF history present. NYHA III/IV — anthracyclines / trastuzumab contraindicated."},
        {"field": "findings.hemoglobin_g_dl", "label": "Haemoglobin",
         "type": "float", "impact": "recommended", "range_min": 3, "range_max": 22,
         "units": "g/dL"},
        {"field": "findings.wbc_k_ul", "label": "WBC (×10⁹/L)",
         "type": "float", "impact": "recommended", "range_min": 0, "range_max": 1000,
         "units": "×10⁹/L",
         "helper": "Hyperleukocytosis (>50-100) — risk of leukostasis in AML/ALL/CML-blast."},
        {"field": "findings.uncontrolled_hypertension", "label": "Uncontrolled hypertension?",
         "type": "boolean", "impact": "recommended",
         "helper": "Contraindicated / use with caution with VEGF inhibitors (bevacizumab, sunitinib, lenvatinib)."},
    ],
}


def _inject_common_screening(quest: dict) -> dict:
    """Append the universal screening group to a questionnaire's groups
    list at bundle time, unless the YAML already has a group with the
    same title (idempotent — manual customisation wins)."""
    groups = list(quest.get("groups") or [])
    title = _COMMON_SCREENING_GROUP["title"]
    if any(g.get("title") == title for g in groups):
        return quest
    groups.append(_COMMON_SCREENING_GROUP)
    return {**quest, "groups": groups}


_STUB_TITLE_NOTICE_RE = re.compile(r"\s*\(auto-generated STUB\)\s*", re.IGNORECASE)


def _clean_questionnaire_title(title: object) -> str:
    """Public display title without internal scaffold notices."""
    cleaned = _STUB_TITLE_NOTICE_RE.sub("", str(title or "")).strip()
    return cleaned.replace("HCV-asociated", "HCV-associated")


def _stringify_code(code: object) -> str:
    if isinstance(code, list):
        return ", ".join(str(item) for item in code if item)
    return str(code or "").strip()


def _questionnaire_display_titles(
    data: dict,
    disease_names_by_id: dict[str, dict],
) -> dict[str, str]:
    title_en = _clean_questionnaire_title(data.get("title"))
    names = disease_names_by_id.get(data.get("disease_id")) or {}
    disease_uk = names.get("ukrainian")
    if not disease_uk:
        return {"title_en": title_en, "title_uk": title_en}

    if "— newly diagnosed (1L)" in title_en:
        title_uk = f"{disease_uk} — вперше діагностована (1L)"
    elif "— first line" in title_en:
        title_uk = f"{disease_uk} — перша лінія"
    else:
        title_uk = disease_uk
    return {"title_en": title_en, "title_uk": title_uk}


def bundle_questionnaires(output_dir: Path) -> dict:
    """Pre-render all curated Questionnaire YAML files to a single
    JSON file at docs/questionnaires.json + thin manifest for /try.html.

    Manifest carries only the dropdown-needed fields (id + title +
    disease_id + disease_icd) — ~30× smaller than the full payload — so
    /try.html populates dropdowns instantly. Full payload is lazy-fetched
    only after the user selects a questionnaire.

    Each questionnaire is post-processed by `_inject_common_screening`
    so universal fields (LVEF, TB, child-pugh, etc.) appear without
    every disease YAML having to copy them.
    """
    qsrc = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "questionnaires"
    payload = []
    manifest = []
    if qsrc.is_dir():
        import yaml as _yaml
        disease_names_by_id = {}
        disease_codes_by_id = {}
        dsrc = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "diseases"
        if dsrc.is_dir():
            for dpath in sorted(dsrc.glob("*.yaml")):
                try:
                    disease = _yaml.safe_load(dpath.read_text(encoding="utf-8"))
                    if isinstance(disease, dict) and disease.get("id"):
                        disease_names_by_id[disease["id"]] = disease.get("names") or {}
                        disease_codes_by_id[disease["id"]] = disease.get("codes") or {}
                except Exception:
                    continue
        for path in sorted(qsrc.glob("*.yaml")):
            try:
                data = _yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data = _inject_common_screening(data)
                    display_titles = _questionnaire_display_titles(data, disease_names_by_id)
                    disease_codes = disease_codes_by_id.get(data.get("disease_id")) or {}
                    disease_icd = (
                        (data.get("fixed_fields") or {})
                        .get("disease", {})
                        .get("icd_o_3_morphology")
                    )
                    data = {**data, "title": display_titles["title_en"]}
                    payload.append(data)
                    manifest.append({
                        "id": data.get("id"),
                        "title": data.get("title"),
                        **display_titles,
                        "disease_id": data.get("disease_id"),
                        "icd_10": _stringify_code(disease_codes.get("icd_10")),
                        "disease_icd": disease_icd,
                    })
            except Exception:
                continue
    out = output_dir / "questionnaires.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "path": "questionnaires.json",
        "count": len(payload),
        "manifest": manifest,
    }


# ── Landing page (index.html) ─────────────────────────────────────────────


_NAV_LABELS = {
    "uk": {"home": "Головна", "about": "Про проєкт", "try_cta": "План лікування",
           "diseases": "Хвороби", "ask": "Туморборд", "kb": "Онко-вікі",
           "prevent": "Профілактика"},
    "en": {"home": "Home", "about": "About", "try_cta": "Plan Builder",
           "diseases": "Diseases", "ask": "Tumor Board", "kb": "Onco Wiki",
           "prevent": "Prevention"},
}


def _lang_switch_href(page_kind: str, target_lang: str, case_id: str = "") -> str:
    """Build the URL the language-toggle should point to.

    page_kind: 'home' | 'gallery' | 'try' | 'ask' | 'case' | 'capabilities' | 'about' | 'contribute' | 'diseases'
    target_lang: UA-side render asks where the EN mirror lives;
                 EN-side render asks where the UA mirror lives.

    Site layout: EN is the default at root (/), UA lives at /ukr/.
    Uses root-relative absolute paths so any nesting depth resolves
    correctly on openonco.info."""
    uk_prefix = "/ukr"
    if target_lang == "uk":
        # UA page (at /ukr/...) → switcher points to EN mirror at root
        if page_kind == "home":         return "/"
        if page_kind == "gallery":      return "/gallery.html"
        if page_kind == "try":          return "/try.html"
        if page_kind == "ask":          return "/ask.html"
        if page_kind == "case":         return f"/cases/{case_id}.html"
        if page_kind == "capabilities": return "/capabilities.html"
        if page_kind == "about":        return "/about.html"
        if page_kind == "diseases":     return "/diseases.html"
        if page_kind == "contribute":   return "/"
        if page_kind == "specs":        return "/specs.html"
    else:
        # EN page (at root) → switcher points to UA mirror at /ukr/
        if page_kind == "home":         return f"{uk_prefix}/"
        if page_kind == "gallery":      return f"{uk_prefix}/gallery.html"
        if page_kind == "try":          return f"{uk_prefix}/try.html"
        if page_kind == "ask":          return f"{uk_prefix}/ask.html"
        if page_kind == "case":         return f"{uk_prefix}/cases/{case_id}.html"
        if page_kind == "capabilities": return f"{uk_prefix}/capabilities.html"
        if page_kind == "about":        return f"{uk_prefix}/about.html"
        if page_kind == "diseases":     return f"{uk_prefix}/diseases.html"
        if page_kind == "contribute":   return f"{uk_prefix}/"
        if page_kind == "specs":        return f"{uk_prefix}/specs.html"
    return "/"


def _render_top_bar(active: str = "", target_lang: str = "en",
                    lang_switch_href: str = "/ukr/") -> str:
    """Top navigation bar with:
    - brand on the left → links to home
    - reading-only nav (Home, Capabilities, Onco Wiki, Tumor Board, About)
      in the middle
    - language switcher (UA / EN toggle) on the right
    - prominent action buttons on the far right (Plan Builder, Onco Wiki, Tumor Board)

    Per user direction: 'Спробувати' is an action and gets a separate CTA
    button styled distinctly from the nav links.

    Site layout: EN is the default at root (/), UA lives at /ukr/."""
    def cls(name: str) -> str:
        return ' class="active"' if active == name else ""

    labels = _NAV_LABELS.get(target_lang, _NAV_LABELS["en"])
    home_path = "/ukr/" if target_lang == "uk" else "/"
    try_path = "/ukr/try.html" if target_lang == "uk" else "/try.html"
    ask_path = "/ukr/ask.html" if target_lang == "uk" else "/ask.html"
    about_path = "/ukr/about.html" if target_lang == "uk" else "/about.html"

    # Capabilities now folds in the former Limitations section. GitHub,
    # Examples and Specs are grouped under About to keep the main nav focused.
    extra_links = ""
    if target_lang == "uk":
        extra_links = (
            f'<a href="/ukr/capabilities.html"{cls("capabilities")}>Можливості</a>'
        )
    else:  # target_lang == "en"
        extra_links = (
            f'<a href="/capabilities.html"{cls("capabilities")}>Capabilities</a>'
        )

    # Stable visual order is always [UA · EN] regardless of which language
    # is current — clicking the toggle must NOT swap pill positions, only
    # which one is highlighted (CSS .lang-current vs .lang-other).
    is_uk = target_lang == "uk"
    ua_cls = "lang-current" if is_uk else "lang-other"
    en_cls = "lang-other" if is_uk else "lang-current"
    # Tags: <span> for the current pill (no link), <a> for the other.
    ua_tag, ua_attr = ("span", "") if is_uk else ("a", f' href="{lang_switch_href}"')
    en_tag, en_attr = ("a", f' href="{lang_switch_href}"') if is_uk else ("span", "")

    kb_href = "/ukr/kb.html" if target_lang == "uk" else "/kb.html"
    kb_current = ' aria-current="page"' if active in {"kb", "diseases"} else ""
    ask_current = ' aria-current="page"' if active == "ask" else ""
    try_current = ' aria-current="page"' if active == "try" else ""
    prevent_href = "/ukr/prevent.html" if target_lang == "uk" else "/prevent.html"
    prevent_current = ' aria-current="page"' if active == "prevent" else ""

    return f"""<header class="top-bar">
  <div class="brand-line">
    <a href="{home_path}" class="brand-mini">OpenOnco</a>
  </div>
  <nav class="top-nav">
    <a href="{home_path}"{cls("home")}>{labels['home']}</a>
    {extra_links}
    <a href="{about_path}"{cls("about")}>{labels['about']}</a>
  </nav>
  <div class="top-right">
    <div class="lang-switch" role="group" aria-label="Language">
      <{ua_tag} class="{ua_cls}"{ua_attr}><span class="lang-flag flag-ua" aria-hidden="true"></span>UA</{ua_tag}>
      <{en_tag} class="{en_cls}"{en_attr}><span class="lang-flag flag-en" aria-hidden="true"></span>EN</{en_tag}>
    </div>
    <div class="top-cta-group">
      <a href="{try_path}" class="btn-cta-top btn-cta-try"{try_current}>{labels['try_cta']}</a>
      <a href="{prevent_href}" class="btn-cta-top btn-cta-secondary"{prevent_current}>{labels['prevent']}</a>
      <a href="{kb_href}" class="btn-cta-top btn-cta-secondary"{kb_current}>{labels['kb']}</a>
      <a href="{ask_path}" class="btn-cta-top btn-cta-secondary"{ask_current}>{labels['ask']}</a>
    </div>
  </div>
</header>"""


def _landing_stat_counts(stats) -> dict[str, int]:
    by_type = {e.type: e.count for e in stats.entities}
    return {
        "diseases": by_type.get("diseases", 0),
        "redflags": by_type.get("redflags", 0),
        "indications": by_type.get("indications", 0),
        "regimens": by_type.get("regimens", 0),
        "algorithms": by_type.get("algorithms", 0),
        "sources": by_type.get("sources", 0),
        "drugs": by_type.get("drugs", 0),
    }


def _render_landing_v2(stats, *, target_lang: str = "en") -> str:
    counts = _landing_stat_counts(stats)
    is_en = target_lang == "en"

    if is_en:
        title = "OpenOnco — oncology decisions you can audit"
        kicker = "Open-source clinical decision support"
        h1 = "Cross-checks NCCN, ESMO, and drug labels for you — so you verify, not research."
        sub = (
            f"One JSON patient profile in, a standard <em>and</em> an aggressive treatment "
            f"plan out — side by side, with a citation under every recommendation. The engine "
            f"reads {counts['sources']} sources for you and surfaces {counts['redflags']} "
            f"red flags worth a second look.",
            "Rules-first, not LLM-driven. The plan cannot hallucinate a drug or a dose. "
            "The clinical decision stays with you; the engine is the second pair of eyes "
            "that read every guideline at once.",
        )
        primary = "Try the plan builder"
        secondary = "See a sample plan →"
        tertiary = "Ask the AI Tumor Board"
        gallery_href = "/gallery.html"
        diseases_href = "/diseases.html"
        note = "Open-data inputs: CIViC (CC0) for biomarker actionability, ClinicalTrials.gov for trial-aware options, PubMed/PMID/DOI and DailyMed/openFDA for literature and drug-label context. No LLM chooses treatment: plans are rules-first with YAML provenance, so LLM hallucinations are excluded from the plan. The clinician remains the final authority (CHARTER §11)."
        footer = "Informational tool for clinicians, not a medical device (CHARTER §15 + §11)."
        try_href = "/try.html"
        kb_href = "/kb.html"
        ask_href = "/ask.html"
        about_href = "/about.html"
        stats_label = "Knowledge base scale"
        stat_labels = {
            "diseases": "Diseases",
            "indications": "Indications",
            "regimens": "Regimens",
            "redflags": "Red flags",
            "sources": "Cited sources",
            "perf": "Per profile",
        }
        pillars_label = "What OpenOnco does for the clinician"
        pillar_time_h = "Saves the routine work"
        pillar_time_sub = (
            "Five tabs collapse into one. The engine does the cross-checking so you can "
            "spend the time on the call, not the lookup."
        )
        pillar_time_cards = [
            ("Pass", "One pass replaces five tabs",
             "The engine resolves NCCN, ESMO, drug labels, and CIViC actionability in a "
             "single pass. No more switching between guidelines, label PDFs, and biomarker "
             "databases for each case."),
            ("Cite", "Citations attached automatically",
             "Every line in the plan ships with the PMID, DOI, DailyMed link, or guideline "
             "section. You verify in 10 seconds instead of running a literature search to "
             "back up each recommendation."),
            ("Sync", f"{counts['sources']} sources refreshed for you",
             "NCCN, ESMO, EHA, BSH, EASL, MoH, WHO, CTCAE, FDA, CIViC — refreshed on a "
             "schedule. No more monitoring every guideline update yourself to know what "
             "changed since last quarter."),
            ("Pair", "Standard + aggressive built together",
             "Both alternatives are generated side by side every time — you don't manually "
             "construct the second option to weigh against the first. CHARTER §15.2 C6: the "
             "alternative is never buried."),
        ]
        pillar_miss_h = "Surfaces what's easy to overlook"
        pillar_miss_sub = (
            "The engine is a checklist that runs against every profile. It cannot replace "
            "clinical judgment — but it can stop a tired Friday afternoon from missing a "
            "contraindication."
        )
        pillar_miss_cards = [
            ("Flag", f"{counts['redflags']} red flags worth a second look",
             "Drug interactions, contraindications, organ-function thresholds, high-risk "
             "cytogenetics, bulky disease — every red flag fires automatically against the "
             "profile and surfaces in the plan for review."),
            ("Match", "Targetable mutations don't slip past",
             "CIViC actionability lookup is fusion-aware. A BRAF V600E or a BCR::ABL1 "
             "finding maps to ESCAT-tier evidence before it can quietly disappear into a "
             "long workup report."),
            ("Rules", "No hallucinated drugs or doses",
             "The plan is assembled by a declarative rule engine, not by an LLM. A drug "
             "must exist in the KB with a real label entry; a dose must come from a curated "
             "Regimen YAML. No creative invention."),
            ("Ask", "Refuses to default silently",
             "When the profile lacks data — missing cytogenetics, no ECOG, incomplete "
             "biomarker panel — the engine emits an Open Question instead of guessing. "
             "CHARTER §15.2 C6: anti automation-bias is mandatory."),
        ]
        cta_doors_label = "Where to go next"
        cta_doors = [
            ("btn-primary", try_href, "Build a plan from a case"),
            ("btn-secondary", ask_href, "Ask the AI Tumor Board"),
            ("btn-secondary", kb_href, "Browse Onco Wiki"),
        ]
        perf_value = "~200"
        perf_unit = "ms"
        carousel_label = "Audience"
        carousel_slides = [
            {
                "key": "doctor",
                "tab": "For clinicians",
                "eyebrow": "Clinical workflow",
                "title": "From structured case facts to a cited plan draft.",
                "body": (
                    "OpenOnco gives the oncologist a transparent second layer for MDT prep: "
                    "standard and aggressive tracks, red flags, dose context, source IDs and "
                    "review status in one view."
                ),
                "items": [
                    "Two-track treatment plan: guideline-grade and trial-aware",
                    "Biomarker, renal, hepatic and infection risks surfaced before sign-off",
                    "Every branch remains auditable by source and YAML provenance",
                ],
                "href": try_href,
                "cta": "Build a virtual plan",
            },
            {
                "key": "investor",
                "tab": "For investors",
                "eyebrow": "Infrastructure thesis",
                "title": "A governed open layer for oncology decision infrastructure.",
                "body": (
                    "The asset is not a chatbot wrapper. It is a growing clinical knowledge graph, "
                    "rules engine, public specification stack and distribution path for hospitals, "
                    "labs and AI-assisted contributors."
                ),
                "items": [
                    "Public corpus, rules engine and specs evolve as separate auditable assets",
                    "Clear non-device CDS positioning and visible clinical review gates",
                    "Open corpus creates trust, auditability and ecosystem leverage",
                ],
                "href": about_href,
                "cta": "Review the project",
            },
            {
                "key": "lab",
                "tab": "For laboratories",
                "eyebrow": "Molecular handoff",
                "title": "Make biomarker reports immediately actionable for the care team.",
                "body": (
                    "A lab can hand clinicians a structured bridge from NGS and pathology findings "
                    "to disease-specific actionability, trial-aware options and patient-profile "
                    "prefill without exposing private data on the public site."
                ),
                "items": [
                    "Variant and biomarker context connects to disease, regimen and monitoring",
                    "QR/profile handoff can prefill the browser-side plan builder",
                    "CIViC-derived evidence remains citable and inspectable",
                ],
                "href": kb_href,
                "cta": "Explore actionability",
            },
            {
                "key": "patient",
                "tab": "For patients",
                "eyebrow": "Patient-facing explanation",
                "title": "A clearer version of the plan to discuss with the doctor.",
                "body": (
                    "OpenOnco can render the same clinical logic in plain language: what the "
                    "plan is trying to do, why tests and biomarkers matter, and what questions "
                    "the patient should bring back to the oncology team."
                ),
                "items": [
                    "Plain-language summary without changing the clinician-owned decision",
                    "Helps patients understand biomarkers, monitoring and warning signs",
                    "Keeps the doctor as the final authority for treatment choices",
                ],
                "href": try_href,
                "cta": "See a patient-friendly plan",
            },
        ]
    else:
        title = "OpenOnco — онкологічні рішення, які можна перевірити"
        kicker = "Відкрита підтримка клінічних рішень"
        h1 = "Звіряє за вас NCCN, ESMO і label-и — ви перевіряєте, не досліджуєте."
        sub = (
            f"Один JSON-профіль пацієнта на вході — план standard <em>і</em> aggressive "
            f"поруч, із цитатою під кожною рекомендацією. Engine читає за вас "
            f"{counts['sources']} джерела і виносить на огляд {counts['redflags']} red flag, "
            f"які варті повторного погляду.",
            "Rules-first, а не LLM. План не може «вигадати» препарат чи дозу. "
            "Клінічне рішення лишається за вами; engine — це друга пара очей, "
            "що читає всі гайдлайни одночасно.",
        )
        primary = "Спробувати конструктор плану"
        secondary = "Подивитися приклад плану →"
        tertiary = "Запитати AI-туморборд"
        gallery_href = "/ukr/gallery.html"
        diseases_href = "/ukr/diseases.html"
        note = "Відкриті джерела: CIViC (CC0) для біомаркерної клінічної значущості, ClinicalTrials.gov для trial-aware опцій, PubMed/PMID/DOI та DailyMed/openFDA для літератури й контексту інструкцій до препаратів. LLM не обирає лікування: план збирається rules-first із YAML provenance, тому LLM-галюцинації виключені з плану. Фінальне рішення лишається за лікарем (CHARTER §11)."
        footer = "Це інформаційний інструмент для лікаря, не медичний пристрій (CHARTER §15 + §11)."
        try_href = "/ukr/try.html"
        kb_href = "/ukr/kb.html"
        ask_href = "/ukr/ask.html"
        about_href = "/ukr/about.html"
        stats_label = "Масштаб бази знань"
        stat_labels = {
            "diseases": "Хвороби",
            "indications": "Показання",
            "regimens": "Режими",
            "redflags": "Red flag",
            "sources": "Цитованих джерел",
            "perf": "На профіль",
        }
        pillars_label = "Що OpenOnco робить для лікаря"
        pillar_time_h = "Економить рутинну роботу"
        pillar_time_sub = (
            "П'ять вкладок згортаються в один прохід. Engine робить крос-чек, а ви "
            "витрачаєте час на саме рішення, а не на пошук джерел."
        )
        pillar_time_cards = [
            ("Pass", "Один прохід замість п'яти вкладок",
             "Engine за один прохід розв'язує NCCN, ESMO, інструкції до препаратів і "
             "CIViC-actionability. Більше не треба перемикатися між гайдлайнами, "
             "label-PDF і базами біомаркерів для кожного кейсу."),
            ("Cite", "Цитати додаються автоматично",
             "Кожен рядок плану несе PMID, DOI, посилання на DailyMed або секцію "
             "гайдлайну. Ви перевіряєте за 10 секунд, а не запускаєте літ. пошук, "
             "щоб обґрунтувати кожну рекомендацію."),
            ("Sync", f"{counts['sources']} джерела оновлюються за вас",
             "NCCN, ESMO, EHA, BSH, EASL, МОЗ, WHO, CTCAE, FDA, CIViC — оновлюються "
             "за розкладом. Більше не треба самостійно моніторити кожен апдейт "
             "гайдлайну, щоб знати, що змінилося за останній квартал."),
            ("Pair", "Standard + aggressive будуються разом",
             "Обидві альтернативи генеруються поруч щоразу — ви не будуєте другий "
             "варіант вручну, щоб зважити його проти першого. CHARTER §15.2 C6: "
             "альтернатива ніколи не схована."),
        ]
        pillar_miss_h = "Виносить на огляд те, що легко пропустити"
        pillar_miss_sub = (
            "Engine — це чек-лист, що пробігає кожен профіль. Він не замінює клінічне "
            "судження — але може не дати втомленому п'ятничному вечору пропустити "
            "протипоказання."
        )
        pillar_miss_cards = [
            ("Flag", f"{counts['redflags']} red flag, варті повторного погляду",
             "Drug interactions, протипоказання, пороги органної функції, high-risk "
             "цитогенетика, bulky disease — кожен red flag спрацьовує автоматично "
             "на профілі й виноситься в план для огляду."),
            ("Match", "Таргетні мутації не загубляться",
             "CIViC actionability lookup — fusion-aware. Знахідка BRAF V600E чи "
             "BCR::ABL1 мапиться на ESCAT-tier evidence до того, як могла б тихо "
             "зникнути в довгому workup-звіті."),
            ("Rules", "Жодного «вигаданого» препарату чи дози",
             "План збирається декларативним rule engine, а не LLM. Препарат мусить "
             "існувати в KB зі справжньою label-інструкцією; доза мусить прийти з "
             "кураторського Regimen YAML. Жодного творчого винаходу."),
            ("Ask", "Відмовляється мовчки додумувати",
             "Коли в профілі бракує даних — немає цитогенетики, немає ECOG, неповна "
             "біомаркерна панель — engine видає Open Question замість здогадки. "
             "CHARTER §15.2 C6: anti automation-bias обов'язковий."),
        ]
        cta_doors_label = "Куди далі"
        cta_doors = [
            ("btn-primary", try_href, "Побудувати план із кейсу"),
            ("btn-secondary", ask_href, "Запитати AI-туморборд"),
            ("btn-secondary", kb_href, "Переглянути Онко-вікі"),
        ]
        perf_value = "~200"
        perf_unit = "мс"
        carousel_label = "Аудиторія"
        carousel_slides = [
            {
                "key": "doctor",
                "tab": "Для лікаря",
                "eyebrow": "Клінічний workflow",
                "title": "Від структурованих фактів кейсу до цитованого draft-плану.",
                "body": (
                    "OpenOnco дає онкологу прозорий другий шар для підготовки MDT: стандартний "
                    "і агресивний треки, red flags, контекст дозування, source IDs і статус "
                    "ревʼю в одному вікні."
                ),
                "items": [
                    "Два треки лікування: guideline-grade та trial-aware",
                    "Біомаркери, ниркові, печінкові й інфекційні ризики видно до sign-off",
                    "Кожна гілка аудіюється через джерела та YAML provenance",
                ],
                "href": try_href,
                "cta": "Побудувати віртуальний план",
            },
            {
                "key": "investor",
                "tab": "Для інвестора",
                "eyebrow": "Infrastructure thesis",
                "title": "Керований open layer для онкологічної decision infrastructure.",
                "body": (
                    "Це не wrapper навколо chatbot. Це клінічна knowledge graph, rule engine, "
                    "публічний стек специфікацій і канал дистрибуції для лікарень, лабораторій "
                    "та AI-assisted contributors."
                ),
                "items": [
                    "Публічний корпус, rule engine і specs розвиваються як окремі auditable assets",
                    "Чітке non-device CDS positioning і видимі clinical review gates",
                    "Відкритий корпус створює trust, auditability та ecosystem leverage",
                ],
                "href": about_href,
                "cta": "Подивитись проєкт",
            },
            {
                "key": "lab",
                "tab": "Для лабораторії",
                "eyebrow": "Molecular handoff",
                "title": "Перетворюйте біомаркерні звіти на actionable context для команди.",
                "body": (
                    "Лабораторія може передати лікарю структурований міст від NGS і патології "
                    "до disease-specific actionability, trial-aware опцій і prefill профілю "
                    "пацієнта без приватних даних на публічному сайті."
                ),
                "items": [
                    "Variant і biomarker context звʼязаний із хворобою, режимом і monitoring",
                    "QR/profile handoff може заповнити браузерний plan builder",
                    "CIViC-derived evidence залишається citable та inspectable",
                ],
                "href": kb_href,
                "cta": "Відкрити actionability",
            },
            {
                "key": "patient",
                "tab": "Для пацієнта",
                "eyebrow": "Пояснення для пацієнта",
                "title": "Зрозуміла версія плану для розмови з лікарем.",
                "body": (
                    "OpenOnco може показати ту саму клінічну логіку простою мовою: що "
                    "план має зробити, чому важливі аналізи й біомаркери, і які питання "
                    "пацієнт має повернути онкологічній команді."
                ),
                "items": [
                    "Plain-language summary без заміни рішення лікаря",
                    "Допомагає зрозуміти біомаркери, monitoring і warning signs",
                    "Фінальний вибір лікування залишається за лікарем",
                ],
                "href": try_href,
                "cta": "Подивитись patient-friendly план",
            },
        ]

    carousel_tabs_html = "\n".join(
        f'        <button type="button" class="home-carousel-tab{" is-active" if i == 0 else ""}" '
        f'data-home-slide="{slide["key"]}" aria-controls="home-slide-{slide["key"]}" '
        f'aria-selected="{str(i == 0).lower()}">{slide["tab"]}</button>'
        for i, slide in enumerate(carousel_slides)
    )
    carousel_slides_html = "\n".join(
        f"""        <article class="home-carousel-slide{' is-active' if i == 0 else ''}" id="home-slide-{slide['key']}" data-home-panel="{slide['key']}">
          <p class="home-carousel-eyebrow">{slide['eyebrow']}</p>
          <h2>{slide['title']}</h2>
          <p>{slide['body']}</p>
          <ul>
{chr(10).join(f'            <li>{item}</li>' for item in slide['items'])}
          </ul>
          <a class="home-carousel-cta" href="{slide['href']}">{slide['cta']} →</a>
        </article>"""
        for i, slide in enumerate(carousel_slides)
    )

    sub_paragraphs = sub if isinstance(sub, (list, tuple)) else (sub,)
    sub_html = "\n      ".join(
        f'<p class="home-sub">{paragraph}</p>'
        for paragraph in sub_paragraphs
    )

    def _stat_block(num_html: str, lbl: str, href: str | None = None) -> str:
        inner = (
            f'        <div class="promo-stat-num">{num_html}</div>\n'
            f'        <div class="promo-stat-lbl">{html.escape(lbl)}</div>'
        )
        if href:
            inner = (
                f'        <a class="promo-stat-link" href="{href}">\n'
                f'  {inner}\n'
                '        </a>'
            )
        return (
            '      <div class="promo-stat">\n'
            f'{inner}\n'
            '      </div>'
        )

    stats_html = "\n".join([
        _stat_block(str(counts['diseases']), stat_labels['diseases'], href=diseases_href),
        _stat_block(str(counts['indications']), stat_labels['indications']),
        _stat_block(str(counts['regimens']), stat_labels['regimens']),
        _stat_block(str(counts['redflags']), stat_labels['redflags']),
        _stat_block(str(counts['sources']), stat_labels['sources']),
        _stat_block(
            f'{perf_value}<span class="promo-stat-plus">{html.escape(perf_unit)}</span>',
            stat_labels['perf'],
        ),
    ])

    def _pillar_card_block(tag: str, lbl: str, body: str, *, accent: bool) -> str:
        css = "num-card num-card--accent" if accent else "num-card"
        return (
            f'      <div class="{css}">\n'
            f'        <div class="num-big">{html.escape(tag)}</div>\n'
            f'        <div class="num-lbl">{lbl}</div>\n'
            f'        <p class="num-text">{body}</p>\n'
            '      </div>'
        )

    pillar_time_html = "\n\n".join(
        _pillar_card_block(tag, lbl, body, accent=True)
        for tag, lbl, body in pillar_time_cards
    )
    pillar_miss_html = "\n\n".join(
        _pillar_card_block(tag, lbl, body, accent=False)
        for tag, lbl, body in pillar_miss_cards
    )

    cta_doors_html = "\n      ".join(
        f'<a class="btn {cls}" href="{href}">{html.escape(text)}</a>'
        for cls, href, text in cta_doors
    )

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#14532d">
<meta name="mobile-web-app-capable" content="yes">
<link href="/style.css" rel="stylesheet">
</head>
<body class="home-page">
{_render_top_bar(active="home", target_lang=target_lang, lang_switch_href=_lang_switch_href("home", target_lang))}

<main class="home-main">
  <section class="home-hero">
    <div class="home-hero-inner">
      <p class="home-kicker">{kicker}</p>
      <h1>{h1}</h1>
      {sub_html}
      <div class="cta-row">
        <a class="btn btn-primary" href="{try_href}">{primary}</a>
        <a class="btn btn-secondary" href="{gallery_href}">{secondary}</a>
      </div>
    </div>
  </section>

  <section class="home-stats-band" aria-label="{stats_label}">
    <div class="promo-stats">
{stats_html}
    </div>
  </section>

  <section class="home-pillars" aria-label="{pillars_label}">
    <h2 class="home-pillar-h">{pillar_time_h}</h2>
    <p class="home-pillar-sub">{pillar_time_sub}</p>
    <div class="num-grid num-grid--rich">

{pillar_time_html}

    </div>

    <h2 class="home-pillar-h home-pillar-h--alt">{pillar_miss_h}</h2>
    <p class="home-pillar-sub">{pillar_miss_sub}</p>
    <div class="num-grid num-grid--rich">

{pillar_miss_html}

    </div>
  </section>

  <section class="home-source-band" aria-label="OpenOnco sources">
    <p class="home-note">{note}</p>
  </section>

  <section class="home-cta-doors" aria-label="{cta_doors_label}">
    <div class="cta-row">
      {cta_doors_html}
    </div>
  </section>

  <footer class="page-foot">
    Open-source · MIT-style usage · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    <br>
    {footer}
  </footer>
</main>
</body>
</html>
"""


def render_landing(stats, *, target_lang: str = "en") -> str:
    return _render_landing_v2(stats, target_lang=target_lang)


def render_landing_legacy(stats, *, target_lang: str = "en") -> str:
    # Most corpus-mass cards live on /capabilities.html. The landing pulls
    # only the headline counters (diseases, redflags, indications, regimens,
    # algorithms) so the "Ready for patients today" / "Red flags" cards stay
    # in lock-step with the KB instead of drifting into stale text.
    by_type = {e.type: e.count for e in stats.entities}
    n_diseases = by_type.get("diseases", 0)
    n_redflags = by_type.get("redflags", 0)
    n_indications = by_type.get("indications", 0)
    n_regimens = by_type.get("regimens", 0)
    n_algorithms = by_type.get("algorithms", 0)

    if target_lang == "en":
        hero_h1 = "Open-source infrastructure for oncology clinical decision-making"
        hero_sub = (
            "Get clear, evidence-based treatment strategies in minutes. Upload a patient "
            "profile to receive standard and aggressive options, built on global clinical "
            "guidelines and references. Transparent and based on internationally recognized "
            "standards."
        )
        cta_primary = "Build a plan →"
        cta_secondary = "See examples"
        try_href = "/try.html"
        gallery_href = "/gallery.html"
        capabilities_href = "/capabilities.html"
        how_h2 = "Why it matters and how it works"
        how_lead_1 = (
            "To prescribe a treatment, an oncologist or clinical pharmacologist spends "
            "2–4&nbsp;hours of manual work: opening the NCCN PDF, cross-checking the ESMO "
            "guideline, re-reading the MoH protocol, verifying the national formulary for "
            "drug availability, looking up renal/hepatic dose adjustments, adding "
            "supportive care, remembering vaccinations and opportunistic-infection "
            "prophylaxis. Every time, for every patient, from scratch. Any missed "
            "contraindication can cost a life."
        )
        how_lead_2 = (
            "OpenOnco automates the grunt work: <strong>the logic is the same as a "
            "classic multidisciplinary team (MDT)</strong>, augmented by an analytical "
            "layer. Several specialists around the patient, case discussion, an agreed "
            "plan, return to the case when new data arrives. We simply formalize this as "
            "a structured engine — each &laquo;virtual specialist&raquo; is a versioned "
            "module with its own rules and source list. The clinician receives a ready "
            "draft plan with all citations and only verifies and tunes it for the "
            "specific patient."
        )
        trust_1_strong = "AI is not the doctor."
        trust_1_text = (
            "No LLM decides what to prescribe — clinical logic runs in a declarative "
            "rule engine."
        )
        trust_2_strong = "No external LLM calls"
        trust_2_text = (
            "when a plan is built. Every algorithm is open and auditable line-by-line on "
            "GitHub."
        )
        trust_3_strong = "only to scientific databases"
        trust_3_text_pre = "Lookups go"
        trust_3_text_post = ": PubMed, ClinicalTrials.gov, DailyMed, openFDA, CIViC (CC0), NCCN/ESMO/EHA/ASH/BSH, MoH."
        df_aria = "OpenOnco — data flow from patient profile to two treatment plans"
        df1_title = "Patient profile"
        df1_body = (
            "FHIR R4 / mCODE: diagnosis, stage, histology, biomarkers, labs, prior lines, "
            "comorbidities."
        )
        df1_aria = "Example patient biomarkers"
        df2_title = "Open-standards verification"
        df2_body = (
            "Every diagnosis code, lab value, dose and drug is grounded in a public "
            "international standard. No closed vocabularies."
        )
        df2_aria = "Open standards used for verification"
        df3_title = "Red flags, dose adjustments, links"
        df3_body = (
            "A declarative rule engine surfaces risks, auto-adjusts dosing, and wires "
            "biomarker → drug → monitoring connections."
        )
        df3_li_1 = f"{n_redflags} red flags across {n_diseases} diseases"
        df3_li_2 = "renal / hepatic / age / weight adjustments"
        df3_li_3 = "biomarker ↔ regimen ↔ monitoring"
        df4_title = "Two plans with full citations"
        df4_body = (
            "<strong>Standard</strong> (guideline-grade) + <strong>aggressive</strong> "
            "(trials with higher efficacy). Every claim is a versioned citation. Plans "
            "refresh automatically as new data arrives."
        )
        moh_label = "MoH"
        why_today_h = "Why start using it today"
        why_cards = [
            ("2–4 hours → 5 minutes",
             "Less time on manual NCCN/ESMO/MoH cross-checking, more patients seen. "
             "Fewer missed contraindications, less harm."),
            ("No black box",
             "An LLM is not the decision-maker — a declarative rule engine is, with "
             "public code and a public KB. Plans are built <strong>without external LLM "
             "calls</strong>; only scientific databases (PubMed, ClinicalTrials.gov, "
             "DailyMed, openFDA, CIViC) are queried. The clinician sees every &laquo;why&raquo; "
             "alongside every &laquo;what&raquo;."),
            ("Biomarkers you won&rsquo;t miss",
             "TP53, CD30, MYD88, eGFR, hepatic function — every flag automatically "
             "rewrites the plan: contraindications, dose adjustments, supportive care, "
             "monitoring."),
            ("New data → instant re-check",
             "Fresh labs or clinician decisions update both plans automatically — no "
             "need to re-sweep all the sources by hand."),
            ("MoH registration & NHSU coverage next to every drug",
             "Each drug in the plan is tagged: whether it is registered in Ukraine "
             "(MoH) and whether it is reimbursed by the state medical-guarantees "
             "programme (NHSU). The clinician immediately sees what is free, what is "
             "by prescription, and what has to be sourced separately. Access is "
             "<strong>metadata shown next to the recommendation</strong>, not a filter "
             "— regimen choice is driven by evidence, not by registration status."),
            ("Patient-friendly simplified report",
             "A separate mode generates a plain-language version of the plan for the "
             "patient: no Latin, no acronyms, with explanations of why each step was "
             "chosen and what to watch for between visits. Same plan, two voices — "
             "clinical for the oncologist, human for the patient."),
            ("Free, open, forever",
             "MIT-style. No paywall, no restrictions for public hospitals. Open-source "
             "means it can&rsquo;t quietly disappear or be locked behind investors "
             "tomorrow."),
            ("Ready for patients today",
             f"{n_diseases} diseases, {n_redflags} red flags, {n_indications} indications, "
             f"{n_regimens} regimens, {n_algorithms} treatment algorithms — clinical sign-off "
             "received. The first real-patient plans were rated strong by practising "
             "oncologists. The KB grows weekly, but it is already the densest open "
             "evidence-to-plan layer for Ukrainian oncology that exists. No reason to wait."),
            ("CIViC actionability — fully open, fully citable",
             "Our biomarker-to-drug evidence layer comes from <strong>CIViC (CC0)</strong>, "
             "the Clinical Interpretation of Variants in Cancer at WashU — not OncoKB "
             "(closed, non-commercial-only). The engine reads a nightly YAML snapshot, "
             "matches variants <strong>fusion-aware</strong> (BCR::ABL1, KMT2A rearrangements, "
             "etc.), renders ESCAT-tier as the eye-level signal with CIViC evidence rating "
             "underneath. A monthly CI refresh diffs upstream changes — no silent drift."),
            ("Per-disease coverage matrix — public, honest",
             f"<a href=\"/diseases.html\"><strong>/diseases.html</strong></a> shows, for each "
             f"of the {n_diseases} diseases, exactly what we have: biomarker counts, drugs, "
             "indications, regimens, red flags, 1L/2L algorithm checkmarks, questionnaire "
             "status, fill% and verified%. Grouped by lymphoid heme / myeloid heme / solid "
             "tumours. Same data also exposed as <code>disease_coverage.json</code> for "
             "machine consumption. No «trust us, it's in there» — see the matrix."),
            ("Verify our algorithms with your AI tokens",
             "The remaining bottleneck isn't code — it's two-reviewer sign-off on each "
             "Indication. <strong>TaskTorrent</strong> is our distributed-AI contribution "
             "shelf: maintainer publishes structured chunks (~100k–300k tokens of work each), "
             "your AI agent (Claude Code, Codex, Cursor, ChatGPT) takes one and opens a PR "
             "in 1–3 hours. No clinical expertise needed — you trigger structured drafting; "
             f"clinical co-leads sign off. <a href=\"https://github.com/{GH_REPO}/blob/master/docs/contributing/CONTRIBUTOR_QUICKSTART.md\" target=\"_blank\" rel=\"noopener\"><strong>How to start →</strong></a>"),
        ]
        why_today_foot = (
            "Every missed biomarker can cost a life. Every hour of manual cross-checking "
            "is an hour the patient waits for a decision. The tool is ready today — "
            "start with a virtual patient and see your typical case through a layer of "
            "open standards."
        )
        why_cta_secondary = "What&rsquo;s currently in the KB"
    else:
        hero_h1 = "Open-source інфраструктура клінічних рішень в онкології"
        hero_sub = (
            "Отримайте зрозумілі, доказово обґрунтовані стратегії лікування за хвилини. "
            "Завантажте профіль пацієнта — і отримайте стандартний та агресивний варіанти "
            "на основі світових клінічних настанов і референсів. Прозоро та відповідно до "
            "міжнародно визнаних стандартів."
        )
        cta_primary = "Побудувати план лікування →"
        cta_secondary = "Дивитись приклади"
        try_href = "/ukr/try.html"
        gallery_href = "/ukr/gallery.html"
        capabilities_href = "/ukr/capabilities.html"
        how_h2 = "Чому це потрібно і як це працює"
        how_lead_1 = (
            "Щоб призначити лікування, лікар або клінічний фармаколог витрачає "
            "2–4&nbsp;години ручної роботи: відкриває NCCN PDF, звіряє ESMO guideline, "
            "перечитує МОЗ протокол, перевіряє НСЗУ-формуляр на доступність препарату, "
            "шукає dose adjustments для нирок чи печінки, додає supportive care, не "
            "забуває про вакцинації та профілактику опортуністичних інфекцій. І так — "
            "для кожного пацієнта, кожного разу заново. Будь-яка пропущена "
            "контраіндикація може коштувати життя."
        )
        how_lead_2 = (
            "OpenOnco автоматизує цю чорнову роботу: <strong>логіка така сама, як у "
            "класичної мультидисциплінарної команди (MDT)</strong>, посиленої шаром "
            "аналітичних алгоритмів. Кілька спеціалістів навколо пацієнта, обговорення "
            "випадку, узгоджений план, повернення до випадку при появі нових даних. Ми "
            "просто оформлюємо це як structured engine — кожен &laquo;віртуальний "
            "лікар&raquo; це модуль із власною версією, правилами та списком джерел. "
            "Лікар отримує готовий проєкт плану з усіма посиланнями і лише верифікує та "
            "коригує його під конкретного пацієнта."
        )
        trust_1_strong = "AI не є лікарем."
        trust_1_text = (
            "LLM не вирішує, що призначати — клінічну логіку виконує декларативний "
            "rule engine."
        )
        trust_2_strong = "Жодних викликів зовнішніх LLM"
        trust_2_text = (
            "у момент побудови плану. Усі алгоритми відкриті, перевіряються "
            "рядок-за-рядком на GitHub."
        )
        trust_3_strong = "лише в наукові бази"
        trust_3_text_pre = "Запити йдуть"
        trust_3_text_post = ": PubMed, ClinicalTrials.gov, DailyMed, openFDA, CIViC (CC0), NCCN/ESMO/EHA/ASH/BSH, МОЗ."
        df_aria = "OpenOnco — потік даних від профілю пацієнта до двох планів лікування"
        df1_title = "Профіль пацієнта"
        df1_body = (
            "FHIR R4 / mCODE: діагноз, стадія, гістологія, біомаркери, лабораторні "
            "показники, попередні лінії терапії, коморбідності."
        )
        df1_aria = "Приклад біомаркерів пацієнта"
        df2_title = "Верифікація відкритими стандартами"
        df2_body = (
            "Кожен код діагнозу, лабораторний показник, доза й препарат — у публічному "
            "міжнародному стандарті. Жодних закритих словників."
        )
        df2_aria = "Відкриті стандарти, якими верифікуються дані"
        df3_title = "Red flags, корекції та зв&rsquo;язки"
        df3_body = (
            "Декларативний rule engine знаходить ризики, автоматично коригує дози й "
            "вибудовує зв&rsquo;язки біомаркер → препарат → моніторинг."
        )
        df3_li_1 = f"{n_redflags} червоних прапорців по {n_diseases} діагнозах"
        df3_li_2 = "корекції на нирки, печінку, вік, вагу"
        df3_li_3 = "зв&rsquo;язок біомаркер ↔ режим ↔ моніторинг"
        df4_title = "Два плани з повними цитатами"
        df4_body = (
            "<strong>Стандартний</strong> (за керівницями) + <strong>агресивний</strong> "
            "(трайали з вищою ефективністю). Кожне твердження — посилання на джерело з "
            "версією. План оновлюється автоматично, щойно з&rsquo;являються нові дані."
        )
        moh_label = "МОЗ"
        why_today_h = "Чому варто почати користуватись уже сьогодні"
        why_cards = [
            ("2–4 години → 5 хвилин",
             "Лікар витрачає менше часу на чорнову звірку NCCN/ESMO/МОЗ і встигає "
             "прийняти більше пацієнтів. Менше пропущених контраіндикацій — менше шкоди."),
            ("Жодного &laquo;чорного ящика&raquo;",
             "Не LLM вирішує лікування, а декларативний rule engine із публічним кодом "
             "і публічною KB. План будується <strong>без викликів зовнішніх LLM</strong> "
             "— лише запити в наукові бази (PubMed, ClinicalTrials.gov, DailyMed, "
             "openFDA, CIViC). Лікар бачить кожне &laquo;чому&raquo; поряд із кожним "
             "&laquo;що&raquo;."),
            ("Біомаркери, які не пропустиш",
             "TP53, CD30, MYD88, eGFR, печінкова функція — кожен прапорець автоматично "
             "переписує план: контраіндикації, корекція дози, supportive care, моніторинг."),
            ("Перевірка нових даних — миттєво",
             "Свіжі лабораторні чи рішення лікаря оновлюють обидва плани автоматично, "
             "без повторного ручного перебору джерел."),
            ("Реєстрація МОЗ та покриття НСЗУ — поряд із кожним препаратом",
             "Кожен препарат у плані позначений: чи зареєстрований в Україні (МОЗ) і чи "
             "покривається державною програмою медичних гарантій (НСЗУ). Лікар одразу "
             "бачить, що доступно безкоштовно, що — за рецептом, а що доведеться шукати "
             "окремо. Доступність — це <strong>метадані поряд із рекомендацією</strong>, "
             "а не фільтр: вибір режиму керується доказами, а не реєстраційним статусом."),
            ("Спрощений звіт для пацієнта",
             "Окремий режим генерує версію плану зрозумілою мовою для пацієнта: без "
             "латини, без абревіатур, з поясненням, чому призначено саме це і на що "
             "звертати увагу між візитами. Той самий план, дві мови — клінічна для лікаря, "
             "людська для пацієнта."),
            ("Безкоштовно, відкрито, назавжди",
             "MIT-style. Без paywall, без обмежень для державних лікарень. Open-source "
             "гарантує, що завтра воно нікуди не зникне і його не &laquo;закриють&raquo; "
             "інвестори."),
            ("Готово до пацієнтів сьогодні",
             f"{n_diseases} діагнозів, {n_redflags} червоних прапорців, {n_indications} "
             f"індикацій, {n_regimens} режимів, {n_algorithms} алгоритмів лікування — "
             "клінічний sign-off отриманий. Перші реальні плани вже верифіковані "
             "практикуючими онкологами як сильні. KB росте щотижня, але це вже найщільніший "
             "відкритий шар «доказ → план» для української онкології, що існує. Немає сенсу чекати."),
            ("CIViC actionability — повністю відкрита, повністю citable",
             "Шар biomarker→drug evidence ми взяли з <strong>CIViC (CC0)</strong> — "
             "Clinical Interpretation of Variants in Cancer (WashU), а не з OncoKB "
             "(закритий, non-commercial-only). Engine читає nightly YAML snapshot, "
             "матчить варіанти <strong>fusion-aware</strong> (BCR::ABL1, KMT2A "
             "rearrangements тощо), рендерить ESCAT-tier як головний сигнал з CIViC "
             "evidence rating під ним. Monthly CI refresh diff-ить upstream — без "
             "тихого дрейфу."),
            ("Per-disease coverage matrix — публічна і чесна",
             f"<a href=\"/ukr/diseases.html\"><strong>/ukr/diseases.html</strong></a> показує для "
             f"кожної з {n_diseases} хвороб, що саме у нас є: counts по біомаркерах, "
             "препаратах, показаннях, режимах, red flags, checkmarks для алгоритмів 1L/2L, "
             "статус анкети, fill% і verified%. Згрупована за лімфоїдною / мієлоїдною "
             "гематологією і солідними пухлинами. Ті ж дані доступні машинно як "
             "<code>disease_coverage.json</code>. Без «там же є щось» — є матриця."),
            ("Верифікувати наші алгоритми токенами вашого AI",
             "Залишковий bottleneck — не код, а two-reviewer sign-off на кожній Indication. "
             "<strong>TaskTorrent</strong> — наша полка розподілених AI-контрибуцій: "
             "maintainer публікує structured chunks (~100k–300k токенів роботи кожен), "
             "ваш AI-агент (Claude Code, Codex, Cursor, ChatGPT) бере один і відкриває PR "
             "за 1-3 години. Клінічна експертиза не потрібна — ви тригерите structured "
             "drafting; clinical co-leads потім signoff'ять. "
             f"<a href=\"https://github.com/{GH_REPO}/blob/master/docs/contributing/CONTRIBUTOR_QUICKSTART.md\" target=\"_blank\" rel=\"noopener\"><strong>Як почати →</strong></a>"),
        ]
        why_today_foot = (
            "Кожен пропущений біомаркер може коштувати життя. Кожна година ручного "
            "звіряння — це години, які пацієнт чекає рішення. Інструмент готовий вже "
            "сьогодні — почніть із віртуального пацієнта і подивіться, як виглядає ваш "
            "типовий випадок крізь шар відкритих стандартів."
        )
        why_cta_secondary = "Що зараз у базі знань"

    why_cards_html = "\n".join(
        f'        <div class="why-card">\n'
        f'          <div class="why-card-h">{h}</div>\n'
        f'          <p>{p}</p>\n'
        f'        </div>'
        for h, p in why_cards
    )

    return f"""<!DOCTYPE html>
<html lang="{'en' if target_lang == 'en' else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco — Open-source CDS for oncology</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0a2e1a">
<meta name="mobile-web-app-capable" content="yes">
<link href="/style.css" rel="stylesheet">
</head>
<body>
{_render_top_bar(active="home", target_lang=target_lang, lang_switch_href=_lang_switch_href("home", target_lang))}

<main>
  <section class="hero">
    <div class="hero-content">
      <h1>{hero_h1}</h1>
      <p class="hero-sub">
        {hero_sub}
      </p>
      <div class="cta-row">
        <a class="btn btn-primary" href="{try_href}">{cta_primary}</a>
        <a class="btn btn-secondary" href="{gallery_href}">{cta_secondary}</a>
      </div>
    </div>
  </section>

  <section class="how">
    <h2>{how_h2}</h2>
    <p class="how-lead">
      {how_lead_1}
    </p>
    <p class="how-lead">
      {how_lead_2}
    </p>

    <div class="trust-strip" role="note">
      <div class="trust-pill trust-pill--no">
        <span class="trust-pill-mark">×</span>
        <span class="trust-pill-text"><strong>{trust_1_strong}</strong> {trust_1_text}</span>
      </div>
      <div class="trust-pill trust-pill--no">
        <span class="trust-pill-mark">×</span>
        <span class="trust-pill-text"><strong>{trust_2_strong}</strong> {trust_2_text}</span>
      </div>
      <div class="trust-pill trust-pill--yes">
        <span class="trust-pill-mark">✓</span>
        <span class="trust-pill-text">{trust_3_text_pre} <strong>{trust_3_strong}</strong>{trust_3_text_post}</span>
      </div>
    </div>

    <div class="dataflow" aria-label="{df_aria}">
      <div class="dataflow-stage" data-stage="1">
        <div class="dataflow-num">01 · INPUT</div>
        <div class="dataflow-title">{df1_title}</div>
        <div class="dataflow-body">
          {df1_body}
          <div class="biomarker-row" aria-label="{df1_aria}">
            <span class="biomarker">CD30+</span>
            <span class="biomarker">BCL2/MYC</span>
            <span class="biomarker">TP53</span>
            <span class="biomarker">IPI 4</span>
            <span class="biomarker">eGFR 42</span>
          </div>
        </div>
      </div>
      <div class="dataflow-arrow" aria-hidden="true">→</div>
      <div class="dataflow-stage" data-stage="2">
        <div class="dataflow-num">02 · VERIFY</div>
        <div class="dataflow-title">{df2_title}</div>
        <div class="dataflow-body">
          {df2_body}
          <div class="std-row" aria-label="{df2_aria}">
            <span class="std-pill">ICD-O-3</span>
            <span class="std-pill">LOINC</span>
            <span class="std-pill">RxNorm</span>
            <span class="std-pill">ATC</span>
            <span class="std-pill">CTCAE v5</span>
            <span class="std-pill">NCCN</span>
            <span class="std-pill">ESMO</span>
            <span class="std-pill">{moh_label}</span>
          </div>
        </div>
      </div>
      <div class="dataflow-arrow" aria-hidden="true">→</div>
      <div class="dataflow-stage" data-stage="3">
        <div class="dataflow-num">03 · BIOMARKERS</div>
        <div class="dataflow-title">{df3_title}</div>
        <div class="dataflow-body">
          {df3_body}
          <ul class="flow-list">
            <li><span class="rf-tag rf-red">RF</span> {df3_li_1}</li>
            <li><span class="rf-tag rf-amber">DOSE</span> {df3_li_2}</li>
            <li><span class="rf-tag rf-teal">LINK</span> {df3_li_3}</li>
          </ul>
        </div>
      </div>
      <div class="dataflow-arrow" aria-hidden="true">→</div>
      <div class="dataflow-stage" data-stage="4">
        <div class="dataflow-num">04 · OUTPUT</div>
        <div class="dataflow-title">{df4_title}</div>
        <div class="dataflow-body">
          {df4_body}
        </div>
      </div>
    </div>

    <div class="why-today">
      <h3 class="why-today-h">{why_today_h}</h3>
      <div class="why-today-grid">
{why_cards_html}
      </div>
      <p class="why-today-foot">
        {why_today_foot}
      </p>
      <div class="cta-row">
        <a class="btn btn-primary" href="{try_href}">{cta_primary}</a>
        <a class="btn btn-secondary" href="{capabilities_href}">{why_cta_secondary}</a>
      </div>
    </div>
  </section>

  <footer class="page-foot">
    Open-source · MIT-style usage · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    <br>
    {'No real patient data · CHARTER §9.3. Informational tool for clinicians, not a medical device (CHARTER §15 + §11).' if target_lang == 'en' else 'Жодних реальних пацієнтських даних · CHARTER §9.3. Це інформаційний інструмент для лікаря, не медичний пристрій (CHARTER §15 + §11).'}
  </footer>
</main>
</body>
</html>
"""


# ── Gallery page ──────────────────────────────────────────────────────────


def _questionnaire_icd_o_3_codes() -> set:
    """ICD-O-3 morphology codes for which we have a curated questionnaire.
    Used to decide whether a gallery card opens into a real form or just
    a JSON dump on /try.html."""
    qsrc = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "questionnaires"
    codes: set = set()
    if not qsrc.is_dir():
        return codes
    import yaml as _yaml
    for path in qsrc.glob("*.yaml"):
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        code = (
            ((data or {}).get("fixed_fields") or {}).get("disease") or {}
        ).get("icd_o_3_morphology")
        if code:
            codes.add(code)
    return codes


def _unique_questionnaire_icd_to_disease_id_map() -> dict[str, str]:
    """Return ICD→disease_id only for ICDs that identify exactly one
    try-page questionnaire disease.

    Several oncology entities share broad morphology codes (8070/3,
    8140/3, 8500/3, 9680/3, 9699/3). Those codes are useful as secondary
    hints but must not be promoted to disease_id for example filtering,
    otherwise the try page can show an HNSCC example under cervical, etc.
    """
    qsrc = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "questionnaires"
    by_icd: dict[str, set[str]] = {}
    if not qsrc.is_dir():
        return {}
    import yaml as _yaml
    for path in qsrc.glob("*.yaml"):
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        did = (data or {}).get("disease_id")
        code = (
            ((data or {}).get("fixed_fields") or {}).get("disease") or {}
        ).get("icd_o_3_morphology")
        if did and code:
            by_icd.setdefault(str(code), set()).add(str(did).upper())
    return {
        code: next(iter(dids))
        for code, dids in by_icd.items()
        if len(dids) == 1
    }


def _case_has_questionnaire(case: CaseEntry, codes: set) -> bool:
    """True if the case's example JSON has a disease ICD-O-3 code that
    matches a curated questionnaire."""
    p = EXAMPLES / case.file
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    code = ((data or {}).get("disease") or {}).get("icd_o_3_morphology")
    return bool(code and code in codes)


def _load_disease_name_map() -> dict[str, dict[str, str]]:
    """Walk diseases/*.yaml and produce {DIS-ID: {ua, en}}.

    UA falls back to preferred → english if `names.ukrainian` missing;
    EN falls back to preferred → ukrainian. Used by the gallery to
    label disease-grouped tiles."""
    import yaml as _yaml
    src = REPO_ROOT / "knowledge_base" / "hosted" / "content" / "diseases"
    out: dict[str, dict[str, str]] = {}
    if not src.is_dir():
        return out
    for path in sorted(src.glob("*.yaml")):
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        did = data.get("id")
        if not did:
            continue
        names = data.get("names") or {}
        ua = names.get("ukrainian") or names.get("preferred") or names.get("english") or did
        en = names.get("english") or names.get("preferred") or names.get("ukrainian") or did
        out[str(did).upper()] = {"ua": ua, "en": en}
    return out


def _gallery_case_disease_meta() -> list[dict]:
    """For each CaseEntry, derive (disease_id, disease label UA/EN, ICD)
    by loading its example JSON. Cases whose JSON is missing or carries
    no recognised disease land in a synthetic 'OTHER' bucket so the UI
    still surfaces them.

    Resolution order:
      1. `disease.id` — direct DIS-* lookup against KB name map. Catches
         all `auto_*.json` and `variant_*.json` stubs that carry only
         `disease: {id: "DIS-X"}` without ICD-O-3 morphology. Without
         this fallback, ~half of all KB diseases collapse into OTHER
         because their auto-generated examples don't set ICD codes.
      2. `disease.icd_o_3_morphology` via the ICD→DIS map (kept for
         curated cases whose JSON sometimes carries only ICD).
      3. OTHER bucket if neither resolves.
    """
    icd_map = _icd_to_disease_id_map()
    name_map = _load_disease_name_map()
    out: list[dict] = []
    for c in CASES:
        p = EXAMPLES / c.file
        did: str | None = None
        icd = None
        if p.exists():
            try:
                ex = json.loads(p.read_text(encoding="utf-8"))
                disease_block = (ex or {}).get("disease") or {}
                # Step 1: direct disease.id lookup
                raw_id = disease_block.get("id")
                if isinstance(raw_id, str) and raw_id.upper().startswith("DIS-"):
                    candidate = raw_id.upper()
                    if candidate in name_map:
                        did = candidate
                # Step 2: ICD fallback
                icd = disease_block.get("icd_o_3_morphology")
                if did is None and icd:
                    did = icd_map.get(str(icd))
            except Exception:
                pass
        if did:
            names = name_map.get(did, {"ua": did, "en": did})
            out.append({
                "case": c,
                "disease_id": did,
                "icd": icd,
                "label_ua": names["ua"],
                "label_en": names["en"],
            })
        else:
            out.append({
                "case": c,
                "disease_id": "OTHER",
                "icd": icd,
                "label_ua": "Інше / без класифікації",
                "label_en": "Other / unclassified",
            })
    return out


def render_gallery(*, target_lang: str = "en") -> str:
    """Disease-grouped gallery (CSD UX rev 2026-04-27).

    Initial view is a tiled grid of diseases — each tile lists the
    disease name + how many examples we have for it. Clicking a tile
    drills into that disease's case list. The disease-level taxonomy
    page (/diseases.html) covers everything else, so the gallery
    intentionally drops the old category-chip filter."""
    import html as _html
    is_en = target_lang == "en"
    case_path_prefix = "/cases/" if is_en else "/ukr/cases/"
    quest_codes = _questionnaire_icd_o_3_codes()
    case_meta = [
        m for m in _gallery_case_disease_meta()
        if m["case"].case_id not in GALLERY_EXCLUDED_CASE_IDS
        and (
            not GALLERY_FEATURED_CASE_IDS
            or m["case"].case_id in GALLERY_FEATURED_CASE_IDS
        )
    ]
    n_cases = len(case_meta)

    # Group cases by disease_id, preserving CASES order within each group.
    grouped: dict[str, dict] = {}
    for i, m in enumerate(case_meta):
        did = m["disease_id"]
        bucket = grouped.setdefault(did, {
            "disease_id": did,
            "label_ua": m["label_ua"],
            "label_en": m["label_en"],
            "icds": set(),
            "items": [],
        })
        if m.get("icd"):
            bucket["icds"].add(str(m["icd"]))
        bucket["items"].append({**m, "default_order": i})
    # Sort diseases alphabetically by display label (UA primary).
    sort_key = "label_en" if is_en else "label_ua"
    diseases = sorted(grouped.values(), key=lambda d: d[sort_key].lower())

    def _examples_word(n: int) -> str:
        if is_en:
            return "example" if n == 1 else "examples"
        last2 = n % 100
        last1 = n % 10
        if 11 <= last2 <= 14:
            return "прикладів"
        if last1 == 1:
            return "приклад"
        if 2 <= last1 <= 4:
            return "приклади"
        return "прикладів"

    # ── Disease tile grid ──
    disease_tiles: list[str] = []
    for d in diseases:
        label = d[sort_key]
        n = len(d["items"])
        n_word = _examples_word(n)
        best_rank = min(
            _case_quality_meta(item["case"], has_case_page=True)["quality_rank"]
            for item in d["items"]
        )
        quality_text = (
            "curated first" if is_en and best_rank <= 20
            else "best first" if is_en
            else "кураторські першими" if best_rank <= 20
            else "кращі першими"
        )
        icds = sorted(str(code) for code in d.get("icds", []) if code)
        icd_text = ", ".join(icds[:3])
        icd_suffix = f" +{len(icds) - 3}" if len(icds) > 3 else ""
        icd_html = (
            f'<span class="dt-icd">ICD-O-3 {_html.escape(icd_text + icd_suffix)}</span>'
            if icds else ""
        )
        # data-search holds UA + EN labels and ICD-O-3 codes so the search
        # box works regardless of the page's render language.
        search_blob = " ".join([d["label_ua"], d["label_en"], *icds]).lower()
        disease_tiles.append(
            f'<button type="button" class="disease-tile" '
            f'data-disease-id="{_html.escape(d["disease_id"])}" '
            f'data-search="{_html.escape(search_blob)}">'
            f'<span class="dt-label">{_html.escape(label)}</span>'
            f'{icd_html}'
            f'<span class="dt-count">{n} {n_word}</span>'
            f'<span class="dt-quality">{_html.escape(quality_text)}</span>'
            f'</button>'
        )
    disease_tiles_html = "\n    ".join(disease_tiles)

    # ── Per-disease card lists (hidden until selected) ──
    case_lists: list[str] = []
    for d in diseases:
        cards: list[str] = []
        for item in d["items"]:
            c: CaseEntry = item["case"]
            has_quest = _case_has_questionnaire(c, quest_codes)
            json_only_pill = "" if has_quest else (
                f'<span class="case-json-only" title="'
                f'{("Form not yet available — opens as JSON on Try-it" if is_en else "Опитувальник для цієї хвороби ще не готовий — на Try-it відкриється як JSON")}'
                f'">JSON-only</span>'
            )
            quality = _case_quality_meta(c, has_case_page=True)
            quality_label = quality["quality_label_en"] if is_en else quality["quality_label"]
            card_label = (c.label_en or c.label_ua) if is_en else c.label_ua
            card_summary = (c.summary_en or c.summary_ua) if is_en else c.summary_ua
            cards.append(
                f"""<a class="case-card" href="{case_path_prefix}{c.case_id}.html"
   data-default-order="{item['default_order']}"
   data-name="{_html.escape(card_label)}">
  <div class="case-badge-row">
    <div class="case-badge {c.badge_class}">{c.badge}</div>
    <span class="case-quality {quality["quality_class"]}">{_html.escape(quality_label)}</span>
    {json_only_pill}
  </div>
  <h3>{_html.escape(card_label)}</h3>
  <p>{_html.escape(card_summary)}</p>
  <div class="case-foot">{c.file}</div>
</a>"""
            )
        cards_html = "\n".join(cards)
        label = d[sort_key]
        case_lists.append(
            f'<section class="case-list" data-disease-id="{_html.escape(d["disease_id"])}" hidden>\n'
            f'  <header class="case-list-header">\n'
            f'    <h2>{_html.escape(label)}</h2>\n'
            f'    <span class="case-list-count">{len(d["items"])} {_examples_word(len(d["items"]))}</span>\n'
            f'  </header>\n'
            f'  <div class="case-grid">\n{cards_html}\n  </div>\n'
            f'</section>'
        )
    case_lists_html = "\n".join(case_lists)

    if is_en:
        lead_html = (
            f'{n_cases} synthetic patient profiles run through the engine, '
            f'grouped by disease. Pick a disease to see its examples — each '
            f'click opens a full Plan or Diagnostic Brief as a clinician would '
            f'see it in tumor-board. If something looks clinically wrong — '
            f'<a href="{GH_NEW_ISSUE}?title=%5Bfeedback%5D+&labels=tester-feedback" '
            f'target="_blank" rel="noopener">open an issue</a>.'
        )
        page_title = "Sample cases"
        search_ph = "Search disease or ICD-O-3…"
        back_label = "← All diseases"
        empty_label = "No diseases match your search."
    else:
        lead_html = (
            f'{n_cases} синтетичних профілів пацієнтів, згрупованих за хворобою. '
            f'Оберіть хворобу зі списку — кожен клік відкриває повний Plan або '
            f'Diagnostic Brief, як його побачить лікар у tumor-board. Якщо '
            f'щось виглядає клінічно неправильно — '
            f'<a href="{GH_NEW_ISSUE}?title=%5Bfeedback%5D+&labels=tester-feedback" '
            f'target="_blank" rel="noopener">відкрий issue</a>.'
        )
        page_title = "Готові приклади"
        search_ph = "Шукати хворобу або ICD-O-3…"
        back_label = "← Усі хвороби"
        empty_label = "Жодна хвороба не підходить під запит."

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · {page_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0a2e1a">
<meta name="mobile-web-app-capable" content="yes">
<link href="/style.css" rel="stylesheet">
</head>
<body>
{_render_top_bar(active="gallery", target_lang=target_lang, lang_switch_href=_lang_switch_href("gallery", target_lang))}

<main class="gallery">
  <h1>{page_title}</h1>
  <p class="lead">{lead_html}</p>

  <!-- Stage 1: disease grid (default visible) -->
  <section id="diseaseStage" class="disease-stage">
    <div class="disease-search-row">
      <input type="search" id="diseaseSearch" class="disease-search"
             placeholder="{search_ph}" autocomplete="off"
             aria-label="{search_ph}">
      <span class="disease-search-count" id="diseaseSearchCount">{len(diseases)}</span>
    </div>
    <div class="disease-tile-grid" id="diseaseTileGrid">
    {disease_tiles_html}
    </div>
    <p class="disease-empty" id="diseaseEmpty" hidden>{empty_label}</p>
  </section>

  <!-- Stage 2: case list for the selected disease (hidden by default) -->
  <section id="caseStage" class="case-stage" hidden>
    <button type="button" class="case-back-btn" id="caseBackBtn">{back_label}</button>
    <div id="caseListContainer">
    {case_lists_html}
    </div>
  </section>

  <footer class="page-foot">
    OpenOnco — open-source · MIT-style usage
    · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    · {'No real patient data' if is_en else 'Жодних реальних пацієнтських даних'} · CHARTER §9.3
  </footer>
</main>

<script>
(function() {{
  var diseaseStage = document.getElementById("diseaseStage");
  var caseStage = document.getElementById("caseStage");
  var tileGrid = document.getElementById("diseaseTileGrid");
  var tiles = Array.prototype.slice.call(tileGrid.querySelectorAll(".disease-tile"));
  var search = document.getElementById("diseaseSearch");
  var searchCount = document.getElementById("diseaseSearchCount");
  var emptyMsg = document.getElementById("diseaseEmpty");
  var backBtn = document.getElementById("caseBackBtn");
  var listContainer = document.getElementById("caseListContainer");
  var lists = Array.prototype.slice.call(listContainer.querySelectorAll(".case-list"));

  function showDiseaseStage() {{
    caseStage.hidden = true;
    diseaseStage.hidden = false;
    lists.forEach(function(l) {{ l.hidden = true; }});
    if (history.replaceState) history.replaceState(null, "", window.location.pathname);
    // Restore scroll to top of stage so user sees the search bar.
    diseaseStage.scrollIntoView({{ block: "start", behavior: "auto" }});
  }}

  function showDiseaseCases(diseaseId) {{
    var found = false;
    lists.forEach(function(l) {{
      var match = l.dataset.diseaseId === diseaseId;
      l.hidden = !match;
      if (match) found = true;
    }});
    if (!found) return;
    diseaseStage.hidden = true;
    caseStage.hidden = false;
    if (history.replaceState) history.replaceState(null, "", "#" + encodeURIComponent(diseaseId));
    caseStage.scrollIntoView({{ block: "start", behavior: "auto" }});
  }}

  function applySearch() {{
    var q = (search.value || "").trim().toLowerCase();
    var visible = 0;
    tiles.forEach(function(t) {{
      var blob = t.dataset.search || "";
      var match = !q || blob.indexOf(q) !== -1;
      t.style.display = match ? "" : "none";
      if (match) visible++;
    }});
    searchCount.textContent = visible;
    emptyMsg.hidden = visible !== 0;
  }}

  tiles.forEach(function(t) {{
    t.addEventListener("click", function() {{
      showDiseaseCases(t.dataset.diseaseId);
    }});
  }});
  backBtn.addEventListener("click", showDiseaseStage);
  search.addEventListener("input", applySearch);

  // Deep-link support: gallery.html#DIS-DLBCL-NOS opens that disease.
  function applyHash() {{
    var h = window.location.hash.replace(/^#/, "");
    if (!h) {{ showDiseaseStage(); return; }}
    try {{ h = decodeURIComponent(h); }} catch (e) {{}}
    showDiseaseCases(h);
  }}
  window.addEventListener("hashchange", applyHash);
  applyHash();
}})();
</script>
</body>
</html>
"""


# ── Clinical question page (optional LLM adapter) ─────────────────────────


def render_ask(*, target_lang: str = "en") -> str:
    is_en = target_lang == "en"
    title = "Tumor board question" if is_en else "Запит до tumor board"
    kicker = "OpenOnco AI draft" if is_en else "OpenOnco AI-чернетка"
    lead = (
        "Paste an oncology vignette in natural language. ChatGPT structures the case, "
        "OpenOnco checks it against the rule engine, and the page returns an answer, "
        "reasonable alternatives, or clarifying questions."
        if is_en else
        "Опишіть онкологічну клінічну ситуацію своїми словами. ChatGPT структурує кейс, "
        "OpenOnco звіряє його з алгоритмами, а сторінка повертає відповідь, обґрунтовані "
        "альтернативи або уточнювальні питання."
    )
    endpoint_label = "API endpoint" if is_en else "API endpoint"
    case_label = "Clinical situation" if is_en else "Клінічна ситуація"
    run_label = "Answer with OpenOnco" if is_en else "Відповісти через OpenOnco"
    clear_label = "Clear" if is_en else "Очистити"
    examples_title = "Example prompts" if is_en else "Приклади формату"
    use_example_label = "Use" if is_en else "Вставити"
    quota_label = "Questions used" if is_en else "Використано запитів"
    quota_hero_label = "free-text questions per browser" if is_en else "текстові запити на браузер"
    wait_label = "Typical wait" if is_en else "Орієнтовне очікування"
    wait_value = "30-90 sec" if is_en else "30-90 с"
    progress_idle = "Ready for a clinical question" if is_en else "Готово до клінічного запиту"
    progress_idle_eta = "Usually 30-90 sec" if is_en else "Зазвичай 30-90 с"
    progress_step_1 = "Structuring case" if is_en else "Структурую кейс"
    progress_step_2 = "Matching OpenOnco algorithms" if is_en else "Зіставляю з алгоритмами OpenOnco"
    progress_step_3 = "Checking biomarkers and options" if is_en else "Перевіряю біомаркери й опції"
    progress_step_4 = "Writing answer" if is_en else "Формую відповідь"
    progress_done = "Answer is ready" if is_en else "Відповідь готова"
    progress_failed = "Request stopped" if is_en else "Запит зупинено"
    progress_done_eta = "Done" if is_en else "Готово"
    progress_failed_eta = "Check the message below" if is_en else "Перевірте повідомлення нижче"
    progress_eta_prefix = "approx." if is_en else "ще приблизно"
    progress_eta_unit = "s" if is_en else "с"
    plan_link_label = "Open in plan generator" if is_en else "Відкрити в генераторі планів"
    plan_link_hint = (
        "Good KB match found. The structured profile can be opened in the in-browser plan generator."
        if is_en else
        "Є добрий збіг із KB. Структурований профіль можна відкрити в браузерному генераторі планів."
    )
    plan_link_error = (
        "Plan-generator link could not be created in this browser."
        if is_en else
        "Не вдалося створити посилання на генератор планів у цьому браузері."
    )
    placeholder = (
        "62-year-old patient with metastatic gastric cancer, HER2-negative, MSS, PD-L1 CPS 25. What is the optimal first line?"
        if is_en else
        "62-річний пацієнт із метастатичним раком шлунка, HER2-негативний, MSS, PD-L1 CPS 25. Яка оптимальна перша лінія?"
    )
    empty_msg = "Paste a clinical situation first." if is_en else "Спочатку вставте клінічну ситуацію."
    loading_msg = "Analyzing the case. This usually takes under 90 seconds." if is_en else "Аналізую кейс. Зазвичай це займає до 90 секунд."
    error_msg = "Request failed" if is_en else "Запит не вдався"
    endpoint_unavailable_msg = (
        "The clinical-question API did not return JSON. This public site is static unless a server adapter is deployed; use the browser plan generator or enter a working API endpoint."
        if is_en else
        "Clinical-question API не повернув JSON. Публічний сайт статичний, доки не розгорнуто серверний адаптер; скористайтеся браузерним генератором планів або вкажіть робочий API endpoint."
    )
    invalid_json_msg = (
        "Invalid JSON response from the clinical-question API"
        if is_en else
        "Невалідна JSON-відповідь від clinical-question API"
    )
    limit_msg = (
        "You have used all 3 free-text questions in this browser."
        if is_en else
        "У цьому браузері вже використано всі 3 текстові запити."
    )
    safety = (
        "Do not paste real identifiable patient data. This is a tumor-board draft, not autonomous medical advice."
        if is_en else
        "Не вставляйте реальні персональні дані пацієнта. Це чернетка для tumor board, а не автономна медична порада."
    )
    examples = (
        [
            (
                "Gastric 1L",
                "62-year-old patient with metastatic gastric cancer and diffuse peritoneal carcinomatosis. Histology: poorly differentiated adenocarcinoma with signet-ring cells, MSS, HER2-negative, PD-L1 CPS 25. What is the optimal first-line treatment?"
            ),
            (
                "GBM supportive",
                "30-year-old man with a 2 cm contrast-enhancing left parietal glioblastoma, ECOG 1, no comorbidities and no seizures. Which option is NOT part of initial management: resection, radiotherapy, steroids, temozolomide, or prophylactic anti-epileptic therapy?"
            ),
            (
                "CUP poor PS",
                "74-year-old woman with painful hepatomegaly, multiple liver metastases, poorly differentiated adenocarcinoma and no primary site on PET. WHO PS is 3. What is the most appropriate strategy?"
            ),
            (
                "mCRC first line",
                "52-year-old man with metastatic right-sided colon cancer, unresectable liver, lung and peritoneal metastases. KRAS p.G12C, NRAS/BRAF wild type, MSS, HER2-negative. What systemic first-line therapy is most appropriate?"
            ),
            (
                "NSCLC confusion",
                "68-year-old patient with metastatic squamous NSCLC involving liver, adrenals and pleura. New disorientation and aggressive behaviour; brain MRI shows no metastases. What is the most likely cause?"
            ),
            (
                "Pharmacogenomics",
                "Patient is planned for fluoropyrimidine-based chemotherapy for gastrointestinal cancer. Which pharmacogenomic test is recommended before treatment to reduce severe toxicity risk?"
            ),
            (
                "Breast HR+/HER2-",
                "61-year-old postmenopausal woman with metastatic ER-positive, HER2-negative breast cancer, bone and liver metastases, no visceral crisis, ECOG 1. What is the preferred first-line systemic treatment?"
            ),
            (
                "Ovarian maintenance",
                "58-year-old woman with stage IIIC high-grade serous ovarian cancer after debulking surgery and response to platinum-taxane chemotherapy. BRCA1 pathogenic variant detected. What maintenance treatment should be discussed?"
            ),
            (
                "Pancreatic 1L",
                "66-year-old patient with metastatic pancreatic adenocarcinoma, liver metastases, ECOG 1, bilirubin normal and no major comorbidities. What first-line systemic therapy options are reasonable?"
            ),
        ]
        if is_en else
        [
            (
                "Gastric 1L",
                "62-річний пацієнт із метастатичним раком шлунка, поширений перитонеальний канцероматоз. Гістологія: недиференційована аденокарцинома з перснеподібними клітинами, MSS, HER2-негативний, PD-L1 CPS = 25. Яка оптимальна перша лінія лікування?"
            ),
            (
                "GBM supportive",
                "30-річний чоловік із гліобластомою лівої тім'яної частки 2 см, ECOG 1, без супутньої патології, судом не було. Що НЕ входить до лікування: резекція, радіотерапія, стероїди, темозоломід чи профілактичні протиепілептичні?"
            ),
            (
                "CUP poor PS",
                "74-річна жінка, біль через гепатомегалію, множинні метастази в печінці, низькодиференційована аденокарцинома без первинного вогнища, PET-негативна, WHO PS 3. Яка найбільш доцільна тактика?"
            ),
            (
                "mCRC first line",
                "52-річний чоловік із метастатичним раком сліпої кишки, нерезектабельні метастази в печінку, легені та очеревину. KRAS p.G12C, NRAS/BRAF дикого типу, MSS, HER2-негативний. Яке системне лікування першої лінії найбільш доцільне?"
            ),
            (
                "NSCLC confusion",
                "68-річний пацієнт із метастатичним плоскоклітинним НДРЛ з ураженням печінки, наднирників і плеври. Нова дезорієнтація та агресія; МРТ головного мозку без метастазів. Яка найбільш імовірна причина симптомів?"
            ),
            (
                "Pharmacogenomics",
                "Пацієнту планують фторпіримідин-вмісну хіміотерапію з приводу пухлини ШКТ. Яке фармакогеномне тестування до початку лікування рекомендоване для зниження ризику тяжкої токсичності?"
            ),
            (
                "Breast HR+/HER2-",
                "61-річна жінка в постменопаузі з метастатичним ER-позитивним, HER2-негативним раком молочної залози, метастази в кістки та печінку, без вісцерального кризу, ECOG 1. Яка переважна перша лінія системної терапії?"
            ),
            (
                "Ovarian maintenance",
                "58-річна жінка зі стадією IIIC high-grade серозного раку яєчника після циторедуктивної операції та відповіді на platinum-taxane хіміотерапію. Виявлено патогенний варіант BRCA1. Яку підтримувальну терапію слід обговорити?"
            ),
            (
                "Pancreatic 1L",
                "66-річний пацієнт із метастатичною аденокарциномою підшлункової залози, метастази в печінку, ECOG 1, білірубін у нормі, суттєвих супутніх хвороб немає. Які варіанти першої лінії системної терапії є обґрунтованими?"
            ),
        ]
    )
    examples_json = json.dumps(
        [{"title": title, "text": text} for title, text in examples],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · {html.escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link href="/style.css" rel="stylesheet">
<style>
.ask-hero {{ display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:22px; align-items:end; margin-bottom:22px; }}
.ask-kicker {{ margin:0 0 8px; color:#0f766e; font-weight:800; letter-spacing:0; text-transform:uppercase; font-size:12px; }}
.ask-hero h1 {{ margin-bottom:10px; }}
.ask-hero-meter {{ display:grid; grid-template-columns:repeat(2, minmax(112px, 1fr)); gap:10px; min-width:260px; }}
.ask-stat {{ border:1px solid #d6e4de; background:#f8fbf8; border-radius:8px; padding:12px; }}
.ask-stat strong {{ display:block; color:#073b22; font-size:24px; line-height:1; margin-bottom:5px; }}
.ask-stat span {{ color:#53605a; font-size:13px; line-height:1.25; }}
.ask-grid {{ display:grid; grid-template-columns:minmax(0, 0.92fr) minmax(0, 1.08fr); gap:18px; align-items:start; }}
.ask-panel {{ border:1px solid #dbe7df; border-radius:8px; background:#fff; padding:18px; box-shadow:0 14px 38px rgba(9, 44, 27, 0.08); }}
.ask-panel h2 {{ font-size:22px; }}
.ask-endpoint {{ padding:10px 12px; border:1px solid #e2e8f0; border-radius:8px; background:#f8fafc; }}
.ask-endpoint input {{ margin-top:6px; font-size:12px; color:#475569; }}
.ask-panel textarea {{ width:100%; min-height:310px; resize:vertical; font:14px/1.5 var(--mono); border-color:#cbd5e1; border-radius:8px; background:#fbfdfc; }}
.ask-panel textarea:focus, .ask-panel input:focus {{ outline:2px solid rgba(20, 118, 82, 0.22); border-color:#0f766e; }}
.ask-panel input {{ width:100%; }}
.ask-actions {{ display:flex; gap:10px; margin-top:14px; flex-wrap:wrap; }}
.ask-actions .btn {{ min-height:42px; }}
.ask-result {{ white-space:pre-wrap; font:14px/1.55 var(--mono); background:#102018; color:#ecfdf5; border:1px solid #244d38; border-radius:8px; padding:16px; min-height:380px; overflow:auto; box-shadow:inset 0 1px 0 rgba(255,255,255,0.06); }}
.ask-result:empty::before {{ content:""; display:block; min-height:1px; }}
.ask-muted {{ color:#647067; font-size:14px; }}
.ask-examples {{ display:grid; gap:10px; margin:12px 0 14px; max-height:460px; overflow:auto; padding-right:4px; }}
.ask-example {{ display:grid; grid-template-columns:1fr auto; gap:12px; align-items:center; border:1px solid #dbe7df; border-radius:8px; padding:12px; background:#f8fbf8; }}
.ask-example-title {{ font-weight:800; margin-bottom:4px; color:#073b22; }}
.ask-example-text {{ color:#56635c; font-size:13px; line-height:1.38; }}
.ask-quota {{ display:flex; justify-content:space-between; gap:10px; margin-top:12px; font-size:13px; color:#56635c; }}
.ask-quota strong {{ color:#073b22; }}
.ask-progress {{ margin-top:14px; padding:14px; border:1px solid #cfe5d8; border-radius:8px; background:#f7fcf8; }}
.ask-progress-head {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:10px; font-size:14px; }}
.ask-progress-head strong {{ color:#073b22; }}
.ask-progress-head span {{ color:#53605a; font-size:13px; white-space:nowrap; }}
.ask-progress-track {{ height:12px; overflow:hidden; border-radius:999px; background:#dfe9e2; box-shadow:inset 0 1px 2px rgba(15, 23, 42, 0.12); }}
.ask-progress-fill {{ width:0%; height:100%; border-radius:999px; background:linear-gradient(90deg, #0f766e, #22c55e, #f59e0b); transition:width 420ms ease; }}
.ask-progress.is-running .ask-progress-fill {{ box-shadow:0 0 18px rgba(34, 197, 94, 0.45); }}
.ask-progress-steps {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; padding:0; margin:12px 0 0; list-style:none; }}
.ask-progress-steps li {{ min-height:42px; padding:8px; border-radius:8px; background:#eef6f0; color:#647067; font-size:12px; line-height:1.25; border:1px solid transparent; }}
.ask-progress-steps li.is-active {{ border-color:#0f766e; background:#e7f7ee; color:#073b22; font-weight:800; }}
.ask-progress-steps li.is-done {{ background:#dcfce7; color:#14532d; }}
.ask-plan-link {{ display:none; margin-bottom:12px; padding:12px; border:1px solid #b7e4c7; background:#f0fdf4; border-radius:8px; }}
.ask-plan-link.is-visible {{ display:block; }}
.ask-plan-link p {{ margin:0 0 8px; color:#166534; font-size:14px; }}
@media (max-width: 900px) {{ .ask-hero, .ask-grid {{ grid-template-columns:1fr; }} .ask-hero-meter {{ min-width:0; }} }}
@media (max-width: 640px) {{ .ask-hero-meter, .ask-progress-steps {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width: 520px) {{ .ask-example {{ grid-template-columns:1fr; }} .ask-progress-head {{ display:block; }} .ask-progress-head span {{ display:block; margin-top:4px; }} }}
</style>
</head>
<body>
{_render_top_bar(active="ask", target_lang=target_lang, lang_switch_href=_lang_switch_href("ask", target_lang))}

<main class="try-page">
  <div class="ask-hero">
    <div>
      <p class="ask-kicker">{kicker}</p>
      <h1>{html.escape(title)}</h1>
      <p class="lead">{lead}</p>
      <p class="ask-muted">{safety}</p>
    </div>
    <div class="ask-hero-meter" aria-label="{quota_label}">
      <div class="ask-stat"><strong>3</strong><span>{quota_hero_label}</span></div>
      <div class="ask-stat"><strong>{wait_value}</strong><span>{wait_label}</span></div>
    </div>
  </div>

  <div class="ask-grid">
    <section class="ask-panel">
      <label class="qt-label ask-endpoint">
        {endpoint_label}
        <input id="endpointInput" value="/api/clinical-question" spellcheck="false">
      </label>
      <label class="qt-label" style="margin-top:12px">
        {case_label}
        <textarea id="caseText" spellcheck="true" placeholder="{html.escape(placeholder)}"></textarea>
      </label>
      <div class="ask-quota">
        <span>{quota_label}</span>
        <strong><span id="quotaUsed">0</span> / 3</strong>
      </div>
      <div class="ask-actions">
        <button id="askBtn" class="btn">{run_label}</button>
        <button id="clearAskBtn" class="btn btn-secondary">{clear_label}</button>
      </div>
      <div id="askProgress" class="ask-progress" aria-live="polite">
        <div class="ask-progress-head">
          <strong id="progressLabel">{progress_idle}</strong>
          <span id="progressEta">{progress_idle_eta}</span>
        </div>
        <div class="ask-progress-track" aria-hidden="true">
          <div id="progressFill" class="ask-progress-fill"></div>
        </div>
        <ol class="ask-progress-steps">
          <li id="progressStep1" class="is-active">{progress_step_1}</li>
          <li id="progressStep2">{progress_step_2}</li>
          <li id="progressStep3">{progress_step_3}</li>
          <li id="progressStep4">{progress_step_4}</li>
        </ol>
      </div>
      <p id="askStatus" class="ask-muted" role="status" aria-live="polite"></p>
    </section>
    <section class="ask-panel">
      <h2 style="margin-top:0">{examples_title}</h2>
      <div id="askExamples" class="ask-examples"></div>
      <div id="planGeneratorLinkWrap" class="ask-plan-link">
        <p>{plan_link_hint}</p>
        <a id="planGeneratorLink" class="btn" href="try.html">{plan_link_label}</a>
      </div>
      <div id="askResult" class="ask-result"></div>
    </section>
  </div>
</main>

<script>
(function() {{
  const ASK_EXAMPLES = {examples_json};
  const MAX_QUESTIONS = 3;
  const USER_KEY = 'openonco-ask-user-id-v1';
  const COUNT_KEY = 'openonco-ask-count-v1';
  const DEFAULT_ENDPOINT = '/api/clinical-question';
  const PUBLIC_ENDPOINT = 'https://openonco-vercel-api.vercel.app/api/clinical-question';
  const endpointInput = document.getElementById('endpointInput');
  const caseText = document.getElementById('caseText');
  const askBtn = document.getElementById('askBtn');
  const clearBtn = document.getElementById('clearAskBtn');
  const status = document.getElementById('askStatus');
  const result = document.getElementById('askResult');
  const quotaUsed = document.getElementById('quotaUsed');
  const examplesRoot = document.getElementById('askExamples');
  const planLinkWrap = document.getElementById('planGeneratorLinkWrap');
  const planLink = document.getElementById('planGeneratorLink');
  const progressBox = document.getElementById('askProgress');
  const progressFill = document.getElementById('progressFill');
  const progressLabel = document.getElementById('progressLabel');
  const progressEta = document.getElementById('progressEta');
  const progressSteps = [
    document.getElementById('progressStep1'),
    document.getElementById('progressStep2'),
    document.getElementById('progressStep3'),
    document.getElementById('progressStep4')
  ];
  const PROGRESS_COPY = [
    {{ at: 0, label: '{progress_step_1}' }},
    {{ at: 34, label: '{progress_step_2}' }},
    {{ at: 64, label: '{progress_step_3}' }},
    {{ at: 86, label: '{progress_step_4}' }}
  ];
  let progressTimer = null;
  let progressStartedAt = 0;
  const configured = window.OPENONCO_CLINICAL_QUESTION_ENDPOINT;
  const isLocalHost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isFilePage = window.location.protocol === 'file:';
  function defaultEndpointCandidates() {{
    if (configured) return [configured];
    if (isFilePage) return [PUBLIC_ENDPOINT];
    if (isLocalHost) return [DEFAULT_ENDPOINT];
    return [DEFAULT_ENDPOINT, PUBLIC_ENDPOINT];
  }}
  endpointInput.value = defaultEndpointCandidates()[0];

  function getUserId() {{
    let id = localStorage.getItem(USER_KEY);
    if (!id) {{
      const browserCrypto = window.crypto || window.msCrypto;
      const suffix = (browserCrypto && browserCrypto.randomUUID) ? browserCrypto.randomUUID() : String(Date.now()) + '-' + Math.random().toString(16).slice(2);
      id = 'ask-' + suffix;
      localStorage.setItem(USER_KEY, id);
    }}
    return id;
  }}

  function getCount() {{
    const n = Number(localStorage.getItem(COUNT_KEY) || '0');
    return Number.isFinite(n) && n > 0 ? Math.min(n, MAX_QUESTIONS) : 0;
  }}

  function setCount(n) {{
    localStorage.setItem(COUNT_KEY, String(Math.min(Math.max(n, 0), MAX_QUESTIONS)));
    updateQuota();
  }}

  function updateQuota() {{
    const used = getCount();
    quotaUsed.textContent = String(used);
    askBtn.disabled = used >= MAX_QUESTIONS;
    if (used >= MAX_QUESTIONS) status.textContent = '{limit_msg}';
  }}

  function setProgress(percent, label, eta, activeIndex) {{
    const pct = Math.max(0, Math.min(100, Math.round(percent)));
    progressFill.style.width = pct + '%';
    progressLabel.textContent = label;
    progressEta.textContent = eta;
    progressSteps.forEach((step, idx) => {{
      step.classList.toggle('is-active', idx === activeIndex);
      step.classList.toggle('is-done', idx < activeIndex || pct >= 100);
    }});
  }}

  function resetProgress() {{
    if (progressTimer) window.clearInterval(progressTimer);
    progressTimer = null;
    progressBox.classList.remove('is-running');
    setProgress(0, '{progress_idle}', '{progress_idle_eta}', 0);
  }}

  function startProgress() {{
    resetProgress();
    progressBox.classList.add('is-running');
    progressStartedAt = Date.now();
    const durationMs = 90000;
    const tick = () => {{
      const elapsed = Date.now() - progressStartedAt;
      const pct = Math.min(92, 8 + (elapsed / durationMs) * 84);
      let activeIndex = 0;
      PROGRESS_COPY.forEach((step, idx) => {{
        if (pct >= step.at) activeIndex = idx;
      }});
      const remainingSec = Math.max(10, Math.ceil((durationMs - elapsed) / 1000));
      setProgress(pct, PROGRESS_COPY[activeIndex].label, '{progress_eta_prefix} ' + remainingSec + ' {progress_eta_unit}', activeIndex);
    }};
    tick();
    progressTimer = window.setInterval(tick, 900);
  }}

  function finishProgress(ok) {{
    if (progressTimer) window.clearInterval(progressTimer);
    progressTimer = null;
    progressBox.classList.remove('is-running');
    setProgress(ok ? 100 : 0, ok ? '{progress_done}' : '{progress_failed}', ok ? '{progress_done_eta}' : '{progress_failed_eta}', ok ? 3 : 0);
  }}

  function renderExamples() {{
    examplesRoot.innerHTML = '';
    ASK_EXAMPLES.forEach((ex) => {{
      const row = document.createElement('div');
      row.className = 'ask-example';
      const body = document.createElement('div');
      const title = document.createElement('div');
      title.className = 'ask-example-title';
      title.textContent = ex.title;
      const text = document.createElement('div');
      text.className = 'ask-example-text';
      text.textContent = ex.text;
      body.appendChild(title);
      body.appendChild(text);
      const btn = document.createElement('button');
      btn.className = 'btn btn-secondary';
      btn.type = 'button';
      btn.textContent = '{use_example_label}';
      btn.addEventListener('click', () => {{
        caseText.value = ex.text;
        caseText.focus();
      }});
      row.appendChild(body);
      row.appendChild(btn);
      examplesRoot.appendChild(row);
    }});
  }}

  function renderPayload(payload) {{
    const lines = [];
    if (payload.direct_answer) lines.push(payload.direct_answer);
    if (payload.selected_options && payload.selected_options.length) {{
      lines.push('');
      lines.push('Options:');
      payload.selected_options.forEach(o => lines.push('- ' + (o.label ? o.label + '. ' : '') + o.text));
    }}
    if (payload.rationale && payload.rationale.length) {{
      lines.push('');
      lines.push('Rationale:');
      payload.rationale.forEach(x => lines.push('- ' + x));
    }}
    if (payload.clarifying_questions && payload.clarifying_questions.length) {{
      lines.push('');
      lines.push('Clarifying questions:');
      payload.clarifying_questions.forEach(x => lines.push('- ' + x));
    }}
    if (payload.engine_limitations && payload.engine_limitations.length) {{
      lines.push('');
      lines.push('Engine limitations:');
      payload.engine_limitations.forEach(x => lines.push('- ' + x));
    }}
    if (payload.safety_note) {{
      lines.push('');
      lines.push(payload.safety_note);
    }}
    return lines.join('\\n') || JSON.stringify(payload, null, 2);
  }}

  function canOpenInPlanGenerator(payload) {{
    return !!(
      payload &&
      payload.status === 'answered' &&
      payload.patient_profile &&
      payload.engine_summary &&
      payload.engine_summary.ok === true &&
      payload.engine_summary.mode === 'treatment'
    );
  }}

  async function profileToHash(profile) {{
    const json = JSON.stringify(profile);
    if (!('CompressionStream' in window)) throw new Error('CompressionStream unavailable');
    const stream = new Blob([json], {{ type: 'application/json' }}).stream().pipeThrough(new CompressionStream('gzip'));
    const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {{
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }}
    return btoa(binary).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
  }}

  async function updatePlanGeneratorLink(payload) {{
    planLinkWrap.classList.remove('is-visible');
    planLink.removeAttribute('href');
    if (!canOpenInPlanGenerator(payload)) return;
    try {{
      const token = await profileToHash(payload.patient_profile);
      planLink.href = 'try.html#p=' + token;
      planLinkWrap.classList.add('is-visible');
    }} catch (err) {{
      console.warn('Plan-generator link failed:', err);
      status.textContent = '{plan_link_error}';
    }}
  }}

  async function readJsonResponse(resp, endpoint) {{
    const contentType = (resp.headers.get('content-type') || '').toLowerCase();
    const text = await resp.text();
    if (!contentType.includes('application/json')) {{
      const err = new Error('{endpoint_unavailable_msg} Endpoint: ' + endpoint + '. HTTP ' + resp.status + '.');
      err.retryable = true;
      throw err;
    }}
    try {{
      return text ? JSON.parse(text) : {{}};
    }} catch (err) {{
      throw new Error('{invalid_json_msg}: ' + err.message);
    }}
  }}

  function endpointCandidatesForRequest() {{
    const entered = endpointInput.value.trim();
    const defaults = defaultEndpointCandidates();
    const candidates = entered ? [entered] : defaults.slice();
    defaults.forEach((endpoint) => {{
      if (endpoint && !candidates.includes(endpoint)) candidates.push(endpoint);
    }});
    return candidates;
  }}

  async function postClinicalQuestion(body) {{
    const candidates = endpointCandidatesForRequest();
    const errors = [];
    for (const endpoint of candidates) {{
      try {{
        const resp = await fetch(endpoint, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(body)
        }});
        const payload = await readJsonResponse(resp, endpoint);
        if (!resp.ok) {{
          const err = new Error(payload.message || ('HTTP ' + resp.status));
          err.status = resp.status;
          throw err;
        }}
        if (endpointInput.value.trim() !== endpoint) endpointInput.value = endpoint;
        return payload;
      }} catch (err) {{
        errors.push(endpoint + ': ' + err.message);
        if (err.status && err.status !== 404) throw err;
      }}
    }}
    throw new Error(errors.join(' | ') || 'No clinical-question endpoint available');
  }}

  askBtn.addEventListener('click', async () => {{
    if (getCount() >= MAX_QUESTIONS) {{
      status.textContent = '{limit_msg}';
      return;
    }}
    const text = caseText.value.trim();
    if (!text) {{
      status.textContent = '{empty_msg}';
      return;
    }}
    askBtn.disabled = true;
    status.textContent = '{loading_msg}';
    result.textContent = '';
    planLinkWrap.classList.remove('is-visible');
    startProgress();
    try {{
      const payload = await postClinicalQuestion({{ case_text: text, locale: document.documentElement.lang || 'uk', user_id: getUserId() }});
      if (typeof payload.questions_used === 'number') setCount(payload.questions_used);
      else setCount(getCount() + 1);
      result.textContent = renderPayload(payload);
      await updatePlanGeneratorLink(payload);
      status.textContent = payload.status || 'ok';
      finishProgress(true);
    }} catch (err) {{
      status.textContent = '{error_msg}: ' + err.message;
      result.textContent = '';
      planLinkWrap.classList.remove('is-visible');
      finishProgress(false);
    }} finally {{
      updateQuota();
    }}
  }});
  clearBtn.addEventListener('click', () => {{
    caseText.value = '';
    result.textContent = '';
    status.textContent = '';
    planLinkWrap.classList.remove('is-visible');
    resetProgress();
  }});
  renderExamples();
  getUserId();
  updateQuota();
  resetProgress();
}})();
</script>
</body>
</html>
"""


# ── Try page (Pyodide interactive) ────────────────────────────────────────


_PYODIDE_VERSION = "0.26.4"


def render_try(
    *,
    target_lang: str = "en",
    bundle_version: str = "",
    questionnaires_manifest: list = None,
    examples_manifest: list = None,
) -> str:
    # Pyodide assets live at site root — root-relative paths work for both
    # /try.html (EN, default) and /ukr/try.html (UA mirror). The Pyodide
    # engine bundle is a single shared copy.
    #
    # Dropdown manifests (~15 KB total) are inlined as JS constants so the
    # form populates instantly. Full questionnaires.json (~640 KB) and
    # examples.json (~230 KB) are lazy-fetched only after the user selects
    # an option — saves ~870 KB on first paint.
    qm = questionnaires_manifest if questionnaires_manifest is not None else []
    em = examples_manifest if examples_manifest is not None else []
    qm_json = json.dumps(qm, ensure_ascii=False).replace("</", "<\\/")
    em_json = json.dumps(em, ensure_ascii=False).replace("</", "<\\/")
    page_title = "Plan Builder" if target_lang == "en" else "План лікування"
    page_lead = (
        "Build a cited treatment-plan draft from a virtual patient profile. "
        "The in-browser engine shows which diagnosis, staging, biomarker and safety fields change the plan. "
        "<strong>No real patient data.</strong> Drafts are stored in your browser localStorage."
        if target_lang == "en" else
        "Побудуйте цитований draft-план лікування з віртуального профілю пацієнта. "
        "Браузерний engine показує, які поля діагнозу, стадії, біомаркерів і безпеки змінюють план. "
        "<strong>Жодних реальних пацієнтських даних.</strong> Чернетка зберігається у browser localStorage."
    )
    return f"""<!DOCTYPE html>
<html lang="{'en' if target_lang == 'en' else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · {page_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0a2e1a">
<meta name="mobile-web-app-capable" content="yes">
<link href="/style.css" rel="stylesheet">
</head>
<body>
{_render_top_bar(active="try", target_lang=target_lang, lang_switch_href=_lang_switch_href("try", target_lang))}

<main class="try-page">
  <h1>{page_title}</h1>
  <p class="lead">
    {page_lead}
  </p>

  <!-- Top status banner stays for loading/warnings. Success messages live in
       the lower status area so examples do not push the questionnaire down. -->
  <div id="statusTop" class="status-top is-busy" data-kind="info" role="status" aria-live="polite">
    <span class="status-top-spinner" aria-hidden="true"></span>
    <span class="status-top-body">
      <span class="status-top-text">{'Loading questionnaires…' if target_lang == 'en' else 'Завантажую опитувальники…'}</span>
      <span class="status-top-progress" aria-hidden="true">
        <span id="statusTopProgress" class="status-top-progress-fill"></span>
      </span>
    </span>
  </div>

  <div class="quest-toolbar" data-step-label="{'1. Pick a disease and (optionally) an example' if target_lang == 'en' else '1. Оберіть хворобу та (опційно) приклад'}">
    <label class="qt-label">
      {'Disease' if target_lang == 'en' else 'Хвороба'}
      <input id="diseaseSearch" type="search"
             placeholder="{'Search · name, abbreviation (HCC, DLBCL), or ICD' if target_lang == 'en' else 'Пошук · назва, скорочення (HCC, DLBCL) або ICD'}"
             autocomplete="off"
             aria-label="{'Filter diseases' if target_lang == 'en' else 'Фільтр хвороб'}">
      <select id="diseaseSelect">
        <option value="">{'— select —' if target_lang == 'en' else '— оберіть —'}</option>
      </select>
    </label>
    <label class="qt-label">
      {'Load an example' if target_lang == 'en' else 'Завантажити приклад'}
      <select id="exampleSelect">
        <option value="">{'— select —' if target_lang == 'en' else '— оберіть —'}</option>
      </select>
    </label>
    <div class="qt-spacer"></div>
    <div class="qt-modes">
      <button id="modeFormBtn" class="mode-btn active" data-mode="form">{'Form' if target_lang == 'en' else 'Форма'}</button>
      <button id="modeJsonBtn" class="mode-btn" data-mode="json">Raw JSON (advanced)</button>
    </div>
    <button id="resetBtn" class="btn btn-secondary qt-reset">{'Clear' if target_lang == 'en' else 'Очистити'}</button>
  </div>

  <div class="quest-readiness" id="questReadiness">
    <div class="quest-readiness-head">
      <span>{'Questionnaire readiness' if target_lang == 'en' else 'Готовність анкети'}</span>
      <span class="quest-readiness-score"><span id="progressText">0 / 0</span> · <span id="progressPct">0%</span></span>
    </div>
    <div class="impact-bar" aria-hidden="true">
      <div class="impact-bar-fill" id="progressFill"></div>
    </div>
    <div class="quest-readiness-critical" id="readinessCriticalText">
      {'Pick a disease to start.' if target_lang == 'en' else 'Оберіть хворобу, щоб почати.'}
    </div>
  </div>

  <div class="try-actions quest-cta quest-actions-top" aria-label="{'Plan actions' if target_lang == 'en' else 'Дії з планом'}">
    <button id="runBtn" class="btn btn-primary" type="button" disabled>
      {'Generate full Plan' if target_lang == 'en' else 'Згенерувати повний Plan'}
    </button>
    <button id="viewPlanBtn" class="btn btn-primary" type="button" disabled>
      {'Show plan' if target_lang == 'en' else 'Показати план'}
    </button>
    <button id="pdfBtn" class="btn btn-primary" type="button" disabled
            title="{'Save as PDF via your browser print dialog' if target_lang == 'en' else 'Зберегти як PDF через діалог друку браузера'}">
      {'Download PDF' if target_lang == 'en' else 'Скачати PDF'}
    </button>
  </div>

  <!-- Early-paint warmup: a tiny synchronous script that runs before the
       module-script below. Populates dropdowns from a localStorage cache
       (written on the previous successful boot) so repeat visitors see
       a filled dropdown the moment the toolbar renders, without waiting
       for the Pyodide-importing module script to download + parse. The
       module script later re-renders from the inline manifest, which
       wins if the cached version is stale. -->
  <script>
  (function() {{
    try {{
      localStorage.removeItem('openonco-manifests-v1');
      localStorage.removeItem('openonco-manifests-v2');
      var raw = localStorage.getItem('openonco-manifests-v3');
      if (!raw) return;
      var data = JSON.parse(raw);
      var ds = document.getElementById('diseaseSelect');
      function cleanCachedQuestionnaireTitle(q) {{
        if (!q) return '';
        var title = {'(q.title_en || q.title || "")' if target_lang == 'en' else '(q.title_uk || q.title_en || q.title || "")'};
        var stubNotice = 'auto-generated ' + 'STUB';
        title = String(title).replace(new RegExp('\\\\s*\\\\(' + stubNotice + '\\\\)\\\\s*', 'ig'), '').trim();
        var icd10 = q.icd_10 ? String(q.icd_10).trim() : '';
        var icdo3 = q.disease_icd ? String(q.disease_icd).trim() : '';
        if (icd10) return title + ' · ICD-10 ' + icd10;
        if (icdo3) return title + ' · ICD-O-3 ' + icdo3;
        return title;
      }}
      if (ds && data && Array.isArray(data.questionnaires)) {{
        var frag = document.createDocumentFragment();
        var ph = document.createElement('option');
        ph.value = ''; ph.textContent = '{"— select —" if target_lang == "en" else "— оберіть —"}';
        frag.appendChild(ph);
        data.questionnaires.forEach(function(q, i) {{
          var opt = document.createElement('option');
          opt.value = i;
          opt.textContent = cleanCachedQuestionnaireTitle(q);
          frag.appendChild(opt);
        }});
        ds.innerHTML = '';
        ds.appendChild(frag);
        ds.dataset.warmedUp = '1';
      }}
      var es = document.getElementById('exampleSelect');
      if (es && data && Array.isArray(data.examples)) {{
        var frag2 = document.createDocumentFragment();
        var ph2 = document.createElement('option');
        ph2.value = ''; ph2.textContent = '{"— select an example —" if target_lang == "en" else "— оберіть приклад —"}';
        frag2.appendChild(ph2);
        data.examples.forEach(function(ex, i) {{
          var opt = document.createElement('option');
          opt.value = i;
          var base = {'(ex.label_en || ex.label)' if target_lang == 'en' else 'ex.label'};
          var quality = {'(ex.quality_label_en || ex.quality_label)' if target_lang == 'en' else 'ex.quality_label'};
          opt.textContent = quality ? (base + ' · ' + quality) : base;
          frag2.appendChild(opt);
        }});
        es.innerHTML = '';
        es.appendChild(frag2);
      }}
    }} catch (e) {{ /* silent */ }}
  }})();
  </script>

  <div class="quest-grid">
    <section class="quest-form-pane" id="formPane">
      <div id="exampleLockBanner" class="example-lock-banner" hidden>
        <div class="elb-text">
          <strong>📋 {'Example loaded.' if target_lang == 'en' else 'Завантажено приклад.'}</strong>
          {'Filled fields are locked so you do not accidentally change the example data. Click the button to edit anything.' if target_lang == 'en' else 'Заповнені поля заблоковано, щоб випадково не змінити дані прикладу. Натисни кнопку, щоб редагувати все.'}
        </div>
        <button id="personalizeBtn" type="button" class="btn btn-secondary elb-btn">
          {'Personalise this example' if target_lang == 'en' else 'Персоналізувати цей приклад'}
        </button>
      </div>
      <div id="questGroups"></div>
      <div id="questEmpty" class="quest-empty">
        {'Pick a disease from the list above to start the questionnaire.' if target_lang == 'en' else 'Оберіть хворобу зі списку вище, щоб почати опитування.'}
      </div>
      <div id="questIntro" class="quest-intro" hidden></div>
    </section>

    <section class="quest-form-pane" id="jsonPane" hidden>
      <label class="qt-label">
        Patient profile (JSON)
        <textarea id="patientJson" rows="28" spellcheck="false"
                  placeholder='{{"patient_id": "...", "disease": {{"icd_o_3_morphology": "9699/3"}}, ...}}'></textarea>
      </label>
      <div class="try-actions">
        <button id="formatBtn" class="btn btn-secondary">Format JSON</button>
      </div>
    </section>

    <aside class="quest-side">
      <div class="quest-build-card" id="buildCard">
        <div class="build-card-head">
          <h3>{'Build' if target_lang == 'en' else 'Збірка'}</h3>
          <span id="pwaInstallState" class="build-state">{'Browser' if target_lang == 'en' else 'Браузер'}</span>
        </div>
        <dl class="build-meta">
          <div><dt>Core</dt><dd id="coreVersion">v{bundle_version or 'pending'}</dd></div>
          <div><dt>{'Disease' if target_lang == 'en' else 'Хвороба'}</dt><dd id="diseaseVersion">—</dd></div>
          <div><dt>{'Cache' if target_lang == 'en' else 'Кеш'}</dt><dd id="cacheState">{'Checking…' if target_lang == 'en' else 'Перевіряю…'}</dd></div>
          <div><dt>{'Offline' if target_lang == 'en' else 'Offline'}</dt><dd id="offlineState">{'Network required for first launch' if target_lang == 'en' else 'Мережа потрібна для першого запуску'}</dd></div>
          <div><dt>{'Modules' if target_lang == 'en' else 'Модулі'}</dt><dd id="offlineModulesState">{'Waiting for index' if target_lang == 'en' else 'Чекаю індекс'}</dd></div>
        </dl>
        <div class="offline-cache-progress" id="offlineCacheProgress">
          <div class="offline-cache-bar" id="offlineCacheBar" role="progressbar" aria-label="{'Offline module cache progress' if target_lang == 'en' else 'Прогрес офлайн-кешу модулів'}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div class="offline-cache-fill" id="offlineCacheFill"></div>
          </div>
          <div class="offline-cache-text" id="offlineCacheText">{'Offline cache not started' if target_lang == 'en' else 'Офлайн-кеш ще не запущено'}</div>
        </div>
      </div>

      <div id="status" class="status is-busy">{'Loading questionnaires…' if target_lang == 'en' else 'Завантажую опитувальники…'}</div>
      <div id="error" class="error" hidden></div>
    </aside>
  </div>

  <div id="planModal" class="plan-modal" hidden role="dialog" aria-modal="true"
       aria-label="{'Treatment plan' if target_lang == 'en' else 'План лікування'}">
    <div class="plan-modal-card">
      <div class="plan-modal-toolbar">
        <div class="rt-lang-group" role="group" aria-label="{'Plan language' if target_lang == 'en' else 'Мова плану'}">
          <span class="rt-lang-label">{'Language:' if target_lang == 'en' else 'Мова:'}</span>
          <button id="langUaBtn" class="rt-lang-btn" type="button" data-lang="uk">UA</button>
          <button id="langEnBtn" class="rt-lang-btn" type="button" data-lang="en">EN</button>
        </div>
        <div class="rt-lang-group" role="group" aria-label="{'Audience' if target_lang == 'en' else 'Аудиторія'}">
          <span class="rt-lang-label">{'View:' if target_lang == 'en' else 'Версія:'}</span>
          <button id="modeClinicianBtn" class="rt-lang-btn is-active" type="button"
                  data-mode="clinician"
                  title="{'Full tumor-board brief — for clinicians' if target_lang == 'en' else 'Повний tumor-board brief — для лікаря'}">{'Clinician' if target_lang == 'en' else 'Лікар'}</button>
          <button id="modePatientBtn" class="rt-lang-btn" type="button"
                  data-mode="patient"
                  title="{'Plain-Ukrainian simplified report — for patients' if target_lang == 'en' else 'Спрощений звіт зрозумілою мовою — для пацієнта'}">{'Patient' if target_lang == 'en' else 'Пацієнт'}</button>
        </div>
        <div class="plan-modal-actions">
          <button id="modalHtmlBtn" class="rt-btn" type="button" disabled
                  title="{'Save the current view as a single-file HTML' if target_lang == 'en' else 'Зберегти поточну версію як один HTML-файл'}">
            <span aria-hidden="true">⬇</span> HTML
          </button>
          <button id="modalPdfBtn" class="rt-btn" type="button"
                  title="{'Save as PDF via your browser print dialog' if target_lang == 'en' else 'Зберегти як PDF через діалог друку браузера'}">
            <span aria-hidden="true">📄</span> PDF
          </button>
          <button id="planModalClose" class="rt-btn rt-btn-ghost" type="button"
                  aria-label="{'Close' if target_lang == 'en' else 'Закрити'}">✕</button>
        </div>
      </div>
      <iframe id="resultFrame"></iframe>
    </div>
  </div>

  <footer class="page-foot">
    {'Something not working? <a href="' + GH_NEW_ISSUE + '?title=%5Btry-page%5D+&labels=tester-feedback" target="_blank" rel="noopener">Open an issue</a>.' if target_lang == 'en' else 'Якщо щось не працює — <a href="' + GH_NEW_ISSUE + '?title=%5Btry-page%5D+&labels=tester-feedback" target="_blank" rel="noopener">відкрий issue</a>.'}
    Pyodide v{_PYODIDE_VERSION} · engine bundle <code>openonco-engine-core.zip</code> + per-disease modules.
  </footer>
</main>

<div id="initOverlay" class="init-overlay" hidden role="status" aria-live="polite">
  <div class="init-card">
    <h3>{'Starting the OpenOnco engine' if target_lang == 'en' else 'Готую двигун OpenOnco'}</h3>
    <p class="init-lead">{'The first launch takes ~10–20 seconds — the engine loads directly into your browser. Patient data never leaves your device.' if target_lang == 'en' else 'Перший запуск триває ~10–20 секунд — двигун завантажується безпосередньо у твій браузер. Дані пацієнта не лишають твого пристрою.'}</p>
    <ol class="init-stages" id="initStages">
      <li data-stage="pyodide" class="stage pending">{'Loading the in-browser runtime (~6 MB)' if target_lang == 'en' else 'Готую обчислювач у браузері (~6 МБ)'}</li>
      <li data-stage="pydeps" class="stage pending">{'Setting up the environment' if target_lang == 'en' else 'Налаштовую середовище'}</li>
      <li data-stage="bundle" class="stage pending">{'Loading the OpenOnco knowledge base' if target_lang == 'en' else 'Завантажую базу знань OpenOnco'}</li>
      <li data-stage="validate" class="stage pending">{'Verifying the clinical KB' if target_lang == 'en' else 'Звіряю клінічну базу'}</li>
      <li data-stage="generate" class="stage pending">{'Building a personalised plan' if target_lang == 'en' else 'Будую персональний план'}</li>
    </ol>
    <p class="init-hint" id="initHint">{"If it's working now, next time it'll be ~5 s — the engine stays in memory." if target_lang == 'en' else "Якщо зараз вийшло, наступного разу буде ~5 с — двигун залишається в пам'яті."}</p>
  </div>
</div>

<div id="generatingOverlay" class="generating-overlay" hidden role="dialog" aria-live="polite" aria-modal="true">
  <div class="generating-card">
    <div class="generating-spinner" aria-hidden="true"></div>
    <h3 id="generatingTitle">{'Generating plan…' if target_lang == 'en' else 'Генерую план…'}</h3>
    <p id="generatingLead">{'Hold on 5–15 s. Fields are locked so the result matches the current input.' if target_lang == 'en' else 'Зачекай 5–15 с. Поля заблоковано, щоб результат відповідав поточному вводу.'}</p>
    <p class="generating-hint" id="generatingHint">{'Starting the engine…' if target_lang == 'en' else 'Запускаю двигун…'}</p>
  </div>
</div>

<script type="module">
// Pyodide is loaded lazily on first Generate-click so a slow CDN fetch
// (~few-100 KB module + parse) doesn't block dropdown population.
// Static `import …` would gate the entire module-script body on
// pyodide.mjs being fetched & parsed — meaning the form looked frozen
// on cold visits even though the manifests are already in this HTML.
let loadPyodide = null;
async function ensurePyodideLoader() {{
  if (loadPyodide) return loadPyodide;
  const mod = await import("https://cdn.jsdelivr.net/pyodide/v{_PYODIDE_VERSION}/full/pyodide.mjs");
  loadPyodide = mod.loadPyodide;
  return loadPyodide;
}}

const STORAGE_KEY = 'openonco-try-draft-v1';

// ── DOM refs ──────────────────────────────────────────────────────────────
const status = document.getElementById('status');
const statusTop = document.getElementById('statusTop');
const statusTopText = statusTop ? statusTop.querySelector('.status-top-text') : null;
const statusTopProgress = document.getElementById('statusTopProgress');
const errorBox = document.getElementById('error');
const runBtn = document.getElementById('runBtn');
const formatBtn = document.getElementById('formatBtn');
const resetBtn = document.getElementById('resetBtn');
const diseaseSelect = document.getElementById('diseaseSelect');
const diseaseSearch = document.getElementById('diseaseSearch');
const exampleSelect = document.getElementById('exampleSelect');
const textarea = document.getElementById('patientJson');
const resultFrame = document.getElementById('resultFrame');
const pdfBtn = document.getElementById('pdfBtn');
const modalPdfBtn = document.getElementById('modalPdfBtn');
const viewPlanBtn = document.getElementById('viewPlanBtn');
const planModal = document.getElementById('planModal');
const planModalClose = document.getElementById('planModalClose');
const langUaBtn = document.getElementById('langUaBtn');
const langEnBtn = document.getElementById('langEnBtn');
const modeClinicianBtn = document.getElementById('modeClinicianBtn');
const modePatientBtn = document.getElementById('modePatientBtn');
const modalHtmlBtn = document.getElementById('modalHtmlBtn');
const formPane = document.getElementById('formPane');
const jsonPane = document.getElementById('jsonPane');
const questGroups = document.getElementById('questGroups');
const questIntro = document.getElementById('questIntro');
const questEmpty = document.getElementById('questEmpty');
const personalizeBtn = document.getElementById('personalizeBtn');
const modeFormBtn = document.getElementById('modeFormBtn');
const modeJsonBtn = document.getElementById('modeJsonBtn');

const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const progressPct = document.getElementById('progressPct');
const readinessCriticalText = document.getElementById('readinessCriticalText');
const coreVersionEl = document.getElementById('coreVersion');
const diseaseVersionEl = document.getElementById('diseaseVersion');
const cacheStateEl = document.getElementById('cacheState');
const offlineStateEl = document.getElementById('offlineState');
const pwaInstallStateEl = document.getElementById('pwaInstallState');
const offlineModulesStateEl = document.getElementById('offlineModulesState');
const offlineCacheBarEl = document.getElementById('offlineCacheBar');
const offlineCacheFillEl = document.getElementById('offlineCacheFill');
const offlineCacheTextEl = document.getElementById('offlineCacheText');
const generatingOverlay = document.getElementById('generatingOverlay');
const generatingTitle = document.getElementById('generatingTitle');
const generatingLead = document.getElementById('generatingLead');
const generatingHint = document.getElementById('generatingHint');
const mainTryEl = document.querySelector('main.try-page');
const initOverlay = document.getElementById('initOverlay');
const initStagesEl = document.getElementById('initStages');

// ── State ─────────────────────────────────────────────────────────────────
let pyodide = null;
let enginReady = false;
// CSD-6E + CSD-9C: bundle lazy-load state. `bundleIndex` is the parsed
// index (resolved from /openonco-engine-index.json); `coreBundleLoaded`
// is set after the first core extract; `loadedDiseases` remembers which
// per-disease modules we've already merged so re-runs against the same
// disease don't re-fetch. The legacy monolithic fallback was retired in
// CSD-9C — lazy-load is the only path now.
const BUNDLE_INDEX_URL = '/openonco-engine-index.json';
const CORE_BUNDLE_URL = '/openonco-engine-core.zip';
let bundleIndex = null;
let coreBundleLoaded = false;
const loadedDiseases = new Set();
let offlineCacheStarted = false;
let offlineCacheDone = 0;
let offlineCacheTotal = 0;
let offlineCacheFailed = 0;
// Build-time manifests — instant dropdown population, no fetch.
const QUESTIONNAIRES_MANIFEST = {qm_json};
const EXAMPLES_MANIFEST = {em_json};
const PAGE_LANG = '{target_lang}';
let questionnaires = null;   // lazy-fetched from /questionnaires.json on first need
let examples = null;         // lazy-fetched from /examples.json on first need
let _questionnairesPromise = null;
let _examplesPromise = null;
let activeQuest = null;      // currently selected questionnaire
let generating = false;      // true while runEngine is mid-flight; blocks
                             // input via <main inert> + overlay so the
                             // rendered plan matches a stable snapshot
let uiBusy = false;          // true while a user-triggered async load is
                             // in flight; blocks pointer/keyboard input
                             // with the same modal overlay
let previewToken = 0;        // bumped on each runLivePreview start AND on
                             // runEngine start; stale results are discarded
let answers = {{}};          // {{dotted_path: value}}
let mode = 'form';           // 'form' | 'json'
let evalDebounceTimer = null;    // preview debounce
let whatIfDebounceTimer = null;  // what-if debounce — separate + longer so
                                 // dropdowns/typing don't trigger expensive
                                 // shadow evals every 400ms
let lastPreviewResult = null;    // most recent preview result, fed to
                                 // what-if when its (longer) timer fires
const PREVIEW_DEBOUNCE_MS = 400;
const WHATIF_DEBOUNCE_MS = 1500;

const UI_LOCK_TEXT = {{
  generateTitle: '{"Generating plan…" if target_lang == "en" else "Генерую план…"}',
  generateLead: '{"Hold on 5–15 s. Fields are locked so the result matches the current input." if target_lang == "en" else "Зачекай 5–15 с. Поля заблоковано, щоб результат відповідав поточному вводу."}',
  loadingTitle: '{"Loading…" if target_lang == "en" else "Завантаження…"}',
  loadingLead: '{"Please wait. Actions are locked until loading finishes." if target_lang == "en" else "Зачекайте. Дії заблоковано, доки завантаження не завершиться."}',
  diseaseHint: '{"Loading the questionnaire…" if target_lang == "en" else "Завантажую опитувальник…"}',
  exampleHint: '{"Loading the example and plan…" if target_lang == "en" else "Завантажую приклад і план…"}',
  planHint: '{"Loading the plan view…" if target_lang == "en" else "Завантажую перегляд плану…"}',
  qrHint: '{"Loading profile from QR…" if target_lang == "en" else "Завантажую профіль із QR…"}',
  renderHint: '{"Rendering the plan view…" if target_lang == "en" else "Перемальовую перегляд плану…"}',
  actionLocked: '{"Action locked while the current process finishes." if target_lang == "en" else "Дію заблоковано, доки поточний процес не завершиться."}',
}};

// Initial render language follows the page lang (EN on /try.html, UA on
// /ukr/try.html). User can switch via the buttons in the result toolbar
// without re-running the engine — Pyodide caches _oo_result/_oo_mdt.
let currentResultLang = PAGE_LANG;

// Audience mode for the plan render — 'clinician' (default, full tumor-
// board brief) or 'patient' (plain-UA simplified report). Per
// PATIENT_MODE_SPEC §3, patient mode is treatment-plan only; the toggle
// is disabled for diagnostic-mode results and for example-mode bundles
// (pre-built /cases/<id>.html files don't have a patient-rendered twin).
let currentResultMode = 'clinician';

// planSource tracks where the plan currently shown in the modal came from:
//   null        — no plan yet (form not generated, no example loaded)
//   'example'   — pre-built case HTML loaded from /cases/<case_id>.html;
//                 generate stays disabled because plan IS already generated,
//                 we don't want to lie that clicking does new work
//   'generated' — engine produced this plan from the current profile
// planDirty flips to true the moment the user edits any field (form or JSON)
// after a plan has been shown, which re-enables Generate so the user can
// recompute against the modified profile.
let planSource = null;
let planDirty = false;
let activeExampleCaseId = null;

// ── Helpers ───────────────────────────────────────────────────────────────
function setStatus(msg, kind = 'info', topMode = 'auto') {{
  status.textContent = msg;
  status.dataset.kind = kind;
  // Mirror important transient states to the prominent top banner.
  //  topMode='busy'  → spinner, blue
  //  topMode='ok'    → green ✓
  //  topMode='warn'  → amber
  //  topMode='hide'  → hide top banner (sidebar still updates)
  //  topMode='auto'  → kind=info shows busy, ok→green, warn→amber
  if (!statusTop || !statusTopText) return;
  let mode = topMode;
  if (mode === 'auto') {{
    if (kind === 'ok') mode = 'hide';
    else if (kind === 'warn') mode = 'warn';
    else if (!msg) mode = 'hide';
    else mode = 'busy';
  }}
  if (mode === 'hide' || !msg) {{
    status.classList.remove('is-busy');
    statusTop.hidden = true;
    statusTop.classList.remove('is-busy', 'is-ok', 'is-warn', 'has-progress');
    statusTopText.textContent = '';
    clearLoadingProgress();
    return;
  }}
  status.classList.toggle('is-busy', mode === 'busy');
  statusTop.hidden = false;
  statusTopText.textContent = msg;
  statusTop.dataset.kind = kind;
  statusTop.classList.toggle('is-busy', mode === 'busy');
  statusTop.classList.toggle('is-ok', mode === 'ok');
  statusTop.classList.toggle('is-warn', mode === 'warn');
  if (mode !== 'busy') clearLoadingProgress();
}}
function setLoadingProgress(percent) {{
  if (!statusTop || !statusTopProgress) return;
  const pct = Math.max(0, Math.min(100, Number(percent) || 0));
  statusTop.classList.add('has-progress');
  statusTopProgress.style.setProperty('--status-progress', pct + '%');
}}
function clearLoadingProgress() {{
  if (!statusTop || !statusTopProgress) return;
  statusTop.classList.remove('has-progress');
  statusTopProgress.style.removeProperty('--status-progress');
}}
function setError(msg) {{
  if (msg) {{
    errorBox.hidden = false;
    errorBox.textContent = msg;
  }} else {{
    errorBox.hidden = true;
    errorBox.textContent = '';
  }}
}}

function setText(el, value) {{
  if (el) el.textContent = value;
}}

function setOfflineCacheProgress(done, total, failed = 0) {{
  offlineCacheDone = done;
  offlineCacheTotal = total;
  offlineCacheFailed = failed;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  if (offlineCacheBarEl) offlineCacheBarEl.setAttribute('aria-valuenow', String(pct));
  if (offlineCacheFillEl) offlineCacheFillEl.style.width = pct + '%';
  if (offlineCacheTextEl) {{
    if (total <= 0) {{
      offlineCacheTextEl.textContent = '{"Offline cache not started" if target_lang == "en" else "Офлайн-кеш ще не запущено"}';
    }} else if (done >= total && failed === 0) {{
      offlineCacheTextEl.textContent = '{"All modules cached for offline use" if target_lang == "en" else "Усі модулі збережено для офлайну"}';
    }} else if (done >= total) {{
      offlineCacheTextEl.textContent = '{"Cached with some failed modules" if target_lang == "en" else "Кеш готовий частково, є помилки"}' + ' (' + failed + ')';
    }} else {{
      offlineCacheTextEl.textContent = '{"Caching modules" if target_lang == "en" else "Кешую модулі"}' + ' ' + done + ' / ' + total;
    }}
  }}
  if (offlineModulesStateEl) {{
    if (total <= 0) setText(offlineModulesStateEl, '{"Waiting for index" if target_lang == "en" else "Чекаю індекс"}');
    else if (done >= total && failed === 0) setText(offlineModulesStateEl, '{"Ready offline" if target_lang == "en" else "Офлайн готовий"}');
    else if (done >= total) setText(offlineModulesStateEl, '{"Partial cache" if target_lang == "en" else "Частковий кеш"}');
    else setText(offlineModulesStateEl, Math.round((done / total) * 100) + '%');
  }}
}}

async function refreshBuildPanel(diseaseId = null) {{
  const online = navigator.onLine !== false;
  setText(offlineStateEl, online
    ? '{"Online" if target_lang == "en" else "Онлайн"}'
    : '{"Offline - cached bundles only" if target_lang == "en" else "Offline - лише кешовані bundle"}');

  const swControlled = !!(navigator.serviceWorker && navigator.serviceWorker.controller);
  setText(cacheStateEl, swControlled
    ? '{"Service worker active" if target_lang == "en" else "Service worker активний"}'
    : '{"Browser cache pending" if target_lang == "en" else "Кеш браузера очікує"}');
  setText(pwaInstallStateEl, window.matchMedia('(display-mode: standalone)').matches
    ? '{"Installed" if target_lang == "en" else "Встановлено"}'
    : '{"Browser" if target_lang == "en" else "Браузер"}');

  if (bundleIndex) {{
    setText(coreVersionEl, 'v' + (bundleIndex.core_version || '{bundle_version or "unknown"}'));
    if (offlineCacheTotal <= 0) {{
      const total = offlineBundleUrls().length;
      setOfflineCacheProgress(0, total, 0);
    }}
    if (diseaseId) {{
      const dver = (bundleIndex.disease_versions || {{}})[diseaseId];
      setText(diseaseVersionEl, dver ? diseaseId + ' / v' + dver : diseaseId + ' / core');
    }}
  }}
}}

// ── Plan modal + lang switcher ────────────────────────────────────────────
function highlightLangButtons() {{
  langUaBtn.classList.toggle('is-active', currentResultLang === 'uk');
  langEnBtn.classList.toggle('is-active', currentResultLang === 'en');
}}

function highlightModeButtons() {{
  modeClinicianBtn.classList.toggle('is-active', currentResultMode === 'clinician');
  modePatientBtn.classList.toggle('is-active', currentResultMode === 'patient');
}}

function isInteractionLocked() {{
  return uiBusy || generating;
}}

function setLockedTitle(el, locked) {{
  if (!el) return;
  if (typeof el.dataset.baseTitle === 'undefined') {{
    el.dataset.baseTitle = el.getAttribute('title') || '';
  }}
  if (locked) el.setAttribute('title', UI_LOCK_TEXT.actionLocked);
  else if (el.dataset.baseTitle) el.setAttribute('title', el.dataset.baseTitle);
  else el.removeAttribute('title');
}}

// Patient mode is render-only on top of an already-generated treatment
// PlanResult. It can't toggle for:
//   * diagnostic-mode bundles (no `_render_patient_mode` for DiagnosticPlan)
//   * example-mode (pre-built /cases/*.html — no Pyodide engine running)
//   * pre-generation (planSource === null)
function refreshModeButtonAvailability() {{
  const locked = isInteractionLocked();
  const canPatient = (
    pyodide
    && planSource === 'generated'
    && !planDirty
  );
  modePatientBtn.disabled = locked || !canPatient;
  if (!canPatient) {{
    modePatientBtn.title = (
      planSource === 'example'
        ? '{ "Patient view is available for plans you generate yourself — not for example bundles yet" if target_lang == "en" else "Пацієнтська версія доступна лише для планів, які ви згенерували — не для прикладів" }'
        : '{ "Generate a plan first to enable Patient view" if target_lang == "en" else "Згенеруйте план, щоб увімкнути пацієнтську версію" }'
    );
    if (currentResultMode === 'patient') {{
      currentResultMode = 'clinician';
      highlightModeButtons();
    }}
  }} else {{
    modePatientBtn.title = '{ "Plain-Ukrainian simplified report — for patients" if target_lang == "en" else "Спрощений звіт зрозумілою мовою — для пацієнта" }';
  }}
  modeClinicianBtn.disabled = locked || (planSource === null);
  if (locked) {{
    modePatientBtn.title = UI_LOCK_TEXT.actionLocked;
    modeClinicianBtn.title = UI_LOCK_TEXT.actionLocked;
  }}
}}

function openPlanModal(options = {{}}) {{
  if (!planModal) return;
  if (!options.force && (isInteractionLocked() || planSource === null)) return;
  planModal.hidden = false;
  highlightLangButtons();
}}
function closePlanModal(options = {{}}) {{
  if (!planModal) return;
  if (!options.force && isInteractionLocked()) return;
  planModal.hidden = true;
}}

function downloadPdf() {{
  // Browser-native print → "Save as PDF" works on every modern browser.
  // The render layer ships A4-print-friendly CSS (@page + @media print)
  // so the iframe content paginates cleanly without any extra deps.
  if (uiBusy || generating) return;
  if (planSource == null) return;
  // Modal must be visible so iframe contentWindow is fully laid out and
  // print() picks up the right document.
  const wasHidden = planModal && planModal.hidden;
  if (wasHidden) openPlanModal({{ force: true }});
  try {{
    resultFrame.contentWindow.focus();
    resultFrame.contentWindow.print();
  }} catch (e) {{
    setError('Print failed: ' + (e.message || e));
  }}
}}

async function switchResultMode(newMode) {{
  if (newMode === currentResultMode) return;
  if (modePatientBtn.disabled && newMode === 'patient') return;
  if (!pyodide || planSource !== 'generated') return;
  await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.renderHint, async () => {{
    modeClinicianBtn.disabled = true;
    modePatientBtn.disabled = true;
    try {{
      pyodide.globals.set('_target_lang', currentResultLang);
      pyodide.globals.set('_target_mode', newMode);
      const html = await pyodide.runPythonAsync(`
if _oo_mode == 'diagnostic':
    # Patient mode is treatment-only per PATIENT_MODE_SPEC §3 — fall back
    # to the clinician diagnostic brief regardless of mode toggle.
    html = render_diagnostic_brief_html(_oo_result, mdt=_oo_mdt, target_lang=_target_lang)
else:
    html = render_plan_html(
        _oo_result, mdt=_oo_mdt, target_lang=_target_lang, mode=_target_mode,
    )
html
`);
      resultFrame.removeAttribute('src');
      resultFrame.srcdoc = html;
      currentResultMode = newMode;
      highlightModeButtons();
    }} catch (e) {{
      setError('Re-render failed: ' + (e.message || e));
    }} finally {{
      refreshModeButtonAvailability();
    }}
  }});
}}

function downloadHtml() {{
  if (uiBusy || generating) return;
  if (planSource == null) return;
  let html = resultFrame.srcdoc;
  if (!html) {{
    try {{
      html = '<!DOCTYPE html>\\n' + resultFrame.contentDocument.documentElement.outerHTML;
    }} catch (e) {{
      setError('Could not read the rendered document: ' + (e.message || e));
      return;
    }}
  }}
  const blob = new Blob([html], {{ type: 'text/html;charset=utf-8' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  // Filename encodes audience + lang so a doctor downloading both for the
  // same patient gets distinct files: openonco-plan.<mode>.<lang>.html
  const stamp = new Date().toISOString().slice(0, 10);
  const modePart = (planSource === 'generated' ? '.' + currentResultMode : '');
  a.href = url;
  a.download = `openonco-plan${{modePart}}.${{currentResultLang}}.${{stamp}}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}}

async function switchResultLang(newLang) {{
  if (newLang === currentResultLang) return;
  if (planSource === 'example') {{
    // Pre-built case file: just swap the iframe src to the matching
    // language variant. EN at /cases/<id>.html, UA at /ukr/cases/<id>.html.
    if (!activeExampleCaseId) return;
    await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.planHint, async () => {{
      const frameReady = waitForFrameLoad();
      resultFrame.src = (newLang === 'en' ? '/cases/' : '/ukr/cases/') + activeExampleCaseId + '.html';
      currentResultLang = newLang;
      highlightLangButtons();
      await frameReady;
    }});
    return;
  }}
  if (!pyodide) return;
  await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.renderHint, async () => {{
    // Disable buttons during re-render so user can't double-click
    langUaBtn.disabled = true;
    langEnBtn.disabled = true;
    try {{
      pyodide.globals.set('_target_lang', newLang);
      pyodide.globals.set('_target_mode', currentResultMode);
      const html = await pyodide.runPythonAsync(`
if _oo_mode == 'diagnostic':
    html = render_diagnostic_brief_html(_oo_result, mdt=_oo_mdt, target_lang=_target_lang)
else:
    html = render_plan_html(
        _oo_result, mdt=_oo_mdt, target_lang=_target_lang, mode=_target_mode,
    )
html
`);
      resultFrame.removeAttribute('src');
      resultFrame.srcdoc = html;
      currentResultLang = newLang;
      highlightLangButtons();
    }} catch (e) {{
      setError('Re-render failed: ' + (e.message || e));
    }} finally {{
      langUaBtn.disabled = false;
      langEnBtn.disabled = false;
    }}
  }});
}}

function waitForFrameLoad(timeoutMs = 12000) {{
  if (!resultFrame) return Promise.resolve();
  return new Promise(resolve => {{
    let done = false;
    const finish = () => {{
      if (done) return;
      done = true;
      resultFrame.removeEventListener('load', finish);
      resultFrame.removeEventListener('error', finish);
      resolve();
    }};
    resultFrame.addEventListener('load', finish);
    resultFrame.addEventListener('error', finish);
    setTimeout(finish, timeoutMs);
  }});
}}

async function loadExamplePlan(caseId) {{
  // Show the pre-built case HTML for the just-loaded example so the user
  // sees a plan immediately — without spinning up Pyodide and without
  // pretending the engine just ran. Generate stays disabled until the
  // user edits something (which sets planDirty).
  if (!caseId) return;
  activeExampleCaseId = caseId;
  resultFrame.removeAttribute('srcdoc');
  const frameReady = waitForFrameLoad();
  resultFrame.src = (currentResultLang === 'en' ? '/cases/' : '/ukr/cases/') + caseId + '.html';
  planSource = 'example';
  planDirty = false;
  // Example bundles are always rendered as the clinician view (the
  // pre-built /cases/*.html doesn't have a patient twin yet — see
  // PATIENT_MODE_SPEC §3 + roadmap).
  currentResultMode = 'clinician';
  highlightModeButtons();
  refreshModeButtonAvailability();
  updateWorkflowControls();
  openPlanModal({{ force: true }});
  await frameReady;
}}

function clearPlanState() {{
  planSource = null;
  planDirty = false;
  activeExampleCaseId = null;
  resultFrame.removeAttribute('src');
  resultFrame.removeAttribute('srcdoc');
  viewPlanBtn.disabled = true;
  pdfBtn.disabled = true;
  modalPdfBtn.disabled = true;
  modalHtmlBtn.disabled = true;
  currentResultMode = 'clinician';
  highlightModeButtons();
  refreshModeButtonAvailability();
  closePlanModal({{ force: true }});
}}

pdfBtn.addEventListener('click', downloadPdf);
modalPdfBtn.addEventListener('click', downloadPdf);
modalHtmlBtn.addEventListener('click', downloadHtml);
viewPlanBtn.addEventListener('click', openPlanModal);
planModalClose.addEventListener('click', closePlanModal);
planModal.addEventListener('click', (ev) => {{
  if (ev.target === planModal) closePlanModal();
}});
document.addEventListener('keydown', (ev) => {{
  if ((generating || uiBusy) && ev.key === 'Escape') {{
    ev.preventDefault();
    return;
  }}
  if (ev.key === 'Escape' && !planModal.hidden) closePlanModal();
}});
langUaBtn.addEventListener('click', () => switchResultLang('uk'));
langEnBtn.addEventListener('click', () => switchResultLang('en'));
modeClinicianBtn.addEventListener('click', () => switchResultMode('clinician'));
modePatientBtn.addEventListener('click', () => switchResultMode('patient'));

function escHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }})[c]);
}}

function questionnaireDisplayTitle(q) {{
  if (!q) return '';
  const title = (PAGE_LANG === 'uk'
    ? (q.title_uk || q.title_en || q.title)
    : (q.title_en || q.title)
  ) || '';
  const icd10 = q.icd_10 ? String(q.icd_10).trim() : '';
  const icdo3 = q.disease_icd ? String(q.disease_icd).trim() : '';
  if (icd10) return `${{title}} · ICD-10 ${{icd10}}`;
  if (icdo3) return `${{title}} · ICD-O-3 ${{icdo3}}`;
  return title;
}}

function saveDraft() {{
  try {{
    localStorage.setItem(STORAGE_KEY, JSON.stringify({{
      questId: activeQuest ? activeQuest.id : null,
      answers,
      mode,
      jsonText: textarea.value,
    }}));
  }} catch (e) {{ /* private mode etc — silent fail */ }}
}}

function loadDraft() {{
  try {{
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  }} catch {{ return null; }}
}}

// ── Form rendering ────────────────────────────────────────────────────────
const IMPACT_LABEL = {{
  critical: 'CRITICAL',
  required: 'Required',
  recommended: 'Recommended',
  optional: 'Optional',
}};

// Central action gating. The high-priority controls sit above the form, so
// they must also reflect process locks visually instead of relying only on
// the modal overlay/inert attribute.
function updateWorkflowControls() {{
  const locked = isInteractionLocked();
  let hasInput = false;
  if (mode === 'form') hasInput = !!activeQuest;
  else hasInput = textarea.value.trim().length > 0;
  const planFresh = planSource !== null && !planDirty;
  const hasPlan = planSource !== null;

  runBtn.disabled = locked || !hasInput || planFresh;
  viewPlanBtn.disabled = locked || !hasPlan;
  pdfBtn.disabled = locked || !hasPlan;
  modalPdfBtn.disabled = locked || !hasPlan;
  modalHtmlBtn.disabled = locked || !hasPlan;

  if (resetBtn) resetBtn.disabled = locked;
  if (formatBtn) formatBtn.disabled = locked || mode !== 'json';
  [diseaseSelect, exampleSelect, modeFormBtn, modeJsonBtn, personalizeBtn].forEach(el => {{
    if (el) el.disabled = locked;
  }});
  [runBtn, viewPlanBtn, pdfBtn, resetBtn, formatBtn, diseaseSelect, exampleSelect, modeFormBtn, modeJsonBtn, personalizeBtn].forEach(el => setLockedTitle(el, locked));
  refreshModeButtonAvailability();
}}

// Decoupled from engine readiness — button is clickable as soon as
// there is something to send. The engine itself loads lazily on click
// (and also kicks off in the background after first interaction so the
// live impact panel can populate without waiting for a click).
//
// Disabled when a plan is already shown for the current input — either
// because the user just generated it, or because they loaded an example
// (which auto-displays the pre-built case HTML). Re-enables the moment
// the user edits any field (planDirty), so they can recompute.
function updateRunBtnEnabled() {{
  updateWorkflowControls();
}}

// Mark the currently-shown plan as out-of-sync with the current input.
// Called from every input handler so the next click on Generate runs
// against the modified profile, not the cached/example plan.
function markPlanDirty() {{
  if (planSource !== null) {{
    planDirty = true;
    updateRunBtnEnabled();
  }}
}}

let engineKickoffStarted = false;
function kickoffEngineLoad() {{
  if (engineKickoffStarted) return;
  engineKickoffStarted = true;
  // Don't await — let it run in background so live preview can populate
  // as soon as it's ready. Errors surface via setError on real click.
  ensureEngine().catch(e => console.warn('engine bg load failed:', e));
}}

function hideExampleLockBanner() {{
  const banner = document.getElementById('exampleLockBanner');
  if (banner) banner.hidden = true;
}}
function showExampleLockBanner() {{
  const banner = document.getElementById('exampleLockBanner');
  if (banner) banner.hidden = false;
}}

function lockFilledFields() {{
  // Mark every form field that already has an answer as disabled and
  // tag its wrapper for visual distinction. Fields without a value stay
  // editable so the user can complete anything missing.
  const wrappers = formPane.querySelectorAll('.quest-q');
  wrappers.forEach(wrap => {{
    const field = wrap.dataset.field;
    if (!field) return;
    const inp = wrap.querySelector('input,select,textarea');
    if (!inp) return;
    if (answers[field] !== undefined && answers[field] !== null && answers[field] !== '') {{
      inp.disabled = true;
      wrap.classList.add('locked');
    }} else {{
      inp.disabled = false;
      wrap.classList.remove('locked');
    }}
  }});
}}

function unlockAllFields() {{
  formPane.querySelectorAll('.quest-q').forEach(wrap => {{
    wrap.classList.remove('locked');
    const inp = wrap.querySelector('input,select,textarea');
    if (inp) inp.disabled = false;
  }});
  hideExampleLockBanner();
}}

function renderForm(quest) {{
  activeQuest = quest;
  answers = {{}};
  questGroups.innerHTML = '';
  hideExampleLockBanner();
  if (!quest) {{
    questEmpty.style.display = '';
    questIntro.hidden = true;
    updateRunBtnEnabled();
    return;
  }}
  questEmpty.style.display = 'none';
  if (quest.intro) {{
    questIntro.hidden = false;
    questIntro.textContent = quest.intro;
  }} else {{
    questIntro.hidden = true;
  }}
  for (const group of quest.groups || []) {{
    const groupEl = document.createElement('div');
    groupEl.className = 'quest-group';
    groupEl.innerHTML = `
      <h3>${{escHtml(group.title || '')}}</h3>
      ${{group.description ? `<p class="quest-group-desc">${{escHtml(group.description)}}</p>` : ''}}
    `;
    for (const q of group.questions || []) {{
      groupEl.appendChild(renderQuestion(q));
    }}
    questGroups.appendChild(groupEl);
  }}
  updateRunBtnEnabled();
}}

function renderQuestion(q) {{
  const wrap = document.createElement('div');
  wrap.className = 'quest-q';
  wrap.dataset.field = q.field;
  const impact = q.impact || 'optional';
  wrap.dataset.impact = impact;
  const fieldId = 'fld-' + q.field.replace(/[^A-Za-z0-9]/g, '_');

  const triggers = (q.triggers || []).map(t => `<span class="trigger-pill">${{escHtml(t)}}</span>`).join('');

  let inputHtml = '';
  const placeholder = q.range_min !== undefined && q.range_max !== undefined
    ? `${{q.range_min}}–${{q.range_max}}` : '';
  switch (q.type) {{
    case 'integer':
    case 'float':
      inputHtml = `<input type="number" id="${{fieldId}}" data-field="${{q.field}}"
        ${{q.range_min !== undefined ? `min="${{q.range_min}}"` : ''}}
        ${{q.range_max !== undefined ? `max="${{q.range_max}}"` : ''}}
        ${{q.type === 'float' ? 'step="0.1"' : 'step="1"'}}
        ${{placeholder ? `placeholder="${{placeholder}}"` : ''}}>`;
      break;
    case 'boolean':
      inputHtml = `<select id="${{fieldId}}" data-field="${{q.field}}" data-type="boolean">
        <option value="">—</option>
        <option value="true">{'Yes' if target_lang == 'en' else 'Так'}</option>
        <option value="false">{'No' if target_lang == 'en' else 'Ні'}</option>
      </select>`;
      break;
    case 'enum':
      const opts = (q.options || []).map(o =>
        `<option value="${{escHtml(JSON.stringify(o.value))}}">${{escHtml(o.label)}}</option>`
      ).join('');
      inputHtml = `<select id="${{fieldId}}" data-field="${{q.field}}" data-type="enum">
        <option value="">{'— select —' if target_lang == 'en' else '— оберіть —'}</option>${{opts}}
      </select>`;
      break;
    case 'text':
    default:
      inputHtml = `<input type="text" id="${{fieldId}}" data-field="${{q.field}}">`;
  }}

  wrap.innerHTML = `
    <div class="quest-q-head">
      <label for="${{fieldId}}" class="quest-q-label">${{escHtml(q.label)}}</label>
      <span class="impact-pill impact-${{impact}}">${{IMPACT_LABEL[impact] || impact}}</span>
    </div>
    ${{inputHtml}}
    ${{q.units ? `<span class="quest-units">${{escHtml(q.units)}}</span>` : ''}}
    ${{q.helper ? `<p class="quest-helper">${{escHtml(q.helper)}}</p>` : ''}}
    ${{triggers ? `<div class="quest-triggers">${{triggers}}</div>` : ''}}
  `;

  // Apply default value
  const inp = wrap.querySelector('input,select');
  if (q.default_value !== undefined && q.default_value !== null) {{
    if (q.type === 'boolean') inp.value = String(q.default_value);
    else if (q.type === 'enum') inp.value = JSON.stringify(q.default_value);
    else inp.value = q.default_value;
    answers[q.field] = q.default_value;
  }}
  inp.addEventListener('input', onAnswerChange);
  inp.addEventListener('change', onAnswerChange);
  return wrap;
}}

function readValue(input, type) {{
  const v = input.value;
  if (v === '') return undefined;
  switch (type) {{
    case 'boolean': return v === 'true';
    case 'enum':
      try {{ return JSON.parse(v); }} catch {{ return v; }}
    case 'integer': return parseInt(v, 10);
    case 'float': return parseFloat(v);
    default: return v;
  }}
}}

function onAnswerChange(ev) {{
  const inp = ev.target;
  const field = inp.dataset.field;
  if (!field) return;
  const type = inp.dataset.type
    || (inp.type === 'number' ? (inp.step === '0.1' ? 'float' : 'integer') : 'text');
  const val = readValue(inp, type);
  if (val === undefined) delete answers[field];
  else answers[field] = val;
  markPlanDirty();
  saveDraft();
  updateRunBtnEnabled();
  updateImpactPanelLocal();
}}

function scheduleEval() {{
  if (evalDebounceTimer) clearTimeout(evalDebounceTimer);
  if (whatIfDebounceTimer) clearTimeout(whatIfDebounceTimer);
  evalDebounceTimer = setTimeout(runLivePreview, PREVIEW_DEBOUNCE_MS);
  whatIfDebounceTimer = setTimeout(triggerWhatIfFromState, WHATIF_DEBOUNCE_MS);
}}

function triggerWhatIfFromState() {{
  whatIfDebounceTimer = null;
  if (!enginReady || !activeQuest || generating || !lastPreviewResult) return;
  runWhatIf(lastPreviewResult).catch(e => console.warn('what-if eval error:', e));
}}

// Cancel any pending preview/what-if when user starts interacting with the
// toolbar (disease/example dropdown, mode buttons, reset). Bumps tokens so
// any in-flight Pyodide call's result is discarded the moment it lands.
// We can't interrupt a synchronous wasm call mid-flight, but this prevents
// new evals from starting while the user is choosing from a dropdown —
// which is when native <select> popup needs the main thread free.
function pauseEvalForToolbar() {{
  if (evalDebounceTimer) {{ clearTimeout(evalDebounceTimer); evalDebounceTimer = null; }}
  if (whatIfDebounceTimer) {{ clearTimeout(whatIfDebounceTimer); whatIfDebounceTimer = null; }}
  ++previewToken;
  ++whatIfToken;
}}

// ── Mode switch ───────────────────────────────────────────────────────────
function setMode(newMode) {{
  mode = newMode;
  modeFormBtn.classList.toggle('active', mode === 'form');
  modeJsonBtn.classList.toggle('active', mode === 'json');
  formPane.hidden = mode !== 'form';
  jsonPane.hidden = mode !== 'json';
  if (mode === 'json' && activeQuest) {{
    // Sync form → JSON
    textarea.value = JSON.stringify(buildProfile(), null, 2);
  }}
  saveDraft();
  updateRunBtnEnabled();
}}

// ── Profile assembly + live preview ───────────────────────────────────────
function buildProfile() {{
  if (mode === 'json') {{
    try {{ return JSON.parse(textarea.value); }} catch {{ return null; }}
  }}
  if (!activeQuest) return null;
  // Deep-merge fixed_fields + expand dotted-path answers
  const profile = JSON.parse(JSON.stringify(activeQuest.fixed_fields || {{}}));
  for (const [path, val] of Object.entries(answers)) {{
    if (val === undefined || val === null) continue;
    const parts = path.split('.');
    let cur = profile;
    for (let i = 0; i < parts.length - 1; i++) {{
      const seg = parts[i];
      if (typeof cur[seg] !== 'object' || cur[seg] === null) cur[seg] = {{}};
      cur = cur[seg];
    }}
    cur[parts[parts.length - 1]] = val;
  }}
  return profile;
}}

async function runLivePreview() {{
  const _ooT0 = performance.now();
  const myToken = ++previewToken;
  const profile = buildProfile();
  if (!profile || !activeQuest) {{
    updateImpactPanel(null);
    return;
  }}
  // Local-only progress before Pyodide ready
  const total = (activeQuest.groups || []).reduce(
    (acc, g) => acc + (g.questions || []).length, 0);
  const filled = Object.keys(answers).length;
  setProgress(filled, total);

  // Call evaluator if engine ready
  if (!enginReady) return;
  try {{
    pyodide.globals.set('_profile_json', JSON.stringify(profile));
    pyodide.globals.set('_quest_id', activeQuest.id);
    const resultJson = await pyodide.runPythonAsync(`
import json
from pathlib import Path
from knowledge_base.engine import evaluate_partial
from knowledge_base.validation.loader import load_content
profile = json.loads(_profile_json)
KB = Path('knowledge_base/hosted/content')
ld = load_content(KB)
quest = next((info['data'] for eid, info in ld.entities_by_id.items()
              if info['type'] == 'questionnaires' and info['data'].get('id') == _quest_id), None)
if quest is None:
    _preview_result = json.dumps({{'error': f'Questionnaire {{_quest_id}} not found'}})
else:
    _preview_eval = evaluate_partial(profile, quest, kb_root=KB)
    _payload = _preview_eval.to_dict()
    # P4: enrich fired_redflags with definition + sources so the live
    # impact panel can show meaningful context, not just IDs.
    _rf_lookup = {{
        info['data'].get('id'): info['data']
        for info in ld.entities_by_id.values()
        if info['type'] == 'redflags' and info['data'].get('id')
    }}
    _payload['fired_redflags_detail'] = [
        {{
            'id': rid,
            'definition_ua': (_rf_lookup.get(rid) or {{}}).get('definition_ua'),
            'definition': (_rf_lookup.get(rid) or {{}}).get('definition'),
            'clinical_direction': (_rf_lookup.get(rid) or {{}}).get('clinical_direction'),
            'severity': (_rf_lookup.get(rid) or {{}}).get('severity', 'major'),
            'sources': (_rf_lookup.get(rid) or {{}}).get('sources') or [],
        }}
        for rid in (_payload.get('fired_redflags') or [])
    ]
    _preview_result = json.dumps(_payload)
_preview_result
`);
    if (myToken !== previewToken) {{
      console.log(`[OO] preview ${{(performance.now() - _ooT0).toFixed(0)}}ms (stale, discarded)`);
      return;
    }}
    const result = JSON.parse(resultJson);
    if (result.error) {{
      setError(result.error);
      return;
    }}
    updateImpactPanel(result);
    lastPreviewResult = result;
    console.log(`[OO] preview ${{(performance.now() - _ooT0).toFixed(0)}}ms`);
    // What-if shadow evaluation runs from its own timer (WHATIF_DEBOUNCE_MS,
    // longer than preview) so rapid typing / dropdown interaction doesn't
    // trigger 10-30 sequential Pyodide evals that block the main thread and
    // make <select> popups laggy.
  }} catch (e) {{
    /* Don't spam errors during typing — just log */
    console.warn('preview eval error:', e);
  }}
}}

// ── What-if shadow evaluation ─────────────────────────────────────────────
let whatIfToken = 0;

async function runWhatIf(currentResult) {{
  if (!enginReady || !activeQuest || !currentResult) return;
  const _ooT0 = performance.now();
  const myToken = ++whatIfToken;

  const specs = [];
  for (const group of activeQuest.groups || []) {{
    for (const q of group.questions || []) {{
      if (q.impact !== 'critical' && q.impact !== 'required') continue;
      if (q.type !== 'boolean' && q.type !== 'enum') continue;
      const currentVal = answers[q.field];
      if (q.type === 'boolean') {{
        if (currentVal === true) specs.push({{field: q.field, alt_value: false, label: '{"No" if target_lang == "en" else "Ні"}'}});
        else if (currentVal === false) specs.push({{field: q.field, alt_value: true, label: '{"Yes" if target_lang == "en" else "Так"}'}});
        else {{
          specs.push({{field: q.field, alt_value: true, label: '{"Yes" if target_lang == "en" else "Так"}'}});
          specs.push({{field: q.field, alt_value: false, label: '{"No" if target_lang == "en" else "Ні"}'}});
        }}
      }} else if (q.type === 'enum') {{
        for (const opt of q.options || []) {{
          if (JSON.stringify(opt.value) === JSON.stringify(currentVal)) continue;
          specs.push({{field: q.field, alt_value: opt.value, label: opt.label}});
        }}
      }}
    }}
  }}

  if (specs.length === 0) {{ clearWhatIfMarks(); return; }}

  const profile = buildProfile();
  if (!profile) return;

  pyodide.globals.set('_wf_profile', JSON.stringify(profile));
  pyodide.globals.set('_wf_quest_id', activeQuest.id);
  pyodide.globals.set('_wf_specs', JSON.stringify(specs));
  pyodide.globals.set('_wf_main_ind', currentResult.would_select_indication || '');
  pyodide.globals.set('_wf_main_rfs', JSON.stringify(currentResult.fired_redflags || []));

  let raw;
  try {{
    raw = await pyodide.runPythonAsync(`
import json, copy
from pathlib import Path
from knowledge_base.engine import evaluate_partial
from knowledge_base.validation.loader import load_content
profile = json.loads(_wf_profile)
specs = json.loads(_wf_specs)
main_ind = _wf_main_ind
main_rfs = set(json.loads(_wf_main_rfs))
KB = Path('knowledge_base/hosted/content')
ld = load_content(KB)
quest = next((info['data'] for eid, info in ld.entities_by_id.items()
              if info['type'] == 'questionnaires' and info['data'].get('id') == _wf_quest_id), None)

def _set_path(d, dotted, val):
    parts = dotted.split('.')
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {{}}
        cur = cur[p]
    cur[parts[-1]] = val

results = []
if quest is not None:
    for spec in specs:
        sp = copy.deepcopy(profile)
        _set_path(sp, spec['field'], spec['alt_value'])
        try:
            sr = evaluate_partial(sp, quest, kb_root=KB, loaded_kb=ld).to_dict()
        except Exception:
            continue
        diff = {{}}
        si = sr.get('would_select_indication') or ''
        if si != main_ind:
            diff['indication_now'] = si
        srfs = set(sr.get('fired_redflags') or [])
        added = sorted(srfs - main_rfs)
        removed = sorted(main_rfs - srfs)
        if added: diff['rf_added'] = added
        if removed: diff['rf_removed'] = removed
        if diff:
            results.append({{
                'field': spec['field'],
                'alt_value': spec['alt_value'],
                'label': spec.get('label', ''),
                'diff': diff,
            }})
_wf_result_json = json.dumps(results)
_wf_result_json
`);
  }} catch (e) {{
    console.warn('what-if eval error:', e);
    return;
  }}

  if (myToken !== whatIfToken) {{
    console.log(`[OO] whatif ${{(performance.now() - _ooT0).toFixed(0)}}ms (stale, discarded)`);
    return;
  }}
  let results;
  try {{ results = JSON.parse(raw); }} catch {{ return; }}
  renderWhatIfMarks(results);
  console.log(`[OO] whatif ${{(performance.now() - _ooT0).toFixed(0)}}ms (${{specs.length}} specs, ${{results.length}} differing)`);
}}

function clearWhatIfMarks() {{
  formPane.querySelectorAll('.quest-whatif').forEach(n => n.remove());
}}

function renderWhatIfMarks(results) {{
  clearWhatIfMarks();
  const byField = {{}};
  for (const r of results) {{
    (byField[r.field] = byField[r.field] || []).push(r);
  }}
  for (const field of Object.keys(byField)) {{
    const wrap = formPane.querySelector(`.quest-q[data-field="${{CSS.escape(field)}}"]`);
    if (!wrap) continue;
    const box = document.createElement('div');
    box.className = 'quest-whatif';
    let html = '<div class="whatif-head">{"If this field were different:" if target_lang == "en" else "Якщо це поле буде іншим:"}</div><ul>';
    for (const it of byField[field]) {{
      const parts = [];
      if (it.diff.indication_now) {{
        parts.push(`Indication → <code>${{escHtml(it.diff.indication_now)}}</code>`);
      }}
      if (it.diff.rf_added && it.diff.rf_added.length) {{
        parts.push('<span class="wf-add">+RF</span> ' + it.diff.rf_added.map(r => `<code>${{escHtml(r)}}</code>`).join(' '));
      }}
      if (it.diff.rf_removed && it.diff.rf_removed.length) {{
        parts.push('<span class="wf-rm">−RF</span> ' + it.diff.rf_removed.map(r => `<code>${{escHtml(r)}}</code>`).join(' '));
      }}
      const altLabel = it.label || JSON.stringify(it.alt_value);
      html += `<li><span class="whatif-alt">${{escHtml(altLabel)}}:</span> ${{parts.join(' · ')}}</li>`;
    }}
    html += '</ul>';
    box.innerHTML = html;
    wrap.appendChild(box);
  }}
}}

// Local-only readiness update — runs WITHOUT Pyodide so form interaction
// stays snappy. It only keeps the essential pre-generation signal visible:
// completion progress and missing critical fields.
function updateImpactPanelLocal() {{
  if (!activeQuest) {{
    setProgress(0, 0);
    setReadinessCritical([]);
    return;
  }}
  let total = 0, filled = 0;
  const missing = [];
  for (const group of activeQuest.groups || []) {{
    for (const q of group.questions || []) {{
      total++;
      const val = answers[q.field];
      const isFilled = val !== undefined && val !== null && val !== '';
      if (isFilled) filled++;
      else if (q.impact === 'critical') {{
        missing.push({{ label: q.label, group: group.title || '' }});
      }}
    }}
  }}
  setProgress(filled, total);
  setReadinessCritical(missing);
}}

function setProgress(filled, total) {{
  progressText.textContent = `${{filled}} / ${{total}}`;
  const pct = total ? Math.round(filled * 100 / total) : 0;
  progressPct.textContent = `${{pct}}%`;
  progressFill.style.width = `${{pct}}%`;
}}

function setReadinessCritical(missing) {{
  if (!readinessCriticalText) return;
  if (!activeQuest) {{
    readinessCriticalText.textContent = '{"Pick a disease to start." if target_lang == "en" else "Оберіть хворобу, щоб почати."}';
    readinessCriticalText.dataset.kind = 'idle';
    return;
  }}
  if (!missing || !missing.length) {{
    readinessCriticalText.textContent = '{"Critical fields filled ✓" if target_lang == "en" else "Критичні поля заповнені ✓"}';
    readinessCriticalText.dataset.kind = 'ok';
    return;
  }}
  const preview = missing.slice(0, 2).map(m => m.label).join(', ');
  const extra = missing.length > 2 ? ' +' + (missing.length - 2) : '';
  readinessCriticalText.textContent = '{"Missing critical fields:" if target_lang == "en" else "Бракує критичних полів:"} ' + preview + extra;
  readinessCriticalText.dataset.kind = 'warn';
}}

function updateImpactPanel(result) {{
  if (!result) {{
    updateImpactPanelLocal();
    return;
  }}
  setProgress(result.filled_count, result.total_questions);
  setReadinessCritical(result.missing_critical || []);
}}

// ── Bundle lazy-load (CSD-6E + CSD-9C) ────────────────────────────────────
// Two-tier bundle: fetch openonco-engine-core.zip first (~1.4 MB), then
// fetch the matching per-disease module (~15-40 KB) once we know the
// patient's disease_id. CSD-9C (2026-04-27) drops the legacy monolithic
// fallback — the lazy-load path is the canonical path now. The index
// fetch retries once on transient failure before giving up; if that
// fails too we surface a clear error rather than silently downloading
// 3+ MB of fallback that no longer ships.

async function loadBundleIndex() {{
  if (bundleIndex !== null) return bundleIndex;
  // One retry to absorb a transient CDN hiccup before failing the load.
  let lastErr = null;
  for (let attempt = 0; attempt < 2; attempt++) {{
    try {{
      const r = await fetch(BUNDLE_INDEX_URL + '?t=' + Date.now());
      if (!r.ok) throw new Error('Index fetch HTTP ' + r.status);
      bundleIndex = await r.json();
      refreshBuildPanel().catch(() => {{}});
      return bundleIndex;
    }} catch (e) {{
      lastErr = e;
      if (attempt === 0) {{
        console.warn('[OpenOnco] bundle index fetch failed — retrying once:', e);
        await yieldToBrowser(250);
      }}
    }}
  }}
  console.error('[OpenOnco] bundle index unavailable after retry:', lastErr);
  throw new Error('Bundle index unavailable: ' + (lastErr && lastErr.message || lastErr));
}}

function offlineBundleUrls() {{
  if (!bundleIndex) return [];
  const urls = [];
  if (bundleIndex.core) {{
    const ver = bundleIndex.core_version || '';
    urls.push('/' + bundleIndex.core + (ver ? '?v=' + ver : ''));
  }}
  const diseases = bundleIndex.diseases || {{}};
  const versions = bundleIndex.disease_versions || {{}};
  Object.keys(diseases).sort().forEach((diseaseId) => {{
    const rel = diseases[diseaseId];
    if (!rel) return;
    const ver = versions[diseaseId] || '';
    urls.push('/' + rel + (ver ? '?v=' + ver : ''));
  }});
  return urls;
}}

async function cacheAllBundlesForOffline() {{
  if (offlineCacheStarted) return;
  offlineCacheStarted = true;
  await loadBundleIndex();
  const urls = offlineBundleUrls();
  setOfflineCacheProgress(0, urls.length, 0);
  if (!urls.length) return;
  if (!('caches' in window)) {{
    setText(offlineModulesStateEl, '{"Cache unavailable" if target_lang == "en" else "Кеш недоступний"}');
    return;
  }}
  if (navigator.onLine === false) {{
    setText(offlineModulesStateEl, '{"Offline now" if target_lang == "en" else "Зараз офлайн"}');
    return;
  }}

  const cacheName = 'openonco-bundle-l3-' + (bundleIndex.core_version || 'v1');
  const cache = await caches.open(cacheName);
  let done = 0;
  let failed = 0;
  for (const url of urls) {{
    try {{
      const cached = await cache.match(url, {{ ignoreSearch: true }});
      if (!cached) {{
        const resp = await fetch(url);
        if (!resp || !resp.ok) throw new Error('HTTP ' + (resp && resp.status));
        await cache.put(url, resp.clone());
      }}
    }} catch (e) {{
      failed += 1;
      console.warn('[OpenOnco] offline cache failed for ' + url + ':', e);
    }} finally {{
      done += 1;
      setOfflineCacheProgress(done, urls.length, failed);
      await yieldToBrowser(10);
    }}
  }}
}}

function scheduleOfflineCacheWarmup() {{
  const run = () => cacheAllBundlesForOffline().catch((e) => {{
    console.warn('[OpenOnco] offline cache warmup failed:', e);
    setText(offlineModulesStateEl, '{"Cache failed" if target_lang == "en" else "Кеш не вдався"}');
  }});
  if ('requestIdleCallback' in window) {{
    window.requestIdleCallback(run, {{ timeout: 3000 }});
  }} else {{
    window.setTimeout(run, 1500);
  }}
}}

// Resolve a disease_id from whatever the patient profile / form gives us.
// Order: explicit disease.id (or top-level disease_id) → active
// questionnaire's disease_id → ICD-O-3 morphology → null.
function resolveDiseaseId(profile) {{
  if (!profile) return null;
  const d = profile.disease || {{}};
  if (typeof d.id === 'string' && d.id.startsWith('DIS-')) return d.id.toUpperCase();
  if (typeof profile.disease_id === 'string' && profile.disease_id.startsWith('DIS-')) {{
    return profile.disease_id.toUpperCase();
  }}
  if (activeQuest && typeof activeQuest.disease_id === 'string'
      && activeQuest.disease_id.startsWith('DIS-')) {{
    return activeQuest.disease_id.toUpperCase();
  }}
  const code = d.icd_o_3_morphology;
  if (code && bundleIndex && bundleIndex.icd_to_disease_id) {{
    const did = bundleIndex.icd_to_disease_id[String(code)];
    if (did) return did;
  }}
  return null;
}}

async function loadCoreBundle() {{
  if (coreBundleLoaded) return;
  // CSD-9C: index is required — monolithic fallback retired.
  await loadBundleIndex();
  if (!bundleIndex || !bundleIndex.core) {{
    throw new Error('Bundle index missing core entry — cannot load engine');
  }}
  setStatus('{"Loading the engine core (~1.4 MB)…" if target_lang == "en" else "Завантажую ядро двигуна (~1.4 МБ)…"}');
  setLoadingProgress(62);
  const ver = bundleIndex.core_version || '';
  const url = '/' + bundleIndex.core + (ver ? '?v=' + ver : '');
  const r = await fetch(url);
  if (!r.ok) throw new Error('Core bundle fetch HTTP ' + r.status);
  const buf = await r.arrayBuffer();
  await yieldToBrowser();
  pyodide.unpackArchive(buf, 'zip');
  coreBundleLoaded = true;
}}

// Per-disease module: tiny zip with the disease's indications, regimens,
// algorithms, redflags, and biomarker_actionability cells. Cached in
// localStorage keyed by disease_id + version so subsequent visits skip
// the fetch entirely. Quota is ~5-10 MB; we only cache one disease at a
// time per slot and drop silently on quota errors.
async function loadDiseaseModule(diseaseId) {{
  if (!diseaseId) return;
  if (loadedDiseases.has(diseaseId)) {{
    refreshBuildPanel(diseaseId).catch(() => {{}});
    return;
  }}
  if (!bundleIndex || !bundleIndex.diseases) return;
  const relUrl = bundleIndex.diseases[diseaseId];
  if (!relUrl) {{
    // Disease has no per-disease bundle — its content is fully in core.
    loadedDiseases.add(diseaseId);
    refreshBuildPanel(diseaseId).catch(() => {{}});
    return;
  }}
  const ver = (bundleIndex.disease_versions || {{}})[diseaseId] || '';
  const cacheKey = 'openonco-disease-' + diseaseId + '-' + ver;

  // localStorage cache hit: decode base64 → ArrayBuffer → unpack.
  try {{
    const cached = localStorage.getItem(cacheKey);
    if (cached) {{
      const bin = atob(cached);
      const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      pyodide.unpackArchive(u8.buffer, 'zip');
      loadedDiseases.add(diseaseId);
      refreshBuildPanel(diseaseId).catch(() => {{}});
      console.log('[OO] disease module ' + diseaseId + ' loaded from localStorage cache');
      return;
    }}
  }} catch (e) {{
    console.warn('[OpenOnco] disease cache read failed for ' + diseaseId + ':', e);
    try {{ localStorage.removeItem(cacheKey); }} catch (_) {{}}
  }}

  setStatus('{"Loading module " if target_lang == "en" else "Завантажую модуль "}' + diseaseId + '…');
  setLoadingProgress(86);
  const url = '/' + relUrl + (ver ? '?v=' + ver : '');
  const r = await fetch(url);
  if (!r.ok) throw new Error('Disease module fetch HTTP ' + r.status + ' for ' + diseaseId);
  const buf = await r.arrayBuffer();
  await yieldToBrowser();
  pyodide.unpackArchive(buf, 'zip');
  loadedDiseases.add(diseaseId);
  refreshBuildPanel(diseaseId).catch(() => {{}});

  // Re-validate after merge so the next generate_plan() sees the new YAMLs.
  // apply_disease_module() drops the loader cache; cheap enough to run on
  // every disease swap.
  try {{
    await pyodide.runPythonAsync(
      "from knowledge_base.engine import apply_disease_module\\n" +
      "from pathlib import Path\\n" +
      "apply_disease_module(Path('knowledge_base/hosted/content'))\\n"
    );
  }} catch (e) {{
    console.warn('[OpenOnco] apply_disease_module failed (continuing):', e);
  }}

  // Cache for next visit. Skip silently on quota or encoding errors.
  try {{
    let bin = '';
    const u8 = new Uint8Array(buf);
    const chunk = 0x8000;
    for (let i = 0; i < u8.length; i += chunk) {{
      bin += String.fromCharCode.apply(null, u8.subarray(i, i + chunk));
    }}
    localStorage.setItem(cacheKey, btoa(bin));
  }} catch (e) {{
    // Quota exceeded or encoding hiccup — just don't cache.
  }}
}}

// ── Pyodide loader ────────────────────────────────────────────────────────
// Lazy: runs only when user clicks Generate. Drives the init overlay's
// 4 setup stages (pyodide / pydeps / bundle / validate) with explicit
// yields between each so the browser can repaint and process input
// (F12, scroll, keyboard) instead of locking up for 10–20 s straight.
async function ensureEngine() {{
  if (enginReady) return pyodide;
  let stage = null;
  try {{
    stage = 'pyodide';
    initStageStart(stage);
    setStatus('{"Loading Pyodide…" if target_lang == "en" else "Завантажую Pyodide…"}');
    setLoadingProgress(18);
    await yieldToBrowser(50);
    const _loadPyodide = await ensurePyodideLoader();
    pyodide = await _loadPyodide({{indexURL: "https://cdn.jsdelivr.net/pyodide/v{_PYODIDE_VERSION}/full/"}});
    initStageDone(stage);

    stage = 'pydeps';
    initStageStart(stage);
    setStatus('{"Installing pydantic + pyyaml…" if target_lang == "en" else "Встановлюю pydantic + pyyaml…"}');
    setLoadingProgress(36);
    await yieldToBrowser(50);
    await pyodide.loadPackage(['micropip']);
    await yieldToBrowser();
    await pyodide.runPythonAsync(`
import micropip
await micropip.install(['pydantic', 'pyyaml'])
`);
    initStageDone(stage);

    stage = 'bundle';
    initStageStart(stage);
    setStatus('{"Loading the OpenOnco engine…" if target_lang == "en" else "Завантажую двигун OpenOnco…"}');
    setLoadingProgress(54);
    await yieldToBrowser(50);
    // CSD-6E + CSD-9C: lazy-load core bundle (~1.4 MB). Monolithic
    // fallback retired (CSD-9C 2026-04-27) — the index + core + per-
    // disease modules are the only path. Per-disease modules are
    // fetched later in runEngine() once disease_id is known.
    await loadCoreBundle();
    initStageDone(stage);

    stage = 'validate';
    initStageStart(stage);
    setStatus('{"Verifying the KB…" if target_lang == "en" else "Перевіряю базу…"}');
    setLoadingProgress(78);
    await yieldToBrowser(50);
    const validationSummary = await pyodide.runPythonAsync(`
from pathlib import Path
from knowledge_base.validation.loader import load_content
_r = load_content(Path('knowledge_base/hosted/content'))
if _r.ok:
    _summary = "ok"
else:
    _parts = []
    if _r.schema_errors:
        _parts.append(f"schema({{len(_r.schema_errors)}}): " + "; ".join(f"{{p.name}}: {{m}}" for p, m in _r.schema_errors[:3]))
    if _r.ref_errors:
        _parts.append(f"ref({{len(_r.ref_errors)}}): " + "; ".join(f"{{p.name}}: {{m}}" for p, m in _r.ref_errors[:3]))
    if _r.contract_errors:
        _parts.append(f"contract({{len(_r.contract_errors)}}): " + "; ".join(f"{{p.name}}: {{m}}" for p, m in _r.contract_errors[:3]))
    _summary = " | ".join(_parts)
_summary
`);
    initStageDone(stage);
    enginReady = true;
    setLoadingProgress(100);
    if (validationSummary === 'ok') {{
      setStatus('{"Engine ready ✓" if target_lang == "en" else "Двигун готовий ✓"}', 'ok');
    }} else {{
      console.warn('[OpenOnco] KB validation did not pass — engine loaded anyway for testing.\\n' + validationSummary);
      setStatus('{"Engine ready ⚠ KB not verified (details in console)" if target_lang == "en" else "Двигун готовий ⚠ KB неверифіковано (деталі в консолі)"}', 'warn');
    }}
    return pyodide;
  }} catch (e) {{
    if (stage) initStageError(stage, e && e.message);
    throw e;
  }}
}}

// ── Generate full plan ────────────────────────────────────────────────────
async function runEngine() {{
  if (uiBusy || generating || runBtn.disabled) return;  // double-click / re-entry guard
  const _ooT0 = performance.now();
  setError(null);
  const profile = buildProfile();
  if (!profile) {{
    setError('{"Could not assemble a profile (form / JSON empty)." if target_lang == "en" else "Не вдалося зібрати профіль (форма / JSON порожні)."}');
    return;
  }}

  // Lock the form so input during generation can't desync the rendered
  // plan from a moving profile. <main inert> hard-blocks pointer + keyboard
  // focus; init overlay (sibling of <main>) explains what's happening.
  generating = true;
  updateWorkflowControls();
  if (mainTryEl) mainTryEl.inert = true;
  if (evalDebounceTimer) {{ clearTimeout(evalDebounceTimer); evalDebounceTimer = null; }}
  if (whatIfDebounceTimer) {{ clearTimeout(whatIfDebounceTimer); whatIfDebounceTimer = null; }}
  ++previewToken;
  ++whatIfToken;
  initStagesReset();
  // If engine is already loaded from a prior click, fast-forward setup
  // stages so the doctor sees only "Будую план" active. First run lights
  // up all 5 stages.
  if (enginReady) {{
    initStageDone('pyodide');
    initStageDone('pydeps');
    initStageDone('bundle');
    initStageDone('validate');
  }}
  initShow();
  // On subsequent runs the init stages fast-forward instantly — show the
  // dedicated generating overlay so the user sees a clear blocker while
  // Python/Pyodide runs. First-run: the staged initOverlay already covers it.
  if (enginReady) setGeneratingUI(true, '{"Generating plan…" if target_lang == "en" else "Генерую план…"}');

  try {{
    try {{
      await ensureEngine();
    }} catch (e) {{
      setError('{"The engine failed to load: " if target_lang == "en" else "Двигун не завантажився: "}' + (e.message || e));
      setStatus('');
      return;
    }}
    // CSD-6E: lazy-fetch the per-disease module before generate. No-op
    // when the disease has no per-disease bundle (its content is in
    // core). Failures are surfaced but non-fatal — generate_plan()
    // will fall back to whatever's already loaded.
    try {{
      const did = resolveDiseaseId(profile);
      if (did) await loadDiseaseModule(did);
    }} catch (e) {{
      console.warn('[OpenOnco] disease module load failed (continuing):', e);
    }}
    initStageStart('generate');
    setStatus('{"Building a personalised plan…" if target_lang == "en" else "Будую персональний план…"}');
    setLoadingProgress(92);
    await yieldToBrowser(30);
    const _ooTPython = performance.now();
    try {{
      pyodide.globals.set('_patient_json', JSON.stringify(profile));
      pyodide.globals.set('_target_lang', currentResultLang);
      const html = await pyodide.runPythonAsync(`
import json
from pathlib import Path
from knowledge_base.engine import (
    generate_plan, generate_diagnostic_brief, is_diagnostic_profile,
    orchestrate_mdt, render_plan_html, render_diagnostic_brief_html,
)
patient = json.loads(_patient_json)
KB = Path('knowledge_base/hosted/content')
if is_diagnostic_profile(patient):
    _oo_result = generate_diagnostic_brief(patient, kb_root=KB)
    _oo_mdt = orchestrate_mdt(patient, _oo_result, kb_root=KB)
    _oo_mode = 'diagnostic'
    html = render_diagnostic_brief_html(_oo_result, mdt=_oo_mdt, target_lang=_target_lang)
else:
    # Pyodide can't reach api.clinicaltrials.gov directly — pass the
    # baked cache_root only (no search_fn). Cache hits surface trials;
    # misses fall through to the "search not configured" empty bundle.
    _oo_result = generate_plan(
        patient, kb_root=KB, experimental_cache_root=KB / 'cache' / 'ctgov',
    )
    _oo_mdt = orchestrate_mdt(patient, _oo_result, kb_root=KB)
    _oo_mode = 'treatment'
    html = render_plan_html(_oo_result, mdt=_oo_mdt, target_lang=_target_lang)
html
`);
      initStageDone('generate');
      resultFrame.removeAttribute('src');
      resultFrame.srcdoc = html;
      planSource = 'generated';
      planDirty = false;
      activeExampleCaseId = null;
      // Fresh generation always lands on clinician view; user toggles to
      // patient view via the toolbar (PATIENT_MODE_SPEC §3.5).
      currentResultMode = 'clinician';
      highlightModeButtons();
      refreshModeButtonAvailability();
      updateWorkflowControls();
      openPlanModal({{ force: true }});
      setStatus('{"Plan ready ✓" if target_lang == "en" else "Plan готовий ✓"}', 'ok');
      const _ooTNow = performance.now();
      console.log(`[OO] generate ${{(_ooTNow - _ooT0).toFixed(0)}}ms total (engine-load ${{(_ooTPython - _ooT0).toFixed(0)}}ms + python ${{(_ooTNow - _ooTPython).toFixed(0)}}ms)`);
    }} catch (e) {{
      initStageError('generate', e && e.message);
      setError('{"The engine returned an error:" if target_lang == "en" else "Двигун повернув помилку:"}\\n' + (e.message || e));
      setStatus('');
    }}
  }} finally {{
    generating = false;
    if (mainTryEl) mainTryEl.inert = false;
    setGeneratingUI(false);
    // Brief delay so the doctor sees green checkmarks before the overlay
    // fades — purely cosmetic confirmation that all stages succeeded.
    setTimeout(initHide, 600);
    updateRunBtnEnabled();
  }}
}}

function setGeneratingUI(on, hint, title, lead) {{
  generatingOverlay.hidden = !on;
  // <main inert> hard-blocks pointer + keyboard focus on every interactive
  // element inside (form fields, toolbar, runBtn). The overlay is a sibling
  // of <main>, so it stays interactive — but we don't currently put any
  // controls in it (no cancel — Pyodide runPythonAsync is not interruptable).
  if (mainTryEl) mainTryEl.inert = on;
  if (on && generatingTitle) generatingTitle.textContent = title || UI_LOCK_TEXT.generateTitle;
  if (on && generatingLead) generatingLead.textContent = lead || UI_LOCK_TEXT.generateLead;
  if (on && hint) setGeneratingHint(hint);
}}

function setGeneratingHint(text) {{
  if (generatingHint) generatingHint.textContent = text;
}}

async function withUiLock(title, lead, hint, task) {{
  if (uiBusy || generating) return;
  uiBusy = true;
  updateRunBtnEnabled();
  setGeneratingUI(true, hint, title, lead);
  await yieldToBrowser(16);
  try {{
    return await task();
  }} finally {{
    uiBusy = false;
    setGeneratingUI(false);
    updateRunBtnEnabled();
  }}
}}

// ── Init overlay (one-time engine load with named stages) ─────────────────
// Shown on first Generate click; doctor sees what's happening instead of a
// mystery lag. Yields to the browser between stages so F12, scrolling, and
// keyboard input remain responsive even though wasm chunks block the main
// thread internally.
function initShow() {{ if (initOverlay) initOverlay.hidden = false; }}
function initHide() {{ if (initOverlay) initOverlay.hidden = true; }}

function initStageStart(id) {{
  if (!initStagesEl) return;
  const li = initStagesEl.querySelector(`[data-stage="${{id}}"]`);
  if (!li) return;
  li.classList.remove('pending', 'done', 'error');
  li.classList.add('active');
}}
function initStageDone(id) {{
  if (!initStagesEl) return;
  const li = initStagesEl.querySelector(`[data-stage="${{id}}"]`);
  if (!li) return;
  li.classList.remove('pending', 'active', 'error');
  li.classList.add('done');
}}
function initStageError(id, msg) {{
  if (!initStagesEl) return;
  const li = initStagesEl.querySelector(`[data-stage="${{id}}"]`);
  if (!li) return;
  li.classList.remove('pending', 'active', 'done');
  li.classList.add('error');
  if (msg) li.title = String(msg);
}}
function initStagesReset() {{
  if (!initStagesEl) return;
  initStagesEl.querySelectorAll('.stage').forEach(li => {{
    li.classList.remove('active', 'done', 'error');
    li.classList.add('pending');
  }});
}}

// Yield to the browser so it can repaint + process input between heavy
// synchronous wasm chunks (Pyodide loadPackage / unpackArchive / Python
// eval). 16ms ≈ one frame; 50ms gives visibly snappier dropdowns.
function yieldToBrowser(ms) {{
  return new Promise(resolve => setTimeout(resolve, ms == null ? 16 : ms));
}}

// ── Boot ──────────────────────────────────────────────────────────────────
//
// Lazy-loaders for full questionnaire/example data. Dropdowns populate
// instantly from the build-time manifests above; the full ~870 KB payload
// is fetched only after the user picks something.
function fetchJsonWithTimeout(url, label, timeoutMs = 10000) {{
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, {{ signal: controller.signal }})
    .then(r => {{
      if (!r.ok) throw new Error(label + ' HTTP ' + r.status);
      return r.json();
    }})
    .catch(e => {{
      if (e && e.name === 'AbortError') throw new Error(label + ' timed out');
      throw e;
    }})
    .finally(() => window.clearTimeout(timer));
}}

async function ensureQuestionnaires() {{
  if (questionnaires) return questionnaires;
  if (!_questionnairesPromise) {{
    _questionnairesPromise = fetchJsonWithTimeout('/questionnaires.json', 'questionnaires.json')
      .then(data => {{ questionnaires = data; return data; }})
      .catch(e => {{ _questionnairesPromise = null; throw e; }});
  }}
  return _questionnairesPromise;
}}
async function ensureExamples() {{
  if (examples) return examples;
  if (!_examplesPromise) {{
    _examplesPromise = fetchJsonWithTimeout('/examples.json', 'examples.json')
      .then(data => {{ examples = data; return data; }})
      .catch(e => {{ _examplesPromise = null; throw e; }});
  }}
  return _examplesPromise;
}}

// Persist dropdown manifests across visits. Read by the early-paint
// warmup at the top of the script body, written by loadAssets after a
// successful boot so the next cold visit can paint dropdowns from
// localStorage even before the new HTML's inline manifest is parsed.
const MANIFEST_CACHE_KEY = 'openonco-manifests-v3';
function saveManifestsToCache() {{
  try {{
    localStorage.removeItem('openonco-manifests-v1');
    localStorage.removeItem('openonco-manifests-v2');
    localStorage.setItem(MANIFEST_CACHE_KEY, JSON.stringify({{
      ts: Date.now(),
      questionnaires: QUESTIONNAIRES_MANIFEST,
      examples: EXAMPLES_MANIFEST,
    }}));
  }} catch (e) {{ /* quota or private mode — silent skip */ }}
}}

// Build a lower-cased haystack so the search box matches the full title
// (EN/UA), the disease_id with and without the "DIS-" prefix (so users
// can type "HCC" or "DLBCL"), and both ICD codes.
function diseaseSearchHaystack(q) {{
  if (!q) return '';
  const did = String(q.disease_id || '');
  return [
    q.title_en || q.title || '',
    q.title_uk || '',
    did,
    did.replace(/^DIS-/, ''),
    q.icd_10 || '',
    q.disease_icd || '',
  ].join(' ').toLowerCase();
}}

function renderDiseaseOptions() {{
  const term = (diseaseSearch && diseaseSearch.value || '').trim().toLowerCase();
  const previousVal = diseaseSelect.value;
  diseaseSelect.innerHTML = '';
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = term
    ? ('{"— matches for" if target_lang == "en" else "— збіги для"} "' + term + '" —')
    : '{"— select —" if target_lang == "en" else "— оберіть —"}';
  diseaseSelect.appendChild(placeholder);
  let kept = 0;
  QUESTIONNAIRES_MANIFEST.forEach((q, i) => {{
    if (term && !diseaseSearchHaystack(q).includes(term)) return;
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = questionnaireDisplayTitle(q);
    diseaseSelect.appendChild(opt);
    kept++;
  }});
  if (term && kept === 0) {{
    const none = document.createElement('option');
    none.value = '';
    none.disabled = true;
    none.textContent = '{"(no matching diseases)" if target_lang == "en" else "(жодних збігів)"}';
    diseaseSelect.appendChild(none);
  }}
  // Preserve selection if the previously-chosen disease still matches.
  if (previousVal && [...diseaseSelect.options].some(o => o.value === previousVal)) {{
    diseaseSelect.value = previousVal;
  }}
}}

async function loadAssets() {{
  setLoadingProgress(18);
  // Populate dropdowns from manifests — instant, no network fetch.
  renderDiseaseOptions();
  saveManifestsToCache();
  setLoadingProgress(55);

  // Examples selector — initial population shows all; narrows once a
  // disease is picked.
  repopulateExamples(null);
  setLoadingProgress(72);

  // Restore draft. If the full questionnaire payload is unavailable, keep
  // the page usable from the inlined manifest instead of leaving the boot
  // banner stuck on "Loading questionnaires…".
  const draft = loadDraft();
  let draftRestored = false;
  let draftRestoreFailed = false;
  if (draft && draft.questId) {{
    const idx = QUESTIONNAIRES_MANIFEST.findIndex(q => q.id === draft.questId);
    if (idx >= 0) {{
        try {{
          await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.diseaseHint, async () => {{
            diseaseSelect.value = idx;
            setLoadingProgress(82);
            // Draft restore needs full data — lazy-fetch now
            const fullList = await ensureQuestionnaires();
            renderForm(fullList[idx]);
          repopulateExamples(idx);
          // Apply saved answers
          if (draft.answers) {{
            for (const [field, val] of Object.entries(draft.answers)) {{
              const inp = formPane.querySelector(`[data-field="${{CSS.escape(field)}}"]`);
              if (!inp) continue;
              if (typeof val === 'boolean') inp.value = String(val);
              else if (inp.dataset.type === 'enum') inp.value = JSON.stringify(val);
              else inp.value = val;
              answers[field] = val;
            }}
          }}
          if (draft.jsonText) textarea.value = draft.jsonText;
          if (draft.mode === 'json') setMode('json');
          setStatus('{"Draft restored ✓ Click «Generate» when you are ready." if target_lang == "en" else "Чернетку відновлено ✓ Натисни «Згенерувати» коли готовий."}', 'ok');
          updateRunBtnEnabled();
          updateImpactPanelLocal();
          draftRestored = true;
        }});
      }} catch (e) {{
        draftRestoreFailed = true;
        console.warn('[OpenOnco] failed to restore saved draft:', e);
        setError('{"Could not restore the saved draft: " if target_lang == "en" else "Не вдалося відновити чернетку: "}' + (e.message || e));
        diseaseSelect.value = '';
        renderForm(null);
        repopulateExamples(null);
      }}
    }}
  }}
  if (!draftRestored) {{
    // Initial load done — hide the top busy banner; sidebar still shows hint.
    if (draftRestoreFailed) {{
      setStatus('{"Saved draft could not be restored. Pick a disease to start again." if target_lang == "en" else "Чернетку не вдалося відновити. Оберіть хворобу, щоб почати знову."}', 'warn', 'warn');
    }} else {{
      setStatus('{"Pick a disease from the list to start." if target_lang == "en" else "Оберіть хворобу зі списку, щоб почати."}', 'info', 'hide');
    }}
    updateRunBtnEnabled();
    updateImpactPanelLocal();
  }}
  // Engine is fully lazy now — Pyodide loads only when the user clicks
  // «Згенерувати». Form interaction stays Pyodide-free and snappy.
}}

// ── Examples filtering by selected disease ────────────────────────────────
// We narrow the example dropdown to the active questionnaire disease.
// Match by disease_id first: ICD-O morphology is not unique enough
// (e.g. 8070/3 spans cervical, esophageal, and HNSCC examples).
function exampleDisplayLabel(ex) {{
  const base = {'(ex.label_en || ex.label)' if target_lang == 'en' else 'ex.label'};
  const quality = {'(ex.quality_label_en || ex.quality_label)' if target_lang == 'en' else 'ex.quality_label'};
  return quality ? `${{base}} · ${{quality}}` : base;
}}

function repopulateExamples(activeQuestIdx) {{
  // Filter from manifest only — no need to await full examples payload
  // just to populate a dropdown (manifest carries label + disease_id).
  const activeQuestManifest = activeQuestIdx == null
    ? null
    : (QUESTIONNAIRES_MANIFEST[activeQuestIdx] || {{}});
  const wantDiseaseId = activeQuestManifest && activeQuestManifest.disease_id;
  const wantCode = activeQuestManifest && activeQuestManifest.disease_icd;
  exampleSelect.innerHTML = '';
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = wantDiseaseId == null && wantCode == null
    ? '{"— select an example —" if target_lang == "en" else "— оберіть приклад —"}'
    : '{"— select an example for this disease —" if target_lang == "en" else "— оберіть приклад для цієї хвороби —"}';
  exampleSelect.appendChild(placeholder);
  let n = 0;
  EXAMPLES_MANIFEST
    .map((ex, i) => ({{ ex, i }}))
    .filter((item) => {{
      const ex = item.ex;
    if (wantDiseaseId != null) {{
        return ex.disease_id === wantDiseaseId;
    }} else if (wantCode != null) {{
        return ex.disease_icd === wantCode;
    }}
      return true;
    }})
    .sort((a, b) => {{
      const ar = Number.isFinite(a.ex.quality_rank) ? a.ex.quality_rank : 99;
      const br = Number.isFinite(b.ex.quality_rank) ? b.ex.quality_rank : 99;
      if (ar !== br) return ar - br;
      return exampleDisplayLabel(a.ex).localeCompare(exampleDisplayLabel(b.ex));
    }})
    .forEach((item) => {{
    const ex = item.ex;
    const opt = document.createElement('option');
    opt.value = item.i;
    opt.textContent = exampleDisplayLabel(ex);
    exampleSelect.appendChild(opt);
    n++;
  }});
  if ((wantDiseaseId != null || wantCode != null) && n === 0) {{
    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.disabled = true;
    noneOpt.textContent = '{"(no examples for this disease yet)" if target_lang == "en" else "(прикладів для цієї хвороби поки немає)"}';
    exampleSelect.appendChild(noneOpt);
  }}
}}

// ── Event wiring ──────────────────────────────────────────────────────────
if (diseaseSearch) {{
  diseaseSearch.addEventListener('input', () => {{
    renderDiseaseOptions();
  }});
  // Pressing Enter when exactly one disease matches selects it directly so
  // a clinician typing "DLBCL" + Enter doesn't have to click the dropdown.
  diseaseSearch.addEventListener('keydown', (ev) => {{
    if (ev.key !== 'Enter') return;
    const real = [...diseaseSelect.options].filter(o => o.value !== '' && !o.disabled);
    if (real.length === 1) {{
      ev.preventDefault();
      diseaseSelect.value = real[0].value;
      diseaseSelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }}
  }});
}}

diseaseSelect.addEventListener('change', async () => {{
  await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.diseaseHint, async () => {{
    const i = diseaseSelect.value;
    // Switching disease invalidates whatever plan was on screen — there is
    // no longer any example or generated plan that matches the new form.
    clearPlanState();
    if (i === '') {{
      renderForm(null);
      repopulateExamples(null);
      updateRunBtnEnabled();
      return;
    }}
    const idx = parseInt(i, 10);
    const fullList = await ensureQuestionnaires();
    renderForm(fullList[idx]);
    repopulateExamples(idx);
    exampleSelect.value = '';
    saveDraft();
    updateRunBtnEnabled();
    updateImpactPanelLocal();
  }});
}});

function findQuestionnaireForProfile(profile) {{
  // Match by explicit disease_id first, then ICD-O-3 morphology. The
  // disease_id path is required for diseases with shared ICD-O codes.
  const disease = profile && profile.disease ? profile.disease : {{}};
  const diseaseId = (disease.id || (profile && profile.disease_id) || '').toString();
  if (diseaseId.startsWith('DIS-')) {{
    const normalized = diseaseId.toUpperCase();
    const byId = QUESTIONNAIRES_MANIFEST.findIndex(q => q.disease_id === normalized);
    if (byId >= 0) return byId;
  }}
  const code = disease.icd_o_3_morphology;
  if (!code) return -1;
  return QUESTIONNAIRES_MANIFEST.findIndex(q => q.disease_icd === code);
}}

function getByPath(obj, dotted) {{
  let cur = obj;
  for (const seg of dotted.split('.')) {{
    if (cur === null || typeof cur !== 'object') return undefined;
    cur = cur[seg];
  }}
  return cur;
}}

function populateFormFromProfile(quest, profile) {{
  // Walk every form question and try to read its dotted-path value
  // out of the example profile. Unset inputs stay empty (will count as
  // not-filled so user can finish anything missing).
  for (const group of quest.groups || []) {{
    for (const q of group.questions || []) {{
      const path = q.field;
      if (!path) continue;
      const val = getByPath(profile, path);
      if (val === undefined || val === null) continue;
      const inp = formPane.querySelector(`[data-field="${{CSS.escape(path)}}"]`);
      if (!inp) continue;
      if (q.type === 'boolean') inp.value = String(val);
      else if (q.type === 'enum') inp.value = JSON.stringify(val);
      else inp.value = val;
      answers[path] = val;
    }}
  }}
}}

exampleSelect.addEventListener('change', async () => {{
  await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.exampleHint, async () => {{
    const i = exampleSelect.value;
    if (i === '') return;
    const fullExamples = await ensureExamples();
    const ex = fullExamples[parseInt(i, 10)];
    setError(null);
    // Prefer form mode: find a questionnaire that matches this example's
    // disease and populate it. Fall back to JSON view only when no
    // matching questionnaire exists (most diseases don't have one yet).
    const qIdx = findQuestionnaireForProfile(ex.json);
    if (qIdx >= 0) {{
      diseaseSelect.value = qIdx;
      const fullList = await ensureQuestionnaires();
      renderForm(fullList[qIdx]);
      repopulateExamples(qIdx);
      exampleSelect.value = i;
      populateFormFromProfile(fullList[qIdx], ex.json);
      setMode('form');
      // Lock filled fields and reveal the personalize banner so the user
      // can opt-in to editing the example's data.
      lockFilledFields();
      showExampleLockBanner();
      // Keep the JSON mirror in sync so toggling to JSON shows the loaded data
      textarea.value = JSON.stringify(buildProfile(), null, 2);
      // Show the pre-built case plan when one exists. Hidden starter stubs
      // are form-prefill examples only, so they should not iframe a missing
      // /cases/<id>.html page.
      if (ex.case_id && ex.has_case_page !== false) {{
        await loadExamplePlan(ex.case_id);
        setStatus('{'Example loaded ✓ Plan shown — edit any field to generate your own.' if target_lang == 'en' else 'Приклад завантажено ✓ План показано — зміни поле, щоб згенерувати власний.'}', 'ok');
      }} else {{
        clearPlanState();
        setStatus('{'Starter example loaded ✓ Click «Generate» to build a plan.' if target_lang == 'en' else 'Стартовий приклад завантажено ✓ Натисни «Згенерувати», щоб побудувати план.'}', 'ok');
      }}
    }} else {{
      setMode('json');
      textarea.value = JSON.stringify(ex.json, null, 2);
      // No questionnaire match: still show the prebuilt plan if a case file
      // exists for this example.
      if (ex.case_id && ex.has_case_page !== false) {{
        await loadExamplePlan(ex.case_id);
        setStatus('{"Example loaded as JSON (no questionnaire for this disease yet)" if target_lang == "en" else "Приклад завантажено як JSON (ще немає опитувальника для цієї хвороби)"}', 'ok');
      }} else {{
        clearPlanState();
        setStatus('{"Starter example loaded as JSON" if target_lang == "en" else "Стартовий приклад завантажено як JSON"}', 'ok');
      }}
    }}
    saveDraft();
    updateRunBtnEnabled();
    updateImpactPanelLocal();
  }});
}});

personalizeBtn && personalizeBtn.addEventListener('click', () => {{
  if (isInteractionLocked()) return;
  unlockAllFields();
  setStatus('{"Fields unlocked — edit anything. Click «Generate» when you are ready." if target_lang == "en" else "Поля розблоковано — редагуй що завгодно. Натисни «Згенерувати» коли готовий."}', 'ok');
}});

modeFormBtn.addEventListener('click', () => {{ if (!isInteractionLocked()) setMode('form'); }});
modeJsonBtn.addEventListener('click', () => {{ if (!isInteractionLocked()) setMode('json'); }});
formatBtn && formatBtn.addEventListener('click', () => {{
  if (isInteractionLocked()) return;
  setError(null);
  try {{ textarea.value = JSON.stringify(JSON.parse(textarea.value), null, 2); }}
  catch (e) {{ setError('{"Invalid JSON: " if target_lang == "en" else "Невалідний JSON: "}' + e.message); }}
}});
textarea.addEventListener('input', () => {{
  markPlanDirty();
  saveDraft();
  updateRunBtnEnabled();
  // No live preview from JSON — engine runs only on Generate click.
}});

resetBtn.addEventListener('click', () => {{
  if (isInteractionLocked()) return;
  if (!confirm('{"Clear the form and drop the draft?" if target_lang == "en" else "Очистити форму і прибрати чернетку?"}')) return;
  answers = {{}};
  textarea.value = '';
  diseaseSelect.value = '';
  renderForm(null);
  clearPlanState();
  localStorage.removeItem(STORAGE_KEY);
  updateImpactPanelLocal();
  updateRunBtnEnabled();
  setStatus('{"Cleared." if target_lang == "en" else "Очищено."}');
}});

runBtn.addEventListener('click', runEngine);

// Pause pending evals the moment the user reaches for a toolbar control —
// fires before the native <select> popup opens, so the main thread is free
// to render it. Covers both dropdowns + mode/reset buttons.
[diseaseSelect, exampleSelect, modeFormBtn, modeJsonBtn, resetBtn].forEach(el => {{
  if (!el) return;
  el.addEventListener('mousedown', pauseEvalForToolbar);
  el.addEventListener('focus', pauseEvalForToolbar);
}});

// ── Case-token URL handler (CSD-3-qr-token) ───────────────────────────────
// QR codes printed on CSD Lab NGS reports encode the patient profile in the
// URL hash: openonco.info/try.html#p=<base64-gzip-json>. We decode entirely
// in the browser — CHARTER §9.3, no PHI ever touches a server.
async function loadFromUrlHash() {{
  const hash = window.location.hash.slice(1);  // strip #
  if (!hash) return;
  const params = new URLSearchParams(hash);
  const token = params.get('p');
  if (!token) return;

  try {{
    await withUiLock(UI_LOCK_TEXT.loadingTitle, UI_LOCK_TEXT.loadingLead, UI_LOCK_TEXT.qrHint, async () => {{
    // urlsafe-base64 → bytes (re-add padding) → gunzip → JSON
    const padded = token + '='.repeat((-token.length) & 3);
    const binStr = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
    const bytes = Uint8Array.from(binStr, c => c.charCodeAt(0));
    const ds = new DecompressionStream('gzip');
    const stream = new Response(bytes).body.pipeThrough(ds);
    const json = await new Response(stream).text();
    const patient = JSON.parse(json);

    // Try to match a disease questionnaire so the form mode picks up the
    // profile cleanly — same flow as the example loader.
    const qIdx = findQuestionnaireForProfile(patient);
    if (qIdx >= 0) {{
      diseaseSelect.value = qIdx;
      const fullList = await ensureQuestionnaires();
      renderForm(fullList[qIdx]);
      repopulateExamples(qIdx);
      populateFormFromProfile(fullList[qIdx], patient);
      setMode('form');
      lockFilledFields();
      showExampleLockBanner();
      textarea.value = JSON.stringify(buildProfile(), null, 2);
    }} else {{
      setMode('json');
      textarea.value = JSON.stringify(patient, null, 2);
    }}
    saveDraft();
    updateRunBtnEnabled();
    updateImpactPanelLocal();

    const banner = document.createElement('div');
    banner.className = 'case-token-banner';
    banner.textContent = '{"✓ Profile loaded from QR code. Click «Generate» to build the plan, or edit any field." if target_lang == "en" else "✓ Профіль завантажено з QR-коду. Натисніть «Згенерувати», щоб побудувати план, або відредагуйте поля."}';
    mainTryEl.parentNode.insertBefore(banner, mainTryEl);
    setStatus('{"Profile loaded from QR ✓" if target_lang == "en" else "Профіль із QR завантажено ✓"}', 'ok');
    }});
  }} catch (err) {{
    console.error('Failed to decode case token:', err);
    const banner = document.createElement('div');
    banner.className = 'case-token-banner-error';
    banner.textContent = '{"⚠ Failed to load profile from QR code. Enter JSON manually or pick an example." if target_lang == "en" else "⚠ Не вдалося завантажити профіль із QR-коду. Введіть JSON вручну або оберіть приклад."}';
    mainTryEl.parentNode.insertBefore(banner, mainTryEl);
    setError('QR token decode failed: ' + (err.message || err));
  }}
}}

// Run after loadAssets so questionnaires + examples are populated and
// findQuestionnaireForProfile/populateFormFromProfile can do their job.
loadAssets()
  .then(() => loadFromUrlHash())
  .catch(e => setError('Initialization failed: ' + e));
window.addEventListener('hashchange', loadFromUrlHash);

// CSD-6E: kick off the bundle index fetch as soon as the page loads —
// it's tiny (~5 KB) and lets resolveDiseaseId() pre-resolve from
// ICD-O-3 codes before the user clicks Generate. Best-effort, never
// blocks UI.
loadBundleIndex().then(() => scheduleOfflineCacheWarmup()).catch(() => {{}});
refreshBuildPanel().catch(() => {{}});
window.addEventListener('online', () => refreshBuildPanel().catch(() => {{}}));
window.addEventListener('offline', () => refreshBuildPanel().catch(() => {{}}));
if (navigator.serviceWorker) {{
  navigator.serviceWorker.addEventListener('controllerchange', () => {{
    refreshBuildPanel().catch(() => {{}});
  }});
}}

// CSD-6E polish: register the cache-first service worker so repeat
// visits skip the network for the engine bundle entirely. Best-effort
// — falls through silently when the SW API is unavailable (private
// mode, ITP, file://, etc.).
if ('serviceWorker' in navigator) {{
  window.addEventListener('load', () => {{
    navigator.serviceWorker.register('/sw.js')
      .then(() => refreshBuildPanel().catch(() => {{}}))
      .catch((e) => {{
        console.warn('[OpenOnco] service worker registration failed:', e);
        refreshBuildPanel().catch(() => {{}});
      }});
  }});
}}
</script>
</body>
</html>
"""


# ── Per-case page (back-link banner, no auth gate) ────────────────────────


def _wrap_case_html(rendered_html: str, case: CaseEntry,
                    *, target_lang: str = "en") -> str:
    """Insert the full sticky site top-bar (brand + nav + lang switch +
    Try CTA) plus a case-context sub-bar (back-to-gallery + feedback)
    into the rendered Plan/Brief HTML. No auth gate — landing is fully
    public.

    The Plan/Brief page is otherwise self-contained (own inline CSS,
    no /style.css link), so we inline a self-contained copy of the
    top-bar's styles here to avoid loading the full site stylesheet
    (which would override Plan-specific .page / body rules)."""

    # Self-contained top-bar CSS, mirroring docs/style.css §"Top bar"
    # but stripped to what the case page actually renders. Wrapped in
    # `.oo-topbar-host` so the Plan's own styles are unaffected and the
    # Plan's `body { font-family / color / background }` still wins for
    # the rest of the page.
    topbar_style = (
        '<style>'
        # Sticky positioning so the header stays visible while the
        # doctor scrolls the (long) Plan body. z-index above any
        # Plan-internal sticky elements.
        '.oo-topbar-host{position:sticky;top:0;z-index:100;}'
        '.oo-topbar-host .top-bar{background:#fff;color:#111827;'
        'padding:13px 24px;display:flex;justify-content:space-between;'
        'align-items:center;font-family:Source Sans 3,sans-serif;'
        'border-bottom:1px solid #e5e7eb;width:100%;max-width:100%;overflow-x:clip;}'
        '.oo-topbar-host .brand-line{display:flex;align-items:center;'
        'gap:12px;margin-right:30px;}'
        '.oo-topbar-host .brand-logo{display:none;}'
        '.oo-topbar-host .brand-mini{display:inline-flex;align-items:center;gap:9px;'
        'font-family:Playfair Display,Georgia,serif;'
        'font-size:26px;font-weight:900;color:#14532d;text-decoration:none;letter-spacing:0;}'
        '.oo-topbar-host .top-nav{display:flex;align-items:center;flex:1;'
        'margin:0 24px 0 16px;gap:4px;}'
        '.oo-topbar-host .top-nav a{color:#374151;padding:6px 10px;'
        'text-decoration:none;font-size:14.5px;font-weight:700;border-radius:4px;}'
        '.oo-topbar-host .top-nav a:hover{color:#14532d;background:transparent;}'
        '.oo-topbar-host .top-right{display:flex;align-items:center;gap:14px;'
        'flex-shrink:0;}'
        '.oo-topbar-host .top-cta-group{display:flex;align-items:center;gap:8px;'
        'flex-wrap:wrap;justify-content:flex-end;}'
        '.oo-topbar-host .lang-switch{display:inline-flex;align-items:center;gap:0;'
        'background:#fff;border:1px solid #e5e7eb;border-radius:4px;'
        'font-family:JetBrains Mono,monospace;font-size:11px;letter-spacing:.5px;'
        'overflow:hidden;flex-shrink:0;}'
        '.oo-topbar-host .lang-switch .lang-current,'
        '.oo-topbar-host .lang-switch .lang-other{width:56px;box-sizing:border-box;'
        'padding:4px 9px;display:inline-flex;align-items:center;'
        'justify-content:center;gap:5px;}'
        '.oo-topbar-host .lang-switch .lang-current{background:#14532d;'
        'color:white;font-weight:600;}'
        '.oo-topbar-host .lang-switch .lang-other{color:#374151;'
        'text-decoration:none;transition:background .12s;}'
        '.oo-topbar-host .lang-switch .lang-other:hover{background:transparent;'
        'color:#14532d;}'
        '.oo-topbar-host .lang-switch .lang-flag{display:inline-block;'
        'width:14px;height:10px;border-radius:1.5px;'
        'box-shadow:0 0 0 1px rgba(0,0,0,.25) inset;}'
        '.oo-topbar-host .lang-switch .lang-flag.flag-ua{'
        'background:linear-gradient(to bottom,#0057b7 50%,#ffd500 50%);}'
        '.oo-topbar-host .lang-switch .lang-flag.flag-en{background:#012169 '
        "url(\"data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30' preserveAspectRatio='none'%3E%3Cpath d='M0,0 L60,30 M60,0 L0,30' stroke='%23fff' stroke-width='6'/%3E%3Cpath d='M0,0 L60,30 M60,0 L0,30' stroke='%23C8102E' stroke-width='2'/%3E%3Cpath d='M30,0 V30 M0,15 H60' stroke='%23fff' stroke-width='10'/%3E%3Cpath d='M30,0 V30 M0,15 H60' stroke='%23C8102E' stroke-width='6'/%3E%3C/svg%3E\") center/cover no-repeat;}"
        '.oo-topbar-host .btn-cta-top{color:#14532d;background:white;'
        'padding:10px 16px;border-radius:7px;font-weight:700;'
        'font-size:15px;text-decoration:none;border:1px solid #e5e7eb;'
        'box-shadow:none;'
        'white-space:nowrap;min-width:112px;box-sizing:border-box;text-align:center;'
        'display:inline-block;}'
        '.oo-topbar-host .btn-cta-try{min-width:132px;}'
        '.oo-topbar-host .btn-cta-top:hover{filter:none;}'
        # Sub-bar with case context (back-to-gallery + feedback)
        '.case-bar{background:#0d3f24;color:#dcfce7;padding:8px 24px;'
        'display:flex;justify-content:space-between;align-items:center;'
        'font-family:Source Sans 3,sans-serif;font-size:13px;}'
        '.case-bar a{color:#86efac;text-decoration:none;margin-left:14px;}'
        '.case-bar a:hover{text-decoration:underline;}'
        '@media print{.oo-topbar-host,.case-bar{display:none;}}'
        '@media (max-width:700px){'
        '.oo-topbar-host .top-bar{display:grid;grid-template-columns:minmax(0,1fr) auto;'
        'gap:10px 12px;align-items:center;'
        'padding:12px max(14px,env(safe-area-inset-right)) 14px max(14px,env(safe-area-inset-left));}'
        '.oo-topbar-host .brand-line{grid-column:1;grid-row:1;min-width:0;margin-right:0;}'
        '.oo-topbar-host .brand-mini{max-width:100%;font-size:22px;overflow:hidden;text-overflow:ellipsis;}'
        '.oo-topbar-host .top-right{display:contents;}'
        '.oo-topbar-host .lang-switch{grid-column:2;grid-row:1;justify-self:end;font-size:10px;}'
        '.oo-topbar-host .lang-switch .lang-current,'
        '.oo-topbar-host .lang-switch .lang-other{width:48px;padding:4px 6px;}'
        '.oo-topbar-host .top-nav{grid-column:1/-1;grid-row:2;display:grid;'
        'grid-template-columns:repeat(3,minmax(0,1fr));width:100%;margin:0;gap:4px;justify-content:stretch;}'
        '.oo-topbar-host .top-nav a{min-width:0;padding:8px 4px;text-align:center;'
        'overflow-wrap:anywhere;line-height:1.15;}'
        '.oo-topbar-host .top-cta-group{grid-column:1/-1;grid-row:3;display:grid;'
        'grid-template-columns:repeat(3,minmax(0,1fr));width:100%;gap:6px;justify-content:stretch;}'
        '.oo-topbar-host .btn-cta-top{display:flex;align-items:center;justify-content:center;'
        'width:100%;min-width:0;min-height:44px;padding:8px 6px;font-size:13px;'
        'line-height:1.12;white-space:normal;overflow-wrap:anywhere;}'
        '.oo-topbar-host .btn-cta-try{min-width:0;}'
        '.case-bar{display:grid;gap:6px;padding:8px max(14px,env(safe-area-inset-right)) 8px max(14px,env(safe-area-inset-left));}'
        '.case-bar a{margin-left:0;margin-right:12px;}'
        '}'
        '</style>\n'
    )

    back_label = "← Back to gallery" if target_lang == "en" else "← Назад до галереї"
    feedback_label = "Feedback on this case" if target_lang == "en" else "Feedback на цей кейс"
    gallery_href = "/gallery.html" if target_lang == "en" else "/ukr/gallery.html"

    # Full top-bar (brand + nav + lang switch + Try CTA), pointing the
    # lang switcher at the matching case in the other language so a
    # mid-read switch lands on the same content.
    case_lang_href = _lang_switch_href("case", target_lang, case.case_id)
    topbar_html = (
        '<div class="oo-topbar-host no-print">'
        + _render_top_bar(active="", target_lang=target_lang,
                          lang_switch_href=case_lang_href)
        + '</div>\n'
    )

    case_label = case.label_en if (target_lang == "en" and getattr(case, "label_en", None)) else case.label_ua
    sub_bar_html = (
        '<div class="case-bar no-print">'
        f'<div>OpenOnco · <strong>{case_label}</strong></div>'
        '<div>'
        f'<a href="{gallery_href}">{back_label}</a>'
        f'<a href="{GH_NEW_ISSUE}?title=%5Bfeedback%5D+'
        f'{case.case_id}&labels=tester-feedback" target="_blank" rel="noopener">'
        f'{feedback_label}</a>'
        '</div>'
        '</div>\n'
    )

    head_assets = ""
    if "fonts.googleapis.com/css2?family=Playfair" not in rendered_html:
        head_assets += SITE_FONT_LINK + "\n"
    if "favicon.svg" not in rendered_html:
        head_assets += SITE_FAVICON_LINK + "\n"

    out = rendered_html.replace("</head>", head_assets + topbar_style + "</head>", 1)
    out = out.replace('<div class="page">',
                      topbar_html + sub_bar_html + '<div class="page">', 1)
    return out


# ── Static stylesheet ─────────────────────────────────────────────────────




# ── Capabilities page ─────────────────────────────────────────────────────


# Capabilities / Limitations pages need a heme-vs-solid split and a 1L /
# 2L+ split. We compute these on demand here (rather than extending
# `Stats`) by re-reading the relevant YAML directories. Cheap — small KB.
def _coverage_breakdown() -> dict:
    import yaml as _yaml
    from pathlib import Path as _Path

    base = _Path(__file__).resolve().parent.parent / "knowledge_base" / "hosted" / "content"

    def _load_dir(name):
        d = base / name
        if not d.exists():
            return []
        out = []
        for p in sorted(d.glob("*.yaml")):
            try:
                with p.open(encoding="utf-8") as fh:
                    obj = _yaml.safe_load(fh)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                pass
        return out

    diseases = _load_dir("diseases")
    algorithms = _load_dir("algorithms")
    indications = _load_dir("indications")

    heme_ids: set[str] = set()
    solid_ids: set[str] = set()
    short_by_id: dict[str, str] = {}
    for d in diseases:
        d_id = d.get("id") or ""
        lin = (d.get("lineage") or "").lower()
        short_by_id[d_id] = d_id.replace("DIS-", "")
        if (
            "b_cell" in lin or "t_cell" in lin or "plasma" in lin
            or "myeloid" in lin or "lymph" in lin or "mpn" in lin
            or "leuk" in lin or "mds" in lin
            or lin in {"hodgkin", "myeloma"}
        ):
            heme_ids.add(d_id)
        elif lin:
            solid_ids.add(d_id)

    algos_1l = algos_2l = 0
    diseases_with_2l: set[str] = set()
    for a in algorithms:
        try:
            lot = int(a.get("applicable_to_line_of_therapy"))
        except (TypeError, ValueError):
            continue
        if lot == 1:
            algos_1l += 1
        elif lot >= 2:
            algos_2l += 1
            d_id = a.get("applicable_to_disease")
            if d_id:
                diseases_with_2l.add(d_id)

    inds_1l = inds_2l = 0
    for ind in indications:
        try:
            lot = int((ind.get("applicable_to") or {}).get("line_of_therapy"))
        except (TypeError, ValueError):
            continue
        if lot == 1:
            inds_1l += 1
        elif lot >= 2:
            inds_2l += 1

    diseases_2l_heme_list = ", ".join(
        sorted(short_by_id.get(d, d) for d in diseases_with_2l & heme_ids)
    )
    diseases_2l_solid_list = ", ".join(
        sorted(short_by_id.get(d, d) for d in diseases_with_2l & solid_ids)
    ) or "—"
    solid_disease_list = ", ".join(
        sorted(short_by_id.get(d, d) for d in solid_ids)
    )

    return {
        "heme_diseases": len(heme_ids),
        "solid_diseases": len(solid_ids),
        "algorithms_1l": algos_1l,
        "algorithms_2l_plus": algos_2l,
        "diseases_with_2l_plus": len(diseases_with_2l),
        "diseases_with_2l_plus_heme": len(diseases_with_2l & heme_ids),
        "diseases_with_2l_plus_solid": len(diseases_with_2l & solid_ids),
        "diseases_2l_heme_list": diseases_2l_heme_list,
        "diseases_2l_solid_list": diseases_2l_solid_list,
        "solid_disease_list": solid_disease_list,
        "indications_1l": inds_1l,
        "indications_2l_plus": inds_2l,
    }


def render_capabilities(stats, *, target_lang: str = "en") -> str:
    if target_lang == "en":
        return _render_capabilities_en(stats)
    return _render_capabilities_uk(stats)


def _render_capabilities_uk(stats) -> str:
    by_type = {e.type: e.count for e in stats.entities}
    n_diseases = by_type.get("diseases", 0)
    n_indications = by_type.get("indications", 0)
    n_regimens = by_type.get("regimens", 0)
    n_tests = by_type.get("tests", 0)
    n_redflags = by_type.get("redflags", 0)
    n_workups = by_type.get("workups", 0)
    n_sources = by_type.get("sources", 0)
    n_drugs = by_type.get("drugs", 0)
    n_skills = stats.skills_planned_roles
    cov = _coverage_breakdown()
    n_heme = cov["heme_diseases"]
    n_solid = cov["solid_diseases"]
    n_algos_1l = cov["algorithms_1l"]
    n_algos_2l = cov["algorithms_2l_plus"]
    n_inds_1l = cov["indications_1l"]
    n_inds_2l = cov["indications_2l_plus"]
    n_dis_2l = cov["diseases_with_2l_plus"]
    n_dis_2l_heme = cov["diseases_with_2l_plus_heme"]
    n_dis_2l_solid = cov["diseases_with_2l_plus_solid"]
    diseases_full = sum(
        1 for d in stats.diseases
        if d.coverage_status in {"stub_full_chain", "reviewed"}
    )

    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · Можливості</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link href="/style.css" rel="stylesheet">
<style>
  /* Tabs */
  .cap-tabs {{
    display: flex; gap: 2px; flex-wrap: wrap;
    border-bottom: 2px solid var(--bg-strong, #e5e7eb);
    margin: 28px 0 0; position: sticky; top: 0;
    background: white; z-index: 20; padding-top: 6px;
  }}
  .cap-tab {{
    padding: 12px 18px; background: transparent; border: 0;
    border-bottom: 3px solid transparent; cursor: pointer;
    font: 500 14px/1 'Source Sans 3', system-ui, sans-serif;
    color: var(--gray-600, #4b5563); transition: color .15s, border-color .15s;
    display: inline-flex; align-items: center; gap: 8px;
  }}
  .cap-tab:hover {{ color: var(--gray-900, #111); }}
  .cap-tab.is-active {{
    color: var(--green-700, #15803d);
    border-bottom-color: var(--green-700, #15803d);
    font-weight: 600;
  }}
  .cap-tab .cap-tab-num {{
    font: 600 11px/1 'JetBrains Mono', monospace;
    background: var(--gray-100, #f3f4f6); color: var(--gray-600, #4b5563);
    padding: 3px 6px; border-radius: 3px;
  }}
  .cap-tab.is-active .cap-tab-num {{
    background: var(--green-50, #f0fdf4); color: var(--green-700, #15803d);
  }}
  .cap-panel {{ display: none; padding-top: 24px; }}
  .cap-panel.is-active {{ display: block; animation: capFade .25s ease; }}
  @keyframes capFade {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; }} }}

  /* Pipeline */
  .pipeline {{
    margin: 24px 0 36px;
    border-radius: 14px; overflow: hidden;
    background: linear-gradient(135deg, #0f3729 0%, #134e3c 50%, #1a6e54 100%);
    color: #ecfdf5; padding: 28px 28px 24px;
    position: relative;
  }}
  .pipeline::before {{
    content: ""; position: absolute; inset: 0;
    background: radial-gradient(circle at 20% 0%, rgba(94,234,212,0.18), transparent 50%);
    pointer-events: none;
  }}
  .pipeline > * {{ position: relative; }}
  .pipeline-head {{
    display: flex; justify-content: space-between; align-items: baseline;
    flex-wrap: wrap; gap: 8px; margin-bottom: 6px;
  }}
  .pipeline-eyebrow {{
    font: 600 11px/1 'JetBrains Mono', monospace;
    letter-spacing: 0.12em; text-transform: uppercase;
    color: #5eead4;
  }}
  .pipeline-version {{ font: 400 11px/1 'JetBrains Mono', monospace; color: #99f6e4; opacity: 0.7; }}
  .pipeline-title {{
    font: 700 24px/1.25 'Playfair Display', Georgia, serif;
    color: white; margin: 0 0 4px;
  }}
  .pipeline-title em {{ color: #5eead4; font-style: italic; font-weight: 700; }}
  .pipeline-sub {{
    font-size: 13.5px; color: #a7f3d0; margin: 0 0 22px; max-width: 720px; line-height: 1.55;
  }}
  .pipeline-grid {{
    display: grid; grid-template-columns: 1fr auto 1fr auto 1fr;
    gap: 14px; align-items: stretch;
  }}
  .pipeline-col {{
    background: rgba(255,255,255,0.06); border: 1px solid rgba(94,234,212,0.18);
    border-radius: 10px; padding: 14px 16px;
    display: flex; flex-direction: column;
  }}
  .pipeline-col.is-out {{ border-color: rgba(94,234,212,0.35); background: rgba(94,234,212,0.07); }}
  .pipeline-col-tag {{
    font: 600 10px/1 'JetBrains Mono', monospace;
    color: #5eead4; letter-spacing: 0.1em; text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .pipeline-col-title {{ font-size: 13.5px; font-weight: 600; color: white; margin-bottom: 8px; }}
  .pipeline-code {{
    font: 400 11.5px/1.55 'JetBrains Mono', monospace;
    color: #d1fae5; white-space: pre; overflow-x: auto;
    background: rgba(0,0,0,0.18); border-radius: 6px;
    padding: 8px 10px; margin: 0; flex: 1;
  }}
  .pipeline-code .pl-k {{ color: #fcd34d; }}
  .pipeline-code .pl-s {{ color: #a5f3fc; }}
  .pipeline-code .pl-c {{ color: #94a3b8; font-style: italic; }}
  .pipeline-stages {{ list-style: none; padding: 0; margin: 0; font-size: 12px; counter-reset: stage; }}
  .pipeline-stages li {{
    padding: 4px 0 4px 22px; color: #d1fae5; position: relative;
    border-bottom: 1px dashed rgba(94,234,212,0.18);
  }}
  .pipeline-stages li:last-child {{ border-bottom: 0; }}
  .pipeline-stages li::before {{
    content: counter(stage); counter-increment: stage;
    position: absolute; left: 0; top: 4px;
    width: 16px; height: 16px; border-radius: 50%;
    background: rgba(94,234,212,0.18); color: #5eead4;
    font: 700 10px/16px 'JetBrains Mono', monospace; text-align: center;
  }}
  .pipeline-track {{
    border-left: 3px solid #5eead4; padding: 4px 0 4px 10px;
    margin-bottom: 8px;
  }}
  .pipeline-track.is-alt {{ border-left-color: #fcd34d; opacity: 0.92; }}
  .pipeline-track-label {{
    font: 600 9.5px/1 'JetBrains Mono', monospace; letter-spacing: 0.1em;
    color: #5eead4; text-transform: uppercase; display: block; margin-bottom: 4px;
  }}
  .pipeline-track.is-alt .pipeline-track-label {{ color: #fcd34d; }}
  .pipeline-track-body {{ font-size: 12.5px; color: white; font-weight: 500; line-height: 1.4; }}
  .pipeline-track-meta {{ font-size: 11px; color: #a7f3d0; margin-top: 2px; }}
  .pipeline-arrow {{
    display: flex; align-items: center; justify-content: center;
    color: #5eead4; font-size: 22px; font-weight: 700;
  }}
  .pipeline-foot {{
    margin-top: 14px; padding: 10px 14px;
    background: rgba(0,0,0,0.22); border-radius: 8px;
    font-size: 12px; color: #d1fae5; line-height: 1.5;
    display: flex; gap: 16px; flex-wrap: wrap;
  }}
  .pipeline-foot span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .pipeline-foot strong {{ color: white; font-weight: 600; }}
  .pipeline-foot .pip-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #5eead4; display: inline-block; }}

  /* Key numbers */
  .key-nums {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin: 20px 0 32px;
  }}
  .key-num {{
    background: white; border: 1px solid var(--gray-200, #e5e7eb);
    border-top: 3px solid var(--teal, #14b8a6);
    border-radius: 8px; padding: 14px 14px 12px;
  }}
  .key-num-val {{
    font: 700 26px/1 'Playfair Display', Georgia, serif;
    color: var(--gray-900, #111); margin-bottom: 4px;
  }}
  .key-num-lbl {{
    font-size: 11.5px; color: var(--gray-600, #4b5563); line-height: 1.35;
  }}
  .key-num.is-warn {{ border-top-color: var(--amber, #d97706); }}
  .key-num.is-warn .key-num-val {{ color: var(--amber, #d97706); }}

  /* Pillars */
  .pillars {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px; margin: 24px 0 8px;
  }}
  .pillar {{
    background: var(--gray-50, #f9fafb);
    border-left: 3px solid var(--green-600, #16a34a);
    border-radius: 0 8px 8px 0; padding: 12px 14px;
  }}
  .pillar-title {{
    font-size: 13px; font-weight: 600; color: var(--gray-900, #111);
    margin-bottom: 4px; display: flex; align-items: center; gap: 8px;
  }}
  .pillar-title .pillar-ic {{
    width: 18px; height: 18px; border-radius: 50%;
    background: var(--green-100, #dcfce7); color: var(--green-700, #15803d);
    display: inline-flex; align-items: center; justify-content: center;
    font: 700 11px/1 'JetBrains Mono', monospace;
  }}
  .pillar-text {{ font-size: 12.5px; color: var(--gray-600, #4b5563); line-height: 1.5; }}

  /* Mobile */
  @media (max-width: 880px) {{
    .pipeline-grid {{ grid-template-columns: 1fr; }}
    .pipeline-arrow {{ transform: rotate(90deg); padding: 4px 0; }}
    .cap-tabs {{ gap: 0; }}
    .cap-tab {{ padding: 10px 12px; font-size: 13px; }}
  }}
</style>
</head>
<body>
{_render_top_bar(active="capabilities", target_lang="uk", lang_switch_href=_lang_switch_href("capabilities", "uk"))}

<main>
  <section class="info-page">
    <h1>Можливості</h1>
    <p class="lead">
      Декларативний rule engine для онкологічних рекомендацій. JSON-профіль на вході —
      <strong>Plan</strong> із двома альтернативними треками (стандартний + агресивний) на виході,
      кожна claim з citation на джерело.
    </p>

    <div class="callout callout-hard">
      <strong>STUB-статус клінічного контенту.</strong>
      Dual sign-off: <strong>{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</strong>
      (CHARTER §6.1 вимагає два Clinical Co-Lead approvals).
      Це proposed-plan: structured data + algorithm + sources на місці, але без dual sign-off.
      Інструмент підтримки рішень, не медичний пристрій. Стан на <code>{stats.generated_at_utc}</code>.
    </div>

    <nav class="cap-tabs" role="tablist" aria-label="Розділи">
      <button class="cap-tab is-active" role="tab" data-tab="overview" aria-selected="true"><span class="cap-tab-num">01</span>Огляд</button>
      <button class="cap-tab" role="tab" data-tab="engine" aria-selected="false"><span class="cap-tab-num">02</span>Engine</button>
      <button class="cap-tab" role="tab" data-tab="data" aria-selected="false"><span class="cap-tab-num">03</span>Дані пацієнта</button>
      <button class="cap-tab" role="tab" data-tab="limits" aria-selected="false"><span class="cap-tab-num">04</span>Межі</button>
      <button class="cap-tab" role="tab" data-tab="contribute" aria-selected="false"><span class="cap-tab-num">05</span>Долучитись</button>
    </nav>

    <!-- TAB 1: OVERVIEW -->
    <section class="cap-panel is-active" id="panel-overview" role="tabpanel">

      <div class="pipeline" role="img" aria-label="OpenOnco — pipeline: JSON-профіль → engine → Plan з двома треками">
        <div class="pipeline-head">
          <span class="pipeline-eyebrow">OpenOnco · engine у двох словах</span>
          <span class="pipeline-version">v{OPENONCO_VERSION} · {stats.generated_at_utc}</span>
        </div>
        <h2 class="pipeline-title">
          Один JSON-профіль → <em>два плани лікування</em> з citation під кожною claim.
        </h2>
        <p class="pipeline-sub">
          Без LLM у клінічному рішенні. Без серверу. Patient JSON залишається на машині.
          Час обробки одного профілю — 50-200&nbsp;мс.
        </p>

        <div class="pipeline-grid">
          <div class="pipeline-col">
            <div class="pipeline-col-tag">Вхід</div>
            <div class="pipeline-col-title">Profile (FHIR / mCODE)</div>
<pre class="pipeline-code"><span class="pl-c"># приклад: DLBCL</span>
<span class="pl-k">disease</span>: DLBCL-NOS
<span class="pl-k">line_of_therapy</span>: <span class="pl-s">1L</span>
<span class="pl-k">biomarkers</span>:
  CD79B_mut: <span class="pl-s">true</span>
  MYC_rearr: <span class="pl-s">false</span>
  COO: <span class="pl-s">ABC</span>
<span class="pl-k">findings</span>:
  ipi: <span class="pl-s">3</span>
  ecog: <span class="pl-s">1</span>
  ldh_ratio: <span class="pl-s">1.8</span></pre>
          </div>

          <div class="pipeline-arrow" aria-hidden="true">→</div>

          <div class="pipeline-col">
            <div class="pipeline-col-tag">Engine · 6 стадій</div>
            <div class="pipeline-col-title">Algorithm walk + RedFlags + CIViC</div>
            <ol class="pipeline-stages">
              <li>Resolve algorithm</li>
              <li>Flatten findings</li>
              <li>Eval {n_redflags} RedFlags</li>
              <li>Walk decision tree</li>
              <li>Materialize tracks</li>
              <li>Resolve regimens</li>
            </ol>
          </div>

          <div class="pipeline-arrow" aria-hidden="true">→</div>

          <div class="pipeline-col is-out">
            <div class="pipeline-col-tag">Вихід</div>
            <div class="pipeline-col-title">Plan з ≥2 tracks + trace</div>
            <div class="pipeline-track">
              <span class="pipeline-track-label">Track A · default</span>
              <div class="pipeline-track-body">R-CHOP × 6</div>
              <div class="pipeline-track-meta">NCCN BCEL-D · ESMO 2024</div>
            </div>
            <div class="pipeline-track is-alt">
              <span class="pipeline-track-label">Track B · alternative</span>
              <div class="pipeline-track-body">Pola-R-CHP × 6</div>
              <div class="pipeline-track-meta">POLARIX 2022 (CD79B+, ABC)</div>
            </div>
          </div>
        </div>

        <div class="pipeline-foot">
          <span><span class="pip-dot"></span> trace покрокова</span>
          <span><span class="pip-dot"></span> source citations на кожній claim</span>
          <span><span class="pip-dot"></span> AccessMatrix (НСЗУ)</span>
          <span><span class="pip-dot"></span> Open Questions</span>
          <span><span class="pip-dot"></span> <strong>~200&nbsp;мс</strong> на профіль</span>
        </div>
      </div>

      <div class="key-nums">
        <div class="key-num"><div class="key-num-val">{n_diseases}</div><div class="key-num-lbl">хвороб у KB</div></div>
        <div class="key-num"><div class="key-num-val">{n_indications}</div><div class="key-num-lbl">показань ({n_inds_1l} 1L · {n_inds_2l} 2L+)</div></div>
        <div class="key-num"><div class="key-num-val">{n_regimens}</div><div class="key-num-lbl">режимів лікування</div></div>
        <div class="key-num"><div class="key-num-val">{n_drugs}</div><div class="key-num-lbl">препаратів (ATC/RxNorm)</div></div>
        <div class="key-num"><div class="key-num-val">{n_redflags}</div><div class="key-num-lbl">red flags</div></div>
        <div class="key-num"><div class="key-num-val">{n_sources}</div><div class="key-num-lbl">цитованих джерел</div></div>
        <div class="key-num"><div class="key-num-val">{n_skills}</div><div class="key-num-lbl">лікар-скілів (MDT)</div></div>
        <div class="key-num is-warn"><div class="key-num-val">{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</div><div class="key-num-lbl">з dual sign-off</div></div>
      </div>

      <div class="pillars">
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">01</span>Не «чорний ящик»</div>
          <div class="pillar-text">Кожен крок алгоритму у trace. LLM не приймає клінічних рішень (CHARTER §8.3).</div>
        </div>
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">02</span>Кожна claim з citation</div>
          <div class="pillar-text">source_id + position + paraphrased quote + page/section. Render-time guard.</div>
        </div>
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">03</span>Privacy by design</div>
          <div class="pillar-text">CLI / Pyodide / Python import. Серверу немає. Patient JSON не покидає машину.</div>
        </div>
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">04</span>Plan живе</div>
          <div class="pillar-text"><code>revise_plan()</code> оновлює рекомендацію щойно з'являються нові біомаркери чи findings.</div>
        </div>
      </div>

      <div class="info-section">
        <h2>Coverage matrix</h2>
        <p class="info-text">
          Сторінка <a href="/ukr/diseases.html"><code>/ukr/diseases.html</code></a> — per-disease таблиця:
          counts по біомаркерах / препаратах / показаннях / red flags, checkmarks 1L+2L, fill% і verified%.
          Згрупована за лімфоїдною, мієлоїдною гематологією і солідними пухлинами. Канонічна UI-поверхня
          для <code>/disease_coverage.json</code>.
          <a href="/ukr/diseases.html"><strong>→ Дивитись матрицю</strong></a>
        </p>
        <p class="info-text">
          <a href="/ukr/gallery.html"><code>/ukr/gallery.html</code></a> — 586 кейсів
          (159 hand-curated + 362 verified variant profiles + 65 auto-base). Кожен — повний Plan або
          Diagnostic Brief з усіма citation. Disease-grouped drill-down.
          <a href="/ukr/gallery.html"><strong>→ Дивитись приклади</strong></a>
        </p>
      </div>
    </section>

    <!-- TAB 2: ENGINE -->
    <section class="cap-panel" id="panel-engine" role="tabpanel">

      <div class="info-section">
        <h2>6 стадій обробки запиту</h2>
        <p class="info-text">
          Лікар дає engine'у JSON-профіль. Engine виконує 6 послідовних стадій і повертає Plan з ≥2 tracks
          (CHARTER §15.2 C6 — alternative не сховано).
        </p>
        <div class="flow-strip">
          <div class="flow-step">
            <div class="flow-num">Stage 1</div>
            <div class="flow-title">Disease + Algorithm resolve</div>
            <div class="flow-desc"><code>disease.id</code> + <code>line_of_therapy</code> + <code>disease_state</code> → Algorithm entity.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 2</div>
            <div class="flow-title">Findings flatten</div>
            <div class="flow-desc">Об'єднує demographics + biomarkers + findings в один flat dict.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 3</div>
            <div class="flow-title">RedFlag eval</div>
            <div class="flow-desc">{n_redflags} RF проти findings (<code>any_of</code>/<code>all_of</code>/<code>none_of</code> з threshold-ами).</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 4</div>
            <div class="flow-title">Algorithm walk</div>
            <div class="flow-desc">Decision tree крок за кроком. Trace зберігає fired_red_flags на кожному кроці.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 5</div>
            <div class="flow-title">Tracks materialize</div>
            <div class="flow-desc">Indication → tracks (standard / aggressive / surveillance) з biomarker filter.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 6</div>
            <div class="flow-title">Per-track resolve</div>
            <div class="flow-desc">Indication → Regimen (з phases) + Monitoring + SupportiveCare + AccessMatrix.</div>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h2>CIViC actionability</h2>
        <p class="info-text">
          Раніше actionability приходила з OncoKB — ToS заборонив non-commercial public derivatives (конфлікт з CHARTER §2).
          Мігрували на <strong>CIViC (CC0)</strong> WashU. Engine читає локальний nightly YAML snapshot
          (<code>knowledge_base/hosted/civic/&lt;date&gt;/</code>) — детермінізм + офлайн. Fusion-aware matcher
          обробляє і point mutations (BRAF V600E), і fusions (BCR::ABL1). Render: ESCAT tier — primary,
          CIViC evidence rating — у details. Monthly refresh CI відкриває PR з diff'ом.
        </p>
      </div>

      <div class="info-section">
        <h2>Multi-phase regimens</h2>
        <p class="info-text">
          <code>Regimen.phases</code> — впорядкований список named blocks (induction → consolidation → maintenance),
          кожен зі своїм cycle schedule і тригером переходу. Реальні протоколи (R-CHOP × 6 → maintenance,
          AML 7+3 → HiDAC consolidation, axi-cel bridging → infusion). <code>bridging_options</code> — список
          регіменів-мостів між фазами (для CAR-T). Старі однофазні YAMLs auto-wrap у one-phase form через
          <code>auto_wrap_legacy_components()</code>.
        </p>
      </div>

      <div class="info-section">
        <h2>Citation guard — 3 layers</h2>
        <p class="info-text">
          Трирівнева система — три точки, де ловимо claims без джерел:
        </p>
        <table class="kv-table">
          <thead><tr><th>Layer</th><th>Де ловить</th><th>Що робить</th></tr></thead>
          <tbody>
            <tr>
              <td><strong>L1</strong> · Loader</td>
              <td>YAML load (Pydantic)</td>
              <td>SRC-* referential integrity. Невідомий SRC-ID → load fail.</td>
            </tr>
            <tr>
              <td><strong>L2</strong> · Verifier</td>
              <td>Contributor PR (CI)</td>
              <td>Three-layer grounding: source exists, paraphrase grounded, anchor in section.</td>
            </tr>
            <tr>
              <td><strong>L3</strong> · Render</td>
              <td>HTML output</td>
              <td>Без citation → warn-badge (lenient) або skip cell (<code>strict_citation_guard=True</code>).</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="info-section">
        <h2>Три способи запуску</h2>
        <div class="num-grid num-grid--rich">
          <div class="num-card">
            <div class="num-big">CLI</div>
            <div class="num-lbl">Локально</div>
            <p class="num-text">
              <code>python -m knowledge_base.engine.cli --patient profile.json --render plan.html</code>.
              Offline.
            </p>
          </div>
          <div class="num-card num-card--accent">
            <div class="num-big">Pyodide</div>
            <div class="num-lbl">У браузері (try.html)</div>
            <p class="num-text">
              Python WASM + micropip + engine bundle (~2.4 МБ). Перший запуск 8-15&nbsp;сек,
              далі — як CLI. Service worker для offline.
            </p>
          </div>
          <div class="num-card">
            <div class="num-big">Library</div>
            <div class="num-lbl">Python import</div>
            <p class="num-text">
              <code>from knowledge_base.engine import generate_plan, revise_plan</code> —
              EHR / CSV / batch testing. Stateless, deterministic.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 3: DATA -->
    <section class="cap-panel" id="panel-data" role="tabpanel">

      <div class="info-section">
        <h2>Що engine читає з profile</h2>
        <p class="info-text">
          Лише structured поля з чіткою семантикою. Невпізнані поля ігноруються — ніяких прихованих ефектів.
        </p>
        <table class="kv-table">
          <thead><tr><th>Категорія</th><th>Поля</th><th>Як використовуємо</th></tr></thead>
          <tbody>
            <tr>
              <td>Disease (вхідна точка)</td>
              <td><code>disease.id</code> · <code>icd_o_3_morphology</code> · <code>line_of_therapy</code> · <code>disease_state</code></td>
              <td>визначає який Algorithm запускати</td>
            </tr>
            <tr>
              <td>Diagnostic mode</td>
              <td><code>suspicion.lineage_hint</code> · <code>tissue_locations</code> · <code>presentation</code></td>
              <td>вмикає DiagnosticPlan замість Plan</td>
            </tr>
            <tr>
              <td>Demographics</td>
              <td><code>age</code> · <code>ecog</code> · <code>fit_for_transplant</code> · <code>decompensated_cirrhosis</code> · <code>pregnancy_status</code></td>
              <td>filter у <code>Indication.applicable_to.demographic_constraints</code></td>
            </tr>
            <tr>
              <td>Biomarkers</td>
              <td>будь-які <code>BIO-X</code> з KB: <code>BIO-CLL-HIGH-RISK-GENETICS</code>, <code>BIO-HCV-RNA</code>, …</td>
              <td>тригерять RedFlags, filter'ять Indications, мапляться у CIViC</td>
            </tr>
            <tr>
              <td>Findings</td>
              <td>сотні structured полів — <code>dominant_nodal_mass_cm</code>, <code>ldh_ratio_to_uln</code>, <code>tp53_mutation</code>, …</td>
              <td>thresholds у RedFlag triggers</td>
            </tr>
            <tr>
              <td>Prior tests</td>
              <td><code>prior_tests_completed: [TEST-IDs]</code></td>
              <td>виключає вже зроблені тести з workup_steps</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="info-section">
        <h2>Що engine повертає — Plan</h2>
        <table class="kv-table">
          <thead><tr><th>Поле</th><th>Що містить</th></tr></thead>
          <tbody>
            <tr><td><code>tracks[]</code></td><td>≥2 alternative tracks (default first): indication + regimen (+ phases) + monitoring + supportive_care + contraindications</td></tr>
            <tr><td><code>access_matrix</code></td><td>per-track agg: UA-реєстрації, НСЗУ-покриття, cost (₴), <code>AccessPathway</code>. Stale-cost warn &gt; 180 днів.</td></tr>
            <tr><td><code>experimental_options</code></td><td>третій трек — <code>enumerate_experimental_options()</code> запитує ClinicalTrials.gov v2. 7-day TTL cache.</td></tr>
            <tr><td><code>actionability_hits</code></td><td>CIViC matches з ESCAT-primary + variant, evidence rating, clinical significance, source citations</td></tr>
            <tr><td><code>fda_compliance</code></td><td>FDA Criterion 4 fields: intended_use, patient_population_match, algorithm_summary, automation_bias_warning</td></tr>
            <tr><td><code>trace</code></td><td>покрокова історія walk_algorithm: step / outcome / branch / fired_red_flags</td></tr>
            <tr><td><code>warnings</code></td><td>schema/ref errors, time_critical disqualifications, missing data hints, citation-guard warnings</td></tr>
            <tr><td><code>supersedes</code> / <code>superseded_by</code></td><td>версійний chain між plans для одного пацієнта</td></tr>
          </tbody>
        </table>
        <p class="info-text">
          Опціонально вмикається <strong>MDT brief</strong> — <code>orchestrate_mdt()</code> додає
          required/recommended/optional ролі з {n_skills} віртуальних спеціалістів + open questions + provenance graph.
        </p>
      </div>

      <div class="info-section">
        <h2>Оновлення плану — <code>revise_plan()</code></h2>
        <p class="info-text">
          Три легальні переходи + одна заборона. Попередній plan не мутується — повертається deep copy
          з <code>superseded_by</code>. Per CHARTER §10.2 — стара версія зберігається indefinitely.
        </p>
        <table class="kv-table">
          <thead><tr><th>Із</th><th>Зміна</th><th>Перехід</th><th>Результат</th></tr></thead>
          <tbody>
            <tr><td>DiagnosticPlan vN</td><td>тільки suspicion</td><td>diagnostic → diagnostic</td><td>DiagnosticPlan v(N+1)</td></tr>
            <tr><td>DiagnosticPlan vN</td><td>підтверджена histology</td><td>diagnostic → treatment <strong>(promotion)</strong></td><td>Plan v1</td></tr>
            <tr><td>Plan vN</td><td>оновлення з histology</td><td>treatment → treatment</td><td>Plan v(N+1)</td></tr>
            <tr><td>Plan vN</td><td>видалено histology</td><td colspan="2"><span style="color:var(--red);font-weight:600;">ILLEGAL — ValueError, CHARTER §15.2 C7</span></td></tr>
          </tbody>
        </table>
      </div>

      <div class="callout callout-good">
        <strong>Privacy.</strong> Patient JSON ніколи не залишає машину користувача.
        Немає логів, немає БД. Reproducibility:
        <code>Plan.knowledge_base_state.algorithm_version</code> фіксує версію KB →
        same input + same KB = same output.
      </div>
    </section>

    <!-- TAB 4: LIMITS -->
    <section class="cap-panel" id="panel-limits" role="tabpanel">

      <div class="info-section">
        <h2>Open Questions — engine відмовляється від рішень без даних</h2>
        <p class="info-text">
          Замість мовчазного default'у engine явно фіксує які поля бракує і якого тесту чи висновку потребує
          (MDT_ORCHESTRATOR_SPEC §3). Рендеряться у Plan як окрема section, не сховано.
        </p>
        <table class="kv-table">
          <thead><tr><th>Code</th><th>Тригер</th><th>Що emit'ить engine</th></tr></thead>
          <tbody>
            <tr><td><strong>Q1</strong></td><td>Histology not confirmed</td><td>«Treatment Plan generated against ICD-O-3 code only; confirm primary histology before therapy»</td></tr>
            <tr><td><strong>Q2</strong></td><td>Stage missing</td><td>«Lugano/Ann Arbor stage required for confident risk-stratification»</td></tr>
            <tr><td><strong>Q3</strong></td><td>RF clause incomplete</td><td>«Cytogenetic panel incomplete; high-risk status assessed with partial data»</td></tr>
            <tr><td><strong>Q4</strong></td><td>Biomarker missing</td><td>«IGHV mutation status + FISH del(17p) required to confirm 1L recommendation»</td></tr>
            <tr><td><strong>Q5</strong></td><td>Performance status missing</td><td>«ECOG required for transplant-eligibility assessment»; fall на conservative default</td></tr>
            <tr><td><strong>Q6</strong></td><td>Drug not NSZU-reimbursed</td><td>«D-VRd: daratumumab not currently NSZU-reimbursed; verify funding pathway»</td></tr>
            <tr><td><strong>DQ1-4</strong></td><td>Diagnostic-mode: tissue / lineage / presentation / hypotheses missing</td><td>знижує confidence workup match; lineage_hint + tissue превалює</td></tr>
          </tbody>
        </table>
        <div class="callout">
          <strong>Чому не «беремо default тихо»:</strong> CHARTER §15.2 C6 (anti automation-bias) —
          engine не може робити вигляд, що знає, коли не знає.
        </div>
      </div>

      <div class="info-section">
        <h2>Gap-и персоналізації — навмисні</h2>
        <p class="info-text">
          «Персоналізація» в OpenOnco — це rule-based вибір з фіксованих варіантів, не AI-генерація.
          Це навмисна архітектурна позиція (CHARTER §8.3).
        </p>
        <div class="gap-grid">
          <div class="gap-card">
            <div class="gap-tag">Gap 1</div>
            <h3>Без per-patient dose calc</h3>
            <p>Regimen зберігає <strong>стандартну дозу</strong> (bortezomib 1.3 mg/m²), не множиться на BSA і не зменшується під CrCl 30 автоматично. Принципово — уникнути FDA device classification.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 2</div>
            <h3>Без response-adapted cycles</h3>
            <p>Regimen фіксує <code>total_cycles: 6 + 2 maintenance</code>. Не адаптується на основі response (PR vs CR після PET2). Re-staging через окремий <code>revise_plan</code>.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 3</div>
            <h3>Genomic matching обмежений CIViC</h3>
            <p>Поза CIViC (rare, novel variants) emits warning «no actionability evidence», без «creative» інтерпретацій.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 4</div>
            <h3>SupportiveCare однакова</h3>
            <p>PJP prophylaxis attached до D-VRd для всіх — engine не знає альтернатив (dapsone замість bactrim). Лікар substitute'ить.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 5</div>
            <h3>Без cumulative-toxicity tracking</h3>
            <p>2L plan для пацієнта що отримав bortezomib у 1L з grade 2 нейропатією — profile не carrier'ить <code>prior_treatment_history</code> structured; лікар сам інтерпретує.</p>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h2>CHARTER-обмеження — will not change</h2>
        <p class="info-text">
          Принципові архітектурні рішення, що гатекіпять FDA / клінічну безпеку.
        </p>
        <div class="gap-grid">
          <div class="gap-card gap-hard">
            <div class="gap-tag">§8.3</div>
            <h3>LLM не приймає клінічні рішення</h3>
            <p>LLM лише: boilerplate, doc drafts, extraction (з human verification), translation з clinical review. <strong>Не</strong>: вибір режиму, дози, інтерпретація biomarker.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§15.2 C7</div>
            <h3>Без histology — без Plan</h3>
            <p>Treatment Plan тільки якщо <code>disease.id</code> підтверджено. Інакше DiagnosticPlan mode. <code>revise_plan</code> treatment → diagnostic — <strong>заборонено</strong>.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§15.2 C5</div>
            <h3>Без time-critical</h3>
            <p>Не призначений для emergency oncology (oncologic emergencies). Indication з <code>time_critical: true</code> → disqualification warning.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§6.1</div>
            <h3>Two-reviewer merge</h3>
            <p>Будь-яка зміна clinical content потребує 2 з 3 Clinical Co-Lead approvals. Без цього — STUB.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§15.2 C6</div>
            <h3>Anti automation-bias</h3>
            <p>Завжди ≥2 tracks side-by-side. Alternative не buried, не «click to expand». Лікар бачить вибір, не директиву.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§9.3</div>
            <h3>Patient data ніколи у repo</h3>
            <p><code>patient_plans/</code> gitignored. Site показує тільки synthetic examples. Telemetry заборонена без consent.</p>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h2>Never list — що engine ніколи не робить</h2>
        <div class="gap-grid">
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Не сховує alternative track</h3><p>Обидві рекомендації завжди показані. UI не має «expand to see alternative».</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Не генерує Indication LLM-ом</h3><p>Усе з curated KB. Немає Indication → warning, не «creative invention».</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Не модифікує дози</h3><p>Дози зі стандартного NCCN/ESMO. Adjustments тільки через явні <code>dose_modification_rules</code>.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Не оцінює «що краще»</h3><p>Algorithm обирає default, але не вирішує що default кращий. Лікар має автономію — automation_bias_warning.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Не інтерпретує imaging</h3><p>«Bulky disease» приходить як structured field. Image analysis = device classification.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Не робить cohort matching</h3><p>«У базі з N пацієнтів M% обрали X» — потребує persisted patient registry + privacy review. Не зараз.</p></div>
        </div>
      </div>

      <div class="info-section">
        <h2>Поточне покриття — де STUB і чого немає</h2>
        <table class="kv-table">
          <thead><tr><th>Категорія</th><th>Стан</th><th>Що це означає</th></tr></thead>
          <tbody>
            <tr><td>Хвороби з повним ланцюгом</td><td>{diseases_full} / {n_diseases}</td><td>Решта частково модельовані</td></tr>
            <tr><td>Indications 1L</td><td>{n_inds_1l}</td><td>Перша лінія для всіх {n_diseases} хвороб</td></tr>
            <tr><td>Indications 2L+</td><td>{n_inds_2l}</td><td>{n_dis_2l_heme} гематол. + {n_dis_2l_solid} солід. Решта solid 2L+ частково</td></tr>
            <tr><td>Pediatric oncology</td><td>0</td><td>Out of scope MVP — окремий track</td></tr>
            <tr><td>Радіотерапія</td><td>частково</td><td>RT у мультимодальних Indications; як окрема сутність — не моделюється</td></tr>
            <tr><td>Хірургія</td><td>не модельовано</td><td>Surgical oncology indications відсутні</td></tr>
            <tr><td>НСЗУ formulary live-feed</td><td>статичний flag</td><td>Hard-coded на режимах; не auto-refresh</td></tr>
            <tr><td>Reviewer dual sign-off</td><td><strong>{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</strong></td><td>Основна bottleneck-метрика — capacity план: {stats.reviewer_signoffs_total} → ≥85% verified</td></tr>
            <tr><td>Live gap dashboard</td><td><a href="/ukr/clinical-gaps.html">→ link</a></td><td>Build-generated audit (sign-off, solid 2L+, surgery, RT, supportive)</td></tr>
          </tbody>
        </table>
        <div class="callout">
          <strong>Що НЕ означає STUB:</strong> structured data + algorithm + sources вже є.
          STUB означає: не пройшло dual sign-off. «Proposed plan», не «approved plan».
        </div>
      </div>

      <div class="info-section">
        <h2>Workflow для лікаря</h2>
        <p class="info-text">
          Engine — підготовка до tumor-board, не заміна. Лікар: <strong>1)</strong> перевіряє sources
          (кожна claim з citation, guard відсікав комірки без джерел) → <strong>2)</strong> заповнює Open Questions
          (замовляє тести, <code>revise_plan</code>) → <strong>3)</strong> адаптує під пацієнта (дози, supportive care,
          UA-availability) → <strong>4)</strong> обговорює на tumor board (MDT brief — structured agenda).
          Engine — draft, лікар — final.
        </p>
      </div>
    </section>

    <!-- TAB 5: CONTRIBUTE -->
    <section class="cap-panel" id="panel-contribute" role="tabpanel">

      <div class="info-section">
        <h2>TaskTorrent — верифікувати алгоритми токенами вашого AI</h2>
        <p class="info-text">
          Найбільший gap — <strong>{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</strong> dual-reviewer sign-off.
          Bottleneck не вирішується новим кодом — він вирішується контрибуторами з AI-tool'ами,
          що беруть structured chunks роботи.
        </p>
        <div class="num-grid num-grid--rich">
          <div class="num-card num-card--accent">
            <div class="num-big">1</div>
            <div class="num-lbl">Що це</div>
            <p class="num-text">
              Maintainer публікує «чанк» — одну завершену задачу (~100k–300k токенів):
              «реверифікувати BMA evidence для DLBCL × 17 entities» або «backfill source-license для 8 sources».
              Контрибутор бере чанк, AI виконує, відкриває PR.
            </p>
          </div>
          <div class="num-card">
            <div class="num-big">2</div>
            <div class="num-lbl">Що від вас потрібно</div>
            <p class="num-text">
              AI-tool з token budget (Claude Code Pro+, Codex, Cursor, ChatGPT з web). GitHub + <code>gh</code> CLI.
              Python 3.10+. ~1-3 години. <strong>Без клінічної експертизи</strong> — ви тригерите drafting,
              лікарі-co-leads signoff'ять.
            </p>
          </div>
          <div class="num-card">
            <div class="num-big">3</div>
            <div class="num-lbl">8-line bootstrap</div>
            <p class="num-text">
              Скопіюйте 8-рядковий промпт з
              <a href="https://github.com/{GH_REPO}/blob/master/docs/contributing/CONTRIBUTOR_QUICKSTART.md" target="_blank" rel="noopener"><code>CONTRIBUTOR_QUICKSTART.md</code></a>
              у AI-агент. Він знайде доступний chunk, claim'не, виконає, прогоне валідатор, відкриє PR.
            </p>
          </div>
          <div class="num-card num-card--accent">
            <div class="num-big">4</div>
            <div class="num-lbl">Що буде з PR</div>
            <p class="num-text">
              Maintainer перевіряє mechanical (валідатор, schema). Clinical Co-Lead — sample review semantic
              (CHARTER §6.1). Merge → sidecar landing → upsert у hosted KB → render. Атрибуція у
              <code>_contribution_meta.yaml</code>.
            </p>
          </div>
        </div>
        <div class="cta-row" style="margin-top:24px;">
          <a class="btn btn-primary" href="https://github.com/{GH_REPO}/blob/master/docs/contributing/CONTRIBUTOR_QUICKSTART.md" target="_blank" rel="noopener">Contributor Quickstart →</a>
          <a class="btn btn-secondary" href="https://github.com/{GH_REPO}/issues?q=is%3Aissue+is%3Aopen+label%3Achunk-task+label%3Astatus-active" target="_blank" rel="noopener">Активні чанки →</a>
        </div>
        <div class="callout callout-good" style="margin-top:18px;">
          <strong>Що це дає Україні.</strong> Кожен верифікований BMA — одна actionability claim,
          яку рендеримо як «approved», не «STUB», для українських лікарів. Один контрибутор за вечір
          з токенами Pro+ підписки може просунути 10-20 BMA через signoff prep — тиждень роботи однієї
          людини за іншою моделлю.
        </div>
      </div>

      <div class="info-section">
        <h2>Активність останніх днів</h2>
        <p class="info-text">
          За 4 дні TaskTorrent — <strong>7 хвиль</strong>, десятки chunks, ~73 BMA-кандидати,
          23 BMA-драфти готові до clinical signoff, 53 source stubs, 1,251 UA-language fields drafted.
          Останні структурні апдейти:
        </p>
        <ul style="font-size:14px; line-height:1.65; color:var(--gray-700);">
          <li><strong>CIViC pivot</strong> — engine + 29 BIO + 399 BMA YAMLs мігровано з OncoKB-схеми; monthly snapshot refresh CI.</li>
          <li><strong>Multi-phase regimens (PR1-3)</strong> — <code>Regimen.phases</code>, <code>bridging_options</code>, phases-aware render, back-compat auto-wrap.</li>
          <li><strong>Citation guard L3</strong> — render-time перевірка кожної BMA-комірки.</li>
          <li><strong>Coverage matrix</strong> — <a href="/ukr/diseases.html">/ukr/diseases.html</a> per-disease drill-down.</li>
          <li><strong>586 кейсів у gallery</strong> — Phase 2 chunked feat: ~60 нових hand-curated за 4 дні.</li>
        </ul>
      </div>
    </section>

  </section>

  <footer class="page-foot">
    Open-source · MIT-style usage · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    <br>
    Жодних реальних пацієнтських даних · CHARTER §9.3.
    Це інформаційний інструмент для лікаря, не медичний пристрій (CHARTER §15 + §11).
  </footer>
</main>

<script>
  (function() {{
    var tabs = document.querySelectorAll('.cap-tab');
    var panels = document.querySelectorAll('.cap-panel');

    function activate(name) {{
      tabs.forEach(function(t) {{
        var on = t.dataset.tab === name;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
      }});
      panels.forEach(function(p) {{
        p.classList.toggle('is-active', p.id === 'panel-' + name);
      }});
    }}

    tabs.forEach(function(tab) {{
      tab.addEventListener('click', function() {{
        var name = tab.dataset.tab;
        activate(name);
        if (history.replaceState) {{
          history.replaceState(null, '', '#' + name);
        }}
      }});
    }});

    var hash = (window.location.hash || '').replace('#', '');
    if (hash && document.getElementById('panel-' + hash)) {{
      activate(hash);
    }}
  }})();
</script>
</body>
</html>
"""


def _render_capabilities_en(stats) -> str:
    by_type = {e.type: e.count for e in stats.entities}
    n_diseases = by_type.get("diseases", 0)
    n_indications = by_type.get("indications", 0)
    n_regimens = by_type.get("regimens", 0)
    n_tests = by_type.get("tests", 0)
    n_redflags = by_type.get("redflags", 0)
    n_workups = by_type.get("workups", 0)
    n_sources = by_type.get("sources", 0)
    n_drugs = by_type.get("drugs", 0)
    n_skills = stats.skills_planned_roles
    cov = _coverage_breakdown()
    n_heme = cov["heme_diseases"]
    n_solid = cov["solid_diseases"]
    n_algos_1l = cov["algorithms_1l"]
    n_algos_2l = cov["algorithms_2l_plus"]
    n_inds_1l = cov["indications_1l"]
    n_inds_2l = cov["indications_2l_plus"]
    n_dis_2l = cov["diseases_with_2l_plus"]
    n_dis_2l_heme = cov["diseases_with_2l_plus_heme"]
    n_dis_2l_solid = cov["diseases_with_2l_plus_solid"]
    diseases_full = sum(
        1 for d in stats.diseases
        if d.coverage_status in {"stub_full_chain", "reviewed"}
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · Capabilities</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link href="/style.css" rel="stylesheet">
<style>
  /* Tabs */
  .cap-tabs {{
    display: flex; gap: 2px; flex-wrap: wrap;
    border-bottom: 2px solid var(--bg-strong, #e5e7eb);
    margin: 28px 0 0; position: sticky; top: 0;
    background: white; z-index: 20; padding-top: 6px;
  }}
  .cap-tab {{
    padding: 12px 18px; background: transparent; border: 0;
    border-bottom: 3px solid transparent; cursor: pointer;
    font: 500 14px/1 'Source Sans 3', system-ui, sans-serif;
    color: var(--gray-600, #4b5563); transition: color .15s, border-color .15s;
    display: inline-flex; align-items: center; gap: 8px;
  }}
  .cap-tab:hover {{ color: var(--gray-900, #111); }}
  .cap-tab.is-active {{
    color: var(--green-700, #15803d);
    border-bottom-color: var(--green-700, #15803d);
    font-weight: 600;
  }}
  .cap-tab .cap-tab-num {{
    font: 600 11px/1 'JetBrains Mono', monospace;
    background: var(--gray-100, #f3f4f6); color: var(--gray-600, #4b5563);
    padding: 3px 6px; border-radius: 3px;
  }}
  .cap-tab.is-active .cap-tab-num {{
    background: var(--green-50, #f0fdf4); color: var(--green-700, #15803d);
  }}
  .cap-panel {{ display: none; padding-top: 24px; }}
  .cap-panel.is-active {{ display: block; animation: capFade .25s ease; }}
  @keyframes capFade {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; }} }}

  /* Pipeline */
  .pipeline {{
    margin: 24px 0 36px;
    border-radius: 14px; overflow: hidden;
    background: linear-gradient(135deg, #0f3729 0%, #134e3c 50%, #1a6e54 100%);
    color: #ecfdf5; padding: 28px 28px 24px;
    position: relative;
  }}
  .pipeline::before {{
    content: ""; position: absolute; inset: 0;
    background: radial-gradient(circle at 20% 0%, rgba(94,234,212,0.18), transparent 50%);
    pointer-events: none;
  }}
  .pipeline > * {{ position: relative; }}
  .pipeline-head {{
    display: flex; justify-content: space-between; align-items: baseline;
    flex-wrap: wrap; gap: 8px; margin-bottom: 6px;
  }}
  .pipeline-eyebrow {{
    font: 600 11px/1 'JetBrains Mono', monospace;
    letter-spacing: 0.12em; text-transform: uppercase;
    color: #5eead4;
  }}
  .pipeline-version {{ font: 400 11px/1 'JetBrains Mono', monospace; color: #99f6e4; opacity: 0.7; }}
  .pipeline-title {{
    font: 700 24px/1.25 'Playfair Display', Georgia, serif;
    color: white; margin: 0 0 4px;
  }}
  .pipeline-title em {{ color: #5eead4; font-style: italic; font-weight: 700; }}
  .pipeline-sub {{
    font-size: 13.5px; color: #a7f3d0; margin: 0 0 22px; max-width: 720px; line-height: 1.55;
  }}
  .pipeline-grid {{
    display: grid; grid-template-columns: 1fr auto 1fr auto 1fr;
    gap: 14px; align-items: stretch;
  }}
  .pipeline-col {{
    background: rgba(255,255,255,0.06); border: 1px solid rgba(94,234,212,0.18);
    border-radius: 10px; padding: 14px 16px;
    display: flex; flex-direction: column;
  }}
  .pipeline-col.is-out {{ border-color: rgba(94,234,212,0.35); background: rgba(94,234,212,0.07); }}
  .pipeline-col-tag {{
    font: 600 10px/1 'JetBrains Mono', monospace;
    color: #5eead4; letter-spacing: 0.1em; text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .pipeline-col-title {{ font-size: 13.5px; font-weight: 600; color: white; margin-bottom: 8px; }}
  .pipeline-code {{
    font: 400 11.5px/1.55 'JetBrains Mono', monospace;
    color: #d1fae5; white-space: pre; overflow-x: auto;
    background: rgba(0,0,0,0.18); border-radius: 6px;
    padding: 8px 10px; margin: 0; flex: 1;
  }}
  .pipeline-code .pl-k {{ color: #fcd34d; }}
  .pipeline-code .pl-s {{ color: #a5f3fc; }}
  .pipeline-code .pl-c {{ color: #94a3b8; font-style: italic; }}
  .pipeline-stages {{ list-style: none; padding: 0; margin: 0; font-size: 12px; counter-reset: stage; }}
  .pipeline-stages li {{
    padding: 4px 0 4px 22px; color: #d1fae5; position: relative;
    border-bottom: 1px dashed rgba(94,234,212,0.18);
  }}
  .pipeline-stages li:last-child {{ border-bottom: 0; }}
  .pipeline-stages li::before {{
    content: counter(stage); counter-increment: stage;
    position: absolute; left: 0; top: 4px;
    width: 16px; height: 16px; border-radius: 50%;
    background: rgba(94,234,212,0.18); color: #5eead4;
    font: 700 10px/16px 'JetBrains Mono', monospace; text-align: center;
  }}
  .pipeline-track {{
    border-left: 3px solid #5eead4; padding: 4px 0 4px 10px;
    margin-bottom: 8px;
  }}
  .pipeline-track.is-alt {{ border-left-color: #fcd34d; opacity: 0.92; }}
  .pipeline-track-label {{
    font: 600 9.5px/1 'JetBrains Mono', monospace; letter-spacing: 0.1em;
    color: #5eead4; text-transform: uppercase; display: block; margin-bottom: 4px;
  }}
  .pipeline-track.is-alt .pipeline-track-label {{ color: #fcd34d; }}
  .pipeline-track-body {{ font-size: 12.5px; color: white; font-weight: 500; line-height: 1.4; }}
  .pipeline-track-meta {{ font-size: 11px; color: #a7f3d0; margin-top: 2px; }}
  .pipeline-arrow {{
    display: flex; align-items: center; justify-content: center;
    color: #5eead4; font-size: 22px; font-weight: 700;
  }}
  .pipeline-foot {{
    margin-top: 14px; padding: 10px 14px;
    background: rgba(0,0,0,0.22); border-radius: 8px;
    font-size: 12px; color: #d1fae5; line-height: 1.5;
    display: flex; gap: 16px; flex-wrap: wrap;
  }}
  .pipeline-foot span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .pipeline-foot strong {{ color: white; font-weight: 600; }}
  .pipeline-foot .pip-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #5eead4; display: inline-block; }}

  /* Key numbers */
  .key-nums {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin: 20px 0 32px;
  }}
  .key-num {{
    background: white; border: 1px solid var(--gray-200, #e5e7eb);
    border-top: 3px solid var(--teal, #14b8a6);
    border-radius: 8px; padding: 14px 14px 12px;
  }}
  .key-num-val {{
    font: 700 26px/1 'Playfair Display', Georgia, serif;
    color: var(--gray-900, #111); margin-bottom: 4px;
  }}
  .key-num-lbl {{
    font-size: 11.5px; color: var(--gray-600, #4b5563); line-height: 1.35;
  }}
  .key-num.is-warn {{ border-top-color: var(--amber, #d97706); }}
  .key-num.is-warn .key-num-val {{ color: var(--amber, #d97706); }}

  /* Pillars */
  .pillars {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px; margin: 24px 0 8px;
  }}
  .pillar {{
    background: var(--gray-50, #f9fafb);
    border-left: 3px solid var(--green-600, #16a34a);
    border-radius: 0 8px 8px 0; padding: 12px 14px;
  }}
  .pillar-title {{
    font-size: 13px; font-weight: 600; color: var(--gray-900, #111);
    margin-bottom: 4px; display: flex; align-items: center; gap: 8px;
  }}
  .pillar-title .pillar-ic {{
    width: 18px; height: 18px; border-radius: 50%;
    background: var(--green-100, #dcfce7); color: var(--green-700, #15803d);
    display: inline-flex; align-items: center; justify-content: center;
    font: 700 11px/1 'JetBrains Mono', monospace;
  }}
  .pillar-text {{ font-size: 12.5px; color: var(--gray-600, #4b5563); line-height: 1.5; }}

  /* Mobile */
  @media (max-width: 880px) {{
    .pipeline-grid {{ grid-template-columns: 1fr; }}
    .pipeline-arrow {{ transform: rotate(90deg); padding: 4px 0; }}
    .cap-tabs {{ gap: 0; }}
    .cap-tab {{ padding: 10px 12px; font-size: 13px; }}
  }}
</style>
</head>
<body>
{_render_top_bar(active="capabilities", target_lang="en", lang_switch_href=_lang_switch_href("capabilities", "en"))}

<main>
  <section class="info-page">
    <h1>Capabilities</h1>
    <p class="lead">
      A declarative rule engine for oncology recommendations. JSON profile in —
      <strong>Plan</strong> with two alternative tracks (standard + aggressive) out,
      every claim shipping with a citation to its source.
    </p>

    <div class="callout callout-hard">
      <strong>STUB status across all clinical content.</strong>
      Dual sign-off: <strong>{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</strong>
      (CHARTER §6.1 requires two Clinical Co-Lead approvals).
      This is a proposed plan: structured data + algorithm + sources are in place, but without dual sign-off.
      Decision-support tool, not a medical device. State as of <code>{stats.generated_at_utc}</code>.
    </div>

    <nav class="cap-tabs" role="tablist" aria-label="Sections">
      <button class="cap-tab is-active" role="tab" data-tab="overview" aria-selected="true"><span class="cap-tab-num">01</span>Overview</button>
      <button class="cap-tab" role="tab" data-tab="engine" aria-selected="false"><span class="cap-tab-num">02</span>Engine</button>
      <button class="cap-tab" role="tab" data-tab="data" aria-selected="false"><span class="cap-tab-num">03</span>Patient data</button>
      <button class="cap-tab" role="tab" data-tab="limits" aria-selected="false"><span class="cap-tab-num">04</span>Limits</button>
      <button class="cap-tab" role="tab" data-tab="contribute" aria-selected="false"><span class="cap-tab-num">05</span>Contribute</button>
    </nav>

    <!-- TAB 1: OVERVIEW -->
    <section class="cap-panel is-active" id="panel-overview" role="tabpanel">

      <div class="pipeline" role="img" aria-label="OpenOnco — pipeline: JSON profile → engine → Plan with two tracks">
        <div class="pipeline-head">
          <span class="pipeline-eyebrow">OpenOnco · engine in two words</span>
          <span class="pipeline-version">v{OPENONCO_VERSION} · {stats.generated_at_utc}</span>
        </div>
        <h2 class="pipeline-title">
          One JSON profile → <em>two treatment plans</em>, every claim cited.
        </h2>
        <p class="pipeline-sub">
          No LLM in the clinical decision. No server. Patient JSON stays on the machine.
          Per-profile processing: 50-200&nbsp;ms.
        </p>

        <div class="pipeline-grid">
          <div class="pipeline-col">
            <div class="pipeline-col-tag">Input</div>
            <div class="pipeline-col-title">Profile (FHIR / mCODE)</div>
<pre class="pipeline-code"><span class="pl-c"># example: DLBCL</span>
<span class="pl-k">disease</span>: DLBCL-NOS
<span class="pl-k">line_of_therapy</span>: <span class="pl-s">1L</span>
<span class="pl-k">biomarkers</span>:
  CD79B_mut: <span class="pl-s">true</span>
  MYC_rearr: <span class="pl-s">false</span>
  COO: <span class="pl-s">ABC</span>
<span class="pl-k">findings</span>:
  ipi: <span class="pl-s">3</span>
  ecog: <span class="pl-s">1</span>
  ldh_ratio: <span class="pl-s">1.8</span></pre>
          </div>

          <div class="pipeline-arrow" aria-hidden="true">→</div>

          <div class="pipeline-col">
            <div class="pipeline-col-tag">Engine · 6 stages</div>
            <div class="pipeline-col-title">Algorithm walk + RedFlags + CIViC</div>
            <ol class="pipeline-stages">
              <li>Resolve algorithm</li>
              <li>Flatten findings</li>
              <li>Eval {n_redflags} RedFlags</li>
              <li>Walk decision tree</li>
              <li>Materialize tracks</li>
              <li>Resolve regimens</li>
            </ol>
          </div>

          <div class="pipeline-arrow" aria-hidden="true">→</div>

          <div class="pipeline-col is-out">
            <div class="pipeline-col-tag">Output</div>
            <div class="pipeline-col-title">Plan with ≥2 tracks + trace</div>
            <div class="pipeline-track">
              <span class="pipeline-track-label">Track A · default</span>
              <div class="pipeline-track-body">R-CHOP × 6</div>
              <div class="pipeline-track-meta">NCCN BCEL-D · ESMO 2024</div>
            </div>
            <div class="pipeline-track is-alt">
              <span class="pipeline-track-label">Track B · alternative</span>
              <div class="pipeline-track-body">Pola-R-CHP × 6</div>
              <div class="pipeline-track-meta">POLARIX 2022 (CD79B+, ABC)</div>
            </div>
          </div>
        </div>

        <div class="pipeline-foot">
          <span><span class="pip-dot"></span> step-by-step trace</span>
          <span><span class="pip-dot"></span> source citation on every claim</span>
          <span><span class="pip-dot"></span> AccessMatrix</span>
          <span><span class="pip-dot"></span> Open Questions</span>
          <span><span class="pip-dot"></span> <strong>~200&nbsp;ms</strong> per profile</span>
        </div>
      </div>

      <div class="key-nums">
        <div class="key-num"><div class="key-num-val">{n_diseases}</div><div class="key-num-lbl">diseases in KB</div></div>
        <div class="key-num"><div class="key-num-val">{n_indications}</div><div class="key-num-lbl">indications ({n_inds_1l} 1L · {n_inds_2l} 2L+)</div></div>
        <div class="key-num"><div class="key-num-val">{n_regimens}</div><div class="key-num-lbl">treatment regimens</div></div>
        <div class="key-num"><div class="key-num-val">{n_drugs}</div><div class="key-num-lbl">drugs (ATC/RxNorm)</div></div>
        <div class="key-num"><div class="key-num-val">{n_redflags}</div><div class="key-num-lbl">red flags</div></div>
        <div class="key-num"><div class="key-num-val">{n_sources}</div><div class="key-num-lbl">cited sources</div></div>
        <div class="key-num"><div class="key-num-val">{n_skills}</div><div class="key-num-lbl">clinician skills (MDT)</div></div>
        <div class="key-num is-warn"><div class="key-num-val">{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</div><div class="key-num-lbl">with dual sign-off</div></div>
      </div>

      <div class="pillars">
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">01</span>Not a black box</div>
          <div class="pillar-text">Every algorithm step in the trace. LLM doesn't make clinical decisions (CHARTER §8.3).</div>
        </div>
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">02</span>Every claim with a citation</div>
          <div class="pillar-text">source_id + position + paraphrased quote + page/section. Render-time guard.</div>
        </div>
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">03</span>Privacy by design</div>
          <div class="pillar-text">CLI / Pyodide / Python import. No server. Patient JSON never leaves the machine.</div>
        </div>
        <div class="pillar">
          <div class="pillar-title"><span class="pillar-ic">04</span>Plan stays alive</div>
          <div class="pillar-text"><code>revise_plan()</code> refreshes the recommendation as new biomarkers or findings arrive.</div>
        </div>
      </div>

      <div class="info-section">
        <h2>Coverage matrix</h2>
        <p class="info-text">
          <a href="/diseases.html"><code>/diseases.html</code></a> — per-disease table:
          counts of biomarkers / drugs / indications / red flags, 1L+2L checkmarks, fill% and verified%.
          Grouped by lymphoid + myeloid hematology and solid tumors. Canonical UI for
          <code>/disease_coverage.json</code>.
          <a href="/diseases.html"><strong>→ View matrix</strong></a>
        </p>
        <p class="info-text">
          <a href="/gallery.html"><code>/gallery.html</code></a> — 586 cases
          (159 hand-curated + 362 verified variant profiles + 65 auto-base). Each — a full Plan or
          Diagnostic Brief with all citations. Disease-grouped drill-down.
          <a href="/gallery.html"><strong>→ View examples</strong></a>
        </p>
      </div>
    </section>

    <!-- TAB 2: ENGINE -->
    <section class="cap-panel" id="panel-engine" role="tabpanel">

      <div class="info-section">
        <h2>6-stage request processing</h2>
        <p class="info-text">
          The clinician feeds the engine a JSON profile. The engine runs 6 sequential stages
          and returns a Plan with ≥2 tracks (CHARTER §15.2 C6 — alternative never hidden).
        </p>
        <div class="flow-strip">
          <div class="flow-step">
            <div class="flow-num">Stage 1</div>
            <div class="flow-title">Disease + Algorithm resolve</div>
            <div class="flow-desc"><code>disease.id</code> + <code>line_of_therapy</code> + <code>disease_state</code> → Algorithm entity.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 2</div>
            <div class="flow-title">Findings flatten</div>
            <div class="flow-desc">Merges demographics + biomarkers + findings into one flat dict.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 3</div>
            <div class="flow-title">RedFlag eval</div>
            <div class="flow-desc">{n_redflags} RFs against findings (<code>any_of</code>/<code>all_of</code>/<code>none_of</code> with thresholds).</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 4</div>
            <div class="flow-title">Algorithm walk</div>
            <div class="flow-desc">Decision tree step by step. Trace records fired_red_flags at each node.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 5</div>
            <div class="flow-title">Tracks materialize</div>
            <div class="flow-desc">Indication → tracks (standard / aggressive / surveillance) with biomarker filter.</div>
          </div>
          <div class="flow-step">
            <div class="flow-num">Stage 6</div>
            <div class="flow-title">Per-track resolve</div>
            <div class="flow-desc">Indication → Regimen (with phases) + Monitoring + SupportiveCare + AccessMatrix.</div>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h2>CIViC actionability</h2>
        <p class="info-text">
          Actionability data used to come from OncoKB — but their ToS blocked non-commercial public
          derivatives (conflict with CHARTER §2). We migrated to <strong>CIViC (CC0)</strong> (WashU).
          The engine reads a local nightly YAML snapshot
          (<code>knowledge_base/hosted/civic/&lt;date&gt;/</code>) — deterministic + offline. The
          fusion-aware matcher handles both point mutations (BRAF V600E) and fusions (BCR::ABL1).
          Render: ESCAT tier — primary, CIViC evidence rating — in details. Monthly refresh CI opens
          a PR with the diff.
        </p>
      </div>

      <div class="info-section">
        <h2>Multi-phase regimens</h2>
        <p class="info-text">
          <code>Regimen.phases</code> is an ordered list of named blocks (induction → consolidation →
          maintenance), each with its own cycle schedule and transition trigger. Real-world protocols
          (R-CHOP × 6 → maintenance, AML 7+3 → HiDAC consolidation, axi-cel bridging → infusion).
          <code>bridging_options</code> — bridging regimens between phases (for CAR-T). Legacy
          single-phase YAMLs auto-wrap into one-phase form via <code>auto_wrap_legacy_components()</code>.
        </p>
      </div>

      <div class="info-section">
        <h2>Citation guard — 3 layers</h2>
        <p class="info-text">
          A three-layer verification system — three places where we catch unsourced claims:
        </p>
        <table class="kv-table">
          <thead><tr><th>Layer</th><th>Where</th><th>What</th></tr></thead>
          <tbody>
            <tr>
              <td><strong>L1</strong> · Loader</td>
              <td>YAML load (Pydantic)</td>
              <td>SRC-* referential integrity. Unknown SRC-ID → load fail.</td>
            </tr>
            <tr>
              <td><strong>L2</strong> · Verifier</td>
              <td>Contributor PR (CI)</td>
              <td>Three-layer grounding: source exists, paraphrase grounded, anchor in section.</td>
            </tr>
            <tr>
              <td><strong>L3</strong> · Render</td>
              <td>HTML output</td>
              <td>No citation → warn-badge (lenient) or skip cell (<code>strict_citation_guard=True</code>).</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="info-section">
        <h2>Three ways to run</h2>
        <div class="num-grid num-grid--rich">
          <div class="num-card">
            <div class="num-big">CLI</div>
            <div class="num-lbl">Locally</div>
            <p class="num-text">
              <code>python -m knowledge_base.engine.cli --patient profile.json --render plan.html</code>.
              Offline.
            </p>
          </div>
          <div class="num-card num-card--accent">
            <div class="num-big">Pyodide</div>
            <div class="num-lbl">In the browser (try.html)</div>
            <p class="num-text">
              Python WASM + micropip + engine bundle (~2.4 MB). First load 8-15&nbsp;s,
              then like a local CLI. Service worker for offline.
            </p>
          </div>
          <div class="num-card">
            <div class="num-big">Library</div>
            <div class="num-lbl">Python import</div>
            <p class="num-text">
              <code>from knowledge_base.engine import generate_plan, revise_plan</code> —
              EHR / CSV / batch testing. Stateless, deterministic.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 3: DATA -->
    <section class="cap-panel" id="panel-data" role="tabpanel">

      <div class="info-section">
        <h2>What the engine reads from a profile</h2>
        <p class="info-text">
          Only structured fields with explicit semantics. Unknown fields are ignored — no hidden effects.
        </p>
        <table class="kv-table">
          <thead><tr><th>Category</th><th>Fields</th><th>How we use it</th></tr></thead>
          <tbody>
            <tr>
              <td>Disease (entry point)</td>
              <td><code>disease.id</code> · <code>icd_o_3_morphology</code> · <code>line_of_therapy</code> · <code>disease_state</code></td>
              <td>determines which Algorithm to run</td>
            </tr>
            <tr>
              <td>Diagnostic mode</td>
              <td><code>suspicion.lineage_hint</code> · <code>tissue_locations</code> · <code>presentation</code></td>
              <td>activates DiagnosticPlan instead of Plan</td>
            </tr>
            <tr>
              <td>Demographics</td>
              <td><code>age</code> · <code>ecog</code> · <code>fit_for_transplant</code> · <code>decompensated_cirrhosis</code> · <code>pregnancy_status</code></td>
              <td>filter on <code>Indication.applicable_to.demographic_constraints</code></td>
            </tr>
            <tr>
              <td>Biomarkers</td>
              <td>any <code>BIO-X</code> from KB: <code>BIO-CLL-HIGH-RISK-GENETICS</code>, <code>BIO-HCV-RNA</code>, …</td>
              <td>trigger RedFlags, filter Indications, map to CIViC</td>
            </tr>
            <tr>
              <td>Findings</td>
              <td>hundreds of structured fields — <code>dominant_nodal_mass_cm</code>, <code>ldh_ratio_to_uln</code>, <code>tp53_mutation</code>, …</td>
              <td>thresholds in RedFlag triggers</td>
            </tr>
            <tr>
              <td>Prior tests</td>
              <td><code>prior_tests_completed: [TEST-IDs]</code></td>
              <td>excludes already-completed tests from workup_steps</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="info-section">
        <h2>What the engine returns — Plan</h2>
        <table class="kv-table">
          <thead><tr><th>Field</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>tracks[]</code></td><td>≥2 alternative tracks (default first): indication + regimen (+ phases) + monitoring + supportive_care + contraindications</td></tr>
            <tr><td><code>access_matrix</code></td><td>per-track aggregate: registrations, reimbursement, cost ranges, <code>AccessPathway</code>. Stale-cost warning &gt; 180 days.</td></tr>
            <tr><td><code>experimental_options</code></td><td>third track — <code>enumerate_experimental_options()</code> queries ClinicalTrials.gov v2. 7-day TTL cache.</td></tr>
            <tr><td><code>actionability_hits</code></td><td>CIViC matches with ESCAT-primary + variant, evidence rating, clinical significance, source citations</td></tr>
            <tr><td><code>fda_compliance</code></td><td>FDA Criterion 4 fields: intended_use, patient_population_match, algorithm_summary, automation_bias_warning</td></tr>
            <tr><td><code>trace</code></td><td>step-by-step walk_algorithm history: step / outcome / branch / fired_red_flags</td></tr>
            <tr><td><code>warnings</code></td><td>schema/ref errors, time_critical disqualifications, missing data hints, citation-guard warnings</td></tr>
            <tr><td><code>supersedes</code> / <code>superseded_by</code></td><td>version chain between plans for the same patient</td></tr>
          </tbody>
        </table>
        <p class="info-text">
          Optionally enabled: <strong>MDT brief</strong> — <code>orchestrate_mdt()</code> adds
          required/recommended/optional roles from {n_skills} virtual specialists + open questions + provenance graph.
        </p>
      </div>

      <div class="info-section">
        <h2>Plan updates — <code>revise_plan()</code></h2>
        <p class="info-text">
          Three legal transitions + one forbidden. The previous plan is not mutated — a deep copy
          is returned with <code>superseded_by</code> set. Per CHARTER §10.2, old versions persist indefinitely.
        </p>
        <table class="kv-table">
          <thead><tr><th>From</th><th>Change</th><th>Transition</th><th>Result</th></tr></thead>
          <tbody>
            <tr><td>DiagnosticPlan vN</td><td>suspicion only</td><td>diagnostic → diagnostic</td><td>DiagnosticPlan v(N+1)</td></tr>
            <tr><td>DiagnosticPlan vN</td><td>histology confirmed</td><td>diagnostic → treatment <strong>(promotion)</strong></td><td>Plan v1</td></tr>
            <tr><td>Plan vN</td><td>update with histology</td><td>treatment → treatment</td><td>Plan v(N+1)</td></tr>
            <tr><td>Plan vN</td><td>histology removed</td><td colspan="2"><span style="color:var(--red);font-weight:600;">ILLEGAL — ValueError, CHARTER §15.2 C7</span></td></tr>
          </tbody>
        </table>
      </div>

      <div class="callout callout-good">
        <strong>Privacy.</strong> Patient JSON never leaves the user's machine.
        No logs, no DB. Reproducibility:
        <code>Plan.knowledge_base_state.algorithm_version</code> records the KB version →
        same input + same KB = same output.
      </div>
    </section>

    <!-- TAB 4: LIMITS -->
    <section class="cap-panel" id="panel-limits" role="tabpanel">

      <div class="info-section">
        <h2>Open Questions — engine refuses to decide without data</h2>
        <p class="info-text">
          Instead of a silent default, the engine explicitly flags which fields are missing and
          which test or report is needed (MDT_ORCHESTRATOR_SPEC §3). Rendered into the Plan as a
          separate section, never hidden.
        </p>
        <table class="kv-table">
          <thead><tr><th>Code</th><th>Trigger</th><th>What the engine emits</th></tr></thead>
          <tbody>
            <tr><td><strong>Q1</strong></td><td>Histology not confirmed</td><td>«Treatment Plan generated against ICD-O-3 code only; confirm primary histology before therapy»</td></tr>
            <tr><td><strong>Q2</strong></td><td>Stage missing</td><td>«Lugano/Ann Arbor stage required for confident risk-stratification»</td></tr>
            <tr><td><strong>Q3</strong></td><td>RF clause incomplete</td><td>«Cytogenetic panel incomplete; high-risk status assessed with partial data»</td></tr>
            <tr><td><strong>Q4</strong></td><td>Biomarker missing</td><td>«IGHV mutation status + FISH del(17p) required to confirm 1L recommendation»</td></tr>
            <tr><td><strong>Q5</strong></td><td>Performance status missing</td><td>«ECOG required for transplant-eligibility assessment»; falls back to conservative default</td></tr>
            <tr><td><strong>Q6</strong></td><td>Drug not reimbursed</td><td>«D-VRd: daratumumab not currently reimbursed; verify funding pathway»</td></tr>
            <tr><td><strong>DQ1-4</strong></td><td>Diagnostic-mode: tissue / lineage / presentation / hypotheses missing</td><td>lowers workup match confidence; lineage_hint + tissue dominate</td></tr>
          </tbody>
        </table>
        <div class="callout">
          <strong>Why no silent default:</strong> CHARTER §15.2 C6 (anti automation-bias) —
          the engine cannot pretend to know when it doesn't.
        </div>
      </div>

      <div class="info-section">
        <h2>Personalization gaps — deliberate</h2>
        <p class="info-text">
          «Personalization» in OpenOnco is rule-based selection from a fixed catalog,
          not AI-generation. Deliberate architectural choice (CHARTER §8.3).
        </p>
        <div class="gap-grid">
          <div class="gap-card">
            <div class="gap-tag">Gap 1</div>
            <h3>No per-patient dose calculation</h3>
            <p>Regimen stores <strong>the standard dose</strong> (bortezomib 1.3 mg/m²), not multiplied by patient BSA, not adjusted automatically for CrCl 30. By design — to avoid FDA device classification.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 2</div>
            <h3>No response-adapted cycles</h3>
            <p>Regimen pins <code>total_cycles: 6 + 2 maintenance</code>. Not adapted automatically by response (PR vs CR after PET2). Re-staging via a separate <code>revise_plan</code>.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 3</div>
            <h3>Genomic matching limited to CIViC</h3>
            <p>Outside CIViC (rare, novel variants) emits a warning «no actionability evidence», without creative interpretations.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 4</div>
            <h3>SupportiveCare identical across cohort</h3>
            <p>PJP prophylaxis attached to D-VRd for everyone — the engine doesn't know alternatives (dapsone instead of bactrim). The clinician substitutes.</p>
          </div>
          <div class="gap-card">
            <div class="gap-tag">Gap 5</div>
            <h3>No cumulative-toxicity tracking</h3>
            <p>2L plan for a patient who got bortezomib in 1L with grade 2 neuropathy — the profile doesn't carry <code>prior_treatment_history</code> as a structured field; the clinician interprets manually.</p>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h2>CHARTER constraints — will not change</h2>
        <p class="info-text">
          Principled architectural decisions that gate FDA / clinical safety.
        </p>
        <div class="gap-grid">
          <div class="gap-card gap-hard">
            <div class="gap-tag">§8.3</div>
            <h3>LLM doesn't decide clinically</h3>
            <p>LLM only: boilerplate, doc drafts, extraction (with human verification), translation with clinical review. <strong>Not</strong>: regimen choice, doses, biomarker interpretation.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§15.2 C7</div>
            <h3>No histology — no Plan</h3>
            <p>Treatment Plan only if <code>disease.id</code> is confirmed. Otherwise DiagnosticPlan mode. <code>revise_plan</code> treatment → diagnostic is <strong>forbidden</strong>.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§15.2 C5</div>
            <h3>No time-critical</h3>
            <p>Not intended for emergency oncology (oncologic emergencies). Indication with <code>time_critical: true</code> → disqualification warning.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§6.1</div>
            <h3>Two-reviewer merge</h3>
            <p>Any change to clinical content needs 2 of 3 Clinical Co-Lead approvals. Without that — STUB.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§15.2 C6</div>
            <h3>Anti automation-bias</h3>
            <p>Always ≥2 tracks side-by-side. Alternative is never buried, never «click to expand». The clinician sees a choice, not a directive.</p>
          </div>
          <div class="gap-card gap-hard">
            <div class="gap-tag">§9.3</div>
            <h3>Patient data never in repo</h3>
            <p><code>patient_plans/</code> gitignored. Site shows only synthetic examples. Telemetry forbidden without explicit consent.</p>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h2>Never list — what the engine never does</h2>
        <div class="gap-grid">
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Hide the alternative track</h3><p>Both recommendations are always shown. The UI has no «expand to see alternative» pattern.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Generate Indication via LLM</h3><p>Everything from the curated KB. No matching Indication → warning, not «creative invention».</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Modify doses</h3><p>Doses come from the standard NCCN/ESMO. Adjustments only via explicit <code>dose_modification_rules</code>.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Judge «which is better»</h3><p>The algorithm picks a default but doesn't claim it's superior. The clinician has full autonomy — automation_bias_warning.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Interpret imaging</h3><p>«Bulky disease» arrives as a structured field, not from image analysis. Image analysis = device classification.</p></div>
          <div class="gap-card gap-hard"><div class="gap-tag">Never</div><h3>Cohort matching</h3><p>«N patients chose X in M% of cases» — requires a persisted patient registry + privacy review. Not yet.</p></div>
        </div>
      </div>

      <div class="info-section">
        <h2>Current coverage — STUB status and gaps</h2>
        <table class="kv-table">
          <thead><tr><th>Category</th><th>State</th><th>Meaning</th></tr></thead>
          <tbody>
            <tr><td>Diseases with full chain</td><td>{diseases_full} / {n_diseases}</td><td>The rest are partially modeled</td></tr>
            <tr><td>Indications 1L</td><td>{n_inds_1l}</td><td>First line for all {n_diseases} diseases</td></tr>
            <tr><td>Indications 2L+</td><td>{n_inds_2l}</td><td>{n_dis_2l_heme} heme + {n_dis_2l_solid} solid. Other solid 2L+ partial.</td></tr>
            <tr><td>Pediatric oncology</td><td>0</td><td>Out of MVP scope — separate track</td></tr>
            <tr><td>Radiation therapy</td><td>partial</td><td>RT in multimodal Indications; not modeled as a standalone entity</td></tr>
            <tr><td>Surgery</td><td>not modeled</td><td>Surgical oncology indications absent</td></tr>
            <tr><td>Formulary live-feed</td><td>static flag</td><td>Hard-coded on regimens; not auto-refreshed</td></tr>
            <tr><td>Reviewer dual sign-off</td><td><strong>{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</strong></td><td>Primary bottleneck metric — capacity plan: {stats.reviewer_signoffs_total} → ≥85% verified</td></tr>
            <tr><td>Live gap dashboard</td><td><a href="/clinical-gaps.html">→ link</a></td><td>Build-generated audit (sign-off, solid 2L+, surgery, RT, supportive care)</td></tr>
          </tbody>
        </table>
        <div class="callout">
          <strong>What STUB does NOT mean:</strong> structured data + algorithm + sources are already in place.
          What STUB means: didn't pass Clinical Co-Lead dual sign-off. «Proposed plan», not «approved plan».
        </div>
      </div>

      <div class="info-section">
        <h2>Clinician workflow</h2>
        <p class="info-text">
          The engine prepares for a tumor board, it does not replace one. The clinician:
          <strong>1)</strong> verifies sources (every claim cited, guard already dropped uncited cells) →
          <strong>2)</strong> closes Open Questions (orders tests, calls <code>revise_plan</code>) →
          <strong>3)</strong> adapts to the patient (doses, supportive care, regional availability) →
          <strong>4)</strong> discusses at the tumor board (MDT brief — structured agenda).
          Engine: draft. Clinician: final.
        </p>
      </div>
    </section>

    <!-- TAB 5: CONTRIBUTE -->
    <section class="cap-panel" id="panel-contribute" role="tabpanel">

      <div class="info-section">
        <h2>TaskTorrent — verify algorithms with your AI's tokens</h2>
        <p class="info-text">
          The biggest gap — <strong>{stats.reviewer_signoffs_reviewed}/{stats.reviewer_signoffs_total}</strong> dual-reviewer sign-off.
          The bottleneck doesn't dissolve with new code — it dissolves through contributors with AI tools
          who pick up structured chunks of work.
        </p>
        <div class="num-grid num-grid--rich">
          <div class="num-card num-card--accent">
            <div class="num-big">1</div>
            <div class="num-lbl">What it is</div>
            <p class="num-text">
              A maintainer publishes a «chunk» — one self-contained task (~100k–300k tokens):
              «reverify BMA evidence for DLBCL × 17 entities» or «backfill source-license for 8 sources».
              A contributor claims the chunk, AI executes, PR opens.
            </p>
          </div>
          <div class="num-card">
            <div class="num-big">2</div>
            <div class="num-lbl">What you need</div>
            <p class="num-text">
              An AI tool with a token budget (Claude Code Pro+, Codex, Cursor, ChatGPT with web). GitHub + <code>gh</code> CLI.
              Python 3.10+. ~1-3 hours of your time. <strong>No clinical expertise required</strong> —
              you trigger structured drafting; the clinical co-leads sign off.
            </p>
          </div>
          <div class="num-card">
            <div class="num-big">3</div>
            <div class="num-lbl">8-line bootstrap</div>
            <p class="num-text">
              Copy the 8-line prompt from
              <a href="https://github.com/{GH_REPO}/blob/master/docs/contributing/CONTRIBUTOR_QUICKSTART.md" target="_blank" rel="noopener"><code>CONTRIBUTOR_QUICKSTART.md</code></a>
              into your AI agent. It finds an available chunk, claims it, runs the work, runs the validator, opens a PR.
            </p>
          </div>
          <div class="num-card num-card--accent">
            <div class="num-big">4</div>
            <div class="num-lbl">What happens to the PR</div>
            <p class="num-text">
              The maintainer checks the mechanical part (validator, schema). A Clinical Co-Lead does a
              sample review of the semantic part (CHARTER §6.1). Merge → sidecar landing → upsert into
              hosted KB → render. Attribution recorded in <code>_contribution_meta.yaml</code>.
            </p>
          </div>
        </div>
        <div class="cta-row" style="margin-top:24px;">
          <a class="btn btn-primary" href="https://github.com/{GH_REPO}/blob/master/docs/contributing/CONTRIBUTOR_QUICKSTART.md" target="_blank" rel="noopener">Contributor Quickstart →</a>
          <a class="btn btn-secondary" href="https://github.com/{GH_REPO}/issues?q=is%3Aissue+is%3Aopen+label%3Achunk-task+label%3Astatus-active" target="_blank" rel="noopener">Active chunks →</a>
        </div>
        <div class="callout callout-good" style="margin-top:18px;">
          <strong>Impact.</strong> Every verified BMA is one actionability claim we can render as
          «approved» instead of «STUB». One contributor with Pro+ tokens in an evening can push
          10-20 BMAs through signoff prep — about a week of work for one person under any other model.
        </div>
      </div>

      <div class="info-section">
        <h2>Recent activity</h2>
        <p class="info-text">
          Over the last 4 days TaskTorrent saw <strong>7 waves</strong>, dozens of chunks,
          ~73 BMA candidates, 23 BMA drafts ready for clinical signoff, 53 source stubs,
          1,251 UA-language fields drafted. Recent structural updates:
        </p>
        <ul style="font-size:14px; line-height:1.65; color:var(--gray-700);">
          <li><strong>CIViC pivot</strong> — engine + 29 BIO + 399 BMA YAMLs migrated off OncoKB schema; monthly snapshot refresh CI.</li>
          <li><strong>Multi-phase regimens (PR1-3)</strong> — <code>Regimen.phases</code>, <code>bridging_options</code>, phases-aware render, back-compat auto-wrap.</li>
          <li><strong>Citation guard L3</strong> — render-time check on every BMA cell.</li>
          <li><strong>Coverage matrix</strong> — <a href="/diseases.html">/diseases.html</a> per-disease drill-down.</li>
          <li><strong>586 cases in gallery</strong> — Phase 2 chunked feat: ~60 new hand-curated in 4 days.</li>
        </ul>
      </div>
    </section>

  </section>

  <footer class="page-foot">
    Open-source · MIT-style usage · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    <br>
    No real patient data · CHARTER §9.3.
    Information tool for clinicians, not a medical device (CHARTER §15 + §11).
  </footer>
</main>

<script>
  (function() {{
    var tabs = document.querySelectorAll('.cap-tab');
    var panels = document.querySelectorAll('.cap-panel');

    function activate(name) {{
      tabs.forEach(function(t) {{
        var on = t.dataset.tab === name;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
      }});
      panels.forEach(function(p) {{
        p.classList.toggle('is-active', p.id === 'panel-' + name);
      }});
    }}

    tabs.forEach(function(tab) {{
      tab.addEventListener('click', function() {{
        var name = tab.dataset.tab;
        activate(name);
        if (history.replaceState) {{
          history.replaceState(null, '', '#' + name);
        }}
      }});
    }});

    var hash = (window.location.hash || '').replace('#', '');
    if (hash && document.getElementById('panel-' + hash)) {{
      activate(hash);
    }}
  }})();
</script>
</body>
</html>
"""


def _build_disease_coverage_rows() -> list[dict]:
    """Bridge to scripts/disease_coverage_matrix.py — re-uses its
    per_disease_metrics walker so the page + the JSON snapshot + the
    plan markdown all share one source of truth."""
    from scripts.disease_coverage_matrix import per_disease_metrics
    return per_disease_metrics(REPO_ROOT / "knowledge_base" / "hosted" / "content")


_DISEASES_PAGE_LABELS = {
    "uk": {
        "title": "Хвороби · OpenOnco",
        "h1": "Хвороби в Onco Wiki",
        "lead": (
            "Покриття OpenOnco за {n} онкологічними діагнозами: біомаркери, "
            "препарати, показання, режими, тривожні ознаки, алгоритми та "
            "практична наповненість бази знань."
        ),
        "sum_diseases": "Усього діагнозів",
        "sum_avg_fill": "Сер. наповненість",
        "sum_algo_1l": "З 1L алгоритмом",
        "sum_algo_2l": "З 2L+ алгоритмом",
        "fam_lymphoid": "Лімфоїдна гематологія",
        "fam_myeloid": "Мієлоїдна гематологія",
        "fam_solid": "Солідні пухлини",
        "th_disease": "Хвороба", "th_icd": "ICD-10",
        "th_bio": "Біомарк.", "th_drug": "Преп.",
        "th_ind": "Показ.", "th_reg": "Режими", "th_rf": "Трив. озн.",
        "th_1l": "1L", "th_2l": "2L+", "th_quest": "Опитувальник",
        "th_fill": "Наповн.", "th_ver": "Вериф.",
        "yes": "✓", "no": "—",
        "metrics_title": "Позначення в таблиці",
        "search_placeholder": "Шукати хворобу або ICD-10 код…",
        "search_empty": "Жодна хвороба не підходить під запит.",
        "metrics": [
            "<b>Біомаркери / Препарати</b> — кількість унікальних сутностей, які використовуються у правилах цієї хвороби.",
            "<b>Показання / Режими / Тривожні ознаки</b> — кількість відповідних записів у базі знань.",
            "<b>1L / 2L+</b> — наявність алгоритму для першої або другої й наступних ліній лікування.",
            "<b>Опитувальник</b> — ✓ якщо для хвороби є ручний клінічний опитувальник; — якщо його ще немає.",
            "<b>Наповненість</b> — зведена оцінка за ключовими типами сутностей: показання, режими, біомаркери, препарати, тривожні ознаки, алгоритм, опитувальник і workup.",
            "<b>Верифікація</b> — частка показань із достатньою кількістю клінічних sign-off за правилами проєкту.",
        ],
        "verified_note": "",
        "table_title": "Покриття за хворобами",
        "avg_label": "середнє",
        "footer_data": "Дані оновлюються при кожному build_site.py запуску. JSON snapshot:",
    },
    "en": {
        "title": "Diseases · OpenOnco",
        "h1": "Diseases in Onco Wiki",
        "lead": (
            "OpenOnco coverage across {n} oncology diagnoses: biomarkers, "
            "drugs, indications/regimens/RedFlags, algorithm and questionnaire "
            "presence, % fill and % Clinical Co-Lead verification."
        ),
        "sum_diseases": "Total diseases",
        "sum_avg_fill": "Avg fill",
        "sum_avg_ver": "Avg verified",
        "sum_with_signed": "With ≥1 verified indication",
        "sum_quest_real": "Hand-authored questionnaires",
        "sum_quest_stub": "STUB questionnaires",
        "sum_algo_1l": "With 1L algorithm",
        "sum_algo_2l": "With 2L+ algorithm",
        "fam_lymphoid": "Lymphoid hematologic",
        "fam_myeloid": "Myeloid hematologic",
        "fam_solid": "Solid tumors",
        "th_disease": "Disease", "th_icd": "ICD-10",
        "th_bio": "Bio", "th_drug": "Drug",
        "th_ind": "Ind", "th_reg": "Reg", "th_rf": "RF",
        "th_1l": "1L", "th_2l": "2L", "th_quest": "Quest",
        "th_fill": "Fill %", "th_ver": "Ver %",
        "yes": "✓", "no": "—",
        "metrics_title": "Metric definitions",
        "search_placeholder": "Search disease or ICD-10 code…",
        "search_empty": "No diseases match your search.",
        "metrics": [
            "<b>#Bio</b> — distinct biomarkers referenced by this disease's Indications + Regimens",
            "<b>#Drug</b> — distinct drugs in this disease's regimens",
            "<b>#Ind / #Reg / #RF</b> — Indications / Regimens / RedFlags for this disease",
            "<b>1L / 2L</b> — Algorithm presence for first-line / second-line+",
            "<b>Quest</b> — ✓ hand-authored / STUB auto-generated / — absent",
            "<b>Fill %</b> — composite over 8 entity types: ≥1 indication, ≥1 regimen, ≥1 biomarker, ≥1 drug, ≥1 redflag, 1L algo, questionnaire, workup",
            "<b>Ver %</b> — % of this disease's indications with reviewer_signoffs ≥ 2 (CHARTER §6.1)",
        ],
        "verified_note": (
            "<b>Ver % is mostly 0%</b> — dev-mode signoff exemption "
            "(<code>project_charter_dev_mode_exemptions</code>) is in effect "
            "until Clinical Co-Leads are appointed. This is intentional, not a bug."
        ),
        "table_title": "Disease coverage",
        "avg_label": "avg",
        "footer_data": "Data refreshes on every build_site.py run. JSON snapshot:",
    },
}


_DISEASE_UK_NAMES = {
    "DIS-AITL": "Ангіоімунобластна Т-клітинна лімфома",
    "DIS-ALCL": "Системна анапластична великоклітинна лімфома",
    "DIS-AML": "Гострий мієлоїдний лейкоз",
    "DIS-ANAL-SCC": "Плоскоклітинний рак анального каналу",
    "DIS-APL": "Гострий промієлоцитарний лейкоз",
    "DIS-ATLL": "Лейкоз/лімфома дорослих Т-клітин",
    "DIS-B-ALL": "B-лімфобластний лейкоз/лімфома",
    "DIS-BCC": "Базальноклітинна карцинома",
    "DIS-BREAST": "Інвазивний рак молочної залози",
    "DIS-BURKITT": "Лімфома Беркітта",
    "DIS-CERVICAL": "Рак шийки матки",
    "DIS-CHL": "Класична лімфома Годжкіна",
    "DIS-CHOLANGIOCARCINOMA": "Холангіокарцинома",
    "DIS-CHONDROSARCOMA": "Хондросаркома",
    "DIS-CLL": "Хронічний лімфоцитарний лейкоз / мала лімфоцитарна лімфома",
    "DIS-CML": "Хронічний мієлоїдний лейкоз",
    "DIS-CRC": "Колоректальна карцинома",
    "DIS-DLBCL-NOS": "Дифузна великоклітинна B-клітинна лімфома, NOS",
    "DIS-EATL": "Ентеропатій-асоційована Т-клітинна лімфома",
    "DIS-ENDOMETRIAL": "Рак ендометрія",
    "DIS-EPITHELIOID-SARCOMA": "Епітеліоїдна саркома",
    "DIS-ESOPHAGEAL": "Рак стравоходу",
    "DIS-ET": "Есенціальна тромбоцитемія",
    "DIS-FL": "Фолікулярна лімфома",
    "DIS-GASTRIC": "Аденокарцинома шлунка та гастроезофагеального переходу",
    "DIS-GBM": "Гліобластома",
    "DIS-GI-NET": "Нейроендокринна пухлина ШКТ",
    "DIS-GIST": "Гастроінтестинальна стромальна пухлина",
    "DIS-GLIOMA-LOW-GRADE": "Гліома низького ступеня злоякісності",
    "DIS-GRANULOSA-CELL": "Гранульозоклітинна пухлина яєчника дорослого типу",
    "DIS-HCC": "Гепатоцелюлярна карцинома",
    "DIS-HCL": "Волосатоклітинний лейкоз",
    "DIS-HCV-MZL": "HCV-асоційована лімфома маргінальної зони",
    "DIS-HGBL-DH": "Високозлоякісна B-клітинна лімфома з double-hit / triple-hit",
    "DIS-HNSCC": "Плоскоклітинний рак голови та шиї",
    "DIS-HSTCL": "Гепатоспленічна Т-клітинна лімфома",
    "DIS-IFS": "Інфантильна фібросаркома",
    "DIS-IMT": "Запальна міофібробластична пухлина",
    "DIS-JMML": "Ювенільний мієломоноцитарний лейкоз",
    "DIS-LAM": "Лімфангіолейоміоматоз",
    "DIS-MASTOCYTOSIS": "Просунутий системний мастоцитоз",
    "DIS-MCL": "Мантійноклітинна лімфома",
    "DIS-MDS-HR": "Мієлодиспластичні синдроми високого ризику",
    "DIS-MDS-LR": "Мієлодиспластичні синдроми низького ризику",
    "DIS-MELANOMA": "Меланома шкіри",
    "DIS-MENINGIOMA": "Менінгіома",
    "DIS-MESOTHELIOMA": "Злоякісна мезотеліома",
    "DIS-MF-SEZARY": "Грибоподібний мікоз / синдром Сезарі",
    "DIS-MM": "Множинна мієлома",
    "DIS-MPNST": "Злоякісна пухлина оболонки периферичного нерва",
    "DIS-MTC": "Медулярна карцинома щитоподібної залози",
    "DIS-NK-T-NASAL": "Екстранодальна NK/T-клітинна лімфома, назальний тип",
    "DIS-NLPBL": "Нодулярна лімфоцитарно-переважна B-клітинна лімфома",
    "DIS-NODAL-MZL": "Нодальна лімфома маргінальної зони",
    "DIS-NSCLC": "Недрібноклітинний рак легені",
    "DIS-OVARIAN": "Рак яєчника",
    "DIS-PCNSL": "Первинна лімфома ЦНС",
    "DIS-PDAC": "Протокова аденокарцинома підшлункової залози",
    "DIS-PMBCL": "Первинна медіастинальна великоклітинна B-клітинна лімфома",
    "DIS-PMF": "Первинний мієлофіброз",
    "DIS-PNET": "Нейроендокринна пухлина підшлункової залози",
    "DIS-PROSTATE": "Аденокарцинома передміхурової залози",
    "DIS-PTCL-NOS": "Периферична Т-клітинна лімфома, NOS",
    "DIS-PTLD": "Посттрансплантаційне лімфопроліферативне захворювання",
    "DIS-PV": "Справжня поліцитемія",
    "DIS-RCC": "Нирковоклітинна карцинома",
    "DIS-SALIVARY": "Карцинома слинних залоз",
    "DIS-SCLC": "Дрібноклітинний рак легені",
    "DIS-SOFT-TISSUE-SARCOMA": "Саркома м'яких тканин",
    "DIS-SPLENIC-MZL": "Селезінкова лімфома маргінальної зони",
    "DIS-T-ALL": "T-лімфобластний лейкоз/лімфома",
    "DIS-T-PLL": "T-клітинний пролімфоцитарний лейкоз",
    "DIS-TESTICULAR-GCT": "Герміногенна пухлина яєчка",
    "DIS-TGCT": "Теносиновіальна гігантоклітинна пухлина",
    "DIS-THYROID-ANAPLASTIC": "Анапластична карцинома щитоподібної залози",
    "DIS-THYROID-PAPILLARY": "Папілярна карцинома щитоподібної залози",
    "DIS-UROTHELIAL": "Уротеліальна карцинома",
    "DIS-WM": "Макроглобулінемія Вальденстрема / лімфоплазмоцитарна лімфома",
}


def _disease_display_name(r: dict, target_lang: str) -> str:
    if target_lang == "uk":
        return _DISEASE_UK_NAMES.get(r["id"], r["name"] or "")
    return r["name"] or ""


def _disease_row_html(r: dict, lbl: dict, target_lang: str) -> str:
    yes, no = lbl["yes"], lbl["no"]
    algo_1l = yes if r["algo_1l"] else no
    algo_2l = yes if r["algo_2l"] else no
    has_real_questionnaire = r["has_quest"] and not r["is_stub_quest"]
    quest = yes if has_real_questionnaire else no
    fill_class = "fill-high" if r["fill_pct"] >= 75 else ("fill-mid" if r["fill_pct"] >= 50 else "fill-low")
    ver_class = "ver-high" if r["verified_pct"] >= 60 else ("ver-mid" if r["verified_pct"] >= 1 else "ver-low")
    short_id = r["id"].replace("DIS-", "")
    display_name = _disease_display_name(r, target_lang)
    name = display_name[:64]
    search_blob = " ".join(
        str(part) for part in (r.get("id"), display_name, r.get("name"), r.get("family"), r.get("icd10"))
        if part
    ).lower()
    return (
        f'<tr id="{html.escape(r["id"])}" data-search="{html.escape(search_blob)}">'
        f'<td><strong>{html.escape(short_id)}</strong> <span class="dis-name">{html.escape(name)}</span></td>'
        f'<td class="mono">{html.escape(r["icd10"] or "")}</td>'
        f'<td class="num">{r["n_bios"]}</td>'
        f'<td class="num">{r["n_drugs"]}</td>'
        f'<td class="num">{r["n_inds"]}</td>'
        f'<td class="num">{r["n_regs"]}</td>'
        f'<td class="num">{r["n_rfs"]}</td>'
        f'<td class="ck">{algo_1l}</td>'
        f'<td class="ck">{algo_2l}</td>'
        f'<td class="ck quest-cell quest-{("real" if has_real_questionnaire else "none")}">{quest}</td>'
        f'<td class="num pct {fill_class}"><strong>{r["fill_pct"]}%</strong></td>'
        f'<td class="num pct {ver_class}">{r["verified_pct"]}%</td>'
        '</tr>'
    )



def render_diseases(stats, *, target_lang: str = "en") -> str:
    """Per-disease coverage page. Pulls live metrics from
    disease_coverage_matrix.per_disease_metrics so this page is the
    canonical UI surface for the same data exported as
    /disease_coverage.json."""
    import html as _html
    rows = _build_disease_coverage_rows()
    lbl = _DISEASES_PAGE_LABELS.get(target_lang, _DISEASES_PAGE_LABELS["en"])

    n = len(rows)
    avg_fill = round(sum(r["fill_pct"] for r in rows) / max(1, n), 1)
    n_algo_1l = sum(1 for r in rows if r["algo_1l"])
    n_algo_2l = sum(1 for r in rows if r["algo_2l"])
    lead_text = lbl["lead"].format(n=n)

    # Group by family
    by_family: dict[str, list[dict]] = {
        "Лімфоїдна гематологія": [],
        "Мієлоїдна гематологія": [],
        "Солідні пухлини": [],
    }
    for r in rows:
        by_family.setdefault(r["family"], []).append(r)

    fam_label_map = {
        "Лімфоїдна гематологія": lbl["fam_lymphoid"],
        "Мієлоїдна гематологія": lbl["fam_myeloid"],
        "Солідні пухлини": lbl["fam_solid"],
    }

    family_blocks: list[str] = []
    for fam_key in ("Лімфоїдна гематологія", "Мієлоїдна гематологія", "Солідні пухлини"):
        flist = by_family.get(fam_key) or []
        if not flist:
            continue
        flist_sorted = sorted(flist, key=lambda x: (-x["fill_pct"], _disease_display_name(x, target_lang)))
        rows_html = "\n".join(_disease_row_html(r, lbl, target_lang) for r in flist_sorted)
        f_fill = round(sum(r["fill_pct"] for r in flist) / max(1, len(flist)), 1)
        f_ver = round(sum(r["verified_pct"] for r in flist) / max(1, len(flist)), 1)
        family_blocks.append(f"""
<section class="dis-family">
  <h2>{fam_label_map[fam_key]} <span class="fam-count">({len(flist)})</span></h2>
  <table class="dis-table">
    <thead><tr>
      <th class="th-disease">{lbl["th_disease"]}</th>
      <th>{lbl["th_icd"]}</th>
      <th class="th-num">{lbl["th_bio"]}</th>
      <th class="th-num">{lbl["th_drug"]}</th>
      <th class="th-num">{lbl["th_ind"]}</th>
      <th class="th-num">{lbl["th_reg"]}</th>
      <th class="th-num">{lbl["th_rf"]}</th>
      <th class="th-ck">{lbl["th_1l"]}</th>
      <th class="th-ck">{lbl["th_2l"]}</th>
      <th class="th-ck">{lbl["th_quest"]}</th>
      <th class="th-num">{lbl["th_fill"]}</th>
      <th class="th-num">{lbl["th_ver"]}</th>
    </tr></thead>
    <tbody>
{rows_html}
    </tbody>
    <tfoot><tr>
      <td colspan="10"><em>{lbl.get("avg_label", "avg")}</em></td>
      <td class="num pct"><em>{f_fill}%</em></td>
      <td class="num pct"><em>{f_ver}%</em></td>
    </tr></tfoot>
  </table>
</section>
""")

    metrics_li = "\n".join(f"<li>{m}</li>" for m in lbl["metrics"])
    verified_note = lbl.get("verified_note") or ""
    verified_note_html = f'<div class="verified-note">{verified_note}</div>' if verified_note else ""

    top_bar = _render_top_bar(
        active="diseases", target_lang=target_lang,
        lang_switch_href=_lang_switch_href("diseases", target_lang),
    )

    return f"""<!DOCTYPE html>
<html lang="{target_lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html.escape(lbl['title'])}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link href="/style.css" rel="stylesheet">
<style>
.dis-summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0 24px; }}
.dis-summary .card {{ background: var(--gray-50); border-left: 3px solid var(--green-600); padding: 10px 14px; border-radius: 4px; }}
.dis-summary .card .v {{ font-family: var(--font-display); font-size: 22px; color: var(--green-800); }}
.dis-summary .card .k {{ font-size: 12px; color: var(--gray-500); text-transform: uppercase; letter-spacing: 0.5px; }}
.dis-matrix-search {{ margin: 2px 0 18px; max-width: 680px; }}
.dis-family {{ margin: 28px 0; }}
.dis-family h2 {{ margin-bottom: 8px; }}
.dis-family .fam-count {{ font-size: 14px; color: var(--gray-500); font-weight: normal; }}
.dis-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.dis-table th {{ background: var(--green-700); color: white; padding: 6px 8px; text-align: left; font-weight: 600; font-size: 11px; text-transform: none; letter-spacing: 0; line-height: 1.15; }}
.dis-table td {{ padding: 6px 8px; border-bottom: 1px solid var(--gray-100); vertical-align: top; }}
.dis-table tr:nth-child(even) td {{ background: var(--gray-50); }}
.dis-table tfoot td {{ background: var(--gray-100); font-style: italic; color: var(--gray-700); }}
.dis-table .num {{ text-align: right; font-family: var(--font-mono); }}
.dis-table .ck {{ text-align: center; }}
.dis-table .mono {{ font-family: var(--font-mono); font-size: 11px; color: var(--gray-500); }}
.dis-table .dis-name {{ color: var(--gray-700); font-weight: normal; }}
.dis-table .pct {{ font-weight: 600; }}
.dis-table .pct.fill-high {{ color: #166534; }}
.dis-table .pct.fill-mid {{ color: #b45309; }}
.dis-table .pct.fill-low {{ color: #991b1b; }}
.dis-table .pct.ver-high {{ color: #166534; background: #ecfdf5; }}
.dis-table .pct.ver-mid {{ color: #b45309; }}
.dis-table .pct.ver-low {{ color: var(--gray-500); }}
.quest-cell.quest-real {{ color: #166534; font-weight: 600; }}
.quest-cell.quest-none {{ color: var(--gray-500); }}
.dis-metrics {{ background: var(--gray-50); padding: 16px 20px; border-radius: 6px; margin: 18px 0 24px; font-size: 13px; }}
.dis-metrics ul {{ padding-left: 20px; line-height: 1.7; }}
.dis-metrics .verified-note {{ background: #fef3c7; border-left: 3px solid #d97706; padding: 10px 14px; margin-top: 12px; border-radius: 4px; color: #92400e; }}
.dis-table-title {{ margin-top: 26px; }}
.dis-footer-data {{ font-size: 12px; color: var(--gray-500); margin-top: 20px; }}
.dis-footer-data a {{ font-family: var(--font-mono); }}
@media (max-width: 800px) {{ .dis-summary {{ grid-template-columns: repeat(2, 1fr); }} .dis-table {{ font-size: 11px; }} }}
</style>
</head>
<body>
{top_bar}
<main>
  <section class="info-page">
    <h1>{_html.escape(lbl['h1'])}</h1>
    <p class="lead">{_html.escape(lead_text)}</p>

    <div class="dis-metrics">
      <h3>{lbl['metrics_title']}</h3>
      <ul>
        {metrics_li}
      </ul>
      {verified_note_html}
    </div>

    <div class="dis-summary">
      <div class="card"><div class="k">{lbl['sum_diseases']}</div><div class="v">{n}</div></div>
      <div class="card"><div class="k">{lbl['sum_avg_fill']}</div><div class="v">{avg_fill}%</div></div>
      <div class="card"><div class="k">{lbl['sum_algo_1l']}</div><div class="v">{n_algo_1l}/{n}</div></div>
      <div class="card"><div class="k">{lbl['sum_algo_2l']}</div><div class="v">{n_algo_2l}/{n}</div></div>
    </div>

    <div class="disease-search-row dis-matrix-search">
      <input type="search" id="matrixSearch" class="disease-search"
             placeholder="{_html.escape(lbl['search_placeholder'])}" autocomplete="off"
             aria-label="{_html.escape(lbl['search_placeholder'])}">
      <span class="disease-search-count" id="matrixSearchCount">{n}</span>
    </div>
    <p class="disease-empty" id="matrixEmpty" hidden>{_html.escape(lbl['search_empty'])}</p>

    <h2 class="dis-table-title">{lbl.get('table_title', 'Disease coverage')}</h2>
    {''.join(family_blocks)}

    <p class="dis-footer-data">{lbl['footer_data']} <a href="/disease_coverage.json">/disease_coverage.json</a></p>
  </section>
</main>
<script>
(function() {{
  var input = document.getElementById("matrixSearch");
  if (!input) return;
  var families = Array.prototype.slice.call(document.querySelectorAll(".dis-family"));
  var count = document.getElementById("matrixSearchCount");
  var empty = document.getElementById("matrixEmpty");

  function applySearch() {{
    var q = (input.value || "").trim().toLowerCase();
    var visible = 0;
    families.forEach(function(section) {{
      var sectionVisible = 0;
      var rows = Array.prototype.slice.call(section.querySelectorAll("tbody tr"));
      rows.forEach(function(row) {{
        var blob = row.dataset.search || "";
        var match = !q || blob.indexOf(q) !== -1;
        row.style.display = match ? "" : "none";
        if (match) sectionVisible++;
      }});
      section.hidden = sectionVisible === 0;
      visible += sectionVisible;
    }});
    count.textContent = visible;
    empty.hidden = visible !== 0;
  }}

  input.addEventListener("input", applySearch);
  applySearch();
}})();
</script>
</body>
</html>
"""


def bundle_disease_coverage(output_dir: Path) -> dict:
    """Write JSON snapshot of per-disease coverage for CI / external tooling.
    Same source data as the /diseases.html page."""
    rows = _build_disease_coverage_rows()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_diseases": len(rows),
        "rows": rows,
    }
    out = output_dir / "disease_coverage.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": "disease_coverage.json", "count": len(rows)}


# ── Specs page ────────────────────────────────────────────────────────────


_SPECS_CATALOG: list[dict] = [
    {
        "id": "CHARTER",
        "file": "CHARTER.md",
        "tag": "governance",
        "title_uk": "Charter та Governance",
        "title_en": "Charter & Governance",
        "summary_uk": (
            "Управління проектом, scope (що проект робить і чого не робить), "
            "FDA non-device CDS positioning (§15 з constraints C1-C7), two-reviewer rule "
            "для clinical content (§6.1), patient-data privacy (§9.3), forbidden prompt "
            "patterns для LLM (§8.3 — LLM не приймає клінічні рішення)."
        ),
        "summary_en": (
            "Project governance, scope (what it does and what it explicitly does not), "
            "FDA non-device CDS positioning (§15 with constraints C1-C7), the two-reviewer "
            "rule for clinical content (§6.1), patient-data privacy (§9.3), forbidden "
            "prompt patterns for LLMs (§8.3 — LLMs do not make clinical decisions)."
        ),
    },
    {
        "id": "CLINICAL_CONTENT_STANDARDS",
        "file": "CLINICAL_CONTENT_STANDARDS.md",
        "tag": "clinical",
        "title_uk": "Clinical Content Standards",
        "title_en": "Clinical Content Standards",
        "summary_uk": (
            "Стандарти клінічного контенту: citation format (source_id + position + "
            "paraphrase + page), evidence-level taxonomy (Tier 1-6), reviewer signoff "
            "workflow, STUB → reviewed transition criteria. Кожна claim у Indication / "
            "Regimen / RedFlag має посилання на Source entity."
        ),
        "summary_en": (
            "Clinical content standards: citation format (source_id + position + "
            "paraphrase + page), evidence-level taxonomy (Tier 1-6), reviewer sign-off "
            "workflow, STUB → reviewed transition criteria. Every claim in an Indication / "
            "Regimen / RedFlag links to a Source entity."
        ),
    },
    {
        "id": "DATA_STANDARDS",
        "file": "DATA_STANDARDS.md",
        "tag": "data",
        "title_uk": "Data Standards — Patient Model",
        "title_en": "Data Standards — Patient Model",
        "summary_uk": (
            "Patient profile data model. FHIR R4/R5 + mCODE alignment у плані. "
            "Кодові системи: LOINC + ICD-10/O-3 + RxNorm + CTCAE v5.0. Без SNOMED CT, "
            "без MedDRA у MVP (license gates). Поля профілю та semantic interoperability."
        ),
        "summary_en": (
            "Patient profile data model. FHIR R4/R5 + mCODE alignment on the roadmap. "
            "Code systems: LOINC + ICD-10/O-3 + RxNorm + CTCAE v5.0. No SNOMED CT and no "
            "MedDRA in the MVP (license gates). Profile fields and semantic interoperability."
        ),
    },
    {
        "id": "KNOWLEDGE_SCHEMA_SPECIFICATION",
        "file": "KNOWLEDGE_SCHEMA_SPECIFICATION.md",
        "tag": "schema",
        "title_uk": "Knowledge Schema Specification",
        "title_en": "Knowledge Schema Specification",
        "summary_uk": (
            "Pydantic schemas всіх KB entities — Disease / Indication / Regimen / "
            "Algorithm / Biomarker / Drug / Test / Workup / RedFlag / Contraindication / "
            "MonitoringSchedule / SupportiveCare / Source. Defines fields, validators, "
            "referential integrity rules, migration roadmap до PostgreSQL."
        ),
        "summary_en": (
            "Pydantic schemas for every KB entity — Disease / Indication / Regimen / "
            "Algorithm / Biomarker / Drug / Test / Workup / RedFlag / Contraindication / "
            "MonitoringSchedule / SupportiveCare / Source. Defines fields, validators, "
            "referential-integrity rules, and the migration roadmap to PostgreSQL."
        ),
    },
    {
        "id": "SOURCE_INGESTION_SPEC",
        "file": "SOURCE_INGESTION_SPEC.md",
        "tag": "sources",
        "title_uk": "Source Ingestion & Licensing",
        "title_en": "Source Ingestion & Licensing",
        "summary_uk": (
            "Як інгестимо джерела: hosting matrix (referenced vs hosted vs mixed) з H1-H5 "
            "justification, license classification gates, add-a-source checklist (§8), "
            "hosted-source checklist (§20), SourceClient protocol для live APIs."
        ),
        "summary_en": (
            "How we ingest sources: the hosting matrix (referenced vs hosted vs mixed) with "
            "H1-H5 justification, license-classification gates, the add-a-source checklist "
            "(§8), the hosted-source checklist (§20), and the SourceClient protocol for "
            "live APIs."
        ),
    },
    {
        "id": "REFERENCE_CASE_SPECIFICATION",
        "file": "REFERENCE_CASE_SPECIFICATION.md",
        "tag": "testing",
        "title_uk": "Reference Case — \"Patient Zero\"",
        "title_en": "Reference Case — \"Patient Zero\"",
        "summary_uk": (
            "Synthetic HCV-MZL reference case як P0 acceptance test. Defines всі required "
            "fields у patient profile (§2 templates), critical structural assertions для "
            "Plan render output (§1.3), milestones M1-M6 для розширення coverage."
        ),
        "summary_en": (
            "A synthetic HCV-MZL reference case as the P0 acceptance test. Defines every "
            "required patient-profile field (§2 templates), the critical structural "
            "assertions for Plan render output (§1.3), and milestones M1-M6 for expanding "
            "coverage."
        ),
    },
    {
        "id": "MDT_ORCHESTRATOR_SPEC",
        "file": "MDT_ORCHESTRATOR_SPEC.md",
        "tag": "engine",
        "title_uk": "MDT Orchestrator + Decision Provenance",
        "title_en": "MDT Orchestrator + Decision Provenance",
        "summary_uk": (
            "Orchestrate_mdt rules (R1-R9 для treatment, D1-D6 для diagnostic), "
            "role activation logic (required / recommended / optional), Open Questions "
            "механізм (Q1-Q6 + DQ1-DQ4 — engine не приймає рішення без потрібних даних), "
            "decision provenance graph для audit-grade explanation."
        ),
        "summary_en": (
            "Orchestrate_mdt rules (R1-R9 for treatment, D1-D6 for diagnostic), role "
            "activation logic (required / recommended / optional), the Open Questions "
            "mechanism (Q1-Q6 + DQ1-DQ4 — the engine refuses to decide without the "
            "required data), and a decision-provenance graph for audit-grade explanation."
        ),
    },
    {
        "id": "DIAGNOSTIC_MDT_SPEC",
        "file": "DIAGNOSTIC_MDT_SPEC.md",
        "tag": "engine",
        "title_uk": "Diagnostic-Phase MDT (Pre-biopsy)",
        "title_en": "Diagnostic-Phase MDT (Pre-biopsy)",
        "summary_uk": (
            "Pre-biopsy режим: коли histology ще немає, engine emit DiagnosticPlan з "
            "workup brief замість treatment Plan. CHARTER §15.2 C7 hard rule. "
            "DiagnosticWorkup + DiagnosticPlan schemas, generate_diagnostic_brief(), "
            "polymorphic orchestrate_mdt з DQ1-DQ4 rules."
        ),
        "summary_en": (
            "Pre-biopsy mode: when histology is not yet available the engine emits a "
            "DiagnosticPlan with a workup brief instead of a treatment Plan. CHARTER §15.2 "
            "C7 hard rule. DiagnosticWorkup + DiagnosticPlan schemas, "
            "generate_diagnostic_brief(), polymorphic orchestrate_mdt with DQ1-DQ4 rules."
        ),
    },
    {
        "id": "WORKUP_METHODOLOGY_SPEC",
        "file": "WORKUP_METHODOLOGY_SPEC.md",
        "tag": "clinical",
        "title_uk": "Workup Research Methodology",
        "title_en": "Workup Research Methodology",
        "summary_uk": (
            "Як ми будуємо basic workup для будь-якої онкологічної області. Source "
            "hierarchy (Tier 1: NCCN/ESMO/EHA/BSH/WHO/ASH), Test/Workup completeness "
            "checklists, 7-step process для нової domain extension, anti-patterns."
        ),
        "summary_en": (
            "How we build a basic workup for any oncology area. Source hierarchy "
            "(Tier 1: NCCN/ESMO/EHA/BSH/WHO/ASH), Test/Workup completeness checklists, the "
            "7-step process for extending coverage to a new domain, anti-patterns."
        ),
    },
    {
        "id": "SKILL_ARCHITECTURE_SPEC",
        "file": "SKILL_ARCHITECTURE_SPEC.md",
        "tag": "engine",
        "title_uk": "Skill-Oriented Architecture (MDT Roles as Skills)",
        "title_en": "Skill-Oriented Architecture (MDT Roles as Skills)",
        "summary_uk": (
            "Formalізує MDT ролі (гематолог / патолог / радіолог / etc.) як "
            "clinically-verified skills — кожен skill має version, sources, "
            "last_reviewed, clinical_lead. Sizing horizon (~12-15 MVP → 50-60 "
            "comprehensive), 8-domain layout, 5-phase refactor plan."
        ),
        "summary_en": (
            "Formalises MDT roles (haematologist / pathologist / radiologist / etc.) as "
            "clinically-verified skills — each skill carries version, sources, "
            "last_reviewed, clinical_lead. Sizing horizon (~12-15 MVP → 50-60 "
            "comprehensive), 8-domain layout, 5-phase refactor plan."
        ),
    },
]

_SPEC_TAG_LABELS = {
    "governance": "Governance",
    "clinical": "Clinical",
    "data": "Data",
    "schema": "Schema",
    "sources": "Sources",
    "testing": "Testing",
    "engine": "Engine",
}

_SPEC_TAG_COLORS = {
    "governance": "var(--red)",
    "clinical": "var(--green-700)",
    "data": "var(--teal)",
    "schema": "var(--green-600)",
    "sources": "var(--green-700)",
    "testing": "var(--amber)",
    "engine": "var(--green-700)",
}


def render_specs(stats, *, target_lang: str = "en") -> str:
    is_en = target_lang == "en"
    title_key = "title_en" if is_en else "title_uk"
    summary_key = "summary_en" if is_en else "summary_uk"

    spec_cards = []
    for sp in _SPECS_CATALOG:
        gh_url = (
            f"https://github.com/{GH_REPO}/blob/master/specs/{sp['file']}"
        )
        raw_url = (
            f"https://raw.githubusercontent.com/{GH_REPO}/master/specs/{sp['file']}"
        )
        color = _SPEC_TAG_COLORS.get(sp["tag"], "var(--gray-500)")
        tag_label = _SPEC_TAG_LABELS.get(sp["tag"], sp["tag"])
        read_label = "Read on GitHub →" if is_en else "Читати на GitHub →"
        raw_label = "Raw markdown" if is_en else "Raw markdown"
        spec_cards.append(f"""
        <div class="spec-card">
          <div class="spec-card-head">
            <span class="spec-tag" style="background:{color}">{tag_label}</span>
            <code class="spec-id">{sp['file']}</code>
          </div>
          <h3>{sp[title_key]}</h3>
          <p>{sp[summary_key]}</p>
          <div class="spec-card-foot">
            <a href="{gh_url}" target="_blank" rel="noopener">{read_label}</a>
            <a href="{raw_url}" target="_blank" rel="noopener" class="spec-raw">{raw_label}</a>
          </div>
        </div>
        """)

    cards_html = "".join(spec_cards)
    n_specs = len(_SPECS_CATALOG)

    if is_en:
        page_title = "Specifications"
        h1 = "Specifications"
        lead = (
            f"OpenOnco is a specifications-first project. Every architectural, clinical, "
            f"and governance detail is pinned in a markdown document under <code>specs/</code> "
            f"that is versioned and open to public review. {n_specs} active specifications "
            f"cover everything from FDA non-device CDS positioning to the shape of every "
            f"YAML entity in the KB. The full text lives at "
            f"<a href=\"https://github.com/{GH_REPO}/tree/master/specs\" target=\"_blank\" "
            f"rel=\"noopener\">github.com/{GH_REPO}/specs</a>."
        )
        callout = (
            "<strong>Source-of-truth hierarchy</strong> (from CLAUDE.md): when specs "
            "conflict, the binding order is <strong>1.</strong> CHARTER.md → "
            "<strong>2.</strong> other <code>specs/*.md</code> → <strong>3.</strong> "
            "CLAUDE.md → <strong>4.</strong> README.md. Anything under <code>legacy/</code> "
            "is not authoritative."
        )
        active_specs_h = f"Active specifications ({n_specs})"
        regulatory_h = "Regulatory source (PDF)"
        regulatory_p = (
            "The official FDA guidance on non-device CDS classification under "
            "§520(o)(1)(E). Hosted under <code>specs/</code> as a PDF. CHARTER §15 cites "
            "concrete criteria 1-4 from this document to justify OpenOnco's non-device "
            "positioning."
        )
        regulatory_link = "View PDF on GitHub →"
        process_h = "How we update the specifications"
        process_p1 = (
            "Any change under <code>specs/</code> or <code>knowledge_base/hosted/content/</code> "
            "that affects clinical recommendations requires a <strong>two-reviewer merge</strong> "
            "(CHARTER §6.1) — two of three Clinical Co-Lead approvals. This is the hard rule "
            "that gates clinical-content quality. Technical specs (schemas, engine, ingestion) "
            "can merge with a single reviewer to keep development moving, but clinical content "
            "always needs dual sign-off."
        )
        process_p2 = (
            "All specifications are written Ukrainian-first (the interface and the clinical "
            "reviewers are UA), but technical terms and license names stay in English inline. "
            "Versioning is via git: every spec carries <code>v0.1 (draft)</code> in the header "
            "and is bumped on minor/major depending on breaking changes."
        )
        compliance_h = "Compliance + privacy (quick view)"
        compliance_th = ("Guarantee", "Specification", "What it means")
        compliance_rows = [
            ("FDA non-device CDS", "CHARTER.md §15",
             "OpenOnco is designed for the §520(o)(1)(E) carve-out — not a medical device. Constraints C1-C7 are hard-enforced."),
            ("No patient data", "CHARTER.md §9.3",
             "<code>patient_plans/</code> and any patient HTML are gitignored. All examples are synthetic."),
            ("Two-reviewer merge", "CHARTER.md §6.1",
             "Clinical content needs 2 of 3 Clinical Co-Lead approvals; otherwise the Indication stays STUB."),
            ("No LLM clinical judgment", "CHARTER.md §8.3",
             "LLMs do not pick regimens, do not generate doses, and do not interpret biomarkers for therapy selection."),
            ("No treatment without histology", "CHARTER.md §15.2 C7",
             "The engine refuses to generate a treatment Plan without <code>disease.id</code> or <code>icd_o_3_morphology</code> — only a DiagnosticPlan."),
            ("Anti automation-bias", "CHARTER.md §15.2 C6",
             "≥2 alternative tracks are always shown side-by-side; the alternative is never hidden."),
            ("Source hosting default = referenced", "SOURCE_INGESTION_SPEC.md §1.4",
             "We do not duplicate external databases; hosting requires explicit H1-H5 justification."),
            ("Free public resource → non-commercial", "CHARTER.md §2",
             "Many licences (ESMO CC-BY-NC-ND, OncoKB academic, ATC) depend on this. A paid tier would trigger a license audit."),
        ]
        footer_disclaimer = "Informational tool for clinicians, not a medical device (CHARTER §15 + §11)."
    else:
        page_title = "Специфікації"
        h1 = "Специфікації"
        lead = (
            f"OpenOnco — це specifications-first проект. Кожна архітектурна, клінічна, або "
            f"governance деталь зафіксована у markdown-документі під <code>specs/</code>, "
            f"який підлягає версіонуванню та public review. {n_specs} активних специфікацій "
            f"описують все: від FDA non-device CDS positioning до структури кожної YAML "
            f"entity у KB. Усі тексти живуть у <a href=\"https://github.com/{GH_REPO}/tree/master/specs\" "
            f"target=\"_blank\" rel=\"noopener\">github.com/{GH_REPO}/specs</a>."
        )
        callout = (
            "<strong>Source-of-truth ієрархія</strong> (з CLAUDE.md): коли специфікації "
            "конфліктують, обов'язковий порядок: <strong>1.</strong> CHARTER.md → "
            "<strong>2.</strong> інші <code>specs/*.md</code> → <strong>3.</strong> CLAUDE.md → "
            "<strong>4.</strong> README.md. Контент під <code>legacy/</code> не authoritative."
        )
        active_specs_h = f"Активні специфікації ({n_specs})"
        regulatory_h = "Регуляторне джерело (PDF)"
        regulatory_p = (
            "Офіційне керівництво FDA про non-device CDS classification under "
            "§520(o)(1)(E). Лежить у <code>specs/</code> як hosted PDF. CHARTER §15 "
            "цитує конкретні criteria 1-4 з цього документа для обґрунтування OpenOnco "
            "positioning як non-device."
        )
        regulatory_link = "View PDF on GitHub →"
        process_h = "Як ми оновлюємо специфікації"
        process_p1 = (
            "Кожна зміна під <code>specs/</code> або <code>knowledge_base/hosted/content/</code> "
            "що affects clinical recommendations потребує <strong>two-reviewer merge</strong> "
            "(CHARTER §6.1) — два з трьох Clinical Co-Lead approvals. Це жорстке правило "
            "gатекіпить якість клінічного контенту. Технічні специфікації (схеми, engine, "
            "ingestion) можуть merge'итися single-reviewer для прискорення розробки, але "
            "clinical content — завжди dual sign-off."
        )
        process_p2 = (
            "Усі специфікації Ukrainian-first (мова інтерфейсу + клінічних reviewers UA), "
            "але technical terms та license names залишаються English inline. Версіонування "
            "— через git: кожна специфікація має <code>v0.1 (draft)</code> у header, bump "
            "на minor/major залежно від breaking changes."
        )
        compliance_h = "Compliance + Privacy (короткий зріз)"
        compliance_th = ("Гарантія", "Specification", "Що це означає")
        compliance_rows = [
            ("FDA non-device CDS", "CHARTER.md §15",
             "OpenOnco проектується під §520(o)(1)(E) carve-out — не медичний пристрій. Constraints C1-C7 hard-enforced."),
            ("No patient data", "CHARTER.md §9.3",
             "<code>patient_plans/</code> + будь-які patient HTML gitignored. Усі examples — synthetic."),
            ("Two-reviewer merge", "CHARTER.md §6.1",
             "Clinical content потребує 2 з 3 Clinical Co-Lead approvals; інакше Indication залишається STUB."),
            ("No LLM clinical judgment", "CHARTER.md §8.3",
             "LLM не вибирає режими, не генерує дози, не інтерпретує biomarkers для therapy selection."),
            ("No treatment without histology", "CHARTER.md §15.2 C7",
             "Engine відмовляється generate'ити treatment Plan без <code>disease.id</code> або <code>icd_o_3_morphology</code>; тільки DiagnosticPlan."),
            ("Anti automation-bias", "CHARTER.md §15.2 C6",
             "Завжди показуються ≥2 alternative tracks side-by-side; alternative не сховано."),
            ("Source hosting default = referenced", "SOURCE_INGESTION_SPEC.md §1.4",
             "Не дублюємо external бази; hosting потребує explicit H1-H5 justification."),
            ("Free public resource → non-commercial", "CHARTER.md §2",
             "Багато ліцензій (ESMO CC-BY-NC-ND, OncoKB academic, ATC) залежать від цього. Paid tier тригернув би license audit."),
        ]
        footer_disclaimer = "Це інформаційний інструмент для лікаря, не медичний пристрій (CHARTER §15 + §11)."

    compliance_rows_html = "\n".join(
        f"          <tr>\n"
        f"            <td><strong>{g}</strong></td>\n"
        f"            <td><code>{s}</code></td>\n"
        f"            <td>{m}</td>\n"
        f"          </tr>"
        for (g, s, m) in compliance_rows
    )

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · {page_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link href="/style.css" rel="stylesheet">
</head>
<body>
{_render_top_bar(active="specs", target_lang=target_lang, lang_switch_href=_lang_switch_href("specs", target_lang))}

<main>
  <section class="info-page">
    <h1>{h1}</h1>
    <p class="lead">
      {lead}
    </p>

    <div class="callout">
      {callout}
    </div>

    <div class="info-section">
      <h2>{active_specs_h}</h2>
      <div class="spec-grid">
        {cards_html}
      </div>
    </div>

    <div class="info-section">
      <h2>{regulatory_h}</h2>
      <div class="spec-card">
        <div class="spec-card-head">
          <span class="spec-tag" style="background:var(--gray-700)">Regulatory PDF</span>
          <code class="spec-id">Guidance-Clinical-Decision-Software_5.pdf</code>
        </div>
        <h3>FDA Clinical Decision Support Software Guidance</h3>
        <p>
          {regulatory_p}
        </p>
        <div class="spec-card-foot">
          <a href="https://github.com/{GH_REPO}/blob/master/specs/Guidance-Clinical-Decision-Software_5.pdf"
             target="_blank" rel="noopener">{regulatory_link}</a>
        </div>
      </div>
    </div>

    <div class="info-section">
      <h2>{process_h}</h2>
      <p class="info-text">
        {process_p1}
      </p>
      <p class="info-text">
        {process_p2}
      </p>
    </div>

    <div class="info-section">
      <h2>{compliance_h}</h2>
      <table class="kv-table">
        <thead><tr><th>{compliance_th[0]}</th><th>{compliance_th[1]}</th><th>{compliance_th[2]}</th></tr></thead>
        <tbody>
{compliance_rows_html}
        </tbody>
      </table>
    </div>
  </section>

  <footer class="page-foot">
    Open-source · MIT-style usage · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    <br>
    {footer_disclaimer}
  </footer>
</main>
</body>
</html>
"""


def render_about(stats, *, target_lang: str = "en") -> str:
    counts = _landing_stat_counts(stats)
    is_en = target_lang == "en"
    if is_en:
        page_title = "About"
        h1 = "About OpenOnco"
        lead = (
            "OpenOnco is an open clinical knowledge and rules project for oncology. "
            "This page collects the material that used to sit in separate top-menu links: "
            "examples, specifications and GitHub."
        )
        cards = [
            (
                "Examples",
                "/gallery.html",
                "Synthetic cases with rendered plans and diagnostic briefs. Use them to inspect how the engine explains decisions.",
                "Open examples",
            ),
            (
                "Specifications",
                "/specs.html",
                "The authoritative project contract: charter, clinical content rules, schemas, ingestion and governance.",
                "Read specs",
            ),
            (
                "GitHub",
                f"https://github.com/{GH_REPO}",
                "Source code, knowledge-base YAML, issues, pull requests and public review history.",
                "View repository",
            ),
        ]
        principles_h = "Project shape"
        principles = [
            ("Open by default", "Code is MIT-style; specifications and generated content are CC BY 4.0."),
            ("Synthetic public data", "The public site ships no real patient records and no patient-specific private artifacts."),
            ("Clinical review gate", "Clinical content needs reviewer sign-off before it can become trusted content."),
            ("Auditable automation", "Rules, sources and rendered reasoning are visible instead of hidden behind a black box."),
        ]
        stats_h = "Current public corpus"
        release_note = f"Current public build: v{OPENONCO_VERSION}, released {OPENONCO_RELEASE_DATE}."
        footer = "Informational tool for clinicians, not a medical device (CHARTER §15 + §11)."
        stat_labels = {
            "diseases": "diseases",
            "redflags": "red flags",
            "indications": "indications",
            "regimens": "regimens",
            "algorithms": "algorithms",
        }
    else:
        page_title = "About"
        h1 = "About OpenOnco"
        lead = (
            "OpenOnco — відкритий проєкт клінічної бази знань і rule engine для онкології. "
            "На цій сторінці зібрано те, що раніше було окремими пунктами верхнього меню: "
            "приклади, специфікації та GitHub."
        )
        cards = [
            (
                "Приклади",
                "/ukr/gallery.html",
                "Синтетичні кейси з готовими планами й diagnostic briefs. Через них зручно перевіряти пояснення engine.",
                "Відкрити приклади",
            ),
            (
                "Специфікації",
                "/ukr/specs.html",
                "Авторитетний контракт проєкту: charter, правила клінічного контенту, схеми, ingestion і governance.",
                "Читати специфікації",
            ),
            (
                "GitHub",
                f"https://github.com/{GH_REPO}",
                "Код, YAML бази знань, issues, pull requests і публічна історія ревʼю.",
                "Відкрити репозиторій",
            ),
        ]
        principles_h = "Форма проєкту"
        principles = [
            ("Open by default", "Код має MIT-style usage; специфікації та згенерований контент — CC BY 4.0."),
            ("Синтетичні публічні дані", "Публічний сайт не містить реальних пацієнтських записів чи приватних patient artifacts."),
            ("Clinical review gate", "Клінічний контент потребує reviewer sign-off перед статусом trusted content."),
            ("Auditable automation", "Правила, джерела й reasoning видимі, а не сховані за black box."),
        ]
        stats_h = "Поточний публічний корпус"
        release_note = f"Поточна публічна збірка: v{OPENONCO_VERSION}, release {OPENONCO_RELEASE_DATE}."
        footer = "Це інформаційний інструмент для лікаря, не медичний пристрій (CHARTER §15 + §11)."
        stat_labels = {
            "diseases": "хвороб",
            "redflags": "red flags",
            "indications": "індикацій",
            "regimens": "режимів",
            "algorithms": "алгоритмів",
        }

    cards_html = "\n".join(
        f"""        <a class="about-link-card" href="{href}"{' target="_blank" rel="noopener"' if href.startswith('https://') else ''}>
          <span>{title}</span>
          <p>{body}</p>
          <strong>{cta} →</strong>
        </a>"""
        for title, href, body, cta in cards
    )
    principles_html = "\n".join(
        f"""        <div class="about-principle">
          <h3>{title}</h3>
          <p>{body}</p>
        </div>"""
        for title, body in principles
    )
    stats_html = "\n".join(
        f'        <div class="about-stat"><strong>{counts[key]}</strong><span>{label}</span></div>'
        for key, label in stat_labels.items()
    )

    return f"""<!DOCTYPE html>
<html lang="{'en' if is_en else 'uk'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenOnco · {page_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link href="/style.css" rel="stylesheet">
</head>
<body>
{_render_top_bar(active="about", target_lang=target_lang, lang_switch_href=_lang_switch_href("about", target_lang))}

<main>
  <section class="about-hero">
    <p class="home-kicker">OpenOnco</p>
    <h1>{h1}</h1>
    <p>{lead}</p>
  </section>

  <section class="about-link-grid">
{cards_html}
  </section>

  <section class="about-split">
    <div>
      <h2>{principles_h}</h2>
      <div class="about-principles">
{principles_html}
      </div>
    </div>
    <div class="about-stats-panel">
      <h2>{stats_h}</h2>
      <div class="about-stats">
{stats_html}
      </div>
      <p class="about-release">{release_note}</p>
    </div>
  </section>

  <footer class="page-foot">
    Open-source · MIT-style usage · <a href="https://github.com/{GH_REPO}">{GH_REPO}</a>
    <br>
    {footer}
  </footer>
</main>
</body>
</html>
"""


# ── Build orchestration ───────────────────────────────────────────────────


def _build_one_case_worker(args: tuple) -> dict:
    """Top-level wrapper for ProcessPoolExecutor (must be picklable).
    Returns the dict shape that build_site() collects into case_paths_uk/en."""
    case, output_dir, target_lang = args
    p = build_one_case(case, output_dir, target_lang=target_lang)
    return {
        "case_id": case.case_id,
        "lang": target_lang,
        "path": str(p.relative_to(output_dir)),
    }


def _build_all_cases_parallel(output_dir: Path) -> tuple[list[dict], list[dict]]:
    """Render every CASE × {uk, en} in a process pool.

    Each worker re-imports knowledge_base and reloads the YAML KB once on
    startup, then handles a chunk of cases — so a 4-worker pool amortises
    the import cost across ~50 cases per worker. On Windows (spawn) this
    cuts the 99×2-case build from ~12 min serial to ~2 min on 4 cores.
    """
    import os
    from concurrent.futures import ProcessPoolExecutor

    public_cases = _public_case_entries()
    tasks = [(c, output_dir, "uk") for c in public_cases] + \
            [(c, output_dir, "en") for c in public_cases]
    env_workers = os.environ.get("OPENONCO_BUILD_WORKERS")
    if env_workers:
        try:
            n_workers = max(1, int(env_workers))
        except ValueError:
            n_workers = min(os.cpu_count() or 4, 8)
    else:
        n_workers = min(os.cpu_count() or 4, 8)

    if n_workers <= 1 or len(tasks) <= 2:
        results = [_build_one_case_worker(t) for t in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                results = list(ex.map(_build_one_case_worker, tasks, chunksize=4))
        except (OSError, PermissionError):
            # Some sandboxed Windows runners forbid multiprocessing pipe
            # creation. Serial rendering is slower but keeps the static build
            # deterministic and usable in restricted environments.
            results = [_build_one_case_worker(t) for t in tasks]

    uk = [r for r in results if r["lang"] == "uk"]
    en = [r for r in results if r["lang"] == "en"]
    return uk, en


def build_one_case(case: CaseEntry, output_dir: Path,
                   *, target_lang: str = "en") -> Path:
    """Render one case to HTML in `target_lang`. Output path:
    - target_lang='en' → output_dir/cases/<id>.html  (EN is default at root)
    - target_lang='uk' → output_dir/ukr/cases/<id>.html
    """
    patient_path = EXAMPLES / case.file
    patient = json.loads(patient_path.read_text(encoding="utf-8"))

    if is_diagnostic_profile(patient):
        result = generate_diagnostic_brief(patient, kb_root=KB_ROOT)
        mdt = orchestrate_mdt(patient, result, kb_root=KB_ROOT)
        html = render_diagnostic_brief_html(result, mdt=mdt, target_lang=target_lang)
    else:
        result = generate_plan(
            patient,
            kb_root=KB_ROOT,
            experimental_search_fn=search_trials,
            experimental_cache_root=CTGOV_CACHE,
        )
        mdt = orchestrate_mdt(patient, result, kb_root=KB_ROOT)
        html = render_plan_html(result, mdt=mdt, target_lang=target_lang)

    wrapped = _wrap_case_html(html, case, target_lang=target_lang)
    sub = "ukr/cases" if target_lang == "uk" else "cases"
    out_path = output_dir / sub / f"{case.case_id}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(wrapped, encoding="utf-8")
    return out_path


def _copy_landing_assets(output_dir: Path) -> list[str]:
    """Copy infographic images used by the landing into docs/. Source-of-truth
    lives in infograph/ (gitignored except these). Listed by name so we don't
    accidentally copy patient HTMLs (CHARTER §9.3)."""
    src_root = REPO_ROOT / "infograph"
    assets = ["MDT.png", "MDT-light.png"]
    copied: list[str] = []
    for name in assets:
        src = src_root / name
        if src.exists():
            shutil.copyfile(src, output_dir / name)
            copied.append(name)
    # Small brand SVGs live directly under docs/ (committed) - preserve on --clean.
    for asset_name in ("favicon.svg", "logo.svg"):
        asset_src = REPO_ROOT / "docs" / asset_name
        if asset_src.exists() and asset_src.resolve() != (output_dir / asset_name).resolve():
            shutil.copyfile(asset_src, output_dir / asset_name)
            copied.append(asset_name)
    return copied


def build_site(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cases").mkdir(parents=True, exist_ok=True)
    (output_dir / "ukr").mkdir(parents=True, exist_ok=True)
    (output_dir / "ukr" / "cases").mkdir(parents=True, exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "CNAME").write_text(CUSTOM_DOMAIN + "\n", encoding="utf-8")
    (output_dir / "style.css").write_text(_STYLE_CSS, encoding="utf-8")
    landing_assets = _copy_landing_assets(output_dir)
    excluded_case_pages_removed = _remove_excluded_case_pages(output_dir)

    stats = collect_stats()

    # Build engine bundle FIRST so we can stamp its content-hash into
    # try.html as a cache-buster (?v=<hash>). Without this, GitHub Pages
    # serves the zip with Cache-Control: max-age=600 and users get stale
    # bundles for ~10 minutes after a KB push.
    engine_bundle = bundle_engine(output_dir)
    bundle_version = engine_bundle.get("version", "")
    sw_payload = write_service_worker(
        output_dir, core_version=engine_bundle.get("core_version", ""),
    )
    manifest_payload = write_web_manifest(output_dir)

    questionnaires_payload = bundle_questionnaires(output_dir)
    # Bundle dropdowns BEFORE render_try so /try.html can inline the
    # ~15 KB manifests as JS constants — saves the ~870 KB initial fetch
    # of questionnaires.json + examples.json on first paint. Examples are
    # curated only; low-fill auto-stubs stay out of the public picker.
    examples_payload = bundle_examples(
        output_dir,
        questionnaires_manifest=questionnaires_payload.get("manifest", []),
    )
    questionnaires_manifest = questionnaires_payload.get("manifest", [])
    examples_manifest = examples_payload.get("manifest", [])

    # ── EN build (default at site root) ──
    # English is the primary language; the root URLs (/, /capabilities.html,
    # /diseases.html, /gallery.html, /try.html, /cases/<id>.html) all serve
    # English. Bookmarks of the previous UA-default layout are broken — UA
    # users now land via /ukr/ (or click the language switcher).
    (output_dir / "index.html").write_text(
        render_landing(stats, target_lang="en"), encoding="utf-8")
    (output_dir / "capabilities.html").write_text(
        render_capabilities(stats, target_lang="en"), encoding="utf-8")
    (output_dir / "gallery.html").write_text(
        render_gallery(target_lang="en"), encoding="utf-8")
    (output_dir / "diseases.html").write_text(
        render_diseases(stats, target_lang="en"), encoding="utf-8")
    (output_dir / "specs.html").write_text(
        render_specs(stats, target_lang="en"), encoding="utf-8")
    (output_dir / "about.html").write_text(
        render_about(stats, target_lang="en"), encoding="utf-8")
    (output_dir / "try.html").write_text(
        render_try(
            target_lang="en",
            bundle_version=bundle_version,
            questionnaires_manifest=questionnaires_manifest,
            examples_manifest=examples_manifest,
        ), encoding="utf-8")
    (output_dir / "ask.html").write_text(
        render_ask(target_lang="en"), encoding="utf-8")

    # ── UA build (mirror at /ukr/) ──
    # Specs catalog page is rendered in both locales — the underlying
    # markdown specs in /specs/ are still UA-first, but the catalog overview
    # has both UA and EN copy. Per-case Plan/Brief HTMLs ARE rendered in
    # both languages — that's where 80% of the user-facing content lives.
    (output_dir / "ukr" / "index.html").write_text(
        render_landing(stats, target_lang="uk"), encoding="utf-8")
    (output_dir / "ukr" / "capabilities.html").write_text(
        render_capabilities(stats, target_lang="uk"), encoding="utf-8")
    (output_dir / "ukr" / "specs.html").write_text(
        render_specs(stats, target_lang="uk"), encoding="utf-8")
    (output_dir / "ukr" / "about.html").write_text(
        render_about(stats, target_lang="uk"), encoding="utf-8")
    (output_dir / "ukr" / "gallery.html").write_text(
        render_gallery(target_lang="uk"), encoding="utf-8")
    (output_dir / "ukr" / "diseases.html").write_text(
        render_diseases(stats, target_lang="uk"), encoding="utf-8")
    (output_dir / "ukr" / "try.html").write_text(
        render_try(
            target_lang="uk",
            bundle_version=bundle_version,
            questionnaires_manifest=questionnaires_manifest,
            examples_manifest=examples_manifest,
        ), encoding="utf-8")
    (output_dir / "ukr" / "ask.html").write_text(
        render_ask(target_lang="uk"), encoding="utf-8")

    case_paths_uk, case_paths_en = _build_all_cases_parallel(output_dir)
    disease_coverage_payload = bundle_disease_coverage(output_dir)
    kb_wiki_payload = build_kb_wiki(KB_ROOT, output_dir)
    clinical_gap_payload = write_clinical_gap_outputs(output_dir)
    discovery_payload = finalize_site_discovery(output_dir)

    return {
        "output_dir": str(output_dir),
        "cases_built": len(case_paths_uk) + len(case_paths_en),
        "cases_uk": case_paths_uk,
        "cases_en": case_paths_en,
        "engine_bundle": engine_bundle,
        "service_worker": sw_payload,
        "web_manifest": manifest_payload,
        "examples_payload": examples_payload,
        "questionnaires_payload": questionnaires_payload,
        "disease_coverage_payload": disease_coverage_payload,
        "kb_wiki_payload": kb_wiki_payload,
        "clinical_gap_payload": clinical_gap_payload,
        "discovery_payload": discovery_payload,
        "landing_assets": landing_assets,
        "excluded_case_pages_removed": excluded_case_pages_removed,
    }


def _force_utf8_stdout() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:  # pylint: disable=broad-except
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description="Build OpenOnco static site for GitHub Pages.")
    parser.add_argument("--output", default="docs", help="Output directory (default: docs/)")
    parser.add_argument("--clean", action="store_true", help="Wipe output directory before building.")
    args = parser.parse_args(argv)

    output_dir = (REPO_ROOT / args.output) if not Path(args.output).is_absolute() else Path(args.output)
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    report = build_site(output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
