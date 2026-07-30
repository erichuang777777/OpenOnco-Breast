# CI failure audit — recurring red runs (2026-07-30)

Investigation of the persistent GitHub Actions failures on `master`.
Triggered by a report that "git keeps erroring". The local repository was
never at fault: working tree clean, branches intact, no corrupt refs. Every
failure was in CI, and the two `git` messages in the logs were symptoms of
permission and tooling problems rather than repository problems.

## Summary

| # | Workflow | Frequency | Root cause | Class | Fixed |
|---|---|---|---|---|---|
| 1 | KB claim-grounding audit | Weekly, 4 consecutive | Repo setting blocks Actions from creating PRs | Permission | YES |
| 2 | CIViC monthly refresh | Latent (not yet fired) | Same blocked PR creation, same action | Permission | YES |
| 3 | TaskTorrent claim bots | Hourly, until disabled 2026-07-12 | `gh issue list --label` exits non-zero on a missing label | Tooling | YES |
| 4 | — (test hygiene) | Every pytest run | Smoke test writes into the canonical `docs/` report | Test pollution | YES |
| 5 | — (repo hygiene) | Per failed run | Orphan `kb-claim-grounding-refresh-*` branches | Leak | NO — needs explicit instruction |

## 1. KB claim-grounding audit — blocked PR creation

Failed 2026-07-06, -07-13, -07-20, -07-27 (runs 28783583581, 29237138826,
29728954882, 30254716742). The misleading part: the `git push` **succeeded**
every time. The job died on the step after it.

```
* [new branch]  kb-claim-grounding-refresh-30254716742 -> kb-claim-grounding-refresh-30254716742
##[error]GitHub Actions is not permitted to create or approve pull requests.
```

`peter-evans/create-pull-request` commits, pushes the branch, then calls the
PR-creation API. The workflow declared `permissions: pull-requests: write`,
which is correct and irrelevant: the repository-level toggle at
**Settings → Actions → General → Workflow permissions → "Allow GitHub Actions
to create and approve pull requests"** is off, and it overrides the
workflow's own grant. No amount of workflow YAML fixes that from inside.

Consequences:

- The refreshed report never reached `master`.
- Each run leaked one orphan branch (see §5).
- The job reported red weekly, training everyone to ignore the signal.

**Fix.** Converted to the `daily-site-refresh.yml` pattern: regenerate →
diff → commit straight to `master`. Justification for skipping PR review:
the report is a generated audit artifact under `docs/`, not clinical content
under `knowledge_base/hosted/content/`, so CHARTER §6.1 two-reviewer signoff
does not apply. The audit is a measurement, not a gate — it makes no
clinical decision. Added a `concurrency` group and a rebase-before-push,
since `daily-site-refresh` also pushes `docs/` and the two could collide.

## 2. CIViC monthly refresh — the same mine, unstepped

`civic-monthly-refresh.yml` carried an identical `peter-evans/create-pull-request`
call. It had not failed only because CIViC had not drifted enough to produce
a diff; the next month with real drift would have failed identically.

**Fix — deliberately different from §1.** This one is *not* converted to a
direct `master` commit. The CIViC snapshot is clinical evidence data; drift
in evidence levels, directions, or therapy lists can change engine-driven
recommendations, and CHARTER §6.1 requires two Clinical Co-Lead approvals
before it reaches `master`. Committing straight to `master` would have
removed that gate to fix a CI error — the wrong trade.

Instead the job now pushes the `civic-refresh-<run_id>` branch itself (the
part that always worked) and writes the compare/PR link plus the full diff
summary into the job summary, so a human opens the PR. The review gate is
preserved and the job no longer depends on the repo setting. If the setting
is ever enabled, the PR-creation step can be restored.

## 3. TaskTorrent claim bots — `gh` exits non-zero on a missing label

```
subprocess.CalledProcessError: Command '['gh', 'issue', 'list', '--label',
'chunk-task', '--state', 'open', '--json', '...', '--limit', '100']'
returned non-zero exit status 1
```

