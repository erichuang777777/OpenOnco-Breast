"""CSS for the OpenOnco public-facing site (index/gallery/try/capabilities/
limitations/specs).

Extracted from scripts/build_site.py to keep that file's orchestration
logic readable. Loaded once and written to docs/style.css at build time;
also referenced inline by some page renderers via a <style> tag.
"""

STYLESHEET = """
:root {
  --green-900: #0a2e1a;
  --green-800: #0d3f24;
  --green-700: #14532d;
  --green-600: #166534;
  --green-500: #16a34a;
  --green-100: #dcfce7;
  --green-50: #f0fdf4;
  --teal: #0d9488;
  --amber-bg: #fffbeb;
  --amber: #d97706;
  --red-bg: #fef2f2;
  --red: #dc2626;
  --gray-50: #f9fafb;
  --gray-100: #f3f4f6;
  --gray-200: #e5e7eb;
  --gray-500: #6b7280;
  --gray-700: #374151;
  --gray-900: #111827;
  --font-sans: 'Source Sans 3', 'Segoe UI', sans-serif;
  --font-display: 'Playfair Display', Georgia, serif;
  --font-mono: 'JetBrains Mono', Menlo, monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html {
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
}
body {
  font-family: var(--font-sans);
  color: var(--gray-900);
  background: var(--gray-50);
  line-height: 1.55;
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
}
a { color: var(--green-700); }
main { max-width: 1100px; margin: 0 auto; padding: 0 24px 48px; }

/* Top bar */
.top-bar {
  background: white;
  color: var(--gray-900);
  padding: 13px 24px;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid var(--gray-200);
  width: 100%;
  max-width: 100%;
  overflow-x: clip;
}
.brand-line { display: flex; align-items: center; gap: 12px; margin-right: 30px; }
.brand-logo {
  display: none;
}
.brand-mini {
  display: inline-flex; align-items: center; gap: 9px;
  font-family: var(--font-display); font-size: 26px; font-weight: 900;
  color: var(--green-700); text-decoration: none;
  letter-spacing: 0;
}
.brand-version {
  font-family: var(--font-mono); font-size: 10.5px;
  color: var(--green-100); opacity: 0.55;
  background: rgba(255,255,255,0.06);
  padding: 2px 7px; border-radius: 3px; letter-spacing: 0.5px;
  align-self: center;
}
.role-pill {
  background: var(--teal); color: white;
  font-family: var(--font-mono); font-size: 10px;
  padding: 2px 8px; border-radius: 4px; letter-spacing: 0.5px;
  text-transform: uppercase;
}
.top-actions a {
  color: var(--gray-700); margin-left: 16px; text-decoration: none;
  font-size: 14px; font-weight: 700;
}
.top-actions a:hover, .top-actions a.active { color: var(--green-700); }
.top-actions a.active {
  border-bottom: 2px solid var(--green-700); padding-bottom: 1px;
}

/* New top-bar layout: brand · nav · right-cluster (lang switch + try CTA) */
.top-nav { display: flex; align-items: center; flex: 1; margin: 0 24px 0 16px; gap: 4px; }
.top-nav a {
  color: var(--gray-700); padding: 6px 10px; text-decoration: none;
  font-size: 14.5px; font-weight: 700; border-radius: 4px;
}
.top-nav a:hover { color: var(--green-700); background: transparent; }
.top-nav a.active {
  color: var(--green-700); background: transparent;
  box-shadow: inset 0 -2px 0 var(--green-700);
}

.top-right { display: flex; align-items: center; gap: 14px; flex-shrink: 0; }
.top-cta-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }

/* Language switch — compact UA / EN toggle. Fixed-width halves so the
   pill stays the same shape regardless of which language is current. */
.lang-switch {
  display: inline-flex; align-items: center; gap: 0;
  background: white; border: 1px solid var(--gray-200); border-radius: 4px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.5px;
  overflow: hidden; flex-shrink: 0;
}
.lang-switch .lang-current,
.lang-switch .lang-other {
  width: 56px; box-sizing: border-box;
  padding: 4px 9px;
  display: inline-flex; align-items: center; justify-content: center; gap: 5px;
}
.lang-switch .lang-current {
  background: var(--green-700); color: white;
  font-weight: 600;
}
.lang-switch .lang-other {
  color: var(--gray-700);
  text-decoration: none; transition: background .12s;
}
.lang-switch .lang-other:hover { background: transparent; color: var(--green-700); }
/* CSS-painted mini flag — works on every OS (Windows doesn't render
   regional-indicator emoji as flags). 14×10 colored bar. */
.lang-switch .lang-flag {
  display: inline-block; width: 14px; height: 10px; border-radius: 1.5px;
  box-shadow: 0 0 0 1px rgba(0,0,0,.25) inset;
}
.lang-switch .lang-flag.flag-ua {
  background: linear-gradient(to bottom, #0057b7 50%, #ffd500 50%);
}
/* Union Jack via inline SVG — the prior horizontal red/white/blue
   gradient read as the Dutch flag. Paint the actual British flag instead. */
.lang-switch .lang-flag.flag-en {
  background: #012169 url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30' preserveAspectRatio='none'%3E%3Cpath d='M0,0 L60,30 M60,0 L0,30' stroke='%23fff' stroke-width='6'/%3E%3Cpath d='M0,0 L60,30 M60,0 L0,30' stroke='%23C8102E' stroke-width='2'/%3E%3Cpath d='M30,0 V30 M0,15 H60' stroke='%23fff' stroke-width='10'/%3E%3Cpath d='M30,0 V30 M0,15 H60' stroke='%23C8102E' stroke-width='6'/%3E%3C/svg%3E") center/cover no-repeat;
}

/* Header action buttons — distinct from nav reading links. */
.btn-cta-top,
.btn-cta-try {
  color: var(--green-700); padding: 10px 16px; border-radius: 7px;
  font-weight: 700; font-size: 15px; text-decoration: none;
  font-family: var(--font-sans); border: 1px solid var(--gray-200);
  box-shadow: none;
  transition: transform .12s, box-shadow .12s, filter .12s;
  white-space: nowrap;
  min-width: 112px; box-sizing: border-box; text-align: center;
  display: inline-block;
  background: white;
}
.btn-cta-try {
  min-width: 132px;
}
.btn-cta-top:hover,
.btn-cta-try:hover {
  transform: none;
  box-shadow: none;
  filter: none;
}
.btn-cta-top[aria-current="page"],
.btn-cta-try[aria-current="page"] {
  outline: 2px solid var(--green-700); outline-offset: 2px;
}

@media (max-width: 900px) {
  .top-bar { flex-wrap: wrap; gap: 8px; }
  .brand-line { margin-right: 0; }
  .brand-mini { font-size: 22px; }
  .top-nav { order: 3; flex-basis: 100%; margin: 0; justify-content: center; }
  .top-right { gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
  .top-cta-group { width: 100%; justify-content: flex-end; gap: 6px; }
  .lang-switch { font-size: 10px; }
  .lang-switch .lang-current,
  .lang-switch .lang-other { width: 48px; padding: 4px 6px; }
  .btn-cta-top,
  .btn-cta-try { padding: 8px 10px; font-size: 13px; min-width: 98px; }
  .btn-cta-try { min-width: 118px; }
}

@media (max-width: 700px) {
  .top-bar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px 12px;
    align-items: center;
    padding: 12px max(14px, env(safe-area-inset-right)) 14px max(14px, env(safe-area-inset-left));
  }
  .brand-line {
    grid-column: 1;
    grid-row: 1;
    min-width: 0;
    margin-right: 0;
  }
  .brand-mini {
    max-width: 100%;
    font-size: 22px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .top-right {
    display: contents;
  }
  .lang-switch {
    grid-column: 2;
    grid-row: 1;
    justify-self: end;
  }
  .top-nav {
    grid-column: 1 / -1;
    grid-row: 2;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
    margin: 0;
    gap: 4px;
    justify-content: stretch;
  }
  .top-nav a {
    min-width: 0;
    padding: 8px 4px;
    text-align: center;
    overflow-wrap: anywhere;
    line-height: 1.15;
  }
  .top-cta-group {
    grid-column: 1 / -1;
    grid-row: 3;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
    gap: 6px;
    justify-content: stretch;
  }
  .lang-switch { font-size: 10px; }
  .lang-switch .lang-current,
  .lang-switch .lang-other { width: 48px; padding: 4px 6px; }
  .btn-cta-top,
  .btn-cta-try {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-width: 0;
    min-height: 44px;
    padding: 8px 6px;
    font-size: 13px;
    line-height: 1.12;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .btn-cta-try { min-width: 0; }
}

@media (max-width: 380px) {
  .brand-mini {
    font-size: 20px;
  }
  .top-nav a {
    font-size: 13px;
  }
  .btn-cta-top,
  .btn-cta-try {
    font-size: 12.5px;
  }
}

/* Home v2 */
main.home-main {
  max-width: none;
  padding: 0 0 48px;
}
body.home-page {
  background: white;
}
.home-main .page-foot {
  max-width: 1100px;
  margin: 0 auto;
  padding-left: 24px;
  padding-right: 24px;
}
.home-hero {
  min-height: min(520px, 64vh);
  display: flex;
  align-items: center;
  background: white;
  color: var(--gray-900);
}
.home-hero-inner {
  width: min(1100px, 100%);
  margin: 0 auto;
  padding: 72px 24px 58px;
}
.home-kicker {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 1.4px;
  text-transform: uppercase;
  color: var(--green-700);
  margin-bottom: 16px;
}
.home-hero h1 {
  font-family: var(--font-display);
  font-size: 48px;
  line-height: 1.06;
  font-weight: 800;
  color: var(--green-700);
  margin-bottom: 20px;
  max-width: 880px;
}
.home-sub {
  max-width: 700px;
  font-size: 20px;
  line-height: 1.42;
  color: var(--gray-700);
  margin-bottom: 24px;
}
.home-sub + .home-sub {
  margin-top: -12px;
}
.home-note {
  max-width: 680px;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-500);
}
.home-source-band {
  border-top: 1px solid var(--gray-100);
  max-width: 1100px;
  margin: 0 auto;
  padding: 22px 24px 0;
}

/* ── Home: stats band ─────────────────────────────────────────────────
 * Wraps the .promo-stats grid (reused from capabilities.html) on a
 * white background. The promo-stats children are styled for the dark
 * .promo-info block — we re-skin them here for light context.
 */
.home-stats-band {
  max-width: 1100px;
  margin: 28px auto 0;
  padding: 0 24px;
}
.home-stats-band .promo-stats {
  padding: 24px 0;
  margin-bottom: 0;
  border-top: 1px solid var(--gray-200);
  border-bottom: 1px solid var(--gray-200);
}
.home-stats-band .promo-stat-num {
  color: var(--green-700);
}
.home-stats-band .promo-stat-num .promo-stat-plus {
  color: var(--green-900);
}
.home-stats-band .promo-stat-lbl {
  color: var(--gray-500);
}

/* ── Home: two-pillar grid (Saves time / Catches misses) ─────────── */
.home-pillars {
  max-width: 1100px;
  margin: 36px auto 0;
  padding: 0 24px;
}
.home-pillar-h {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--green-700);
  margin: 8px 0 6px;
}
.home-pillar-h--alt {
  margin-top: 48px;
  padding-top: 36px;
  border-top: 1px solid var(--gray-100);
}
.home-pillar-sub {
  font-size: 16px;
  line-height: 1.5;
  color: var(--gray-700);
  margin: 0 0 22px;
  max-width: 720px;
}

/* ── Home: bottom CTA doors row ──────────────────────────────────── */
.home-cta-doors {
  max-width: 1100px;
  margin: 40px auto 24px;
  padding: 22px 24px 0;
  border-top: 1px solid var(--gray-100);
}

body.home-page .btn-primary,
body.home-page .btn-primary:hover {
  background: var(--green-700);
  color: white;
}
body.home-page .btn-secondary {
  background: white;
  color: var(--green-700);
  border-color: var(--gray-200);
}
body.home-page .btn-secondary:hover {
  border-color: var(--green-700);
}
body.home-page .page-foot a {
  color: var(--green-700);
}
body.home-page .home-carousel {
  display: none;
}
.home-carousel {
  width: 100%;
  max-width: 1100px;
  margin-top: 34px;
}
.home-carousel-tabs {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 3px;
  padding: 4px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 8px;
  margin-bottom: 12px;
}
.home-carousel-tab {
  appearance: none;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgba(255,255,255,.74);
  font: 700 13px var(--font-sans);
  padding: 9px 14px;
  cursor: pointer;
  white-space: nowrap;
}
.home-carousel-tab:hover,
.home-carousel-tab.is-active {
  background: white;
  color: #081825;
}
.home-carousel-track {
  position: relative;
  min-height: 300px;
}
.home-carousel-slide {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
  transform: translateY(8px);
  transition: opacity .28s ease, transform .28s ease;
  background: rgba(8, 24, 37, .78);
  border: 1px solid rgba(255,255,255,.16);
  border-top: 4px solid #38bdf8;
  border-radius: 8px;
  padding: 24px 28px;
  box-shadow: 0 18px 45px rgba(0,0,0,.24);
}
.home-carousel-slide:nth-child(2) { border-top-color: var(--amber); }
.home-carousel-slide:nth-child(3) { border-top-color: var(--teal); }
.home-carousel-slide:nth-child(4) { border-top-color: #fb7185; }
.home-carousel-slide.is-active {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}
.home-carousel-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  color: #7dd3fc;
  margin-bottom: 10px;
}
.home-carousel-slide:nth-child(2) .home-carousel-eyebrow { color: #fbbf24; }
.home-carousel-slide:nth-child(3) .home-carousel-eyebrow { color: #5eead4; }
.home-carousel-slide:nth-child(4) .home-carousel-eyebrow { color: #fda4af; }
.home-carousel-slide h2 {
  font-family: var(--font-display);
  font-size: 30px;
  line-height: 1.1;
  color: white;
  margin-bottom: 12px;
}
.home-carousel-slide p {
  max-width: 680px;
  font-size: 15.5px;
  line-height: 1.5;
  color: rgba(255,255,255,.82);
}
.home-carousel-slide ul {
  display: grid;
  gap: 7px;
  list-style: none;
  margin: 16px 0 20px;
}
.home-carousel-slide li {
  position: relative;
  padding-left: 20px;
  color: rgba(255,255,255,.86);
  font-size: 14px;
  line-height: 1.42;
}
.home-carousel-slide li::before {
  content: "";
  position: absolute;
  left: 0;
  top: .62em;
  width: 8px;
  height: 2px;
  background: #7dd3fc;
}
.home-carousel-slide:nth-child(2) li::before { background: #fbbf24; }
.home-carousel-slide:nth-child(3) li::before { background: #5eead4; }
.home-carousel-slide:nth-child(4) li::before { background: #fda4af; }
.home-carousel-cta {
  display: inline-flex;
  align-items: center;
  color: white;
  text-decoration: none;
  font-weight: 800;
  border-bottom: 2px solid rgba(255,255,255,.45);
  padding-bottom: 2px;
}
.home-carousel-cta:hover {
  border-bottom-color: white;
}

.about-hero h1,
.about-split h2,
.about-stats-panel h2 {
  font-family: var(--font-display);
  color: var(--green-900);
}

/* About */
.about-hero {
  padding: 56px 0 28px;
}
.about-hero h1 {
  font-size: 48px;
  line-height: 1.08;
  margin-bottom: 14px;
}
.about-hero p:last-child {
  max-width: 780px;
  font-size: 18px;
  color: var(--gray-700);
}
.about-link-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 34px;
}
.about-link-card {
  display: flex;
  flex-direction: column;
  min-height: 210px;
  padding: 20px;
  background: white;
  border: 1px solid var(--gray-200);
  border-top: 4px solid #0284c7;
  border-radius: 8px;
  color: inherit;
  text-decoration: none;
}
.about-link-card:nth-child(2) { border-top-color: var(--amber); }
.about-link-card:nth-child(3) { border-top-color: var(--green-600); }
.about-link-card span {
  font-family: var(--font-display);
  font-size: 24px;
  color: var(--green-900);
}
.about-link-card p {
  color: var(--gray-700);
  margin: 12px 0 18px;
  font-size: 14.5px;
}
.about-link-card strong {
  margin-top: auto;
  color: var(--green-700);
}
.about-link-card:hover {
  border-color: var(--green-600);
}
.about-split {
  display: grid;
  grid-template-columns: 1.25fr .75fr;
  gap: 28px;
  margin-bottom: 28px;
}
.about-split h2,
.about-stats-panel h2 {
  font-size: 28px;
  margin-bottom: 16px;
}
.about-principles {
  display: grid;
  gap: 12px;
}
.about-principle {
  background: white;
  border-left: 3px solid var(--teal);
  padding: 15px 16px;
}
.about-principle:nth-child(2) { border-left-color: var(--amber); }
.about-principle:nth-child(3) { border-left-color: var(--red); }
.about-principle:nth-child(4) { border-left-color: var(--green-600); }
.about-principle h3 {
  font-size: 16px;
  color: var(--gray-900);
  margin-bottom: 4px;
}
.about-principle p {
  font-size: 14px;
  color: var(--gray-700);
}
.about-stats-panel {
  background: #081825;
  color: white;
  padding: 22px;
  border-radius: 8px;
}
.about-stats-panel h2 {
  color: white;
}
.about-stats {
  display: grid;
  gap: 10px;
}
.about-stat {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
  border-bottom: 1px solid rgba(255,255,255,.14);
  padding-bottom: 9px;
}
.about-stat strong {
  font-family: var(--font-display);
  font-size: 30px;
}
.about-stat span {
  color: rgba(255,255,255,.72);
}
.about-release {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid rgba(255,255,255,.14);
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(255,255,255,.62);
}

@media (max-width: 920px) {
  .about-split {
    grid-template-columns: 1fr;
  }
  .about-link-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 700px) {
  .home-hero {
    min-height: auto;
  }
  .home-hero-inner {
    padding: 42px 18px 52px;
  }
  .home-hero h1 {
    font-size: 44px;
    line-height: 1;
  }
  .home-sub {
    font-size: 16px;
    line-height: 1.45;
    margin-bottom: 16px;
  }
  .home-sub + .home-sub {
    margin-top: -6px;
  }
  .home-source-band {
    padding-top: 18px;
  }
  .home-carousel {
    margin-top: 26px;
  }
  .home-carousel-tabs {
    display: grid;
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .home-carousel-tab {
    min-width: 0;
    padding: 8px 6px;
    font-size: 12px;
  }
  .home-carousel-track {
    min-height: 405px;
  }
  .home-carousel-slide {
    padding: 18px 18px;
  }
  .home-carousel-slide h2 {
    font-size: 24px;
  }
  .home-carousel-slide p,
  .home-carousel-slide li {
    font-size: 13.5px;
  }
  .about-hero {
    padding-top: 36px;
  }
  .about-hero h1 {
    font-size: 36px;
  }
}

@media (max-width: 380px) {
  .home-hero-inner {
    padding-top: 34px;
  }
  .home-hero h1 {
    font-size: 40px;
  }
  .home-sub {
    font-size: 16px;
  }
  .try-page h1 {
    font-size: 28px;
    line-height: 1.06;
  }
  .try-page .lead {
    font-size: 14.5px;
  }
}

/* Hero */
.hero {
  background:
    radial-gradient(ellipse at top left, var(--green-100) 0%, transparent 55%),
    radial-gradient(ellipse at bottom right, #ccfbf1 0%, transparent 55%),
    var(--gray-50);
  padding: 60px 24px 50px;
  margin: 0 -24px;
}
.hero-content { max-width: 880px; margin: 0 auto; }
.eyebrow {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 1.5px;
  text-transform: uppercase; color: var(--green-700); margin-bottom: 16px;
}
.hero h1 {
  font-family: var(--font-display); font-weight: 700; font-size: 44px;
  line-height: 1.12; color: var(--green-900); margin-bottom: 20px;
}
.hero-sub {
  font-size: 18px; color: var(--gray-700); max-width: 720px;
  margin-bottom: 28px;
}
.cta-row { display: flex; gap: 12px; flex-wrap: wrap; }
.btn {
  display: inline-block; padding: 12px 22px; border-radius: 8px;
  font-weight: 600; font-size: 15px; text-decoration: none;
  font-family: var(--font-sans); cursor: pointer; border: none;
}
.btn-primary { background: var(--green-700); color: white; }
.btn-primary:hover { background: var(--green-600); }
.btn-secondary {
  background: white; color: var(--green-700);
  border: 1px solid var(--gray-200);
}
.btn-secondary:hover { border-color: var(--green-600); }
.hero-corpus {
  margin-top: 32px; padding: 18px 22px;
  background: white; border-radius: 12px;
  border: 1px solid var(--green-100);
  box-shadow: 0 4px 14px rgba(10, 46, 26, 0.05);
  display: flex; gap: 22px; align-items: center;
  max-width: 720px;
}
.hcorpus-num {
  font-family: var(--font-display); font-size: 56px;
  color: var(--green-700); line-height: 1;
  flex-shrink: 0;
}
.hcorpus-text {
  font-size: 14.5px; color: var(--gray-700);
  line-height: 1.55;
}
.hcorpus-text strong { color: var(--green-900); }
.hero-meta {
  margin-top: 24px; font-size: 12px; color: var(--gray-500);
  font-family: var(--font-mono);
}

/* Numbers */
.numbers { padding: 50px 0 30px; }
.numbers h2, .problem h2, .how h2, .gallery h1, .try-page h1 {
  font-family: var(--font-display); font-size: 30px;
  color: var(--green-900); margin-bottom: 24px;
}
.numbers-lead {
  font-size: 15px; color: var(--gray-700); margin-bottom: 24px;
  max-width: 880px;
}
.num-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 12px;
}
.num-grid--rich {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.num-card {
  background: white; border: 1px solid var(--gray-200); border-radius: 10px;
  padding: 20px 18px; border-top: 3px solid var(--green-600);
  display: flex; flex-direction: column;
}
.num-card--accent { border-top-color: var(--teal); background: linear-gradient(180deg, var(--green-50) 0%, white 40%); }
.num-big {
  font-family: var(--font-display); font-size: 38px; line-height: 1;
  color: var(--green-900);
}
.num-lbl {
  font-size: 14px; color: var(--gray-900); margin-top: 6px;
  font-weight: 700;
}
.num-detail {
  font-family: var(--font-mono); font-size: 11px; color: var(--gray-500);
  margin-top: 4px;
}
.num-text {
  font-size: 13px; color: var(--gray-700); margin-top: 10px;
  line-height: 1.5;
}
.num-text code {
  font-family: var(--font-mono); font-size: 11px;
  background: var(--gray-100); padding: 1px 5px; border-radius: 3px;
}
.num-text em { font-style: normal; font-family: var(--font-mono); font-size: 12px; color: var(--green-700); }
.num-foot {
  font-size: 13px; color: var(--gray-700); margin-top: 18px;
  padding: 14px 16px; background: var(--amber-bg);
  border-left: 3px solid var(--amber); border-radius: 4px;
}
.num-foot code { font-family: var(--font-mono); font-size: 12px; }

/* Problem */
.problem { padding: 30px 0; }
.problem-text {
  font-size: 16px; color: var(--gray-700); max-width: 880px;
  line-height: 1.65;
}

/* How it works */
.how { padding: 30px 0; }
.how-lead {
  font-size: 15px; color: var(--gray-700); max-width: 880px;
  margin-bottom: 22px;
}

/* Trust strip — sits above the data flow, sets AI/LLM expectations up front. */
.trust-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
  margin: 22px 0 18px;
}
.trust-pill {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 12px 14px; border-radius: 8px;
  font-size: 13.5px; line-height: 1.45;
  border: 1px solid var(--gray-200);
  background: white;
}
.trust-pill--no { border-left: 3px solid var(--red); }
.trust-pill--yes { border-left: 3px solid var(--green-600); background: var(--green-50); }
.trust-pill-mark {
  font-family: var(--font-mono); font-weight: 700;
  width: 22px; height: 22px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%; font-size: 14px;
}
.trust-pill--no .trust-pill-mark { background: var(--red-bg); color: var(--red); }
.trust-pill--yes .trust-pill-mark { background: var(--green-100); color: var(--green-700); }
.trust-pill-text { color: var(--gray-700); }
.trust-pill-text strong { color: var(--gray-900); }

/* Data flow — replaces the prior MDT figure. Four stages on a dark backdrop
   so the open-standards / biomarker chips read as live data, not decoration. */
.dataflow {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr;
  gap: 0; align-items: stretch;
  background: linear-gradient(135deg, #0a2e1a 0%, #0d3f24 60%, #0f4d2c 100%);
  padding: 26px 22px; border-radius: 12px;
  margin: 0 0 28px;
  box-shadow: 0 1px 0 rgba(0,0,0,.04);
}
.dataflow-stage {
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(220,252,231,.10);
  border-radius: 10px;
  padding: 16px 14px;
  color: var(--green-100);
  display: flex; flex-direction: column; gap: 9px;
  min-width: 0;
}
.dataflow-stage[data-stage="1"] { border-top: 3px solid var(--teal); }
.dataflow-stage[data-stage="2"] { border-top: 3px solid #38bdf8; }
.dataflow-stage[data-stage="3"] { border-top: 3px solid var(--amber); }
.dataflow-stage[data-stage="4"] { border-top: 3px solid var(--green-500); }
.dataflow-num {
  font-family: var(--font-mono); font-size: 10.5px;
  color: var(--green-100); opacity: .55; letter-spacing: 1px;
}
.dataflow-title {
  font-family: var(--font-display); font-size: 17px;
  color: white; line-height: 1.25;
}
.dataflow-body {
  font-size: 12.5px; line-height: 1.5;
  color: rgba(220,252,231,.85);
}
.dataflow-body strong { color: white; }
.dataflow-arrow {
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; color: var(--green-100); opacity: .35;
  padding: 0 4px; user-select: none;
}
.biomarker-row, .std-row {
  display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px;
}
.biomarker {
  font-family: var(--font-mono); font-size: 10.5px;
  background: rgba(220,38,38,.18); color: #fecaca;
  border: 1px solid rgba(252,165,165,.30);
  padding: 2px 7px; border-radius: 3px; letter-spacing: 0.3px;
}
.std-pill {
  font-family: var(--font-mono); font-size: 10.5px;
  background: rgba(13,148,136,.22); color: #99f6e4;
  border: 1px solid rgba(94,234,212,.30);
  padding: 2px 7px; border-radius: 3px; letter-spacing: 0.3px;
}
.flow-list { list-style: none; padding: 0; margin: 4px 0 0; font-size: 12.5px; }
.flow-list li {
  display: flex; align-items: baseline; gap: 8px;
  padding: 3px 0; color: rgba(220,252,231,.85);
}
.rf-tag {
  font-family: var(--font-mono); font-size: 9.5px; font-weight: 600;
  padding: 1px 6px; border-radius: 3px; flex-shrink: 0;
  letter-spacing: 0.5px;
}
.rf-tag.rf-red { background: var(--red); color: white; }
.rf-tag.rf-amber { background: var(--amber); color: white; }
.rf-tag.rf-teal { background: var(--teal); color: white; }

@media (max-width: 980px) {
  .dataflow { grid-template-columns: 1fr; padding: 18px 14px; }
  .dataflow-arrow { transform: rotate(90deg); padding: 6px 0; font-size: 18px; }
}

/* Why-today CTA block — closes the section with concrete reasons + CTA. */
.why-today {
  background: white;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 26px 24px;
}
.why-today-h {
  font-family: var(--font-display); font-size: 24px;
  color: var(--green-900); margin-bottom: 16px; line-height: 1.2;
}
.why-today-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}
.why-card {
  background: var(--green-50);
  border-left: 3px solid var(--green-600);
  padding: 13px 15px; border-radius: 6px;
}
.why-card-h {
  font-weight: 600; color: var(--green-900);
  font-size: 14.5px; margin-bottom: 5px;
}
.why-card p {
  font-size: 13px; color: var(--gray-700); line-height: 1.5;
}
.why-card p strong { color: var(--green-900); }
.why-today-foot {
  font-size: 14px; color: var(--gray-700);
  line-height: 1.6; margin-bottom: 18px;
  background: var(--red-bg);
  border-left: 3px solid var(--red);
  border-radius: 0 4px 4px 0;
  padding: 12px 14px;
}

/* Gallery */
.gallery { padding: 32px 0; }
.gallery .lead {
  font-size: 15px; color: var(--gray-700); margin-bottom: 20px;
  max-width: 760px;
}
.case-controls {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 16px; margin-bottom: 22px;
}
.case-chips {
  display: flex; flex-wrap: wrap; gap: 8px; flex: 1 1 auto;
}
.case-chip {
  font: inherit; font-size: 13px;
  padding: 6px 12px; border-radius: 999px;
  border: 1px solid var(--gray-200);
  background: white; color: var(--gray-700);
  cursor: pointer;
  transition: border-color .15s, background .15s, color .15s;
}
.case-chip:hover { border-color: var(--green-600); color: var(--green-900); }
.case-chip.is-active {
  background: var(--green-100); border-color: var(--green-600);
  color: var(--green-900);
}
.case-chip .chip-n {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--gray-500); margin-left: 4px;
}
.case-chip.is-active .chip-n { color: var(--green-700); }
.case-sort {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--gray-700);
}
.case-sort select {
  font: inherit; font-size: 13px;
  padding: 5px 8px; border-radius: 6px;
  border: 1px solid var(--gray-200);
  background: white; color: var(--gray-900);
  cursor: pointer;
}
.case-empty {
  padding: 40px 0; text-align: center;
  color: var(--gray-500); font-size: 14px;
}
.case-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px; margin-bottom: 36px;
}
.case-card {
  display: block; background: white; border-radius: 10px;
  border: 1px solid var(--gray-200); padding: 18px;
  text-decoration: none; color: var(--gray-900);
  transition: border-color .15s, box-shadow .15s, transform .15s;
}
.case-card:hover {
  border-color: var(--green-600);
  box-shadow: 0 6px 16px rgba(10, 46, 26, .07);
  transform: translateY(-1px);
}
.case-badge-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  margin-bottom: 10px;
}
.case-badge {
  display: inline-block; font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 1px; text-transform: uppercase;
  padding: 3px 8px; border-radius: 4px;
}
.case-json-only {
  display: inline-block; font-family: var(--font-mono);
  font-size: 9.5px; letter-spacing: 0.6px;
  padding: 2px 7px; border-radius: 3px;
  background: var(--gray-100); color: var(--gray-500);
  cursor: help;
}
.case-quality {
  display: inline-block; font-family: var(--font-mono);
  font-size: 9.5px; letter-spacing: 0.4px;
  padding: 2px 7px; border-radius: 3px;
  border: 1px solid transparent;
}
.quality-showcase {
  background: var(--green-50); color: var(--green-700);
  border-color: var(--green-200);
}
.quality-curated {
  background: #eef2ff; color: #3730a3; border-color: #c7d2fe;
}
.quality-diagnostic {
  background: var(--amber-bg); color: var(--amber); border-color: #f7d89b;
}
.quality-starter {
  background: var(--gray-50); color: var(--gray-500); border-color: var(--gray-200);
}
.bdg-plan { background: var(--green-100); color: var(--green-700); }
.bdg-diag { background: var(--amber-bg); color: var(--amber); }
.case-card h3 {
  font-family: var(--font-display); font-size: 18px;
  color: var(--green-900); margin-bottom: 8px; line-height: 1.25;
}
.case-card p { font-size: 13px; color: var(--gray-700); }
.case-foot {
  margin-top: 12px; font-family: var(--font-mono);
  font-size: 11px; color: var(--gray-500);
}

/* ── Disease drill-down (gallery rev 2026-04-27) ────────────────────── */
.disease-stage { margin-bottom: 28px; }
.disease-search-row {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 18px;
  max-width: 560px;
}
.disease-search {
  flex: 1 1 auto;
  font: inherit; font-size: 15px;
  padding: 11px 16px;
  border-radius: 8px;
  border: 1.5px solid var(--gray-200);
  background: white; color: var(--gray-900);
  transition: border-color .15s, box-shadow .15s;
}
.disease-search:focus {
  outline: none;
  border-color: var(--green-600);
  box-shadow: 0 0 0 3px rgba(22, 101, 52, 0.10);
}
.disease-search-count {
  font-family: var(--font-mono); font-size: 13px;
  color: var(--gray-500);
  flex: 0 0 auto;
}
.disease-tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.disease-tile {
  display: flex; flex-direction: column; align-items: flex-start;
  gap: 6px;
  padding: 16px 18px; min-height: 78px;
  border-radius: 10px;
  border: 1.5px solid var(--gray-200);
  background: white; color: var(--gray-900);
  font: inherit; text-align: left;
  cursor: pointer;
  transition: border-color .15s, box-shadow .15s, transform .15s, background .15s;
}
.disease-tile:hover {
  border-color: var(--green-600);
  background: var(--green-50);
  box-shadow: 0 6px 16px rgba(10, 46, 26, .08);
  transform: translateY(-1px);
}
.disease-tile:focus-visible {
  outline: 3px solid var(--green-600); outline-offset: 2px;
}
.dt-label {
  font-family: var(--font-display); font-size: 16px;
  color: var(--green-900); line-height: 1.2;
  font-weight: 600;
}
.dt-icd {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--gray-500);
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  padding: 2px 6px;
}
.dt-count {
  font-family: var(--font-mono); font-size: 11.5px;
  color: var(--gray-500); letter-spacing: 0.3px;
}
.dt-quality {
  font-family: var(--font-mono); font-size: 10.5px;
  color: var(--green-700);
  background: var(--green-50);
  border: 1px solid var(--green-200);
  border-radius: 4px;
  padding: 2px 6px;
}
.disease-tile:hover .dt-icd {
  border-color: var(--green-200);
  color: var(--green-700);
}
.disease-tile:hover .dt-count { color: var(--green-700); }
.disease-empty {
  padding: 40px 0; text-align: center;
  color: var(--gray-500); font-size: 14px;
}

/* Stage 2: cases for selected disease */
.case-stage { margin-bottom: 28px; }
.case-back-btn {
  font: inherit; font-size: 13px;
  padding: 7px 14px;
  border-radius: 6px;
  border: 1px solid var(--gray-200);
  background: white; color: var(--gray-700);
  cursor: pointer;
  margin-bottom: 18px;
  transition: border-color .15s, background .15s, color .15s;
}
.case-back-btn:hover {
  border-color: var(--green-600);
  background: var(--green-50);
  color: var(--green-900);
}
.case-list-header {
  display: flex; align-items: baseline; gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--gray-200);
}
.case-list-header h2 {
  font-family: var(--font-display); font-size: 22px;
  color: var(--green-900); margin: 0;
}
.case-list-count {
  font-family: var(--font-mono); font-size: 12px;
  color: var(--gray-500);
}

.kb-stats { margin-top: 16px; }

/* Try page */
.try-page { padding: 32px 0; }
.try-page .lead {
  font-size: 15px; color: var(--gray-700); margin-bottom: 24px;
  max-width: 800px;
}
.try-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
  align-items: start;
}
.try-input label {
  display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px;
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--gray-700); font-weight: 600;
}
.try-input select, .try-input textarea {
  font-family: var(--font-mono); font-size: 13px;
  padding: 10px 12px; border: 1px solid var(--gray-200);
  border-radius: 6px; background: white;
}
.try-input textarea {
  width: 100%; resize: vertical; line-height: 1.45;
  min-height: 380px;
}
.try-input select { width: 100%; }
.try-input select:focus, .try-input textarea:focus {
  outline: 2px solid var(--green-600); outline-offset: 0;
  border-color: var(--green-600);
}
.try-actions { display: flex; gap: 8px; margin-top: 8px; }
.status {
  position: relative; overflow: hidden;
  font-family: var(--font-mono); font-size: 12px; color: var(--gray-700);
  padding: 8px 12px; min-height: 32px; margin-top: 12px;
  background: var(--gray-50); border-radius: 4px;
  border-left: 3px solid var(--gray-200);
}
.status.is-busy {
  padding-bottom: 16px;
}
.status.is-busy::after {
  content: ""; position: absolute; left: 12px; right: 12px; bottom: 6px;
  height: 3px; border-radius: 999px;
  background: linear-gradient(90deg, transparent, #0284c7, #0d9488, transparent);
  animation: status-inline-progress 1.25s ease-in-out infinite;
}
.status[data-kind="ok"] {
  background: var(--green-50); border-left-color: var(--green-500);
  color: var(--green-800);
}
.status[data-kind="warn"] {
  background: #fff8e1; border-left-color: #f59e0b;
  color: #92400e;
}
/* Prominent top status banner — visible above the toolbar so users see
   the engine is mid-load. Animated spinner while busy; turns green on ok. */
.status-top {
  display: flex; align-items: flex-start; gap: 12px;
  font-family: var(--font-sans, inherit); font-size: 15px; font-weight: 600;
  padding: 12px 18px; margin: 0 0 16px 0;
  border-radius: 8px;
  background: #e0f2fe; color: #075985;
  border: 1px solid #7dd3fc;
  box-shadow: 0 1px 4px rgba(2,132,199,0.10);
  transition: background 200ms ease, color 200ms ease, border-color 200ms ease;
}
.status-top[hidden] { display: none; }
.status-top.is-ok {
  background: var(--green-50); color: var(--green-800); border-color: var(--green-500);
}
.status-top.is-warn {
  background: #fff8e1; color: #92400e; border-color: #f59e0b;
}
.status-top-spinner {
  width: 16px; height: 16px; flex: 0 0 16px;
  border: 2.5px solid #bae6fd; border-top-color: #0284c7;
  border-radius: 50%;
  animation: status-top-spin 700ms linear infinite;
}
.status-top.is-ok .status-top-spinner {
  border: 2.5px solid var(--green-500); border-top-color: transparent;
  animation: none;
  /* Render as a check ✓ via CSS — repurpose the spinner box. */
  border-radius: 0; background: transparent;
  width: 14px; height: 8px;
  border-left: 0; border-right: 3px solid var(--green-600);
  border-top: 0; border-bottom: 3px solid var(--green-600);
  transform: rotate(45deg) translateY(-2px);
}
.status-top.is-warn .status-top-spinner {
  animation: none;
  border-color: #f59e0b;
  border-radius: 50%;
}
.status-top:not(.is-busy) .status-top-spinner {
  animation: none;
}
.status-top-body {
  display: flex; flex: 1 1 auto; min-width: 0;
  flex-direction: column; gap: 8px;
}
.status-top-text {
  line-height: 1.25;
}
.status-top-progress {
  display: block; width: 100%; height: 5px;
  overflow: hidden; border-radius: 999px;
  background: rgba(2, 132, 199, 0.18);
}
.status-top-progress-fill {
  display: block; height: 100%; width: var(--status-progress, 34%);
  border-radius: inherit;
  background: linear-gradient(90deg, #0284c7, #0d9488);
  transition: width 220ms ease;
}
.status-top:not(.is-busy) .status-top-progress {
  display: none;
}
.status-top.is-busy:not(.has-progress) .status-top-progress-fill {
  width: 34%;
  animation: status-top-progress 1.25s ease-in-out infinite;
}
@keyframes status-top-spin {
  to { transform: rotate(360deg); }
}
@keyframes status-top-progress {
  from { transform: translateX(-120%); }
  to { transform: translateX(320%); }
}
@keyframes status-inline-progress {
  from { transform: translateX(-105%); }
  to { transform: translateX(105%); }
}
.error {
  font-family: var(--font-mono); font-size: 12px; color: var(--red);
  background: var(--red-bg); padding: 10px 12px; border-radius: 4px;
  margin-top: 10px; white-space: pre-wrap;
  border-left: 3px solid var(--red);
}
.try-output {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 10px; min-height: 600px;
  display: flex; flex-direction: column; overflow: hidden;
}
.placeholder {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 40px; text-align: center; color: var(--gray-500);
}
.placeholder-icon {
  font-size: 48px; color: var(--green-600); margin-bottom: 16px;
  font-family: var(--font-display);
}
#resultFrame {
  flex: 1; width: 100%; height: 800px; border: none;
}

/* Result toolbar (PDF + lang switcher) — appears above #resultFrame
   once a Plan / DiagnosticBrief is rendered. */
.result-toolbar {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 12px; padding: 10px 14px; background: var(--gray-50);
  border: 1px solid var(--gray-200); border-bottom: none;
  border-top-left-radius: 10px; border-top-right-radius: 10px;
}
.rt-btn {
  font-family: var(--font-sans); font-size: 13px; font-weight: 600;
  background: var(--green-700); color: white;
  border: none; border-radius: 6px; padding: 8px 14px;
  cursor: pointer; transition: background 0.15s;
}
.rt-btn:hover { background: var(--green-800); }
.rt-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.rt-lang-group {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--gray-700); font-weight: 600;
}
.rt-lang-label { margin-right: 2px; }
.rt-lang-btn {
  font-family: var(--font-mono); font-size: 11px; font-weight: 600;
  letter-spacing: 0.5px;
  background: white; color: var(--gray-700);
  border: 1px solid var(--gray-200); border-radius: 4px;
  padding: 5px 10px; cursor: pointer; transition: all 0.15s;
}
.rt-lang-btn:hover { background: var(--gray-100); }
.rt-lang-btn.is-active {
  background: var(--green-700); color: white; border-color: var(--green-700);
}
.rt-lang-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Questionnaire UI (try.html) */
.quest-toolbar {
  display: flex; gap: 16px; align-items: flex-end; margin: 24px 0 22px;
  flex-wrap: wrap; padding: 22px 24px; background: linear-gradient(135deg, #f0fdf4 0%, white 60%);
  border: 2px solid var(--green-600); border-radius: 14px;
  box-shadow: 0 4px 16px rgba(22, 101, 52, 0.08);
  position: relative;
}
.quest-toolbar[data-step-label]::before {
  content: attr(data-step-label);
  position: absolute; top: -11px; left: 18px;
  background: var(--green-700); color: white;
  font-size: 11px; font-weight: 700; letter-spacing: 0.6px;
  text-transform: uppercase; padding: 3px 12px; border-radius: 4px;
  font-family: var(--font-mono);
}
/* Make the FIRST TWO selects (Хвороба + Приклад) visually dominant.
   Subsequent labels (mode buttons, JSON toggle) keep the smaller original styling. */
.qt-label {
  display: flex; flex-direction: column; gap: 6px; min-width: 280px;
  font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--gray-700); font-weight: 600;
}
.quest-toolbar > .qt-label:nth-of-type(-n+2) {
  flex: 1 1 320px; min-width: 320px;
}
.quest-toolbar > .qt-label:nth-of-type(-n+2) {
  font-size: 13px; color: var(--green-800); font-weight: 700;
  letter-spacing: 0.4px;
}
.qt-label select, .qt-label input, .qt-label textarea {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  font-family: var(--font-sans); font-size: 13px;
  padding: 8px 10px; border: 1px solid var(--gray-200);
  border-radius: 6px; background: white;
  text-transform: none; letter-spacing: normal; font-weight: 400;
  color: var(--gray-900);
}
/* Bigger, bolder selects for the first two dropdowns */
.quest-toolbar > .qt-label:nth-of-type(-n+2) select {
  font-size: 16px; padding: 12px 14px; font-weight: 500;
  border: 2px solid var(--green-600); border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.quest-toolbar > .qt-label:nth-of-type(-n+2) select:hover {
  border-color: var(--green-700);
  box-shadow: 0 2px 6px rgba(22, 101, 52, 0.15);
}
.quest-toolbar > .qt-label:nth-of-type(-n+2) select:focus {
  outline: none; border-color: var(--green-500);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.25);
}
.qt-spacer { flex: 1; }
.qt-modes {
  display: inline-flex; border: 1px solid var(--gray-200);
  border-radius: 7px; overflow: hidden; background: var(--gray-50);
}
.mode-btn {
  background: transparent; color: var(--gray-700); border: none;
  padding: 8px 14px; font-size: 12.5px; cursor: pointer;
  font-family: var(--font-sans); font-weight: 600;
}
.mode-btn.active {
  background: var(--green-700); color: white;
}
.qt-reset {
  padding: 8px 14px; font-size: 12.5px;
}
.quest-readiness {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 8px; padding: 12px 14px; margin: -8px 0 18px;
}
.quest-readiness-head {
  display: flex; justify-content: space-between; gap: 12px;
  align-items: baseline; margin-bottom: 8px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  letter-spacing: 0.5px; text-transform: uppercase; color: var(--gray-700);
}
.quest-readiness-score {
  color: var(--green-700); white-space: nowrap;
}
.quest-readiness-critical {
  margin-top: 7px; font-size: 12.5px; color: var(--gray-600);
  line-height: 1.45;
}
.quest-readiness-critical[data-kind="ok"] { color: var(--green-700); font-weight: 600; }
.quest-readiness-critical[data-kind="warn"] { color: var(--amber); font-weight: 600; }
.quest-actions-top.quest-cta {
  display: grid; grid-template-columns: minmax(220px, 1.4fr) minmax(150px, 1fr) minmax(150px, 1fr);
  gap: 10px; margin: -4px 0 18px; padding: 12px;
  background: white; border: 1px solid var(--green-200); border-radius: 8px;
  box-shadow: 0 3px 12px rgba(22, 101, 52, 0.08);
}
.quest-actions-top.quest-cta .btn {
  min-height: 44px; width: 100%;
}
.quest-grid {
  display: grid; grid-template-columns: 1fr 380px; gap: 18px;
  margin-bottom: 24px; align-items: start;
}
.quest-grid > * {
  min-width: 0;
}
.quest-form-pane {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 10px; padding: 20px 22px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}
#jsonPane textarea { width: 100%; font-family: var(--font-mono); }
.quest-empty {
  text-align: center; color: var(--gray-500); padding: 60px 20px;
  font-size: 14px;
}
.quest-intro {
  background: var(--green-50); border-left: 3px solid var(--green-600);
  padding: 12px 16px; border-radius: 4px; margin-bottom: 18px;
  font-size: 13.5px; color: var(--gray-700); line-height: 1.55;
}
.quest-group {
  border-top: 1px solid var(--gray-100); padding-top: 18px; margin-top: 18px;
}
.quest-group:first-child { border-top: none; padding-top: 0; margin-top: 0; }
.quest-group h3 {
  font-family: var(--font-display); font-size: 17px;
  color: var(--green-900); margin-bottom: 4px;
}
.quest-group-desc {
  font-size: 12.5px; color: var(--gray-500); margin-bottom: 12px;
}
.quest-q {
  margin: 14px 0; padding: 12px 14px;
  background: var(--gray-50); border-radius: 6px;
  border-left: 2px solid var(--gray-200);
}
.quest-q-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 6px; gap: 12px;
}
.quest-q-label {
  font-weight: 600; font-size: 13.5px; color: var(--gray-900); flex: 1;
}
.quest-q input[type="number"], .quest-q input[type="text"], .quest-q select {
  width: 100%; max-width: 320px; padding: 7px 10px;
  border: 1px solid var(--gray-200); border-radius: 5px;
  font-family: var(--font-sans); font-size: 13px; background: white;
}
.quest-q input:focus, .quest-q select:focus {
  outline: 2px solid var(--green-600); outline-offset: 0;
  border-color: var(--green-600);
}
.quest-units {
  display: inline-block; margin-left: 8px; font-size: 12px;
  color: var(--gray-500); font-family: var(--font-mono);
}
.quest-helper {
  font-size: 12px; color: var(--gray-500);
  margin-top: 6px; line-height: 1.45;
}
.quest-triggers {
  display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px;
}
.trigger-pill {
  font-family: var(--font-mono); font-size: 10px;
  background: var(--green-100); color: var(--green-700);
  padding: 2px 6px; border-radius: 3px; letter-spacing: 0.3px;
}
.impact-pill {
  display: inline-block; font-family: var(--font-mono); font-size: 9.5px;
  letter-spacing: 0.6px; padding: 2px 7px; border-radius: 3px;
  text-transform: uppercase; font-weight: 600;
}
.impact-critical { background: var(--red-bg); color: var(--red); }
.impact-required { background: var(--amber-bg); color: var(--amber); }
.impact-recommended { background: var(--green-100); color: var(--green-700); }
.impact-optional { background: var(--gray-100); color: var(--gray-500); }

.quest-q[data-impact="critical"] {
  border-left: 4px solid var(--red);
  background: linear-gradient(to right, color-mix(in srgb, var(--red) 6%, var(--gray-50)), var(--gray-50) 60%);
}
.quest-q[data-impact="required"] {
  border-left: 4px solid var(--amber);
  background: linear-gradient(to right, color-mix(in srgb, var(--amber) 6%, var(--gray-50)), var(--gray-50) 60%);
}
.quest-q[data-impact="recommended"] { border-left: 3px solid var(--green-600); }

.quest-whatif {
  margin-top: 10px; padding: 8px 10px;
  background: white; border: 1px dashed var(--gray-200);
  border-left: 3px solid var(--green-600);
  border-radius: 4px;
  font-size: 12px;
}
.quest-whatif .whatif-head {
  font-family: var(--font-mono); font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--green-700); font-weight: 600; margin-bottom: 5px;
}
.quest-whatif ul { list-style: none; padding: 0; margin: 0; }
.quest-whatif li {
  color: var(--gray-700); margin: 3px 0;
  line-height: 1.5;
}
.quest-whatif .whatif-alt {
  font-weight: 600; color: var(--gray-900); margin-right: 4px;
}
.quest-whatif code {
  font-size: 11px; padding: 1px 5px; background: var(--gray-100);
  border-radius: 3px; color: var(--green-900);
}
.quest-whatif .wf-add { color: var(--red); font-weight: 600; }
.quest-whatif .wf-rm { color: var(--gray-500); font-weight: 600; }

/* Locked state — fields pre-filled from a loaded example. Visually
   muted but legible; the user opts in to editing via the personalize
   button which removes .locked from every wrapper. */
.quest-q.locked {
  opacity: 0.78;
}
.quest-q.locked input,
.quest-q.locked select,
.quest-q.locked textarea {
  background: var(--gray-100); color: var(--gray-700);
  cursor: not-allowed;
}
.quest-q.locked .quest-q-label::after {
  content: " 🔒"; font-size: 11px; opacity: 0.6;
}

.example-lock-banner {
  display: flex; gap: 14px; align-items: center; justify-content: space-between;
  background: var(--green-50); border: 1px solid var(--green-600);
  border-left: 4px solid var(--green-600);
  padding: 12px 16px; border-radius: 6px; margin-bottom: 18px;
}
.example-lock-banner .elb-text {
  font-size: 13px; line-height: 1.5; color: var(--gray-700); flex: 1;
  min-width: 0;
}
.example-lock-banner .elb-btn {
  white-space: nowrap; flex-shrink: 0;
}

.quest-side {
  position: sticky; top: 20px;
  display: flex; flex-direction: column; gap: 12px;
  min-width: 0;
}
.quest-build-card {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 8px; padding: 14px 16px;
  min-width: 0;
}
.build-card-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; margin-bottom: 10px;
}
.build-card-head h3 {
  font-family: var(--font-display); font-size: 16px;
  color: var(--green-900); margin: 0;
}
.build-state {
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
  letter-spacing: 0.5px; text-transform: uppercase;
  color: var(--green-800); background: var(--green-50);
  border: 1px solid var(--green-100); border-radius: 4px;
  padding: 3px 6px; white-space: nowrap;
}
.build-meta {
  display: grid; gap: 8px; margin: 0;
}
.build-meta div {
  display: grid; grid-template-columns: 74px 1fr; gap: 8px;
  align-items: baseline;
}
.build-meta dt {
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
  letter-spacing: 0.6px; text-transform: uppercase;
  color: var(--gray-500);
}
.build-meta dd {
  margin: 0; min-width: 0; overflow-wrap: anywhere;
  font-family: var(--font-mono); font-size: 11px; color: var(--gray-800);
}
.offline-cache-progress {
  margin-top: 10px;
}
.offline-cache-bar {
  height: 7px; border-radius: 4px; overflow: hidden;
  background: var(--gray-100); border: 1px solid var(--gray-200);
}
.offline-cache-fill {
  width: 0%; height: 100%; border-radius: 4px;
  background: linear-gradient(90deg, var(--green-500), var(--green-700));
  transition: width .2s ease;
}
.offline-cache-text {
  margin-top: 5px; font-family: var(--font-mono); font-size: 10px;
  color: var(--gray-600); overflow-wrap: anywhere;
}
.impact-bar {
  background: var(--gray-100); height: 8px; border-radius: 4px;
  overflow: hidden; margin-bottom: 6px;
}
.impact-bar-fill {
  background: linear-gradient(90deg, var(--green-500), var(--green-600));
  height: 100%; width: 0%; transition: width .3s ease;
}

/* P4: enriched fired-RF item — shows id + direction + definition + sources. */
.rf-fired-item {
  background: var(--green-50); border-left: 3px solid var(--green-600);
  border-radius: 4px; padding: 8px 10px; margin: 6px 0 !important;
}
.rf-fired-head {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-bottom: 4px;
}
.rf-fired-head code {
  font-size: 10.5px;
}
.rf-dir {
  font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.5px;
  padding: 1px 6px; border-radius: 3px; text-transform: uppercase;
  font-weight: 600;
}
.rf-dir-hold        { background: var(--red-bg, #fef2f2); color: var(--red, #b91c1c); }
.rf-dir-intensify   { background: var(--amber-bg, #fef3c7); color: var(--amber, #b45309); }
.rf-dir-de-escalate { background: var(--gray-100); color: var(--gray-700); }
.rf-dir-investigate { background: var(--gray-100); color: var(--gray-500); }
.rf-fired-defn {
  font-size: 11.5px; color: var(--gray-700); line-height: 1.45;
  margin-bottom: 4px;
}
.rf-fired-srcs { display: flex; flex-wrap: wrap; gap: 3px; }
.rf-src-chip {
  font-family: var(--font-mono); font-size: 9.5px;
  background: var(--gray-100); color: var(--gray-700);
  padding: 1px 5px; border-radius: 3px;
}
.quest-cta {
  margin-top: 6px; display: flex; flex-direction: column; gap: 8px;
}
.quest-cta button { width: 100%; }
.quest-cta button:disabled {
  opacity: 0.5; cursor: not-allowed;
}
@media (max-width: 760px) {
  .try-page {
    padding: 24px 0 32px;
  }
  .quest-toolbar {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    gap: 12px;
    padding: 18px 16px 16px;
    border-radius: 10px;
  }
  .qt-label,
  .quest-toolbar > .qt-label:nth-of-type(-n+2) {
    flex: 1 1 100%;
    width: 100%;
    min-width: 0;
  }
  .quest-toolbar > .qt-label:nth-of-type(-n+2) select {
    font-size: 14px;
    padding: 10px 11px;
  }
  .qt-modes,
  .qt-reset {
    width: 100%;
  }
  .qt-modes {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .mode-btn {
    min-width: 0;
    padding: 9px 8px;
    overflow-wrap: anywhere;
  }
  .quest-readiness-head {
    flex-direction: column;
    gap: 4px;
  }
  .quest-actions-top.quest-cta {
    grid-template-columns: 1fr; padding: 10px;
  }
  .quest-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
  }
  .quest-form-pane {
    padding: 16px 14px;
    border-radius: 8px;
  }
  .quest-empty {
    padding: 36px 10px;
  }
  .example-lock-banner {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 12px;
  }
  .example-lock-banner .elb-btn {
    width: 100%;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .quest-build-card {
    padding: 13px 14px;
  }
  .build-card-head {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .build-state {
    white-space: normal;
  }
  .build-meta div {
    grid-template-columns: 1fr;
    gap: 2px;
  }
  .status {
    width: 100%;
  }
}

/* Plan result modal — replaces the old in-page .quest-output section so
   the form stays the focus of the page and the rendered plan only shows
   when the user wants to look at it. */
.plan-modal {
  position: fixed; inset: 0; z-index: 9995;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
  animation: oo-fadein 0.18s ease-out;
}
.plan-modal[hidden] { display: none; }
.plan-modal-card {
  background: white; border-radius: 12px;
  width: min(1000px, 100%); height: min(880px, 92vh);
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
}
.plan-modal-toolbar {
  display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: 12px;
  padding: 10px 14px; background: var(--gray-50);
  border-bottom: 1px solid var(--gray-200);
}
.plan-modal-actions { display: flex; gap: 8px; align-items: center; }
.plan-modal-card #resultFrame {
  flex: 1; width: 100%; border: none; background: white;
}
.rt-btn-ghost {
  background: white !important; color: var(--gray-700) !important;
  border: 1px solid var(--gray-200) !important;
  font-weight: 700; padding: 6px 10px;
}
.rt-btn-ghost:hover {
  background: var(--gray-100) !important; color: var(--green-700) !important;
}

@media (max-width: 900px) {
  .quest-grid { grid-template-columns: 1fr; }
  .quest-side { position: static; }
}
@media (max-width: 800px) {
  .hero h1 { font-size: 32px; }
  .problem-grid, .try-grid { grid-template-columns: 1fr; }
}

/* Generation lock — overlay modal during full-plan generation. Hard-blocks
   form interaction (via inert on <main>) so the rendered plan corresponds
   to a stable input snapshot. Released in runEngine's finally{{}}. */
.generating-overlay {{
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(2px);
  display: flex; align-items: center; justify-content: center;
  animation: oo-fadein 0.18s ease-out;
}}
.generating-overlay[hidden] {{ display: none; }}
.generating-card {{
  background: white; border-radius: 12px;
  padding: 28px 36px; max-width: 460px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
  text-align: center;
}}
.generating-card h3 {{
  margin: 14px 0 8px; font-family: var(--font-display);
  font-size: 22px; color: var(--green-900);
}}
.generating-card p {{
  margin: 6px 0; font-size: 14px; color: var(--gray-700); line-height: 1.5;
}}
.generating-hint {{
  font-size: 12px; color: var(--gray-600);
  font-family: var(--font-mono); margin-top: 14px;
}}
.generating-spinner {{
  width: 36px; height: 36px; margin: 0 auto;
  border: 3px solid var(--gray-200); border-top-color: var(--green-700);
  border-radius: 50%; animation: oo-spin 0.9s linear infinite;
}}
@keyframes oo-spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes oo-fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

/* Init overlay — first-run engine load with named stages so the doctor
   sees what's happening instead of mystery lag. Lower z-index than the
   generating overlay so a generate-click re-uses init for first run, and
   subsequent clicks use the lighter generating overlay. */
.init-overlay {{
  position: fixed; inset: 0; z-index: 9990;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  display: flex; align-items: center; justify-content: center;
  animation: oo-fadein 0.18s ease-out;
}}
.init-overlay[hidden] {{ display: none; }}
.init-card {{
  background: white; border-radius: 12px;
  padding: 28px 36px; max-width: 540px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
}}
.init-card h3 {{
  margin: 0 0 6px; font-family: var(--font-display);
  font-size: 22px; color: var(--green-900);
}}
.init-lead {{
  margin: 0 0 18px; font-size: 13px; color: var(--gray-700); line-height: 1.5;
}}
.init-stages {{
  list-style: none; padding: 0; margin: 0 0 14px;
  display: flex; flex-direction: column; gap: 6px;
  counter-reset: none;
}}
.init-stages .stage {{
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-radius: 8px;
  background: var(--gray-100);
  font-size: 14px; color: var(--gray-700);
  transition: background 0.18s, color 0.18s;
}}
.init-stages .stage::before {{
  content: '○'; color: var(--gray-400); font-size: 16px;
  width: 20px; text-align: center; flex-shrink: 0;
  font-family: var(--font-mono);
}}
.init-stages .stage.active {{
  background: white; color: var(--green-900);
  border: 1px solid var(--green-700); font-weight: 500;
}}
.init-stages .stage.active::before {{
  content: '⟳'; color: var(--green-700);
  display: inline-block;
  animation: oo-spin 0.9s linear infinite;
}}
.init-stages .stage.done {{
  color: var(--gray-700);
}}
.init-stages .stage.done::before {{
  content: '✓'; color: var(--green-700); font-weight: bold;
}}
.init-stages .stage.error {{
  background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;
}}
.init-stages .stage.error::before {{
  content: '✗'; color: #dc2626;
}}
.init-hint {{
  margin: 0; font-size: 12px; color: var(--gray-600);
  font-style: italic; line-height: 1.5;
}}

/* Info pages (capabilities / limitations) */
.info-page { padding: 32px 0 48px; }
.info-page h1 {
  font-family: var(--font-display); font-size: 36px;
  color: var(--green-900); margin-bottom: 10px;
}
.info-page .lead {
  font-size: 16px; color: var(--gray-700); max-width: 820px;
  margin-bottom: 28px; line-height: 1.6;
}
.info-section { margin-top: 36px; }
.info-section h2 {
  font-family: var(--font-display); font-size: 24px;
  color: var(--green-900); margin-bottom: 14px;
}
.info-section p { font-size: 14.5px; color: var(--gray-700); margin-bottom: 12px; }
.info-section .info-text {
  max-width: 820px; line-height: 1.6;
}
.flow-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px; margin: 18px 0;
}
.flow-step {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 10px; padding: 14px 14px;
  border-top: 3px solid var(--green-600);
}
.flow-step .flow-num {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--green-700); margin-bottom: 6px;
  letter-spacing: 1px; text-transform: uppercase;
}
.flow-step .flow-title {
  font-weight: 700; font-size: 14px;
  color: var(--gray-900); margin-bottom: 6px;
  font-family: var(--font-display);
}
.flow-step .flow-desc {
  font-size: 12.5px; color: var(--gray-700); line-height: 1.45;
}
.flow-step code {
  font-family: var(--font-mono); font-size: 11px;
  background: var(--gray-100); padding: 1px 5px; border-radius: 3px;
}

/* Promotional infographic hero (capabilities page) */
.promo-info {
  margin: 28px 0 36px;
  padding: 32px 32px 28px;
  background:
    radial-gradient(circle at 0% 0%, rgba(22, 163, 74, 0.18), transparent 55%),
    radial-gradient(circle at 100% 100%, rgba(13, 148, 136, 0.18), transparent 55%),
    linear-gradient(135deg, var(--green-900) 0%, var(--green-800) 60%, #082017 100%);
  border-radius: 14px;
  color: #e9f5ec;
  box-shadow: 0 12px 32px rgba(10, 46, 26, 0.18);
  position: relative; overflow: hidden;
}
.promo-info::before {
  content: ""; position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 28px 28px;
  pointer-events: none; opacity: 0.5;
}
.promo-info > * { position: relative; }
.promo-eyebrow {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 2px;
  text-transform: uppercase; color: #6ee7b7; opacity: 0.85;
  margin-bottom: 10px;
}
.promo-headline {
  font-family: var(--font-display); font-weight: 700;
  font-size: 34px; line-height: 1.18; color: white;
  margin-bottom: 14px; max-width: 880px;
}
.promo-headline em {
  font-style: normal; color: #6ee7b7;
  background: linear-gradient(120deg, #6ee7b7 0%, #5eead4 100%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.promo-sub {
  font-size: 15px; line-height: 1.55; color: #c5e0cd;
  max-width: 780px; margin-bottom: 26px;
}
.promo-sub strong { color: white; font-weight: 600; }

.promo-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 14px; margin-bottom: 26px;
  padding: 18px 0; border-top: 1px solid rgba(255,255,255,0.12);
  border-bottom: 1px solid rgba(255,255,255,0.12);
}
.promo-stat { text-align: left; }
.promo-stat-num {
  font-family: var(--font-display); font-weight: 900;
  font-size: 38px; line-height: 1; color: white;
  letter-spacing: -0.02em;
}
.promo-stat-num .promo-stat-plus { color: #6ee7b7; font-weight: 700; }
.promo-stat-lbl {
  font-size: 12px; line-height: 1.4; color: #a7c7b1;
  margin-top: 6px; text-transform: uppercase; letter-spacing: 0.6px;
  font-weight: 500;
}

.promo-flow {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1.2fr;
  gap: 12px; align-items: stretch;
  margin-bottom: 26px;
}
.promo-flow-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(110, 231, 183, 0.22);
  border-radius: 10px; padding: 14px 16px;
  backdrop-filter: blur(2px);
}
.promo-flow-card.is-output {
  background: linear-gradient(135deg, rgba(110,231,183,0.16), rgba(94,234,212,0.10));
  border-color: rgba(110, 231, 183, 0.45);
}
.promo-flow-tag {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 1.2px;
  text-transform: uppercase; color: #6ee7b7; margin-bottom: 6px;
}
.promo-flow-title {
  font-family: var(--font-display); font-weight: 700;
  font-size: 17px; color: white; line-height: 1.2; margin-bottom: 6px;
}
.promo-flow-desc {
  font-size: 12.5px; line-height: 1.45; color: #b8d3c0;
}
.promo-flow-desc code {
  font-family: var(--font-mono); font-size: 10.5px;
  background: rgba(255,255,255,0.08); color: #e9f5ec;
  padding: 1px 5px; border-radius: 3px;
}
.promo-flow-arrow {
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-size: 26px;
  color: #6ee7b7; opacity: 0.7; font-weight: 400;
}
.promo-flow-tracks {
  display: flex; gap: 6px; margin-top: 8px;
}
.promo-flow-track {
  flex: 1; padding: 6px 8px; border-radius: 4px;
  font-size: 11px; color: #e9f5ec;
  background: rgba(255,255,255,0.10);
  border-left: 2px solid #6ee7b7;
}
.promo-flow-track.is-alt { border-left-color: #5eead4; opacity: 0.85; }
.promo-flow-track-label {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.8px;
  text-transform: uppercase; color: #6ee7b7; display: block;
}

.promo-pillars {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.promo-pillar {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 10px; padding: 14px 16px;
  display: flex; gap: 12px; align-items: flex-start;
}
.promo-pillar-num {
  font-family: var(--font-display); font-size: 22px; font-weight: 900;
  color: #6ee7b7; line-height: 1; flex-shrink: 0;
  min-width: 28px;
}
.promo-pillar-title {
  font-weight: 700; font-size: 13px; color: white;
  margin-bottom: 4px; letter-spacing: 0.2px;
}
.promo-pillar-desc {
  font-size: 12px; line-height: 1.45; color: #b8d3c0;
}

@media (max-width: 760px) {
  .promo-info { padding: 22px 18px; }
  .promo-headline { font-size: 26px; }
  .promo-flow {
    grid-template-columns: 1fr;
  }
  .promo-flow-arrow { transform: rotate(90deg); padding: 4px 0; }
}
@media print {
  .promo-info {
    background: white; color: var(--gray-900);
    border: 1px solid var(--green-700);
    box-shadow: none;
  }
  .promo-info::before { display: none; }
  .promo-headline, .promo-stat-num, .promo-flow-title, .promo-pillar-title { color: var(--green-900); }
  .promo-headline em { -webkit-text-fill-color: initial; color: var(--green-700); background: none; }
  .promo-eyebrow, .promo-flow-tag, .promo-pillar-num, .promo-stat-num .promo-stat-plus { color: var(--green-700); }
  .promo-sub, .promo-stat-lbl, .promo-flow-desc, .promo-pillar-desc { color: var(--gray-700); }
  .promo-flow-card, .promo-pillar { border-color: var(--gray-200); background: var(--gray-50); }
  .promo-flow-arrow { color: var(--green-700); }
  .promo-flow-track { background: white; border-left-color: var(--green-600); color: var(--gray-900); }
  .promo-flow-track-label { color: var(--green-700); }
}

.gap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.gap-card {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 10px; padding: 16px 18px;
  border-left: 3px solid var(--amber);
}
.gap-card .gap-tag {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--amber); letter-spacing: 0.5px; text-transform: uppercase;
  margin-bottom: 6px;
}
.gap-card h3 {
  font-family: var(--font-display); font-size: 17px;
  color: var(--green-900); margin-bottom: 8px;
}
.gap-card p { font-size: 13px; color: var(--gray-700); line-height: 1.5; }
.gap-card.gap-hard { border-left-color: var(--red); }
.gap-card.gap-hard .gap-tag { color: var(--red); }
.spec-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.spec-card {
  background: white; border: 1px solid var(--gray-200);
  border-radius: 10px; padding: 18px 20px;
  display: flex; flex-direction: column;
  transition: border-color .15s, box-shadow .15s;
}
.spec-card:hover {
  border-color: var(--green-600);
  box-shadow: 0 4px 14px rgba(10, 46, 26, 0.06);
}
.spec-card-head {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 10px; flex-wrap: wrap;
}
.spec-tag {
  display: inline-block; color: white;
  font-family: var(--font-mono); font-size: 10px;
  letter-spacing: 0.6px; text-transform: uppercase;
  padding: 3px 8px; border-radius: 4px; font-weight: 600;
}
.spec-id {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--gray-500);
}
.spec-card h3 {
  font-family: var(--font-display); font-size: 17px;
  color: var(--green-900); margin-bottom: 8px; line-height: 1.3;
}
.spec-card p {
  font-size: 13px; color: var(--gray-700);
  line-height: 1.5; flex: 1; margin-bottom: 12px;
}
.spec-card-foot {
  display: flex; gap: 14px; align-items: center;
  font-size: 12.5px; padding-top: 10px;
  border-top: 1px solid var(--gray-100);
}
.spec-card-foot a {
  color: var(--green-700); text-decoration: none; font-weight: 600;
}
.spec-card-foot a:hover { text-decoration: underline; }
.spec-card-foot .spec-raw {
  color: var(--gray-500); font-weight: 400; font-family: var(--font-mono);
  font-size: 11px;
}
.q-list {
  background: var(--green-50); border: 1px solid var(--green-100);
  border-radius: 8px; padding: 14px 18px; margin: 12px 0;
}
.q-list h4 {
  font-family: var(--font-display); font-size: 15px;
  color: var(--green-900); margin-bottom: 8px;
}
.q-list ul { padding-left: 18px; font-size: 13px; color: var(--gray-700); }
.q-list li { margin-bottom: 4px; line-height: 1.5; }
.q-list code {
  font-family: var(--font-mono); font-size: 11px;
  background: white; padding: 1px 5px; border-radius: 3px;
  color: var(--green-800);
}
.callout {
  background: var(--amber-bg); border-left: 3px solid var(--amber);
  padding: 12px 16px; border-radius: 4px; margin: 16px 0;
  font-size: 13.5px; color: var(--gray-900); line-height: 1.55;
}
.callout.callout-good {
  background: var(--green-50); border-left-color: var(--green-600);
}
.callout.callout-hard {
  background: var(--red-bg); border-left-color: var(--red);
}
.kv-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  margin-top: 10px;
}
.kv-table th, .kv-table td {
  text-align: left; padding: 8px 10px;
  border-bottom: 1px solid var(--gray-100);
}
.kv-table th {
  background: var(--gray-50); font-weight: 600;
  color: var(--gray-700); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.kv-table code {
  font-family: var(--font-mono); font-size: 11px;
  background: var(--gray-100); padding: 1px 5px; border-radius: 3px;
}

/* Page footer */
.page-foot {
  margin-top: 18px; padding-top: 10px;
  border-top: 1px solid var(--gray-200);
  font-size: 11px; line-height: 1.35; color: var(--gray-500);
}
.page-foot a { color: var(--green-700); }

/* ── Variant actionability — ESCAT tier badges ──
   Mirrored from the engine's embedded HTML render so static-site
   pages can use the same tier-badge palette without re-defining it.
   The engine HTML carries its own embedded copy (knowledge_base/engine/
   render_styles.py STYLESHEET) for self-contained Plan documents. */
.tier-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.4px; white-space: nowrap;
}
.escat-IA, .escat-IB { background: #16a34a; color: white; }
.escat-IIA, .escat-IIB { background: #facc15; color: #713f12; }
.escat-IIIA, .escat-IIIB { background: #f97316; color: white; }
.escat-IV { background: #f3f4f6; color: #374151; }
.escat-X { background: #e5e7eb; color: #374151; }
/* Legacy vendor-tier classes were removed in the 2026-04-27 CIViC
   pivot. ESCAT is the source-of-truth tier label. */

/* Case-token banner (CSD-3 QR flow): shown above /try.html when a profile
   was loaded from the URL hash (#p=<token>). Success / error variants. */
.case-token-banner,
.case-token-banner-error {
  font-family: 'Source Sans 3', system-ui, sans-serif;
  font-size: 1em;
  margin: 16px auto;
  max-width: 1200px;
  padding: 12px 18px;
  border-radius: 6px;
}
.case-token-banner {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}
.case-token-banner-error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
"""
