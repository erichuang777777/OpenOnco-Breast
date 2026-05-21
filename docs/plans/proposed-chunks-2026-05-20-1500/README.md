# task_torrent chunk bundle — 2026-05-20-1500

Six chunk specs drafted on 2026-05-20 for the OpenOnco TaskTorrent
shelf, plus their issue bodies and a PowerShell runner to open the
`[Chunk]` issues on `romeo111/task_torrent`.

## Folder contents

```
algo-branch-wiring-ovarian-2l.md            # v0.4 chunk spec — push to task_torrent/chunks/openonco/
algo-branch-wiring-breast-1l.md
algo-branch-wiring-esoph-metastatic-1l.md
prevention-regimen-authoring-wave1.md
workup-thyroid-papillary.md
hereditary-brca-carrier-surveillance.md
issue_bodies/                               # one .md per chunk; used by open_issues.ps1
open_issues.ps1                             # PowerShell runner: opens 6 [Chunk] issues
README.md                                   # this file
```

## Two-step push sequence

These chunks live cross-repo. The chunk SPEC `.md` files belong in
`romeo111/task_torrent`; the `[Chunk]` issues are also opened against
`romeo111/task_torrent` and reference the spec path.

### Step 1 — push chunk specs to `task_torrent`

For each of the six `<chunk-id>.md` files in this folder, push to
`romeo111/task_torrent` at path `chunks/openonco/<chunk-id>.md`. The
canonical patch pattern is documented in
`docs/reviews/cross-repo-task_torrent-sync-plan-2026-04-28.md` §6.

Suggested branch on `task_torrent`:

```
chore/openonco-shelf-expansion-2026-05-20
```

Suggested commit message:

```
chore(shelf): 6 new OpenOnco chunk specs — algo wiring + prevention + workup + hereditary
```

Single PR; squash-merge to `main`.

### Step 2 — open `[Chunk]` issues

After the chunk specs are on `task_torrent` `main`, run from this
folder:

```powershell
cd docs/plans/proposed-chunks-2026-05-20-1500
pwsh ./open_issues.ps1
```

The script opens 6 issues with the canonical
`chunk-task,openonco,status-active,pilot-active` label set, plus
per-chunk topic labels. All labels used by the script already exist
on `task_torrent` (verified 2026-05-20).

## Recommended first-claim order

The 6 chunks vary in complexity. For the incoming volunteer:

1. **First claim** — `algo-branch-wiring-ovarian-2l` (top of the
   52-algorithm backlog by unreached-indication count). Mechanical,
   no clinical signoff needed, worked example PR #597 exists.
2. **Second claim** — `algo-branch-wiring-breast-1l` or
   `algo-branch-wiring-esoph-metastatic-1l`. Same shape; either
   works.
3. **Third claim** — `workup-thyroid-papillary` if volunteer wants
   to try a single-entity authoring chunk (still small scope).
4. **Fourth claim onwards** —
   `prevention-regimen-authoring-wave1` and
   `hereditary-brca-carrier-surveillance`. Higher complexity,
   needs source-verbatim discipline + Clinical Co-Lead
   sample-check.

The shelf README on `task_torrent/chunks/openonco/README.md`
already lists 7 earlier chunks (`civic-bma-reconstruct-all`,
`citation-verify-914-audit`, etc.). Of those, only #11 and #12 have
open `[Chunk]` issues today; the remaining 5 also need step-2
issue opens before they're claimable.

## After the volunteer claims

Watch the issue for the WIP-branch push within 24 h. If no commit
appears, the claim auto-releases per
`docs/chunk-system.md` §"Claim Method" on task_torrent.

## Provenance

- Source eval doc: `docs/reviews/volunteer-shortlist-2026-05-20.md`
  in OpenOnco PR https://github.com/romeo111/OpenOnco/pull/614.
- Chunk-spec contract used: TaskTorrent v0.4 (12 required sections
  + Severity / Min Contributor Tier / Queue soft-required), verified
  against `romeo111/task_torrent/tasktorrent/lint_chunk_spec.py` on
  2026-05-20.
- Existing issue format mirrored from `task_torrent#11` and
  `task_torrent#12` (the two currently-open `status-active` issues
  as of 2026-05-20).
