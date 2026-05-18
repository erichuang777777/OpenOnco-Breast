# OpenOnco state audit — 2026-05-17

Snapshot of repo + engine state, plus one concrete engine finding worth fixing.
Author: Claude (claude/angry-darwin-31b5d0). Not a formal review; intended
as input to next planning pass.

## TL;DR

- **KB validator green.** 3118 entities load cleanly. 78 diseases, 436 indications,
  448 BMAs, 524 RedFlags, 388 sources.
- **Roadmap memory is stale in multiple places.** Several `[ ]` items are
  already shipped on master.
- **Real, scoped engine finding:** Algorithm decision trees contain 443
  free-text `condition:` strings; **376 (85%) are English prose** that the
  current `_eval_clause` evaluator silently treats as False. In at least
  27% of audited algorithms, step-1 is made entirely of prose clauses, so
  the tree falls through to `default_indication` on every patient. The
  clinical "intelligence" of those trees is documentation-only.
- **Branch sprawl is large** (1127 refs, dozens of `worktree-agent-*`
  recovery points). Per CLAUDE.md this is expected, but worth flagging
  as a future cleanup workstream.

## 1. Current state checks

| Check | Result | Command |
| --- | --- | --- |
| KB validator (strict) | OK — 3118 entities, all refs resolve | `python -m knowledge_base.validation.loader knowledge_base/hosted/content --strict` |
| Pytest, engine subset | 23 pass / 3 skip | `pytest tests/test_actionability_invariants.py tests/test_engine.py` |
| Pytest, full suite | did not complete within session timeouts on Windows (background pytest stayed running >8 min with empty stdout — likely buffering or a slow test, not a failure signal) | n/a |
| `git status` on worktree | clean | `git status --short` |

Full-suite pytest convergence on Windows was not verified in this audit. Recommend
adding an explicit `pytest.ini` `--durations=20` invocation to identify the slow
modules; the harness pattern of an empty background output file made it hard
to observe progress.

## 2. Roadmap entries that look stale

Memory file `project_roadmap.md` carries multiple items marked `[ ]` that
are in fact resolved on master:

| Roadmap item | Status on master | Evidence |
| --- | --- | --- |
| `_find_algorithm` does not consult `disease_state` (S5 prostate) | Fixed | commit `dc107fa412` (`fix(engine): _find_algorithm consults patient disease_state`); `knowledge_base/engine/plan.py:166,492` |
| Algorithm dispatch by load-order at collision | Partially addressed | `plan.py:503-506` emits a warning when patient `disease_state` is missing and the matched algo is state-specific |
| `_track_filter.py:177-182` lenient-fallback bug | Resolved | already marked `[~]` STALE further down the roadmap, but the duplicate `[ ]` entry is still in the file and recurs in conversation prompts |

These should be flipped to `[x]` with their SHA so the roadmap stops
proposing already-done work.

## 3. Engine finding: prose `condition:` clauses are silently False

### Reproducer

```python
from knowledge_base.engine.redflag_eval import _eval_clause
_eval_clause({'condition': 'ECOG PS 0-2'}, {'ecog_ps': 1})
# → False  (string is treated as a finding-key lookup; no such key in findings)
_eval_clause(
    {'condition': 'BRCA1 or BRCA2 somatic or germline pathogenic variant'},
    {'biomarkers': {'BIO-BRCA1': 'positive'}},
)
# → False
_eval_clause({'finding': 'ecog_ps', 'threshold': 2, 'comparator': '<='}, {'ecog_ps': 1})
# → True   (structured form works as authored)
```

### Scope (algorithms/ only)

| Metric | Count |
| --- | --- |
| Algorithm files scanned | 152 |
| Total `condition:` strings | 443 |
| Prose-shaped (contain `<`, `>`, `=`, ` and `, ` or `, ALL-CAPS gene token, or `(`) | **376 (85%)** |
| Algorithm files containing ≥1 prose condition | **120 (79%)** |
| Algorithms (all 152 with a `decision_tree`) where step-1 is entirely prose → falls through to `default_indication` on every patient | **45 / 152 (30%)** |

Examples of step-1-prose-only algorithms:

