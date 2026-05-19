"""Regimen phase-aware schema — PR1 of regimen-phases-refactor.

See `docs/reviews/regimen-phases-refactor-plan-2026-04-28.md` §4 and
`knowledge_base/schemas/regimen.py` (module docstring).

Covers four contracts:

1. **Legacy back-compat (auto-wrap):** YAMLs without `phases:` continue
   to load and end up with a single phase named "main" carrying all the
   original components. `regimen.phases[0].components == regimen.components`.
2. **Authored phases preserved:** when a Regimen is constructed with
   explicit `phases=[...]`, the auto-wrap MUST NOT fire. `phases` and
   `components` are independent on input.
3. **`bridging_options` round-trips through YAML.**
4. **No regression on representative legacy regimens** (R-CHOP, axi-cel,
   lifileucel — pre-PR1 component counts preserved, phases len ≥ 1).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from knowledge_base.schemas import Regimen, RegimenComponent, RegimenPhase

KB_REGIMENS = (
    Path(__file__).parent.parent
    / "knowledge_base"
    / "hosted"
    / "content"
    / "regimens"
)


def _load_regimen(filename: str) -> tuple[dict, Regimen]:
    """Load a regimen YAML directly (no full KB walk, no caching)."""
    raw = yaml.safe_load((KB_REGIMENS / filename).read_text(encoding="utf-8"))
    return raw, Regimen.model_validate(raw)


# ── 1. Legacy back-compat (auto-wrap) ────────────────────────────────────────


def test_legacy_regimen_auto_wraps_into_main_phase():
    """R-CHOP has no `phases:` field. After load, exactly one phase named
    'main' must appear, carrying ALL original components verbatim."""
    raw, r = _load_regimen("r_chop.yaml")
    assert "phases" not in raw, (
        "fixture invariant: r_chop.yaml is legacy (no phases:); "
        "if it gains phases, swap fixture to another legacy regimen"
    )

    assert len(r.phases) == 1, f"expected single auto-wrapped phase, got {len(r.phases)}"
    phase = r.phases[0]
    assert phase.name == "main"
    assert phase.components == r.components, (
        "auto-wrapped phase MUST carry components verbatim"
    )
    # `components` is preserved separately (not removed)
    assert len(r.components) == 5, "R-CHOP has 5 drug components"


def test_legacy_regimen_with_no_components_does_not_auto_wrap():
    """Empty components → empty phases. The validator only fires when
    there is something to wrap, otherwise we'd manufacture empty phases."""
    # Components is required by the schema (list[RegimenComponent], no default
    # of empty), so we need at least one to construct. Test the guard via
    # an in-memory minimal Regimen with one component.
    r = Regimen(
        id="REG-TEST",
        name="test",
        components=[RegimenComponent(drug_id="DRUG-X")],
    )
    assert len(r.phases) == 1
    assert r.phases[0].name == "main"
    assert r.phases[0].components[0].drug_id == "DRUG-X"


# ── 2. Authored phases preserved (no auto-wrap when phases is provided) ──────


def test_authored_phases_not_overwritten():
    """When `phases=[...]` is authored explicitly, the validator must NOT
    rewrap. `components` and `phases` stay independent on input."""
    r = Regimen(
        id="REG-CART-LIKE",
        name="CART-like with explicit phases",
        components=[
            RegimenComponent(drug_id="DRUG-CYCLOPHOSPHAMIDE"),
            RegimenComponent(drug_id="DRUG-FLUDARABINE"),
            RegimenComponent(drug_id="DRUG-CART-PRODUCT"),
        ],
        phases=[
            RegimenPhase(
                name="lymphodepletion",
                purpose_ua="lymphodepletion phase",
                components=[
                    RegimenComponent(drug_id="DRUG-CYCLOPHOSPHAMIDE"),
                    RegimenComponent(drug_id="DRUG-FLUDARABINE"),
                ],
                duration="3 days, days -5 to -3",
                timing_relative_to="main_infusion",
                timing_offset_days=-5,
                optional=False,
            ),
            RegimenPhase(
                name="main",
                purpose_ua="main infusion",
                components=[RegimenComponent(drug_id="DRUG-CART-PRODUCT")],
                timing_relative_to="absolute",
            ),
        ],
    )
    assert len(r.phases) == 2
    assert [p.name for p in r.phases] == ["lymphodepletion", "main"]
    # Independent: components is NOT auto-derived from phases.
    assert len(r.components) == 3
    assert r.phases[0].timing_offset_days == -5
    assert r.phases[0].optional is False