`gh issue list --label X` errors when `X` does not exist in the repository
rather than returning an empty list. This repository has no `chunk-task`
label and, at the time of audit, no issues at all — so the call failed on
every single run of both bots. The hourly schedule meant a red run every
hour until the workflow was manually disabled on 2026-07-12
(`state: disabled_manually`).

**Fix.** The listing helpers in both `check_claim_sla.py` and
`auto_release_stale_claims.py` now treat an unreadable chunk board as
"nothing to do": return `[]`, exit 0, and emit a `::warning::` annotation.
The annotation matters — silently returning `[]` would let a genuine auth or
API failure look identical to a quiet day, and a claim-release bot that
silently does nothing is worse than one that crashes loudly.

Two adjacent holes closed while in there:

- `_get_comments` in `check_claim_sla` raised on a per-issue failure,
  aborting the sweep over every remaining issue. Now it skips just the
  unreadable issue. Cost of a skip is at most one hour, since the bot runs
  hourly.
- The catch was widened from `CalledProcessError` to also cover `OSError`,
  so a missing `gh` binary degrades the same way instead of raising
  `FileNotFoundError`.

The workflow remains `disabled_manually`; re-enabling is a separate decision
and requires the Actions tab, since the chunk board is not currently in use.

### Verification matrix

| Scenario | Before | After |
|---|---|---|
| `gh` binary missing | `FileNotFoundError`, exit 1 | warning, exit 0 |
| `chunk-task` label absent (the real CI failure) | `CalledProcessError`, exit 1 | warning, exit 0 |
| Well-formed board | releases correctly | releases correctly (unchanged) |
| 1 of 2 issues unreadable | whole run aborts | skips that issue, processes the other |

## 4. Smoke test writing into the canonical report

`tests/test_claim_grounding.py::test_audit_script_smoke` runs the audit with
`--limit 3` and asserted against `aud.REPORT_MD` / `aud.REPORT_JSON` — the
real `docs/` paths. It even prepared `md_target` / `json_target` under
`tmp_path` and then never used them.

Two consequences, one of them already in the repository:

- Running `pytest` dirties the working tree with a partial report, which is
  easy to stage by accident.
- The committed `docs/kb-claim-grounding-report.json` on `master` shows
  `total_claims: 6` — that is a `--limit 3` test artifact, not a full audit.
  This is why all four orphan branches showed the identical +220/−14 diff
  against `master`: CI was producing the real audit, and `master` was
  holding test output.

**Fix.** `scripts/audit_claim_grounding.py` gained `--out-md` / `--out-json`,
defaulting to the canonical paths so the workflow is unchanged. The smoke
test now passes the `tmp_path` targets it had already built. Confirmed:
`pytest tests/test_claim_grounding.py` leaves `docs/` clean.

The stale committed report self-corrects on the next scheduled run, now that
§1 lets the audit reach `master`.

## 5. Orphan branches — outstanding

Four branches on `origin`, one per failed run:

```
kb-claim-grounding-refresh-28783583581   (2026-07-06)
kb-claim-grounding-refresh-29237138826   (2026-07-13)
kb-claim-grounding-refresh-29728954882   (2026-07-20)
kb-claim-grounding-refresh-30254716742   (2026-07-27)
```

They differ from each other only in the `_Generated` / `generated_at`
timestamp; the audit findings are byte-identical across all four. Each is
one commit ahead of `master` and carries no unique work.

**Not deleted.** CLAUDE.md requires explicit user instruction before any
branch deletion, and "fix the CI failures" is not that instruction. Listed
here so the cleanup is a decision on the record rather than a forgotten
leak. §1 stops new ones from appearing.

## Not addressed

- **Node 20 deprecation warnings.** `actions/checkout@v4`,
  `actions/setup-python@v5`, and `peter-evans/create-pull-request@v6` all
  emit "Node.js 20 is deprecated" and are being forced onto Node 24. These
  are warnings, not failures. Bumping action major versions is a separate
  change with its own blast radius and was not folded into a CI-fix commit.
- **A registered `CI` workflow (`.github/workflows/ci.yml`) has no file on
  `master`.** GitHub still lists it as `active` from its 2026-06-05
  registration. It produces no runs and no failures. Flagged, not touched.
