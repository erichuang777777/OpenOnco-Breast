# algo-branch-wiring-ovarian-2l

## Status
`queued`

## Economic Profile
```yaml
compute_profile: low
verification_method: deterministic
break_even_test: PASS
output_type: kb-yaml-edit
backfilled_retroactively: false
```

Mechanical translation of prose `condition:` strings to structured
`finding:` clauses. Deterministic re-verification via
`generate_plan()` reachability test — same input patient profiles
produce the target indications instead of falling through to
`default_indication`.

## Queue
`A`

## Min Contributor Tier
`new`

## Severity
`low`

## Topic Labels
`mechanical-rewrite`, `engine-wiring`, `algorithm-branch`

## Mission

Wire `ALGO-OVARIAN-2L` so the **6 currently-unreached `IND-*`
entries** referenced from its decision tree become routable.

Per [docs/reviews/openonco-state-audit-2026-05-17.md §3](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/reviews/openonco-state-audit-2026-05-17.md)
and the algorithm-branch backlog at
[docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md),
`ALGO-OVARIAN-2L` is the top algorithm by unreached-indication count
(6) — its `decision_tree` steps use free-text `condition:` strings
(e.g. `"BRCA1 or BRCA2 mutation"`, `"platinum-sensitive recurrence"`,
`"HRD-positive"`, `"prior PARPi exposure"`, `"ECOG PS <= 2"`) that
the engine's `_eval_clause` silently treats as `False`. Every
synthetic patient falls through to `default_indication`; clinically-
defensible alternative tracks never surface.