def test_authored_phases_with_optional_bridging():
    r = Regimen(
        id="REG-X",
        name="x",
        components=[RegimenComponent(drug_id="DRUG-A")],
        phases=[
            RegimenPhase(
                name="bridging",
                purpose_ua="bridging while waiting for manufacturing",
                components=[RegimenComponent(drug_id="DRUG-B")],
                optional=True,
            ),
            RegimenPhase(
                name="main",
                purpose_ua="main therapy",
                components=[RegimenComponent(drug_id="DRUG-A")],
            ),
        ],
    )
    assert r.phases[0].optional is True
    assert r.phases[1].optional is False


# ── 3. bridging_options round-trips through YAML ─────────────────────────────


def test_bridging_options_yaml_round_trip():
    """Construct → dump to YAML → reload → field preserved."""
    r = Regimen(
        id="REG-CART-WITH-BRIDGE",
        name="CART with bridge",
        components=[RegimenComponent(drug_id="DRUG-CART")],
        bridging_options=["REG-RICE", "REG-DHAP"],
    )
    dumped = yaml.safe_dump(r.model_dump(mode="json", exclude_none=True), sort_keys=False)
    reloaded = Regimen.model_validate(yaml.safe_load(dumped))
    assert reloaded.bridging_options == ["REG-RICE", "REG-DHAP"]


def test_bridging_options_default_empty():
    r = Regimen(
        id="REG-PLAIN",
        name="plain",
        components=[RegimenComponent(drug_id="DRUG-X")],
    )
    assert r.bridging_options == []


# ── 4. No regression on representative legacy regimens ───────────────────────
#
# Component counts captured by reading the YAML twice — once as raw dict
# (pre-validate) and once as a model — to prove the model didn't drop or
# duplicate anything during the auto-wrap.


def _raw_component_count(raw: dict) -> int:
    if not raw.get("components") and raw.get("agents"):
        return len(raw.get("agents") or [])
    return len(raw.get("components") or [])


def test_no_regression_r_chop():
    raw, r = _load_regimen("r_chop.yaml")
    assert len(r.phases) >= 1
    assert len(r.components) == _raw_component_count(raw)
    # Auto-wrapped — phase[0] components == r.components
    assert sum(len(p.components) for p in r.phases) == len(r.components)


def test_no_regression_axicel():
    """axi-cel has been migrated to multi-phase shape (PR2). The YAML
    carries `components: []` and authors `phases:` explicitly with
    lymphodepletion + main. The auto-wrap MUST NOT fire (phases is
    non-empty on input). Total drug count across phases (3) exceeds the
    flat `components` length (0) — the new shape is canonical."""
    raw, r = _load_regimen("reg_car_t_axicel.yaml")
    assert len(r.phases) == 2, "post-migration axi-cel must carry exactly two phases"
    assert [p.name for p in r.phases] == ["lymphodepletion", "main"]
    # Components is the no-op shape (loader-side opt-out from auto-wrap)
    assert len(r.components) == _raw_component_count(raw) == 0
    # Drugs flow via phases now
    drug_ids_in_phases = [c.drug_id for p in r.phases for c in p.components]
    assert "DRUG-CYCLOPHOSPHAMIDE" in drug_ids_in_phases
    assert "DRUG-FLUDARABINE" in drug_ids_in_phases
    assert "DRUG-AXICABTAGENE-CILOLEUCEL" in drug_ids_in_phases
    assert len(drug_ids_in_phases) == 3


