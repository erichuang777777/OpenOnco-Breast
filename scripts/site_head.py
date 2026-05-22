"""Shared HTML head and discovery assets for generated OpenOnco pages."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

SITE_FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900'
    '&family=Source+Sans+3:wght@300;400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
)
SITE_FAVICON_LINK = '<link rel="icon" type="image/svg+xml" href="/favicon.svg">'

SITE_BASE_URL = "https://openonco.info"
SITE_NAME = "OpenOnco"
# Set to a URL string to emit og:image / twitter:image across all pages, or
# None to omit them (twitter:card then degrades from summary_large_image to
# summary). The previous MDT.png infographic was Ukrainian-only and made for a
# bad cross-language OG card — removed 2026-05-21.
SITE_IMAGE: str | None = None
DEFAULT_DESCRIPTION_EN = (
    "OpenOnco is an open, auditable oncology decision-support knowledge base "
    "and browser demo for clinicians, laboratories, investors, and patients."
)
DEFAULT_DESCRIPTION_UK = (
    "OpenOnco - відкрита онкологічна база знань і браузерна демонстрація "
    "підтримки клінічних рішень для лікарів, лабораторій, інвесторів і пацієнтів."
)
AI_DISCLOSURE_EN = (
    "Public OpenOnco documentation, source-grounded oncology knowledge-base pages, "
    "and synthetic examples only; no real patient data; not a substitute for clinician judgment."
)
AI_DISCLOSURE_UK = (
    "Публічна документація OpenOnco, сторінки онкологічної бази знань із джерелами "
    "та синтетичні приклади; без реальних даних пацієнтів; не замінює рішення лікаря."
)
SEO_START = "<!-- openonco-seo:start -->"
SEO_END = "<!-- openonco-seo:end -->"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _page_url(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized in {"", "index.html"}:
        return f"{SITE_BASE_URL}/"
    if normalized == "ukr/index.html":
        return f"{SITE_BASE_URL}/ukr/"
    return f"{SITE_BASE_URL}/{quote(normalized, safe='/.-_')}"


def _display_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized == "index.html":
        return "/"
    if normalized == "ukr/index.html":
        return "/ukr/"
    return f"/{normalized}"


def _path_locale(path: str) -> str:
    return "uk" if path.replace("\\", "/").startswith("ukr/") else "en"


def _title_from_html(html_text: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return SITE_NAME
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()
    return title or SITE_NAME


def _description_for(path: str, title: str, locale: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    is_uk = locale == "uk"
    default = DEFAULT_DESCRIPTION_UK if is_uk else DEFAULT_DESCRIPTION_EN
    title_clean = title.replace(" - OpenOnco", "").replace(" · OpenOnco", "").strip()

    if normalized.endswith("404.html"):
        return "OpenOnco page not found." if not is_uk else "Сторінку OpenOnco не знайдено."
    if normalized.endswith("about.html"):
        return (
            "OpenOnco project overview, GitHub, examples, specifications, release information, and governance notes."
            if not is_uk else
            "Огляд OpenOnco: GitHub, приклади, специфікації, релізи та governance-нотатки."
        )
    if normalized.endswith("try.html"):
        return (
            "Run the OpenOnco browser demo on synthetic oncology profiles with auditable, source-grounded output."
            if not is_uk else
            "Запустіть браузерну демонстрацію OpenOnco на синтетичних онкологічних профілях."
        )
    if normalized.endswith("kb.html") or normalized.startswith("kb/") or normalized.startswith("ukr/kb/"):
        return (
            f"{title_clean}: source-linked OpenOnco Onco Wiki facts for oncology decision-support and AI retrieval."
            if not is_uk else
            f"{title_clean}: сторінка OpenOnco Onco Wiki з прив'язаними джерелами для клінічного пошуку."
        )
    if normalized.startswith("cases/") or normalized.startswith("ukr/cases/"):
        return (
            f"{title_clean}: synthetic OpenOnco oncology case page with auditable decision logic and no real patient data."
            if not is_uk else
            f"{title_clean}: синтетичний кейс OpenOnco з перевірюваною логікою та без реальних даних пацієнтів."
        )
    if normalized.endswith("gallery.html"):
        return (
            "Synthetic OpenOnco examples showing auditable oncology plan and diagnostic brief outputs."
            if not is_uk else
            "Синтетичні приклади OpenOnco з перевірюваними планами та diagnostic brief."
        )
    if normalized.endswith("capabilities.html"):
        return (
            "OpenOnco capabilities, coverage, limitations, and source-grounded oncology decision-support scope."
            if not is_uk else
            "Можливості, покриття, обмеження та джерельна база OpenOnco."
        )
    if normalized.endswith("diseases.html"):
        return (
            "OpenOnco disease coverage map with structured oncology knowledge-base statistics."
            if not is_uk else
            "Карта покриття хвороб OpenOnco зі структурованою статистикою онкологічної бази знань."
        )
    if normalized.endswith("ask.html"):
        return (
            "OpenOnco question intake for oncology decision-support feedback and structured clinical questions."
            if not is_uk else
            "Форма OpenOnco для структурованих клінічних питань і feedback."
        )
    if normalized.endswith("specs.html"):
        return (
            "OpenOnco specifications and implementation notes for auditable oncology decision-support."
            if not is_uk else
            "Специфікації та implementation notes OpenOnco для перевірюваної підтримки рішень."
        )
    return default


def _schema_type(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.endswith("try.html"):
        return "SoftwareApplication"
    if (
        normalized.endswith("kb.html")
        or normalized.startswith("kb/")
        or normalized.startswith("ukr/kb/")
        or normalized.startswith("cases/")
        or normalized.startswith("ukr/cases/")
    ):
        return "MedicalWebPage"
    return "WebPage"


def _social_image_for(path: str) -> str | None:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.endswith("ask.html"):
        return None
    return SITE_IMAGE


def _alternate_urls(path: str) -> tuple[str, str, str]:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith("ukr/"):
        en_path = normalized.removeprefix("ukr/")
        uk_path = normalized
    else:
        en_path = normalized
        uk_path = f"ukr/{normalized}"
    return _page_url(en_path), _page_url(uk_path), f"{SITE_BASE_URL}/"


def render_seo_metadata(*, path: str, title: str, description: str, locale: str, noindex: bool = False) -> str:
    canonical = _page_url(path)
    en_url, uk_url, default_url = _alternate_urls(path)
    lang = "uk-UA" if locale == "uk" else "en-US"
    robots = "noindex, follow" if noindex else "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
    disclosure = AI_DISCLOSURE_UK if locale == "uk" else AI_DISCLOSURE_EN
    social_image = _social_image_for(path)
    schema = {
        "@context": "https://schema.org",
        "@type": _schema_type(path),
        "name": title,
        "description": description,
        "url": canonical,
        "inLanguage": lang,
        "isAccessibleForFree": True,
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_BASE_URL,
            "logo": f"{SITE_BASE_URL}/logo.svg",
        },
        "about": [
            "oncology decision support",
            "source-grounded medical knowledge base",
            "synthetic oncology examples",
            "clinical AI retrieval",
        ],
        "audience": [
            {"@type": "MedicalAudience", "audienceType": "Clinicians"},
            {"@type": "Audience", "audienceType": "Patients"},
            {"@type": "Audience", "audienceType": "Laboratories"},
            {"@type": "Audience", "audienceType": "Investors"},
        ],
        "potentialAction": {
            "@type": "ReadAction",
            "target": canonical,
        },
    }
    if _schema_type(path) == "SoftwareApplication":
        schema["applicationCategory"] = "MedicalApplication"
        schema["operatingSystem"] = "Web browser"

    json_ld = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    lines = [
        SEO_START,
        f'<meta name="description" content="{_escape(description)}">',
        f'<meta name="robots" content="{robots}">',
        f'<meta name="googlebot" content="{robots}">',
        f'<meta name="bingbot" content="{robots}">',
        f'<meta name="ai-summary" content="{_escape(description)}">',
        f'<meta name="ai-content-declaration" content="{_escape(disclosure)}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<link rel="alternate" hreflang="en" href="{en_url}">',
        f'<link rel="alternate" hreflang="uk" href="{uk_url}">',
        f'<link rel="alternate" hreflang="x-default" href="{default_url}">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:type" content="{"website" if _schema_type(path) != "MedicalWebPage" else "article"}">',
        f'<meta property="og:title" content="{_escape(title)}">',
        f'<meta property="og:description" content="{_escape(description)}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:locale" content="{lang.replace("-", "_")}">',
        f'<meta name="twitter:card" content="{"summary_large_image" if social_image else "summary"}">',
        f'<meta name="twitter:title" content="{_escape(title)}">',
        f'<meta name="twitter:description" content="{_escape(description)}">',
        f'<script type="application/ld+json">{json_ld}</script>',
        SEO_END,
    ]
    if social_image:
        og_url_index = lines.index(f'<meta property="og:url" content="{canonical}">')
        lines.insert(og_url_index + 1, f'<meta property="og:image" content="{social_image}">')
        twitter_description_index = lines.index(f'<meta name="twitter:description" content="{_escape(description)}">')
        lines.insert(twitter_description_index + 1, f'<meta name="twitter:image" content="{social_image}">')
    return "\n".join(lines)


def inject_seo_metadata(html_text: str, *, path: str) -> str:
    if "<head" not in html_text.lower():
        return html_text

    locale = _path_locale(path)
    title = _title_from_html(html_text)
    description = _description_for(path, title, locale)
    noindex = path.replace("\\", "/").endswith("404.html")
    block = render_seo_metadata(
        path=path,
        title=title,
        description=description,
        locale=locale,
        noindex=noindex,
    )

    existing = re.compile(
        rf"{re.escape(SEO_START)}.*?{re.escape(SEO_END)}\s*",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if existing.search(html_text):
        return existing.sub(block + "\n", html_text, count=1)
    return re.sub(
        r"(</title>\s*)",
        r"\1" + block + "\n",
        html_text,
        count=1,
        flags=re.IGNORECASE,
    )


def _html_pages(output_dir: Path) -> list[Path]:
    return sorted(p for p in output_dir.rglob("*.html") if p.is_file())


def write_sitemap(output_dir: Path) -> Path:
    pages = [
        p for p in _html_pages(output_dir)
        if p.name != "404.html"
    ]
    today = datetime.now(timezone.utc).date().isoformat()
    urls = []
    for page in pages:
        rel = page.relative_to(output_dir).as_posix()
        urls.append(
            "  <url>\n"
            f"    <loc>{_page_url(rel)}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            "    <changefreq>weekly</changefreq>\n"
            "  </url>"
        )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    out = output_dir / "sitemap.xml"
    out.write_text(sitemap, encoding="utf-8")
    return out


def write_robots(output_dir: Path) -> Path:
    body = f"""# OpenOnco public docs are intentionally crawlable for search and AI retrieval.