- `algo_aitl_2l.yaml` → `default=IND-AITL-2L-AZACITIDINE`
- `algo_alcl_2l.yaml` → `default=IND-ALCL-2L-BRENTUXIMAB-MONO`
- `algo_anal_scc_1l.yaml` → `default=IND-ANAL-SCC-LA-1L-NIGRO-CRT`
- `algo_bcc_1l.yaml` → `default=IND-BCC-1L-VISMODEGIB`
- `algo_cervical_metastatic_1l.yaml` → `default=IND-CERVICAL-METASTATIC-1L-PEMBRO-CHEMO-BEV`
- `algo_chondrosarcoma_1l.yaml` → `default=IND-CHONDROSARCOMA-ADVANCED-DOXORUBICIN`

### Why this hasn't surfaced

The dominant clinical routing path is **track filtering on Indication
metadata** (`_track_filter.is_track_excluded` + biomarker_requirements_*).
The Algorithm decision tree is a secondary signal — when it falls through
to `default_indication`, the rest of the engine still produces a sensible
plan from `output_indications` ordered by `is_current_line` + biomarker
filters. So the trees act like clinical documentation: they read well in
the rendered Plan, but they don't actually gate machine decisions.

This is fine as a design choice, but it's not the design the YAML *looks
like* it is. New authors reading e.g. `algo_prostate_mcrpc_2l.yaml`
reasonably assume the engine honours the BRCA / PARPi gate at step 2 — it
doesn't.

### Two paths forward (orthogonal)

1. **Make the silent fallthrough visible.** Detect prose-shaped condition
   strings at evaluation time and emit a one-time warning per clause.
   Authors get told their tree isn't being walked the way it reads. This
   is a small engine-only change (≤30 LOC + 1 test), shipped in this PR.
   Scope note: the warning fires on `{condition: "..."}` clauses only.
   Prose passed under `{finding: "..."}` (deliberate-author shape) is
   not flagged.

2. **Structured condition vocabulary.** Add a small parser or canonical
   AST for clauses like `"ECOG PS <= 2"` → `{finding: ecog, threshold: 2,
   comparator: '<='}`. This is a multi-week workstream and needs spec
   alignment under `specs/KNOWLEDGE_SCHEMA_SPECIFICATION.md` §13-ish. Not
   in scope here.

The first path is the cheapest way to convert "documented surprise" into
"told surprise" without changing engine semantics. Future work can then
migrate the 376 prose clauses to structured form one disease at a time,
gated by clinical co-lead review per CHARTER §6.1.

## 4. Branch sprawl

```
$ git branch -a | wc -l
1127
$ git worktree list | wc -l
≈ 80 (most locked, many detached HEAD)
```

CLAUDE.md notes 30+ `worktree-agent-*` recovery branches is normal. The
true cleanup-eligible candidates are:

- `chore/*` branches whose target merge is already on master (Q-axis upserts,
  curated-examples chunks, etc.) — many already squash-merged via PRs.
- `chunk/curated-examples-*` branches (12) — squash-merged via PR #150 per
  the roadmap, source branches can be retired.

Recommend a one-off `chore/branch-gc-2026-05-17` audit that lists branches
whose tip commit is already an ancestor of master, then deletes them via
an explicit list (never `git branch -D`). Not in scope for this PR; logged
here.

## 5. Recommendations (priority ordered)

1. **Land the prose-condition warning** (this branch). Surfaces the silent
   fallthrough without changing routing semantics.
2. **Roadmap reconciliation pass.** Walk `project_roadmap.md` and flip
   already-done `[ ]` items to `[x] (<SHA>)`. ~30 minutes of mechanical
   work; high signal/noise.
3. **Branch garbage collection** as above (one-off).
4. **Pytest convergence story.** Pick a slow-test offender via
   `--durations=20`, decide between marking it slow or speeding it up.
   Background-pytest on Windows currently masks failures behind buffering.
5. **Eventually**: structured condition AST migration, per disease, gated
   by clinical co-lead review. Authoring queue ≈ 376 clauses across 120
   files. Big-P3 workstream; specifically NOT to be combined with other
   changes.