**Translation pattern (PR [#597](https://github.com/romeo111/cancer-autoresearch/pull/597)
worked example):** replace each free-text `condition:` with a
structured clause keyed on existing patient-profile fields
(`patient.biomarkers["BIO-BRCA1"]`,
`patient.biomarkers["BIO-HRD-STATUS"]`,
`patient.prior_therapies`, `patient.ecog_ps`,
`patient.disease_state.platinum_sensitivity`, etc.).

**Scope of this single chunk:** ONE algorithm (`ALGO-OVARIAN-2L`).
The remaining 51 algorithms with prose conditions remain on the
backlog for follow-up chunks of identical shape.

**KB coverage:** Advances `docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md`
— one of 52 algorithms checked off; 6 of 89 unreached indications
made reachable.

**Out of scope:** authoring new `Indication`, `Regimen`, or `RF`
entities; introducing new patient-profile fields; resolving
clinical-evidence disagreements (e.g. NCCN-vs-ESMO HRD-status
maintenance positioning — see [docs/reviews/bma-coverage-2026-04-27.md §2](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/reviews/bma-coverage-2026-04-27.md));
RT or surgery additions per CHARTER §17. Pure semantics-preserving
translation only.

## Drop Estimate

~1 Drop (~100K tokens). One algorithm read, ≤6 condition strings
translated, ≤5-line YAML diff, golden-test snapshot update, one
example patient JSON regenerated.

## Required Skill

`openonco-contributor:openonco-contribute` — standard contribution
workflow.

**Knowledge required:**

- Read OpenOnco `Algorithm` schema in
  [knowledge_base/schemas/algorithm.py](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/schemas/algorithm.py)
  + `_eval_clause` in
  [knowledge_base/engine/redflag_eval.py](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/engine/redflag_eval.py)
  to understand `{finding: <key>, comparator: ..., threshold: ...}`
  vs `{biomarker: <BIO-ID>, value: positive/negative}` clause shapes.
- Read PR [#597](https://github.com/romeo111/cancer-autoresearch/pull/597)
  end-to-end. That's the canonical worked example for this chunk
  shape.
- Understand `output_indications` ordering: when the decision tree
  falls through, the rest of the engine still produces a sensible
  plan from `output_indications` ordered by `is_current_line` +
  biomarker filters — so the "before" behavior is not a crash; it's
  silently-suboptimal routing.

**No clinical-authoring knowledge required.** Translation must be
1:1 with the prose — if a clause says `BRCA1 or BRCA2 mutation`,
the structured form must check `BIO-BRCA1` OR `BIO-BRCA2`
positive, not invent a new condition. Tests below catch deviation.

## Allowed Sources

This chunk is **engine wiring, not clinical content** — no new
source citations are introduced. The volunteer reads:

- The existing `ALGO-OVARIAN-2L` YAML at
  [knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml)
  (canonical for what each prose condition means).
- The 6 target `IND-OVARIAN-2L-*` YAMLs referenced from the algorithm
  (to confirm field names + biomarker requirements).
- The engine code paths listed under **Required Skill**.

**Banned per OpenOnco pilot:** OncoKB, SNOMED CT, MedDRA (per
[CHARTER §2](https://github.com/romeo111/cancer-autoresearch/blob/master/specs/CHARTER.md)
and OpenOnco-contributor source policy). Not relevant here — chunk
introduces no source citations — but listed for completeness.

## Manifest

| Field | Value |
|---|---|
| `algorithm_id` | `ALGO-OVARIAN-2L` |
| `algorithm_yaml_path` | `knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml` |
| `unreached_indications` | 6 (exact ids enumerated when chunk-task issue opens; resolved from `decision_tree` `output_indications`) |
| `expected_diff_size_loc` | ≤ 15 lines (≤6 conditions × ~2 lines each + minor reformatting) |
| `validator_command` | `py -3.12 -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| `reachability_command` | `python scripts/audit_example_plan_coverage.py --algorithm ALGO-OVARIAN-2L` |
| `golden_test_command` | `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k ovarian` |
| `worked_example_pr` | https://github.com/romeo111/cancer-autoresearch/pull/597 |

The manifest is concrete — the algorithm exists, the 6 target
indications exist, the test commands exist. No source-side dependency
to ingest first.

## Computation

For each `condition:` string in `algo_ovarian_2l.yaml.decision_tree`:

1. **Identify** the clinical concept the prose names
   (e.g. `"BRCA1 or BRCA2 mutation"` → BRCA1 OR BRCA2 positive).
2. **Locate** the matching patient-profile field by reading
   [knowledge_base/schemas/patient.py](https://github.com/romeo111/cancer-autoresearch/blob/master/knowledge_base/schemas/patient.py)
   and the 6 target indications'
   `applicable_to.biomarker_requirements_required` /
   `_excluded` blocks. The field already exists if the indication
   filters on it.
3. **Translate** to the canonical structured shape — either
   `{biomarker: <BIO-ID>, value: positive|negative}` or
   `{finding: <patient-profile-key>, comparator: <op>, threshold: <val>}`.
   Where the prose has `OR` / `AND`, use `{all_of: [...]}` /
   `{any_of: [...]}` wrappers per existing patterns in
   `algo_aitl_2l.yaml` (post-#597).
4. **Re-run** the validator + reachability + golden tests in
   **Manifest**. All three must be green.
5. **Regenerate** the corresponding verified-treatment-example
   patient JSON via
   `python scripts/generate_verified_treatment_examples.py --algorithm ALGO-OVARIAN-2L`,
   confirm at least one previously-unreached indication appears in
   the generated examples.
6. **Open a PR** following the WIP-branch-first claim method.
   Branch: `feat/algo-ovarian-2l-wire-2026-05-20-HHMM`.

If a prose condition cannot be translated 1:1 (e.g. it names a
clinical concept with no corresponding patient-profile field),
**stop and surface to maintainer** — do not invent a new patient-
profile field. That's a separate scoped change, not part of this
chunk.

## Where computation happens

Contributor's machine. Required:

- Python 3.12 (`py -V:3.12` on Windows;
  `python3.12` on Linux/Mac).
- `git clone https://github.com/romeo111/cancer-autoresearch`.
- Read access; PR authored against `master`.

No GPU, no API tokens, no special secrets needed.

## Re-verification

### Pre-acceptance gates (auto-reject)

- KB validator green (`--strict`).
- All `pytest tests/test_engine.py tests/test_verified_treatment_examples.py -k ovarian`
  pass.
- `scripts/audit_example_plan_coverage.py --algorithm ALGO-OVARIAN-2L`
  reports ≥ 1 previously-unreached indication now reachable
  (target: all 6 reachable, but partial wins acceptable if at least
  3 land).
- Diff size ≤ 15 LOC inside the algorithm YAML.
- Diff is **confined** to
  `knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml`
  + generated verified-treatment-example JSON files +
  `scripts/site_cases.py` auto-block (if generator re-run added new
  examples). NO changes to engine code, schema files, indications,
  regimens, redflags, or biomarkers.
- `_contribution.ai_tool` and `_contribution.ai_model` present in
  the contribution-meta sidecar.

### Computational re-verify

`python scripts/audit_example_plan_coverage.py --algorithm
ALGO-OVARIAN-2L --before <baseline-sha> --after <pr-head-sha>`
must show **strict improvement** (more indications reachable post-PR
than pre-PR; none regressed from reachable to unreached).

### Sample human re-verify

Maintainer (1 person): read the 6 condition translations side-by-
side against the prose. Check that each preserves the clinical
intent (no narrowing, no widening). 100% read — only 6 clauses.

**No Clinical Co-Lead signoff required** — this chunk is a
semantics-preserving wire-up, not a clinical-content edit. The
clinical content (which indication applies to which patient
profile) was already authored upstream; this chunk only converts
the gate from "documentation that the engine ignores" to "gate
the engine evaluates."

### Trust threshold

- 1 of 1 maintainer review (per pre-acceptance gates above).
- Auto-merge to `master` once gates green.

## Output Format

Single PR against `https://github.com/romeo111/cancer-autoresearch`,
branch `feat/algo-ovarian-2l-wire-2026-05-20-HHMM`, modifying:

```
knowledge_base/hosted/content/algorithms/algo_ovarian_2l.yaml   # 6 condition translations
examples/patient_verified_ovarian_*.json                        # regenerated by generator
scripts/site_cases.py                                           # auto-block update (if any)
```

Plus a contribution-meta sidecar under
`contributions/algo-branch-wiring-ovarian-2l/_contribution_meta.yaml`
listing AI tool used (if any) per CHARTER §8.3 transparency.

PR description must link:

- The 6 translated condition strings (before → after, in a table).
- Output of `scripts/audit_example_plan_coverage.py
  --algorithm ALGO-OVARIAN-2L` before + after.
- Output of `pytest -k ovarian` green.

## Acceptance Criteria

- All pre-acceptance gates pass.
- Maintainer sample-review confirms 6 condition translations
  preserve clinical intent.
- `scripts/audit_example_plan_coverage.py` reports ≥ 3 of 6
  unreached indications now reachable (≥ 6 is the target win).
- PR diff confined to the file allowlist in
  **Re-verification → Pre-acceptance gates**.

## Rejection Criteria

- A translated condition is **wider** or **narrower** than the
  prose it replaces (e.g. prose says `BRCA1 or BRCA2 germline`,
  translation drops the germline qualifier and lets somatic
  through too).
- A new clinical clause is invented that wasn't in the prose
  (scope creep).
- Diff touches engine code, schema, or any non-allowlisted file.
- KB validator fails.
- `pytest -k ovarian` fails or skips silently.
- Previously-reachable indications become unreachable
  (regression).
- New patient-profile fields invented without surfacing to
  maintainer first.

## Claim Method

`trusted-agent-wip-branch-first` — see
[task_torrent/docs/chunk-system.md §"Claim Method"](https://github.com/romeo111/task_torrent/blob/main/docs/chunk-system.md).

Volunteer opens a `[Chunk] algo-branch-wiring-ovarian-2l` issue
against `romeo111/task_torrent` declaring claim; pushes WIP branch
to `romeo111/cancer-autoresearch` within 24 h; opens PR within 5
working days. If no commit pushed within 24 h, claim auto-releases.

## Reviewer

- Maintainer: 1 (sample-review per **Re-verification**).
- Clinical Co-Lead signoff: **not required** (semantics-preserving
  translation, not clinical content; see **Re-verification →
  Sample human re-verify** for rationale).

## Notes

This is one of **52 identically-shaped chunks** in the algorithm-
branch-wiring family. The backlog at
[docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/plans/kb_algorithm_branch_authoring_backlog_2026-05-18.md)
ranks them by unreached-indication count:

1. `ALGO-OVARIAN-2L` (6) ← **this chunk**
2. `ALGO-BREAST-1L` (5)
3. `ALGO-ESOPH-METASTATIC-1L` (5)
4. … 49 more

If this chunk validates the pattern, the maintainer can spin up the
next two (`ALGO-BREAST-1L`, `ALGO-ESOPH-METASTATIC-1L`) as copy-
paste-this-spec chunks within ~15 minutes each.

The Big-P3 alternative is the **structured-condition AST migration**
discussed in [openonco-state-audit-2026-05-17.md §3 path 2](https://github.com/romeo111/cancer-autoresearch/blob/master/docs/reviews/openonco-state-audit-2026-05-17.md)
— closes the entire class systemically. Out of scope for any
volunteer chunk; lives as a future maintainer workstream.
