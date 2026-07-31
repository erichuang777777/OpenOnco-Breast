"""Auto-release stale chunk claims (14 days no activity).

Run by a GitHub Action on schedule (daily). For each open `[Chunk]` issue
with `chunk-task` label AND assignee set:

1. Check if `tasktorrent/<chunk-id>` branch exists on origin.
2. Find the most recent commit on that branch (or the issue's most recent
   activity if no branch).
3. If activity > 14 days old → comment + drop assignee + relabel
   `status-active`.

Usage:
    python -m scripts.tasktorrent.auto_release_stale_claims [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from typing import Any

STALE_DAYS = 14
CHUNK_ID_RE = re.compile(r"\[Chunk\]\s*(\S+)")


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


def _list_assigned_chunk_issues() -> list[dict]:
    """Assigned open chunk-task issues, or [] if the board isn't set up yet.

    `gh issue list --label chunk-task` exits non-zero when the label does
    not exist in the repo (rather than returning an empty list). No chunk
    board means no claims to sweep, so treat it as "nothing to do" — but
    surface the reason as a workflow annotation so a genuine auth/API
    failure doesn't pass for a quiet day.
    """
    try:
        issues = _gh([
            "issue", "list",
            "--label", "chunk-task",
            "--state", "open",
            "--json", "number,title,assignees,labels,updatedAt",
            "--limit", "100",
        ])
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"::warning::cannot list chunk-task issues, skipping run: {_gh_error(exc)}")
        return []
    return [i for i in issues if i.get("assignees")]


def _extract_chunk_id(title: str) -> str | None:
    """Issue titles look like '[Chunk] civic-bma-reconstruct-all (NSCLC subset)' —
    extract the chunk-id (first token after [Chunk])."""
    m = CHUNK_ID_RE.search(title or "")
    if m:
        return m.group(1).rstrip(".:,;")
    return None


def _branch_last_activity(chunk_id: str) -> dt.datetime | None:
    """Return the timestamp of the latest commit on origin/tasktorrent/<chunk-id>,
    or None if branch missing."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/:owner/:repo/commits",
             "-X", "GET",
             "-f", f"sha=tasktorrent/{chunk_id}",
             "-f", "per_page=1",
             "--jq", ".[0].commit.committer.date"],
            capture_output=True, text=True, check=False,
        )
    except Exception:  # noqa: BLE001
        return None
    if result.returncode != 0:
        return None
    iso = result.stdout.strip().strip('"')
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_stale(activity_at: dt.datetime, now: dt.datetime) -> bool:
    return (now - activity_at).days >= STALE_DAYS


def _release_stale(issue: dict, last_activity: dt.datetime, dry_run: bool) -> None:
    number = issue["number"]
    assignees = [a["login"] for a in issue.get("assignees", [])]
    msg = (
        f"🤖 **Auto-released by stale-claim-bot.** Last activity on "
        f"`tasktorrent/<chunk-id>` was {last_activity.isoformat()} "
        f"({STALE_DAYS}+ days ago). Dropping assignee(s) {', '.join('@' + a for a in assignees)} "
        f"and re-labeling `status-active`.\n\n"
        f"If you still want this chunk, claim again. If you've made progress "
        f"locally but didn't push, push your WIP commits — that resets the timer."
    )
    if dry_run:
        print(f"[dry-run] would release #{number}: {msg[:100]}...")
        return
    _gh(["issue", "comment", str(number), "--body", msg])
    for assignee in assignees:
        _gh(["issue", "edit", str(number), "--remove-assignee", assignee])
    _gh(["issue", "edit", str(number), "--add-label", "status-active"])
    print(f"released #{number}: stale {STALE_DAYS}+ days")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    issues = _list_assigned_chunk_issues()
    print(f"Reviewing {len(issues)} assigned chunk-task issues...")

    now = dt.datetime.now(dt.timezone.utc)
    released = 0
    for issue in issues:
        chunk_id = _extract_chunk_id(issue.get("title", ""))
        if not chunk_id:
            continue
        last_branch = _branch_last_activity(chunk_id)
        if last_branch is None:
            # No branch on origin — fall back to issue activity
            try:
                last = dt.datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
        else:
            last = last_branch
        if _is_stale(last, now):
            _release_stale(issue, last, args.dry_run)
            released += 1

    print(f"\nReleased {released} stale claim(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
