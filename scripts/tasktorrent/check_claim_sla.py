"""Check 24h claim SLA on TaskTorrent chunk-task issues.

Run by a GitHub Action on schedule (hourly). For each open `[Chunk]` issue
with `chunk-task` label:

1. Find the most recent comment containing a claim phrase
   ("I'd like to take this chunk", "claiming", etc.).
2. Check whether the issue has an `assignee` set.
3. If a claim was made > 24h ago AND no assignee was set → comment that
   the chunk is auto-released and re-label `status-active`.

This handles the open-contributor flow where maintainer didn't assign in
time. Trusted-agent flow is unaffected (those use WIP-branch-first, not
issue-comment claims).

Usage:
    python -m scripts.tasktorrent.check_claim_sla [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from typing import Any

SLA_HOURS = 24
CLAIM_PHRASES = [
    r"\bI'd like to take\b",
    r"\bI'd like to claim\b",
    r"\bI'll take this chunk\b",
    r"\bclaiming this chunk\b",
    r"\btaking this chunk\b",
]
CLAIM_RE = re.compile("|".join(CLAIM_PHRASES), re.IGNORECASE)


def _gh(args: list[str]) -> Any:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip().startswith(("{", "[")):
        return json.loads(result.stdout)
    return result.stdout


def _gh_error(exc: Exception) -> str:
    """One-line reason from a failed `gh` call, for log annotations."""
    stderr = getattr(exc, "stderr", None)
    return (stderr or str(exc)).strip().replace("\n", " ")


def _list_chunk_issues() -> list[dict]:
    """Open chunk-task issues, or [] if the board isn't set up yet.

    `gh issue list --label chunk-task` exits non-zero when the label does
    not exist in the repo (rather than returning an empty list), which
    used to crash the hourly workflow on every run. No chunk board means
    no claims to police, so treat it as "nothing to do" — but surface the
    reason as a workflow annotation so a genuine auth/API failure doesn't
    pass for a quiet day.
    """
    try:
        return _gh([
            "issue", "list",
            "--label", "chunk-task",
            "--state", "open",
            "--json", "number,title,assignees,labels",
            "--limit", "100",
        ])
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"::warning::cannot list chunk-task issues, skipping run: {_gh_error(exc)}")
        return []


def _get_comments(issue_number: int) -> list[dict]:
    """Comments on one issue, or [] if that issue can't be read.

    A per-issue failure (deleted mid-run, transient API error) must not
    abort the sweep over the remaining issues — skipping one issue costs
    at most a one-hour delay, since this bot runs hourly.
    """
    try:
        return _gh([
            "issue", "view", str(issue_number),
            "--json", "comments",
        ])["comments"]
    except (subprocess.CalledProcessError, OSError, KeyError, ValueError) as exc:
        print(f"::warning::skipping issue #{issue_number}: {_gh_error(exc)}")
        return []


def _is_past_sla(comment_iso: str, now: dt.datetime) -> bool:
    t = dt.datetime.fromisoformat(comment_iso.replace("Z", "+00:00"))
    return (now - t).total_seconds() > SLA_HOURS * 3600


def _release_for_sla(issue_number: int, claimer_login: str, claim_at: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] would release issue #{issue_number}: SLA breach for {claimer_login}@{claim_at}")
        return
    _gh([
        "issue", "comment", str(issue_number),
        "--body", (
            f"🤖 **Auto-released by claim-SLA-bot.** Claim by @{claimer_login} "
            f"at {claim_at} was not assigned within {SLA_HOURS}h. "
            f"Re-released to `status-active` — anyone can claim again.\n\n"
            f"@{claimer_login}, if you still want this chunk, comment again."
        ),
    ])
    print(f"released issue #{issue_number}: SLA breach (claimer @{claimer_login})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    issues = _list_chunk_issues()
    print(f"Reviewing {len(issues)} open chunk-task issues...")

    now = dt.datetime.now(dt.timezone.utc)
    released = 0
    for issue in issues:
        if issue.get("assignees"):
            continue  # already assigned, no SLA breach
        labels = [l["name"] for l in issue.get("labels", [])]
        if "status-active" not in labels:
            continue
        comments = _get_comments(issue["number"])
        # Find the most recent claim phrase
        latest_claim = None
        for c in comments:
            if CLAIM_RE.search(c.get("body", "") or ""):
                latest_claim = c
        if not latest_claim:
            continue
        claim_at = latest_claim.get("createdAt")
        if not claim_at:
            continue
        if _is_past_sla(claim_at, now):
            _release_for_sla(
                issue["number"],
                latest_claim.get("author", {}).get("login", "unknown"),
                claim_at,
                args.dry_run,
            )
            released += 1

    print(f"\nReleased {released} SLA-breached claim(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