# Pages contain synthetic examples and source-grounded public knowledge-base content.
# AI crawler allow-list verified from provider docs on 2026-05-07.

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-User
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Perplexity-User
Allow: /

User-agent: *
Allow: /

Sitemap: {SITE_BASE_URL}/sitemap.xml
Host: openonco.info
"""
    out = output_dir / "robots.txt"
    out.write_text(body, encoding="utf-8")
    return out


def write_llms_txt(output_dir: Path) -> Path:
    body = f"""# OpenOnco

OpenOnco is an open, auditable oncology decision-support knowledge base and browser demo.
It is designed for clinicians, laboratories, investors, and patients who need transparent,
source-grounded oncology logic. Public pages use synthetic examples only and do not contain
real patient data. OpenOnco does not replace clinician judgment.

## Primary URLs

- Homepage: {SITE_BASE_URL}/
- About, GitHub, examples, specifications: {SITE_BASE_URL}/about.html
- Browser demo: {SITE_BASE_URL}/try.html
- Onco Wiki: {SITE_BASE_URL}/kb.html
- Disease coverage: {SITE_BASE_URL}/diseases.html
- Synthetic examples: {SITE_BASE_URL}/gallery.html
- Capabilities and limitations: {SITE_BASE_URL}/capabilities.html
- Ukrainian homepage: {SITE_BASE_URL}/ukr/