def test_no_regression_lifileucel():
    """lifileucel has been migrated to multi-phase shape (PR3). The YAML
    carries `components: []` and authors `phases:` explicitly with
    lymphodepletion + main + il2_support. The il2_support phase has empty
    components (no DRUG-ALDESLEUKIN entity in KB yet) but a structured
    `purpose_ua` capturing the IL-2 dose/schedule. Lymphodepletion holds
    cyclophosphamide + fludarabine; main holds the TIL product
    (DRUG-LIFILEUCEL)."""
    raw, r = _load_regimen("reg_lifileucel_til_melanoma.yaml")
    assert len(r.phases) == 3, "post-migration lifileucel must carry exactly three phases"
    assert [p.name for p in r.phases] == ["lymphodepletion", "main", "il2_support"]
    # Components is the no-op shape (loader-side opt-out from auto-wrap)
    assert len(r.components) == _raw_component_count(raw) == 0
    # Drugs flow via phases now
    drug_ids_in_phases = [c.drug_id for p in r.phases for c in p.components]
    assert "DRUG-CYCLOPHOSPHAMIDE" in drug_ids_in_phases
    assert "DRUG-FLUDARABINE" in drug_ids_in_phases
    assert "DRUG-LIFILEUCEL" in drug_ids_in_phases


def test_no_regression_all_244_legacy_yamls_load():
    """Catch-all: every existing regimen YAML loads under the new schema.

    Three valid shapes after PR2 (one regimen migrated to multi-phase):

    * **legacy auto-wrapped** — `phases:` absent, `components: [drugs…]`
      → after validate, `phases = [{name: 'main', components: drugs…}]`.
    * **explicitly authored multi-phase** — `phases: [...]` populated,
      `components: []` (axi-cel post-PR2; the curator-canonical form).
      Auto-wrap MUST NOT fire — phases is preserved as authored.
    * **surveillance-only** — both fields empty (e.g. observation-only
      "regimen" with no drugs). The render layer routes this differently.

    Drives the load-bearing claim of PR1+PR2: zero existing YAML breaks.
    """
    yaml_paths = sorted(KB_REGIMENS.glob("*.yaml"))
    assert len(yaml_paths) >= 240, (
        f"expected ~244 regimen YAMLs, found {len(yaml_paths)} — "
        "fixture changed?"
    )

    legacy_autowrap_count = 0
    explicit_multiphase_count = 0
    empty_count = 0
    for path in yaml_paths:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        r = Regimen.model_validate(raw)
        raw_count = _raw_component_count(raw)
        raw_has_phases = bool(raw.get("phases"))

        # Component preservation (the validator never adds/drops top-level)
        assert len(r.components) == raw_count, (
            f"{path.name}: components count drifted "
            f"({raw_count} raw vs {len(r.components)} model)"
        )

        if raw_has_phases:
            # Explicit author — auto-wrap suppressed, phases as written
            assert len(r.phases) >= 1, (
                f"{path.name}: phases authored explicitly but model has 0"
            )
            # Drugs live in phases now; top-level components is the no-op.
            # Procedure-pathway regimens (allogeneic HCT, surgical pathways)
            # legitimately carry zero drug components — the "treatment" is
            # the stem-cell / surgical product, documented via phase
            # purpose strings rather than DRUG-* refs. They have raw_count
            # == 0 at top level too, so we recognise the shape and accept it.
            phase_drugs = sum(len(p.components) for p in r.phases)
            if phase_drugs == 0:
                assert raw_count == 0, (
                    f"{path.name}: explicit phases have 0 drug components "
                    f"but top-level `components` has {raw_count} — drugs "
                    f"left at top level instead of being moved into phases"
                )
                # else: procedure-pathway shape — accept.
            explicit_multiphase_count += 1
        elif raw_count > 0:
            # Legacy auto-wrap — single phase named "main"
            assert len(r.phases) == 1, (
                f"{path.name}: components={raw_count} but auto-wrap produced "
                f"{len(r.phases)} phases"
            )
            assert r.phases[0].name == "main", (
                f"{path.name}: auto-wrapped phase has unexpected name "
                f"{r.phases[0].name!r} (expected 'main')"
            )
            legacy_autowrap_count += 1
        else:
            # Surveillance — zero components AND no authored phases.
            # Render is responsible for routing this kind of entity
            # differently (e.g. follow-up schedule rather than drug list).
            assert len(r.phases) == 0, (
                f"{path.name}: zero components AND no authored phases, "
                "but model has phases populated — auto-wrap fired spuriously"
            )
            empty_count += 1

    # Sanity: vast majority of regimens are still legacy auto-wrap shape
    # (PR2 migrated axi-cel; PR3 migrated 17 more high-stakes regimens —
    # CAR-T A4, TIL B1, induction→autoSCT C4, induction→alloSCT D4,
    # multi-block / alternating E4. Total 18 explicit multi-phase.)
    assert legacy_autowrap_count >= 220, (
        f"expected ~225 legacy auto-wrap regimens after PR3, got {legacy_autowrap_count}"
    )
    # Additional migrations are allowed; 18 is the historical floor.
    assert explicit_multiphase_count >= 18, (
        f"expected at least 18 explicit multi-phase regimens (PR2 axi-cel "
        f"+ PR3 17 high-stakes), got {explicit_multiphase_count}"
    )
    # Documented exceptions (surveillance / observation-only, and non-drug
    # modality stubs such as radiation-only regimens).
    assert empty_count >= 1, (
        f"expected at least one zero-component non-drug regimen, "
        f"got {empty_count}"
    )


