#!/usr/bin/env python3
"""Seed local dev users via the dev login endpoint.

Usage:
    python scripts/seed_dev_users.py          # backend must be running on :8000
    python scripts/seed_dev_users.py --port 8765

Creates one account per role so you can test each permission level.
Requires DEV_LOCAL_LOGIN=true in .env and SQLite DATABASE_URL.
"""

from __future__ import annotations

import argparse
import sys

try:
    import httpx
except ModuleNotFoundError:
    sys.exit("httpx not installed — run: pip install httpx")

DEV_USERS = [
    {"email": "admin@openonco.local",      "role": "kb_admin"},
    {"email": "doctor@openonco.local",     "role": "tumor_board_hcp"},
    {"email": "clinic@openonco.local",     "role": "clinic_hcp"},
    {"email": "auditor@openonco.local",    "role": "auditor"},
]


def seed(base_url: str) -> None:
    print(f"Seeding dev users at {base_url} …\n")
    with httpx.Client(base_url=base_url, timeout=10) as client:
        for u in DEV_USERS:
            r = client.post("/auth/dev/login", json=u)
            if r.status_code == 200:
                print(f"  ✓  {u['role']:20s}  {u['email']}")
            elif r.status_code == 403:
                print("\n✗  DEV_LOCAL_LOGIN is not enabled.")
                print("   Add DEV_LOCAL_LOGIN=true to your .env and restart the backend.")
                sys.exit(1)
            else:
                print(f"  ✗  {u['email']} — HTTP {r.status_code}: {r.text}")

    print("\nDone. Login at http://localhost:5173/login\n")
    print("Available accounts:")
    for u in DEV_USERS:
        print(f"  {u['email']:30s}  role={u['role']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    seed(f"http://localhost:{args.port}")