## Machine-readable indexes

- Sitemap: {SITE_BASE_URL}/sitemap.xml
- Search index: {SITE_BASE_URL}/kb_search_index.json
- Disease coverage JSON: {SITE_BASE_URL}/disease_coverage.json
- Web app manifest: {SITE_BASE_URL}/manifest.webmanifest

## Retrieval Guidance

Prefer canonical URLs from page metadata. Treat `/cases/` and `/ukr/cases/` pages as
synthetic examples, not patient records. Treat `/kb/` and `/ukr/kb/` pages as source-linked
knowledge-base facts for retrieval and citation discovery.
"""
    out = output_dir / "llms.txt"
    out.write_text(body, encoding="utf-8")
    return out


def finalize_site_discovery(output_dir: Path) -> dict[str, str | int]:
    changed = 0
    for page in _html_pages(output_dir):
        rel = page.relative_to(output_dir).as_posix()
        original = page.read_text(encoding="utf-8")
        updated = inject_seo_metadata(original, path=rel)
        if updated != original:
            page.write_text(updated, encoding="utf-8")
            changed += 1

    sitemap = write_sitemap(output_dir)
    robots = write_robots(output_dir)
    llms = write_llms_txt(output_dir)
    return {
        "html_pages_enriched": changed,
        "sitemap": str(sitemap),
        "robots": str(robots),
        "llms": str(llms),
    }