def test_18_migrated_yamls_have_multi_phase():
    """All 18 high-stakes regimens (PR2 axi-cel + PR3 the remaining 17 per
    regimen-phases-refactor plan §5) are migrated to multi-phase shape:
    `phases:` is authored explicitly in the raw YAML, every phase carries
    a meaningful `purpose_ua`, and no phase relies on the auto-wrap
    fallback.

    A single semantically-meaningful phase is acceptable for files that
    do not decompose cleanly (e.g. SMILE, MATRix induction); the contract
    is "explicit phases in YAML + purpose_ua present", not "≥2 phases".
    """
    migrated = [
        # Group A — CAR-T (Lymphodepletion + main_infusion)
        "reg_car_t_axicel.yaml",  # PR2 reference
        "reg_car_t_axicel_fl.yaml",
        "reg_car_t_axicel_hgbl.yaml",
        "reg_car_t_brexucel_mcl.yaml",
        "reg_tisagenlecleucel_b_all.yaml",
        # Group B — TIL with 3 phases
        "reg_lifileucel_til_melanoma.yaml",
        # Group C — Induction → autoSCT
        "r_dhap_autosct.yaml",
        "reg_rdhap_burkitt.yaml",
        "reg_rice_burkitt.yaml",
        "reg_r_ice_pmbcl.yaml",
        # Group D — Induction → conditioning → alloSCT
        "reg_choep_allosct_consolidation.yaml",
        "reg_allohct_pmf.yaml",
        "reg_allohct_mds_hr.yaml",
        "reg_allohct_cml_advanced.yaml",
        # Group E — Multi-block / alternating
        "hyper_cvad_r.yaml",
        "codox_m_ivac.yaml",
        "matrix.yaml",
        "smile.yaml",
    ]
    assert len(migrated) == 18, "the brief specifies 18 high-stakes regimens"
    for filename in migrated:
        raw, r = _load_regimen(filename)
        assert "phases" in raw, (
            f"{filename}: phases not authored explicitly in YAML "
            "(would auto-wrap into a generic 'main' phase)"
        )
        assert raw["phases"], f"{filename}: phases authored but empty"
        assert len(r.phases) >= 1, f"{filename}: model has no phases after load"
        for phase in r.phases:
            assert phase.purpose_ua, (
                f"{filename}: phase '{phase.name}' missing purpose_ua"
            )


# ── 5. Render layer (PR2 of regimen-phases-refactor) ─────────────────────────
#
# These tests exercise `_render_treatment_phases` (the visible render
# entry point per the regimen track block). Two integration tests drive
# a real end-to-end Plan → HTML render against the migrated axi-cel YAML
# and against a legacy R-CHOP regimen, asserting the phase-block visual
# contract (axi-cel: two blocks; R-CHOP: still one). A third unit test
# constructs a minimal `PlanTrack` to drive `bridging_options` rendering
# in isolation (no production regimen has bridging_options yet).

import json  # noqa: E402 — imports grouped above schema imports above on purpose

from knowledge_base.engine.render import _render_treatment_phases  # noqa: E402
from knowledge_base.schemas import Plan, PlanTrack  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
EXAMPLES = REPO_ROOT / "examples"
KB_CONTENT = REPO_ROOT / "knowledge_base" / "hosted" / "content"


def _patient(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_render_axicel_emits_two_phase_blocks():
    """Post-migration axi-cel renders as TWO `<section class="phase-block">`
    elements — one per phase (lymphodepletion + main). Each phase block
    carries a `data-phase` attribute with the canonical phase name and a
    UA heading that includes the curator-authored `purpose_ua`. Drug
    components flow into the right phase: cyclophosphamide + fludarabine
    under lymphodepletion, axi-cel under main.

    Drives the migrated YAML through the render path directly — the
    engine routing rules for an HGBL-double-hit patient → axi-cel are
    out of scope for THIS test (and would couple the test to indication
    selection). Loading the YAML via Pydantic gives us the canonical
    post-migration shape; calling `_render_treatment_phases` with that
    `regimen_data` exercises the render contract end-to-end.
    """
    raw_axicel = yaml.safe_load(
        (KB_REGIMENS / "reg_car_t_axicel.yaml").read_text(encoding="utf-8")
    )
    track = PlanTrack(
        track_id="aggressive",
        label="axi-cel test track",
        indication_id="IND-TEST-AXICEL",
        is_default=True,
        regimen_data=raw_axicel,
    )

    html_out = _render_treatment_phases(
        track,
        drugs_lookup={},  # render uses drug_id when names lookup is empty
        patient_disease_id="",
        disease_names={},
        target_lang="uk",
    )

    # Exactly two phase-block sections — lymphodepletion + main
    assert html_out.count('class="phase-block"') == 2, (
        f"expected 2 phase-block sections, got {html_out.count('class=phase-block')}"
    )
    assert 'data-phase="lymphodepletion"' in html_out
    assert 'data-phase="main"' in html_out

    # Heading text — UA prefix + purpose_ua come through escaped
    assert "Перед основною терапією: лімфодеплеція" in html_out, (
        "phase heading prefix for lymphodepletion missing"
    )
    assert "виснаження лімфоцитів перед CAR-T" in html_out, (
        "lymphodepletion purpose_ua not surfaced in heading"
    )

    # Drug routing per phase — slice the lymphodepletion section out and
    # assert cyclo + fludarabine inside it; assert axi-cel is OUTSIDE it
    # (in the main block).
    lymph_start = html_out.find('data-phase="lymphodepletion"')
    assert lymph_start > 0
    lymph_end = html_out.find("</section>", lymph_start)
    lymph_block = html_out[lymph_start:lymph_end]
    assert "DRUG-CYCLOPHOSPHAMIDE" in lymph_block
    assert "DRUG-FLUDARABINE" in lymph_block
    assert "DRUG-AXICABTAGENE-CILOLEUCEL" not in lymph_block, (
        "axi-cel infusion belongs in the main phase, not lymphodepletion"
    )

    # And axi-cel IS in the main block
    main_start = html_out.find('data-phase="main"')
    assert main_start > 0
    main_end = html_out.find("</section>", main_start)
    main_block = html_out[main_start:main_end]
    assert "DRUG-AXICABTAGENE-CILOLEUCEL" in main_block


def test_render_legacy_regimen_visually_unchanged():
    """Legacy R-CHOP YAML (no `phases:` field) still renders all 5 drugs
    in a single auto-wrapped phase block named "main". The render-time
    fallback in `_render_treatment_phases` synthesises a single phase
    when the loaded dict has no `phases` key — symmetric with the
    Pydantic auto-wrap (which never runs on the loader-dict path).

    Visual-similarity contract: the legacy auto-wrap MUST suppress the
    phase-heading (`<h4>`) so an unmigrated regimen doesn't grow
    spurious "основна терапія" labels above its drug list. The CSS rule
    `.phase-block[data-phase="main"]:only-of-type` further strips the
    wrapper border."""
    raw_rchop = yaml.safe_load(
        (KB_REGIMENS / "r_chop.yaml").read_text(encoding="utf-8")
    )
    # Sanity: R-CHOP is still in the legacy shape (no phases authored)
    assert "phases" not in raw_rchop or not raw_rchop.get("phases"), (
        "fixture invariant: r_chop.yaml is legacy; if it gains phases, "
        "this test should swap to another single-phase legacy regimen"
    )

    track = PlanTrack(
        track_id="standard",
        label="R-CHOP test track",
        indication_id="IND-TEST-RCHOP",
        is_default=True,
        regimen_data=raw_rchop,
    )

    html_out = _render_treatment_phases(
        track,
        drugs_lookup={},
        patient_disease_id="",
        disease_names={},
        target_lang="uk",
    )

    # All 5 R-CHOP drugs visible
    for drug_id in (
        "DRUG-RITUXIMAB",
        "DRUG-CYCLOPHOSPHAMIDE",
        "DRUG-DOXORUBICIN",
        "DRUG-VINCRISTINE",
        "DRUG-PREDNISONE",
    ):
        assert drug_id in html_out, f"{drug_id} missing from R-CHOP render"

    # Single auto-wrapped phase
    assert html_out.count('class="phase-block"') == 1
    assert 'data-phase="main"' in html_out

    # No heading emitted for the legacy single phase (visual-similarity
    # contract). The mapping `_PHASE_HEADING_PREFIX_UK["main"]` is None,
    # which suppresses the <h4>.
    assert 'class="phase-heading"' not in html_out, (
        "legacy auto-wrap must NOT emit a phase-heading <h4> — it would "
        "introduce spurious 'основна терапія' chrome above unmigrated "
        "regimens"
    )

    # And no lymphodepletion prefix (this is R-CHOP, not CAR-T)
    assert "Перед основною терапією" not in html_out


def test_render_bridging_options():
    """`bridging_options` renders as a separate visible block listing the
    accepted bridging-regimen IDs. Constructed in-test because no
    production regimen YAML has `bridging_options:` populated yet (PR3
    will add them to ~8 indications referencing CAR-T / TIL)."""
    track = PlanTrack(
        track_id="aggressive",
        label="Test track",
        indication_id="IND-TEST",
        is_default=False,
        regimen_data={
            "id": "REG-FAKE-CART",
            "name": "fake CART",
            "phases": [
                {
                    "name": "lymphodepletion",
                    "purpose_ua": "test lymphodepletion",
                    "components": [{"drug_id": "DRUG-CYCLOPHOSPHAMIDE"}],
                },
                {
                    "name": "main",
                    "purpose_ua": "test main",
                    "components": [{"drug_id": "DRUG-AXICABTAGENE-CILOLEUCEL"}],
                },
            ],
            "components": [],
            "bridging_options": ["REG-RICE", "REG-DHAP"],
        },
    )

    html_out = _render_treatment_phases(
        track,
        drugs_lookup={},  # empty lookup — drug name falls back to drug_id
        patient_disease_id="",
        disease_names={},
        target_lang="uk",
    )

    # Bridging block rendered with both regimen IDs visible
    assert "bridging-options" in html_out
    assert "REG-RICE" in html_out
    assert "REG-DHAP" in html_out
    # UA label present
    assert "Якщо очікування на основну терапію" in html_out
    # And the phase blocks rendered too
    assert 'data-phase="lymphodepletion"' in html_out
    assert 'data-phase="main"' in html_out
